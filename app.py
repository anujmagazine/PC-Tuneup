"""
PC TuneUp - Local System Optimizer
A self-hosted web app to diagnose and fix Windows performance issues.
"""

import os
import sys
import json
import time
import shutil
import ctypes
import hashlib
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from threading import Thread, Lock
from collections import defaultdict

from flask import Flask, render_template, jsonify, request

import psutil

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def bytes_to_gb(b):
    return round(b / (1024 ** 3), 2)


def bytes_to_mb(b):
    return round(b / (1024 ** 2), 2)


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Memory Leak Tracker (background)
# ---------------------------------------------------------------------------

_mem_tracker = {}  # pid -> list of (timestamp, rss_mb)
_mem_tracker_lock = Lock()

_cpu_samples = {}  # pid -> {name, cpu_percent, memory_mb}
_cpu_lock = Lock()


def _track_memory():
    """Background thread: sample process memory every 60s for leak detection."""
    while True:
        snapshot = {}
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                info = proc.info
                if info["memory_info"]:
                    snapshot[info["pid"]] = {
                        "name": info["name"],
                        "rss_mb": round(info["memory_info"].rss / (1024 ** 2), 1),
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        now = time.time()
        with _mem_tracker_lock:
            # Prune dead pids
            live_pids = set(snapshot.keys())
            for pid in list(_mem_tracker.keys()):
                if pid not in live_pids:
                    del _mem_tracker[pid]
            # Append samples
            for pid, info in snapshot.items():
                if pid not in _mem_tracker:
                    _mem_tracker[pid] = {"name": info["name"], "samples": []}
                _mem_tracker[pid]["samples"].append((now, info["rss_mb"]))
                # Keep last 30 samples (~30 min)
                _mem_tracker[pid]["samples"] = _mem_tracker[pid]["samples"][-30:]

        time.sleep(60)


Thread(target=_track_memory, daemon=True).start()


def _track_cpu():
    """Background thread: sample process CPU every 3s for fan-noise diagnosis."""
    # Warm-up: first call always returns 0, so seed the cache first
    list(psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]))
    time.sleep(3)
    while True:
        snap = {}
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                info = proc.info
                snap[info["pid"]] = {
                    "name": info["name"],
                    "cpu_percent": round(info["cpu_percent"] or 0, 1),
                    "memory_mb": round(info["memory_info"].rss / (1024 ** 2), 1) if info["memory_info"] else 0,
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        with _cpu_lock:
            _cpu_samples.clear()
            _cpu_samples.update(snap)
        time.sleep(3)


Thread(target=_track_cpu, daemon=True).start()


# ---------------------------------------------------------------------------
# Routes: Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Routes: System Overview
# ---------------------------------------------------------------------------

@app.route("/api/system-overview")
def system_overview():
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, _ = divmod(remainder, 60)

    return jsonify({
        "cpu_percent": cpu_percent,
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "ram_total_gb": bytes_to_gb(mem.total),
        "ram_used_gb": bytes_to_gb(mem.used),
        "ram_percent": mem.percent,
        "disk_total_gb": bytes_to_gb(disk.total),
        "disk_used_gb": bytes_to_gb(disk.used),
        "disk_free_gb": bytes_to_gb(disk.free),
        "disk_percent": disk.percent,
        "uptime": f"{hours}h {minutes}m",
        "is_admin": is_admin(),
    })


# ---------------------------------------------------------------------------
# Routes: Diagnosis
# ---------------------------------------------------------------------------

@app.route("/api/diagnose")
def diagnose():
    issues = []

    # 1. High RAM usage
    mem = psutil.virtual_memory()
    if mem.percent > 85:
        issues.append({
            "id": "high_ram", "title": "Your memory (RAM) is almost full",
            "description": f"RAM is at {mem.percent}%. Your PC doesn't have enough memory for what's running, so it's using the slow hard drive instead. This is the #1 reason PCs feel sluggish.",
            "severity": "high",
            "impact": "20-40% faster",
            "effort": "instant",
            "action": "/api/clear-standby-memory",
            "action_label": "Free Memory Now",
            "how": "Click the button to instantly free up cached memory. For a bigger improvement, go to the Running Apps tab and close apps you're not using.",
            "needs_admin": False,
        })
    elif mem.percent > 70:
        issues.append({
            "id": "moderate_ram", "title": "Memory usage is getting high",
            "description": f"RAM is at {mem.percent}%. Not critical yet, but closing a few apps could make things snappier.",
            "severity": "medium",
            "impact": "5-15% faster",
            "effort": "instant",
            "action": "/api/clear-standby-memory",
            "action_label": "Free Memory Now",
            "how": "Click the button to free up cached memory, or close browser tabs and apps you're not actively using.",
            "needs_admin": False,
        })

    # 2. High CPU usage
    cpu = psutil.cpu_percent(interval=1)
    if cpu > 80:
        with _cpu_lock:
            top_cpu = sorted(_cpu_samples.values(), key=lambda x: x["cpu_percent"], reverse=True)
        culprit = top_cpu[0]["name"] if top_cpu and top_cpu[0]["cpu_percent"] > 20 else None
        culprit_pct = top_cpu[0]["cpu_percent"] if culprit else None

        title = f"{culprit} is overloading your processor" if culprit else "Something is overloading your processor"
        desc = f"CPU is at {cpu}%. "
        if culprit:
            desc += f"{culprit} is using {culprit_pct}% CPU on its own — that's the reason your fan is spinning and everything feels slow."
        else:
            desc += "An app or background process is using most of your processing power, making everything else slow."
        issues.append({
            "id": "high_cpu", "title": title,
            "description": desc,
            "severity": "high",
            "impact": "30-50% faster",
            "effort": "1 min",
            "action": None,
            "action_label": "Find the App",
            "tab": "processes",
            "how": "Go to the Running Apps tab → 'What's Causing Fan Noise?' section. It shows the top CPU-using app with specific fix steps.",
            "needs_admin": False,
        })

    # 3. Low disk space
    disk = psutil.disk_usage("C:\\")
    if disk.percent > 90:
        issues.append({
            "id": "low_disk", "title": "Your hard drive is almost full",
            "description": f"Only {bytes_to_gb(disk.free)} GB free. Windows needs free space to work properly. When the drive is this full, everything slows down significantly.",
            "severity": "high",
            "impact": "15-30% faster",
            "effort": "2 min",
            "action": "/api/clean-temp",
            "action_label": "Clean Junk Files",
            "how": "Click the button to delete temporary junk files. Then go to Free Space tab for more options like cleaning browser cache and finding duplicate files.",
            "needs_admin": False,
        })
    elif disk.percent > 75:
        issues.append({
            "id": "moderate_disk", "title": "Disk space is getting low",
            "description": f"{bytes_to_gb(disk.free)} GB free. Not urgent, but cleaning up now prevents problems later.",
            "severity": "medium",
            "impact": "5-10% faster",
            "effort": "2 min",
            "action": "/api/clean-temp",
            "action_label": "Clean Junk Files",
            "how": "Click to clean temporary files. Visit the Free Space tab to clean browser cache and find duplicates.",
            "needs_admin": False,
        })

    # 4. Temp files size
    temp_size = _get_temp_files_size()
    if temp_size > 500:
        issues.append({
            "id": "large_temp", "title": f"{round(temp_size / 1024, 1)} GB of junk files found",
            "description": f"Programs leave behind temporary files that pile up. You have {temp_size} MB that can be safely deleted.",
            "severity": "medium",
            "impact": f"Free {round(temp_size / 1024, 1)} GB of space",
            "effort": "instant",
            "action": "/api/clean-temp",
            "action_label": "Delete Junk Files",
            "how": "Click the button. This is completely safe — it only deletes temporary files that programs no longer need.",
            "needs_admin": False,
        })

    # 5. Too many startup programs
    startup_count = len(_get_startup_programs())
    if startup_count > 10:
        issues.append({
            "id": "many_startup", "title": f"{startup_count} apps launch when your PC starts",
            "description": f"Each startup app slows down your boot time and uses memory in the background. You probably only need a few of them.",
            "severity": "medium",
            "impact": "30-60 sec faster boot",
            "effort": "5 min",
            "action": "/api/open-task-manager",
            "action_label": "Open Task Manager",
            "tab": "startup",
            "how": "Click to open Task Manager. In the Startup tab, right-click apps you don't need at startup and click 'Disable'. Keep antivirus and drivers, disable everything else.",
            "needs_admin": False,
        })

    # 6. Long uptime
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime_days = (datetime.now() - boot_time).days
    if uptime_days >= 7:
        issues.append({
            "id": "long_uptime", "title": f"Your PC hasn't been restarted in {uptime_days} days",
            "description": "Over time, apps leak memory and Windows accumulates temporary state. A restart clears all of this and often makes a big difference.",
            "severity": "low",
            "impact": "10-25% faster",
            "effort": "2 min",
            "action": None,
            "action_label": None,
            "how": "Save your work, then restart from Start menu > Power > Restart. Don't just close the lid — that puts it to sleep, not restart.",
            "needs_admin": False,
        })

    # 7. High memory processes
    heavy_procs = _get_heavy_processes()
    top_hogs = [p for p in heavy_procs if p["memory_mb"] > 500]
    if len(top_hogs) >= 2:
        names = ", ".join(p["name"] for p in top_hogs[:3])
        total_mb = sum(p["memory_mb"] for p in top_hogs[:3])
        issues.append({
            "id": "memory_hogs", "title": f"A few apps are using {round(total_mb / 1024, 1)} GB of RAM",
            "description": f"These apps are using the most memory: {names}. If you're not actively using them, closing them will free up a lot of RAM.",
            "severity": "medium",
            "impact": f"Free {round(total_mb / 1024, 1)} GB RAM",
            "effort": "1 min",
            "action": None,
            "action_label": "See Running Apps",
            "tab": "processes",
            "how": "Go to Running Apps tab. Close apps you're not using by clicking 'End'. Don't close apps you don't recognize — they might be system processes.",
            "needs_admin": False,
        })

    # 8. Browser cache bloat
    cache_info = _get_browser_cache_size()
    total_cache_mb = sum(b["size_mb"] for b in cache_info)
    if total_cache_mb > 500:
        issues.append({
            "id": "browser_cache", "title": f"{round(total_cache_mb / 1024, 1)} GB of browser cache",
            "description": "Your web browser stores copies of websites you visit. Over time this uses a lot of space. Cleaning it is safe — websites will just load slightly slower the first time.",
            "severity": "medium",
            "impact": f"Free {round(total_cache_mb / 1024, 1)} GB space",
            "effort": "instant",
            "action": "/api/clean-browser-cache",
            "action_label": "Clean Browser Cache",
            "how": "Close your browsers first for best results, then click the button. Your passwords and bookmarks will NOT be affected.",
            "needs_admin": False,
        })

    # 9. Windows Update cache
    wu_size = _get_wu_cache_size()
    if wu_size > 500:
        issues.append({
            "id": "wu_cache", "title": f"{round(wu_size / 1024, 1)} GB of old update files",
            "description": "Windows keeps old update files after installing updates. These are no longer needed and can be safely removed.",
            "severity": "medium",
            "impact": f"Free {round(wu_size / 1024, 1)} GB space",
            "effort": "instant",
            "action": "/api/clean-wu-cache",
            "action_label": "Clean Update Cache",
            "how": "Click the button. This requires admin access — see the instructions at the top of the page if you're not running as admin.",
            "needs_admin": True,
        })

    # 10. Thermal throttling
    thermal = _get_thermal_info()
    if thermal.get("throttled"):
        issues.append({
            "id": "thermal", "title": "Your CPU is overheating and slowing itself down",
            "description": f"CPU temperature is {thermal.get('temp_c', '?')}°C. To prevent damage, your processor is running at reduced speed. This has a huge impact on performance.",
            "severity": "high",
            "impact": "30-60% faster",
            "effort": "varies",
            "action": None,
            "action_label": "See Details",
            "tab": "health",
            "how": "Clean dust from laptop vents with compressed air. Use a cooling pad. Don't use on soft surfaces. If your laptop is 3+ years old, it may need new thermal paste ($30-50 at a repair shop).",
            "needs_admin": False,
        })
    elif thermal.get("temp_c") and thermal["temp_c"] > 75:
        issues.append({
            "id": "high_temp", "title": f"CPU temperature is {thermal['temp_c']}°C — getting warm",
            "description": "Not critical yet, but your CPU is warmer than ideal. If it gets hotter, it will start throttling (slowing down to cool off).",
            "severity": "medium",
            "impact": "Prevents future slowdown",
            "effort": "5 min",
            "action": None,
            "action_label": "See Tips",
            "tab": "health",
            "how": "Make sure laptop vents aren't blocked. Clean dust from vents. Use on a hard flat surface, not a bed or pillow.",
            "needs_admin": False,
        })

    # 11. Memory leaks
    leaks = _detect_memory_leaks()
    if leaks:
        names = ", ".join(l["name"] for l in leaks[:3])
        issues.append({
            "id": "mem_leak", "title": "Some apps are slowly eating more memory",
            "description": f"These apps keep using more RAM over time without releasing it: {names}. This is called a 'memory leak' and will make your PC slower the longer it runs.",
            "severity": "medium",
            "impact": "5-15% faster",
            "effort": "1 min",
            "action": None,
            "action_label": "See Details",
            "tab": "processes",
            "how": "Go to Running Apps tab. Find these apps and click 'End' to restart them. Restarting the app usually fixes the leak.",
            "needs_admin": False,
        })

    # 12. Disk health
    disk_health = _get_disk_health()
    for d in disk_health:
        if d.get("status") and d["status"].lower() not in ("ok", ""):
            issues.append({
                "id": "disk_health", "title": f"Your hard drive may be failing",
                "description": f"Drive: {d['model']}. Status: {d['status']}. This is serious — a failing drive can lose all your files and causes major slowdowns.",
                "severity": "high",
                "impact": "Prevent data loss",
                "effort": "30 min",
                "action": None,
                "action_label": "See Details",
                "tab": "health",
                "how": "Back up all important files to an external drive or cloud storage (OneDrive, Google Drive) RIGHT NOW. Then consider replacing the drive or getting a professional to check it.",
                "needs_admin": False,
            })
            break

    # 13. Background services
    bloat_services = _get_bloat_services()
    if len(bloat_services) > 3:
        issues.append({
            "id": "bloat_services", "title": f"{len(bloat_services)} unnecessary services running in the background",
            "description": "Windows runs services you probably don't need (like Xbox, Fax, geolocation). Each one uses a small amount of memory and CPU.",
            "severity": "low",
            "impact": "3-8% faster",
            "effort": "2 min",
            "action": None,
            "action_label": "Manage Services",
            "tab": "health",
            "how": "Go to PC Health tab and scroll to services. Click 'Stop' on services you don't need. This requires admin access. They'll restart on next reboot, so it's safe to try.",
            "needs_admin": True,
        })

    # 14. Heavy swap usage
    swap = psutil.swap_memory()
    if swap.percent > 50:
        issues.append({
            "id": "heavy_swap", "title": "Your PC is using the hard drive as extra memory",
            "description": f"Your RAM is full, so Windows is using {bytes_to_mb(swap.used)} MB of your much-slower hard drive as overflow memory. This is the biggest cause of a 'freezing' or 'hanging' PC.",
            "severity": "high",
            "impact": "40-70% faster",
            "effort": "1 min",
            "action": "/api/clear-standby-memory",
            "action_label": "Free Memory Now",
            "how": "Click to free cached memory. Then go to Running Apps and close apps you don't need. If this keeps happening, your PC may need more RAM.",
            "needs_admin": False,
        })

    # Sort: high first, then medium, then low. Within same severity, by impact.
    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda x: severity_order.get(x["severity"], 3))

    # Health score
    high_count = sum(1 for i in issues if i["severity"] == "high")
    med_count = sum(1 for i in issues if i["severity"] == "medium")
    low_count = sum(1 for i in issues if i["severity"] == "low")
    score = max(0, 100 - (high_count * 25) - (med_count * 10) - (low_count * 3))

    return jsonify({"issues": issues, "health_score": score})


# ---------------------------------------------------------------------------
# Heavy Processes
# ---------------------------------------------------------------------------

def _get_heavy_processes():
    procs = []
    for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent", "status"]):
        try:
            info = proc.info
            mem_mb = bytes_to_mb(info["memory_info"].rss) if info["memory_info"] else 0
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "memory_mb": round(mem_mb, 1),
                "cpu_percent": info["cpu_percent"] or 0,
                "status": info["status"],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x["memory_mb"], reverse=True)
    return procs[:30]


@app.route("/api/processes")
def processes():
    return jsonify(_get_heavy_processes())


# ---------------------------------------------------------------------------
# CPU Hog Detection
# ---------------------------------------------------------------------------

_CPU_FIX_ADVICE = {
    "chrome.exe":        "Chrome is the culprit. Open Chrome's built-in task manager (Shift+Esc inside Chrome) to see which tab is spiking CPU — then close that tab.",
    "msedge.exe":        "Edge browser is using high CPU. Close unused tabs, or restart Edge entirely.",
    "firefox.exe":       "Firefox is CPU-heavy. Try reloading the page or closing background tabs. Restart Firefox if it keeps spinning.",
    "code.exe":          "VS Code is CPU-heavy. Disable unused extensions (Ctrl+Shift+X → disable) or close large projects.",
    "teams.exe":         "Microsoft Teams spikes CPU especially during or after calls. Quit it from the system tray and relaunch.",
    "slack.exe":         "Slack's Electron engine is CPU-hungry. Restart the app — this usually drops CPU immediately.",
    "discord.exe":       "Discord spikes during calls. Try: User Settings → Voice & Video → turn off Hardware Acceleration.",
    "zoom.exe":          "Zoom is heavy during video calls. Turn off your camera (Alt+V) or blur background — these reduce CPU a lot.",
    "antimalware service executable": "Windows Defender is running a background scan. This is safe and will stop on its own. To reduce impact, schedule scans for overnight in Windows Security → Virus & Threat Protection → Manage Settings → Schedule Scan.",
    "msmpeng.exe":       "Windows Defender scan in progress — it will stop on its own. To schedule for off-hours: Windows Security → Virus & Threat Protection → Quick Scan → Manage Settings.",
    "searchindexer.exe": "Windows Search is building its index (happens after updates or when you add lots of files). It stops on its own. To stop it permanently: PC Health tab → stop 'Windows Search (heavy indexing)'.",
    "tiworker.exe":      "Windows Update is running maintenance tasks in the background. It will stop when done. Check Settings → Windows Update for any pending updates.",
    "wuauclt.exe":       "Windows is downloading/installing updates. Let it finish — interrupting can cause issues. Check progress in Settings → Windows Update.",
    "mrt.exe":           "Windows Malware Removal Tool is scanning (runs once a month, takes a few minutes). It will stop on its own — nothing to do.",
    "onedrive.exe":      "OneDrive is syncing files to the cloud. Right-click the cloud icon in your taskbar (bottom right) and choose 'Pause syncing for 2 hours'.",
    "dropbox.exe":       "Dropbox is syncing. Right-click the Dropbox icon in your taskbar and choose 'Pause syncing'.",
    "steam.exe":         "Steam is downloading a game update. Open Steam → Library → Downloads → pause the download.",
    "node.exe":          "A web development server or background app is running hot. Check which app launched Node.js (check your VS Code terminal or any running dev servers).",
    "python.exe":        "A Python script is consuming CPU. Check any running scripts or Jupyter notebooks and stop what you don't need.",
    "java.exe":          "A Java app is CPU-heavy (common with IDEs, Minecraft, or enterprise apps). Close it if you're not using it.",
    "javaw.exe":         "A Java app is CPU-heavy. Close it if you're not using it actively.",
    "photoshop.exe":     "Photoshop is processing. Wait for it to finish — or use Edit → Purge → All to clear its memory cache.",
    "premiere.exe":      "Adobe Premiere is rendering or processing video. This is expected for video work — it uses the CPU by design.",
    "obs64.exe":         "OBS Studio is recording or streaming, which is CPU-heavy by nature. Lower the output resolution or switch to hardware encoding: Settings → Output → Encoder → select your GPU.",
}

_CPU_FIX_DEFAULT = "Close this app if you don't need it right now — that will drop CPU immediately. If you need it, check for updates (newer versions often fix performance issues)."


def _get_cpu_hogs():
    with _cpu_lock:
        procs = [{"pid": pid, **data} for pid, data in _cpu_samples.items()]
    procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
    for p in procs:
        p["fix"] = _CPU_FIX_ADVICE.get(p["name"].lower(), _CPU_FIX_DEFAULT)
    # Only return processes actually using CPU
    return [p for p in procs if p["cpu_percent"] > 0.5][:15]


@app.route("/api/cpu-hogs")
def cpu_hogs():
    return jsonify(_get_cpu_hogs())


@app.route("/api/kill-process", methods=["POST"])
def kill_process():
    pid = request.json.get("pid")
    if not pid:
        return jsonify({"error": "No PID provided"}), 400
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        protected = {"System", "smss.exe", "csrss.exe", "wininit.exe",
                      "services.exe", "lsass.exe", "svchost.exe", "explorer.exe",
                      "winlogon.exe", "dwm.exe"}
        if name in protected:
            return jsonify({"error": f"Cannot kill protected system process: {name}"}), 403
        proc.terminate()
        return jsonify({"success": True, "message": f"Terminated {name} (PID {pid})"})
    except psutil.NoSuchProcess:
        return jsonify({"error": "Process no longer exists"}), 404
    except psutil.AccessDenied:
        return jsonify({"error": "Access denied. Run as Administrator to kill this process."}), 403


# ---------------------------------------------------------------------------
# Temp File Cleanup
# ---------------------------------------------------------------------------

def _get_temp_files_size():
    temp_dirs = [
        os.environ.get("TEMP", ""),
        os.environ.get("TMP", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
        "C:\\Windows\\Temp",
    ]
    total = 0
    seen = set()
    for d in temp_dirs:
        d = os.path.normpath(d)
        if not d or d in seen or not os.path.isdir(d):
            continue
        seen.add(d)
        for dirpath, dirnames, filenames in os.walk(d):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
    return round(total / (1024 * 1024), 1)


@app.route("/api/clean-temp", methods=["POST"])
def clean_temp():
    temp_dirs = [
        os.environ.get("TEMP", ""),
        os.environ.get("TMP", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
    ]
    if is_admin():
        temp_dirs.append("C:\\Windows\\Temp")

    deleted = 0
    failed = 0
    freed = 0
    seen = set()

    for d in temp_dirs:
        d = os.path.normpath(d)
        if not d or d in seen or not os.path.isdir(d):
            continue
        seen.add(d)
        for dirpath, dirnames, filenames in os.walk(d, topdown=False):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    size = os.path.getsize(fp)
                    os.remove(fp)
                    deleted += 1
                    freed += size
                except OSError:
                    failed += 1
            for dn in dirnames:
                try:
                    os.rmdir(os.path.join(dirpath, dn))
                except OSError:
                    pass

    return jsonify({
        "deleted": deleted, "failed": failed,
        "freed_mb": round(freed / (1024 * 1024), 1),
        "message": f"Cleaned {deleted} files, freed {round(freed / (1024 * 1024), 1)} MB.",
    })


@app.route("/api/run-disk-cleanup", methods=["POST"])
def run_disk_cleanup():
    try:
        subprocess.Popen(["cleanmgr", "/d", "C:"])
        return jsonify({"success": True, "message": "Windows Disk Cleanup launched."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Browser Cache Cleanup (NEW)
# ---------------------------------------------------------------------------

def _get_browser_cache_size():
    """Calculate cache sizes for Chrome, Edge, Firefox."""
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    browsers = [
        {"name": "Chrome", "path": os.path.join(local, r"Google\Chrome\User Data\Default\Cache")},
        {"name": "Chrome", "path": os.path.join(local, r"Google\Chrome\User Data\Default\Code Cache")},
        {"name": "Edge", "path": os.path.join(local, r"Microsoft\Edge\User Data\Default\Cache")},
        {"name": "Edge", "path": os.path.join(local, r"Microsoft\Edge\User Data\Default\Code Cache")},
        {"name": "Firefox", "path": os.path.join(local, r"Mozilla\Firefox\Profiles")},
    ]
    results = []
    for b in browsers:
        size = 0
        if b["name"] == "Firefox" and os.path.isdir(b["path"]):
            # Firefox has profile subdirs
            for profile in os.listdir(b["path"]):
                cache_dir = os.path.join(b["path"], profile, "cache2")
                if os.path.isdir(cache_dir):
                    size += _dir_size(cache_dir)
        elif os.path.isdir(b["path"]):
            size = _dir_size(b["path"])
        if size > 0:
            results.append({"name": b["name"], "path": b["path"], "size_mb": round(size / (1024 * 1024), 1)})
    # Merge same-browser entries
    merged = {}
    for r in results:
        if r["name"] in merged:
            merged[r["name"]]["size_mb"] += r["size_mb"]
        else:
            merged[r["name"]] = {"name": r["name"], "size_mb": r["size_mb"]}
    return list(merged.values())


def _dir_size(path):
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


@app.route("/api/browser-cache-info")
def browser_cache_info():
    return jsonify(_get_browser_cache_size())


@app.route("/api/clean-browser-cache", methods=["POST"])
def clean_browser_cache():
    local = os.environ.get("LOCALAPPDATA", "")
    cache_dirs = [
        os.path.join(local, r"Google\Chrome\User Data\Default\Cache"),
        os.path.join(local, r"Google\Chrome\User Data\Default\Code Cache"),
        os.path.join(local, r"Microsoft\Edge\User Data\Default\Cache"),
        os.path.join(local, r"Microsoft\Edge\User Data\Default\Code Cache"),
    ]
    # Firefox profiles
    ff_profiles = os.path.join(local, r"Mozilla\Firefox\Profiles")
    if os.path.isdir(ff_profiles):
        for profile in os.listdir(ff_profiles):
            cache_dir = os.path.join(ff_profiles, profile, "cache2")
            if os.path.isdir(cache_dir):
                cache_dirs.append(cache_dir)

    freed = 0
    deleted = 0
    for d in cache_dirs:
        if not os.path.isdir(d):
            continue
        for dirpath, dirnames, filenames in os.walk(d, topdown=False):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    size = os.path.getsize(fp)
                    os.remove(fp)
                    freed += size
                    deleted += 1
                except OSError:
                    pass
            for dn in dirnames:
                try:
                    os.rmdir(os.path.join(dirpath, dn))
                except OSError:
                    pass

    freed_mb = round(freed / (1024 * 1024), 1)
    return jsonify({
        "success": True,
        "message": f"Cleaned {deleted} browser cache files, freed {freed_mb} MB. Close browsers for best results.",
    })


# ---------------------------------------------------------------------------
# Windows Update Cache Cleanup (NEW)
# ---------------------------------------------------------------------------

def _get_wu_cache_size():
    wu_dir = r"C:\Windows\SoftwareDistribution\Download"
    if os.path.isdir(wu_dir):
        return round(_dir_size(wu_dir) / (1024 * 1024), 1)
    return 0


@app.route("/api/wu-cache-info")
def wu_cache_info():
    return jsonify({"size_mb": _get_wu_cache_size()})


@app.route("/api/clean-wu-cache", methods=["POST"])
def clean_wu_cache():
    if not is_admin():
        return jsonify({"error": "Admin privileges required to clean Windows Update cache."}), 403

    wu_dir = r"C:\Windows\SoftwareDistribution\Download"
    if not os.path.isdir(wu_dir):
        return jsonify({"message": "Windows Update cache directory not found."})

    # Stop Windows Update service first
    subprocess.run(["net", "stop", "wuauserv"], capture_output=True, timeout=30)

    freed = 0
    deleted = 0
    for dirpath, dirnames, filenames in os.walk(wu_dir, topdown=False):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                size = os.path.getsize(fp)
                os.remove(fp)
                freed += size
                deleted += 1
            except OSError:
                pass
        for dn in dirnames:
            try:
                os.rmdir(os.path.join(dirpath, dn))
            except OSError:
                pass

    # Restart Windows Update service
    subprocess.run(["net", "start", "wuauserv"], capture_output=True, timeout=30)

    freed_mb = round(freed / (1024 * 1024), 1)
    return jsonify({
        "success": True,
        "message": f"Cleaned {deleted} Windows Update cache files, freed {freed_mb} MB.",
    })


# ---------------------------------------------------------------------------
# Disk Health / S.M.A.R.T. (NEW)
# ---------------------------------------------------------------------------

def _get_disk_health():
    """Get disk health info via WMIC."""
    disks = []
    try:
        result = subprocess.run(
            ["wmic", "diskdrive", "get", "Model,Status,Size,MediaType", "/format:csv"],
            capture_output=True, text=True, timeout=15
        )
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        if len(lines) > 1:
            headers = [h.strip().lower() for h in lines[0].split(",")]
            for line in lines[1:]:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= len(headers):
                    d = dict(zip(headers, parts))
                    size_gb = 0
                    try:
                        size_gb = round(int(d.get("size", 0)) / (1024 ** 3), 1)
                    except (ValueError, TypeError):
                        pass
                    disks.append({
                        "model": d.get("model", "Unknown"),
                        "status": d.get("status", "Unknown"),
                        "size_gb": size_gb,
                        "media_type": d.get("mediatype", "Unknown"),
                    })
    except Exception:
        pass

    # Try to get S.M.A.R.T. details
    try:
        result = subprocess.run(
            ["wmic", "/namespace:\\\\root\\wmi", "path", "MSStorageDriver_FailurePredictStatus",
             "get", "PredictFailure,Reason", "/format:csv"],
            capture_output=True, text=True, timeout=15
        )
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        if len(lines) > 1:
            for i, line in enumerate(lines[1:]):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3 and i < len(disks):
                    predict_fail = parts[1].lower() == "true"
                    if predict_fail:
                        disks[i]["status"] = "FAILING - Backup data immediately!"
                        disks[i]["smart_warning"] = True
    except Exception:
        pass

    return disks


@app.route("/api/disk-health")
def disk_health():
    return jsonify(_get_disk_health())


# ---------------------------------------------------------------------------
# Thermal / CPU Throttle Detection (NEW)
# ---------------------------------------------------------------------------

def _get_thermal_info():
    """Get CPU temperature and throttling status."""
    info = {"temp_c": None, "throttled": False, "max_speed_mhz": None, "current_speed_mhz": None}

    # Try WMI for temperature
    try:
        result = subprocess.run(
            ["wmic", "/namespace:\\\\root\\wmi", "path", "MSAcpi_ThermalZoneTemperature",
             "get", "CurrentTemperature", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        if len(lines) > 1:
            for line in lines[1:]:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 2:
                    try:
                        # Value is in tenths of Kelvin
                        kelvin_tenths = int(parts[-1])
                        celsius = round((kelvin_tenths / 10) - 273.15, 1)
                        if 0 < celsius < 120:
                            info["temp_c"] = celsius
                            break
                    except (ValueError, TypeError):
                        pass
    except Exception:
        pass

    # Check CPU frequency for throttling
    try:
        freq = psutil.cpu_freq()
        if freq:
            info["max_speed_mhz"] = round(freq.max)
            info["current_speed_mhz"] = round(freq.current)
            if freq.max > 0 and freq.current < freq.max * 0.7:
                info["throttled"] = True
    except Exception:
        pass

    return info


@app.route("/api/thermal")
def thermal():
    return jsonify(_get_thermal_info())


# ---------------------------------------------------------------------------
# Memory Leak Detection (NEW)
# ---------------------------------------------------------------------------

def _detect_memory_leaks():
    """Analyze tracked memory data for processes with steadily growing RSS."""

    # Windows system processes that legitimately grow — not real leaks
    SYSTEM_PROCESSES = {
        "memcompression",      # Windows memory compression — grows under RAM pressure, by design
        "system",              # Windows kernel
        "registry",            # Windows Registry cache
        "smss.exe",            # Session Manager
        "csrss.exe",           # Client Server Runtime
        "wininit.exe",         # Windows Init
        "winlogon.exe",        # Windows Logon
        "services.exe",        # Service Control Manager
        "lsass.exe",           # Local Security Authority
        "svchost.exe",         # Service Host — grows with services, not a leak
        "dwm.exe",             # Desktop Window Manager — grows with open windows
        "explorer.exe",        # Windows Explorer — grows with usage, not a leak
        "antimalware service executable", # Windows Defender
        "msmpeng.exe",         # Windows Defender engine
        "searchindexer.exe",   # Windows Search — grows while indexing
        "ntoskrnl.exe",        # Windows kernel
        "mrt.exe",             # Malware Removal Tool
    }

    # Fix advice tailored per known app
    FIX_ADVICE = {
        "chrome.exe":        "Chrome is known to grow over time. Close tabs you're not using, or restart Chrome to reset memory.",
        "msedge.exe":        "Edge is using more memory over time. Close unused tabs or restart Edge.",
        "firefox.exe":       "Firefox memory grows with open tabs. Restart Firefox to reset it.",
        "code.exe":          "VS Code grows with open projects/extensions. Restart it to free up memory.",
        "teams.exe":         "Microsoft Teams is known for memory leaks. Quit and relaunch it from the Start menu.",
        "outlook.exe":       "Outlook grows over long sessions. Close and reopen it to reset memory.",
        "slack.exe":         "Slack's Electron framework tends to leak memory. Restart the app.",
        "discord.exe":       "Discord grows over time. Quit from the system tray and relaunch.",
        "spotify.exe":       "Spotify leaks memory over long sessions. Close and reopen it.",
        "onedrive.exe":      "OneDrive is growing in memory. Right-click its tray icon and choose Quit, then relaunch.",
        "dropbox.exe":       "Dropbox is growing in memory. Quit from the system tray and relaunch.",
        "zoom.exe":          "Zoom grows during/after calls. Restart the app after your meetings.",
        "acrobat.exe":       "Adobe Acrobat grows with open PDFs. Close documents you're not reading.",
        "photoshop.exe":     "Photoshop holds history and caches in memory. Use Edit > Purge > All to free some.",
        "node.exe":          "A Node.js app is growing in memory. Check the app's logs for errors and restart it.",
        "python.exe":        "A Python script is growing in memory. Restart the script or check for infinite loops.",
        "java.exe":          "A Java app is growing in memory. Restart the application.",
        "javaw.exe":         "A Java app is growing in memory. Restart the application.",
    }

    DEFAULT_FIX = "Close and reopen this app to reset its memory. If it keeps growing, the app may have a bug — check for updates."

    leaks = []
    with _mem_tracker_lock:
        for pid, data in _mem_tracker.items():
            name = data["name"]
            # Skip known system processes
            if name.lower() in SYSTEM_PROCESSES or name.lower().replace(".exe", "") in SYSTEM_PROCESSES:
                continue

            samples = data["samples"]
            if len(samples) < 5:
                continue

            rss_values = [s[1] for s in samples]
            increases = sum(1 for i in range(1, len(rss_values)) if rss_values[i] > rss_values[i - 1])
            total_growth = rss_values[-1] - rss_values[0]

            # Flag if >70% of samples show increase AND grew by >50MB
            if increases / (len(rss_values) - 1) > 0.7 and total_growth > 50:
                fix = FIX_ADVICE.get(name.lower(), DEFAULT_FIX)
                leaks.append({
                    "pid": pid,
                    "name": name,
                    "start_mb": rss_values[0],
                    "current_mb": rss_values[-1],
                    "growth_mb": round(total_growth, 1),
                    "samples": len(samples),
                    "fix": fix,
                })

    leaks.sort(key=lambda x: x["growth_mb"], reverse=True)
    return leaks[:10]


@app.route("/api/memory-leaks")
def memory_leaks():
    return jsonify(_detect_memory_leaks())


# ---------------------------------------------------------------------------
# Background Services Scanner (NEW)
# ---------------------------------------------------------------------------

# Common non-essential services that often run on consumer PCs
_BLOAT_SERVICES = {
    "DiagTrack": "Connected User Experiences and Telemetry",
    "dmwappushservice": "WAP Push Message Routing Service",
    "RetailDemo": "Retail Demo Service",
    "MapsBroker": "Downloaded Maps Manager",
    "lfsvc": "Geolocation Service",
    "SharedAccess": "Internet Connection Sharing",
    "RemoteRegistry": "Remote Registry",
    "WMPNetworkSvc": "Windows Media Player Network Sharing",
    "WerSvc": "Windows Error Reporting",
    "XblAuthManager": "Xbox Live Auth Manager",
    "XblGameSave": "Xbox Live Game Save",
    "XboxNetApiSvc": "Xbox Live Networking Service",
    "XboxGipSvc": "Xbox Accessory Management",
    "Fax": "Fax Service",
    "PhoneSvc": "Phone Service",
    "TabletInputService": "Touch Keyboard and Handwriting Panel",
    "wisvc": "Windows Insider Service",
    "WSearch": "Windows Search (heavy indexing)",
    "SysMain": "Superfetch/SysMain (can cause disk thrashing on HDDs)",
}


def _get_bloat_services():
    """Find non-essential services that are currently running."""
    running = []
    try:
        for service in psutil.win_service_iter():
            try:
                info = service.as_dict()
                sname = info.get("name", "")
                if sname in _BLOAT_SERVICES and info.get("status") == "running":
                    running.append({
                        "name": sname,
                        "display_name": info.get("display_name", sname),
                        "description": _BLOAT_SERVICES[sname],
                        "pid": info.get("pid"),
                    })
            except Exception:
                continue
    except Exception:
        pass
    return running


@app.route("/api/bloat-services")
def bloat_services():
    return jsonify(_get_bloat_services())


@app.route("/api/stop-service", methods=["POST"])
def stop_service():
    if not is_admin():
        return jsonify({"error": "Admin privileges required to stop services."}), 403
    sname = request.json.get("name")
    if not sname or sname not in _BLOAT_SERVICES:
        return jsonify({"error": "Invalid or unknown service."}), 400
    try:
        result = subprocess.run(
            ["net", "stop", sname], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return jsonify({"success": True, "message": f"Stopped service: {sname}"})
        return jsonify({"error": result.stderr.strip() or "Failed to stop service."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Bandwidth Monitor (NEW)
# ---------------------------------------------------------------------------

@app.route("/api/network-usage")
def network_usage():
    """Get per-process network connections and system-wide network I/O."""
    # System-wide counters
    counters = psutil.net_io_counters()
    system_info = {
        "bytes_sent_mb": bytes_to_mb(counters.bytes_sent),
        "bytes_recv_mb": bytes_to_mb(counters.bytes_recv),
    }

    # Per-process: find processes with active network connections
    net_procs = {}
    for conn in psutil.net_connections(kind="inet"):
        if conn.status == "ESTABLISHED" and conn.pid:
            if conn.pid not in net_procs:
                try:
                    proc = psutil.Process(conn.pid)
                    io = proc.io_counters()
                    net_procs[conn.pid] = {
                        "pid": conn.pid,
                        "name": proc.name(),
                        "connections": 0,
                        "read_mb": bytes_to_mb(io.read_bytes),
                        "write_mb": bytes_to_mb(io.write_bytes),
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            net_procs[conn.pid]["connections"] += 1

    proc_list = sorted(net_procs.values(), key=lambda x: x["write_mb"] + x["read_mb"], reverse=True)
    return jsonify({"system": system_info, "processes": proc_list[:20]})


# ---------------------------------------------------------------------------
# Duplicate File Finder (NEW)
# ---------------------------------------------------------------------------

@app.route("/api/find-duplicates", methods=["POST"])
def find_duplicates():
    """Scan common folders for duplicate files. Scan user-specified or default dirs."""
    scan_path = request.json.get("path", os.path.expanduser("~\\Downloads"))
    min_size = 1024 * 1024  # 1MB minimum

    if not os.path.isdir(scan_path):
        return jsonify({"error": f"Directory not found: {scan_path}"}), 400

    # Phase 1: Group by size
    size_map = defaultdict(list)
    file_count = 0
    for dirpath, dirnames, filenames in os.walk(scan_path):
        # Skip hidden/system dirs
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                size = os.path.getsize(fp)
                if size >= min_size:
                    size_map[size].append(fp)
            except OSError:
                pass
            file_count += 1
            if file_count > 50000:  # Safety limit
                break
        if file_count > 50000:
            break

    # Phase 2: Hash files with same size
    hash_map = defaultdict(list)
    for size, files in size_map.items():
        if len(files) < 2:
            continue
        for fp in files:
            try:
                h = hashlib.md5()
                with open(fp, "rb") as f:
                    # Read first 8KB for fast comparison
                    h.update(f.read(8192))
                hash_map[h.hexdigest()].append({"path": fp, "size_mb": round(size / (1024 * 1024), 1)})
            except OSError:
                pass

    # Filter to actual duplicates
    duplicates = []
    total_waste = 0
    for h, files in hash_map.items():
        if len(files) >= 2:
            waste = files[0]["size_mb"] * (len(files) - 1)
            total_waste += waste
            duplicates.append({"files": files, "waste_mb": round(waste, 1)})

    duplicates.sort(key=lambda x: x["waste_mb"], reverse=True)
    return jsonify({
        "duplicates": duplicates[:50],
        "total_waste_mb": round(total_waste, 1),
        "scanned_path": scan_path,
    })


@app.route("/api/delete-file", methods=["POST"])
def delete_file():
    """Delete a specific file. Only allows deleting files under the user's home directory."""
    filepath = request.json.get("path", "")
    if not filepath:
        return jsonify({"error": "No file path provided."}), 400

    filepath = os.path.normpath(filepath)

    # Safety: only allow deleting files under the user's home directory
    home = os.path.normpath(os.path.expanduser("~"))
    if not filepath.lower().startswith(home.lower()):
        return jsonify({"error": "Can only delete files in your user folder."}), 403

    # Safety: don't delete anything in AppData, Desktop special folders
    protected_dirs = [
        os.path.join(home, "AppData"),
        os.path.join(home, ".claude"),
    ]
    for pd in protected_dirs:
        if filepath.lower().startswith(os.path.normpath(pd).lower()):
            return jsonify({"error": "Cannot delete files in protected folders."}), 403

    if not os.path.isfile(filepath):
        return jsonify({"error": "File not found."}), 404

    try:
        size = os.path.getsize(filepath)
        os.remove(filepath)
        freed_mb = round(size / (1024 * 1024), 1)
        return jsonify({"success": True, "message": f"Deleted! Freed {freed_mb} MB.", "freed_mb": freed_mb})
    except OSError as e:
        return jsonify({"error": f"Could not delete: {e.strerror}"}), 500


@app.route("/api/delete-files", methods=["POST"])
def delete_files():
    """Delete multiple files at once."""
    paths = request.json.get("paths", [])
    if not paths:
        return jsonify({"error": "No files provided."}), 400

    home = os.path.normpath(os.path.expanduser("~"))
    protected_dirs = [
        os.path.join(home, "AppData"),
        os.path.join(home, ".claude"),
    ]

    deleted = 0
    failed = 0
    freed = 0

    for filepath in paths:
        filepath = os.path.normpath(filepath)
        if not filepath.lower().startswith(home.lower()):
            failed += 1
            continue
        skip = False
        for pd in protected_dirs:
            if filepath.lower().startswith(os.path.normpath(pd).lower()):
                skip = True
                break
        if skip:
            failed += 1
            continue
        if not os.path.isfile(filepath):
            failed += 1
            continue
        try:
            size = os.path.getsize(filepath)
            os.remove(filepath)
            deleted += 1
            freed += size
        except OSError:
            failed += 1

    freed_mb = round(freed / (1024 * 1024), 1)
    return jsonify({
        "success": True,
        "message": f"Deleted {deleted} files, freed {freed_mb} MB." + (f" {failed} files could not be deleted." if failed else ""),
        "deleted": deleted,
        "failed": failed,
        "freed_mb": freed_mb,
    })


# ---------------------------------------------------------------------------
# Startup Programs
# ---------------------------------------------------------------------------

def _get_startup_programs():
    programs = []
    import winreg
    reg_paths = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    ]
    if is_admin():
        reg_paths.extend([
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
        ])

    for hive, path in reg_paths:
        try:
            key = winreg.OpenKey(hive, path)
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    hive_name = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
                    programs.append({
                        "name": name, "command": value,
                        "source": f"Registry ({hive_name})", "location": f"{hive_name}\\{path}",
                    })
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except OSError:
            continue

    startup_folder = os.path.join(
        os.environ.get("APPDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs\Startup"
    )
    if os.path.isdir(startup_folder):
        for item in os.listdir(startup_folder):
            if item.lower() != "desktop.ini":
                programs.append({
                    "name": item, "command": os.path.join(startup_folder, item),
                    "source": "Startup Folder", "location": startup_folder,
                })
    return programs


@app.route("/api/startup-programs")
def startup_programs():
    return jsonify(_get_startup_programs())


@app.route("/api/open-task-manager", methods=["POST"])
def open_task_manager():
    try:
        subprocess.Popen(["taskmgr", "/0", "/startup"])
        return jsonify({"success": True, "message": "Task Manager opened to Startup tab."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Quick Fixes
# ---------------------------------------------------------------------------

@app.route("/api/flush-dns", methods=["POST"])
def flush_dns():
    try:
        result = subprocess.run(
            ["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=15
        )
        return jsonify({"success": True, "message": result.stdout.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/clear-standby-memory", methods=["POST"])
def clear_standby_memory():
    freed = 0
    for proc in psutil.process_iter(["pid"]):
        try:
            handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, proc.info["pid"])
            if handle:
                ctypes.windll.psapi.EmptyWorkingSet(handle)
                ctypes.windll.kernel32.CloseHandle(handle)
                freed += 1
        except Exception:
            continue
    return jsonify({"success": True, "message": f"Trimmed working set of {freed} processes."})


@app.route("/api/power-plan", methods=["GET"])
def get_power_plan():
    try:
        result = subprocess.run(
            ["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=10
        )
        return jsonify({"plan": result.stdout.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/set-high-performance", methods=["POST"])
def set_high_performance():
    try:
        result = subprocess.run(
            ["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return jsonify({"error": "Could not switch. High Performance plan may not be available."}), 500
        return jsonify({"success": True, "message": "Switched to High Performance power plan."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/disable-visual-effects", methods=["POST"])
def disable_visual_effects():
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "VisualFXSetting", 0, winreg.REG_DWORD, 2)
        winreg.CloseKey(key)
        return jsonify({
            "success": True,
            "message": "Visual effects set to Best Performance. Log out and back in for full effect."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

@app.route("/api/snapshot", methods=["POST"])
def save_snapshot():
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.5)
    disk = psutil.disk_usage("C:\\")
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": cpu,
        "ram_percent": mem.percent,
        "disk_percent": disk.percent,
    }
    filepath = os.path.join(DATA_DIR, "snapshots.json")
    snapshots = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                snapshots = json.load(f)
        except (json.JSONDecodeError, IOError):
            snapshots = []
    snapshots.append(snapshot)
    snapshots = snapshots[-100:]
    with open(filepath, "w") as f:
        json.dump(snapshots, f)
    return jsonify({"success": True})


@app.route("/api/snapshots")
def get_snapshots():
    filepath = os.path.join(DATA_DIR, "snapshots.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return jsonify(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass
    return jsonify([])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = 5555
    print("=" * 60)
    print("  PC TuneUp - Local System Optimizer")
    print(f"  Running at: http://localhost:{port}")
    print(f"  Admin mode: {'YES' if is_admin() else 'NO (run as admin for full features)'}")
    print("=" * 60)

    Thread(target=lambda: (time.sleep(1.5), webbrowser.open(f"http://localhost:{port}"))).start()
    app.run(host="127.0.0.1", port=port, debug=False)
