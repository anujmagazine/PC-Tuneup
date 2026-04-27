# PC TuneUp

A free, open-source, locally-hosted Windows PC optimizer. Diagnoses why your PC is slow and lets you fix it with one click — no cloud, no subscriptions, no data leaves your machine.

Built as a lightweight alternative to bloated tools like AVG TuneUp, CCleaner, etc.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-green?logo=flask&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## What It Does

PC TuneUp scans your Windows PC, identifies what's slowing it down, tells you exactly how to fix each problem in plain English, and lets you fix most issues with a single click — all from a clean web dashboard running on `localhost`.

### All 28 Problems It Detects & Fixes

#### Storage & Disk Issues

| # | Problem | How the App Helps | Fix Method |
|---|---|---|---|
| 1 | **Low disk space** | Detects when C: drive is running out of space | One-click junk file cleanup |
| 2 | **Junk temporary files** | Scans Windows temp dirs, finds hundreds of MBs of junk | One-click delete |
| 3 | **Browser cache bloat** | Measures Chrome, Edge, Firefox cache sizes (often 1-2 GB each) | One-click cleanup for all browsers |
| 4 | **Windows Update cache** | Finds old update files in `SoftwareDistribution\Download` | One-click cleanup (admin) |
| 5 | **Duplicate files** | Scans any folder for identical files using MD5 hashing | Delete individual copies or all at once |
| 6 | **Failing hard drive (S.M.A.R.T.)** | Reads drive health sensors, predicts failure before it happens | Alerts you to back up immediately |
| 7 | **HDD vs SSD detection** | Identifies drive media type | Shows in Disk Health tab |

#### CPU & Performance Issues

| # | Problem | How the App Helps | Fix Method |
|---|---|---|---|
| 8 | **High CPU usage** | Detects when CPU is overloaded (>80%) | Identifies the app causing it; one-click kill |
| 9 | **Thermal throttling** | Reads CPU temperature via WMI, detects when CPU slows itself due to heat | Shows temp, gives cooling tips (compressed air, cooling pad, thermal paste) |
| 10 | **High CPU temperature** | Warns when CPU is getting warm (>75°C) before throttling starts | Preventive tips |
| 11 | **Slow power plan** | Detects if Windows is in Balanced/Power Saver mode | One-click switch to High Performance |
| 12 | **Visual effects wasting CPU** | Windows animations, transparency, and effects use CPU/GPU | One-click disable (sets Best Performance) |
| 13 | **CPU frequency throttling** | Compares current CPU speed to max speed | Detects if CPU is running below capacity |

#### Memory Issues

| # | Problem | How the App Helps | Fix Method |
|---|---|---|---|
| 14 | **High RAM usage** | Alerts when RAM exceeds 70% or 85% | One-click memory free + identifies heavy apps |
| 15 | **Memory-hungry processes** | Finds apps using 500+ MB of RAM each | Lists top 30 processes with "End" button |
| 16 | **Memory leaks** | Background monitor tracks process RAM every 60 seconds, flags apps with steadily growing usage | Shows growth rate, advises restarting the app |
| 17 | **Excessive paging/swap** | Detects when Windows is using the slow hard drive as overflow RAM (>50% swap) | One-click memory free + app cleanup guidance |
| 18 | **Standby memory buildup** | Cached memory that isn't released back to apps that need it | One-click working set trim for all processes |

#### Startup & Background Issues

| # | Problem | How the App Helps | Fix Method |
|---|---|---|---|
| 19 | **Too many startup programs** | Counts programs from Registry (HKCU & HKLM) and Startup folder | Lists all with source; opens Task Manager Startup tab |
| 20 | **Unnecessary background services** | Scans for 19 known non-essential services (Xbox, Fax, telemetry, geolocation, etc.) | One-click stop for each (admin); auto-restarts on reboot |
| 21 | **Windows Search indexer** | Detects if WSearch service is running (heavy disk I/O on older PCs) | One-click stop |
| 22 | **Superfetch/SysMain** | Detects if SysMain is running (causes disk thrashing on HDDs) | One-click stop |
| 23 | **Telemetry services** | Detects DiagTrack and dmwappushservice running | One-click stop |

#### Network Issues

| # | Problem | How the App Helps | Fix Method |
|---|---|---|---|
| 24 | **Bandwidth-hogging apps** | Shows all processes with active network connections, sorted by I/O | Identifies the app; guide to close it or pause sync |
| 25 | **Slow DNS resolution** | Stale DNS cache causing slow or broken website loading | One-click DNS flush (`ipconfig /flushdns`) |
| 26 | **Background downloads** | Identifies OneDrive, Windows Update, Dropbox using bandwidth | Actionable tips to pause syncing |

#### System Health Issues

| # | Problem | How the App Helps | Fix Method |
|---|---|---|---|
| 27 | **Long uptime (no restart)** | Detects when PC hasn't restarted in 7+ days | Advises restart with explanation of why it helps |
| 28 | **Overall health score** | Calculates a 0-100 health score based on all detected issues | Prioritized fix list sorted by impact |

### Every Issue Includes

- **Plain English explanation** of what the problem is and why it matters
- **Step-by-step "How to fix"** instructions anyone can follow
- **Estimated performance improvement** (e.g., "20-40% faster", "Free 2.1 GB space")
- **Effort required** (e.g., "instant", "1 min", "5 min")
- **One-click fix button** where possible
- **Admin access indicator** — clearly tells you when admin is needed and how to get it

---

## Screenshots

The app has 6 tabs:

| Tab | Purpose |
|---|---|
| **Fix Problems** | Dashboard with health score, system stats, and all detected issues with fix buttons |
| **Free Space** | Shows temp files, browser cache, update cache sizes with cleanup buttons + duplicate file finder |
| **Running Apps** | Top processes by memory usage with "End" buttons + memory leak detection |
| **Startup Apps** | Lists all startup programs with instructions to disable them |
| **PC Health** | Disk S.M.A.R.T. status, CPU temperature, background services, speed boost settings |
| **Network** | Bandwidth monitor showing which apps are using the internet |

---

## Installation & Setup

### Prerequisites

- **Windows 10 or 11**
- **Python 3.8+** installed ([Download Python](https://www.python.org/downloads/))
  - During installation, check **"Add Python to PATH"**

### Step 1: Download the Code

```bash
git clone https://github.com/YOUR_USERNAME/pc-tuneup.git
cd pc-tuneup
```

Or download as ZIP from GitHub and extract it.

### Step 2: Install Dependencies

Open **Command Prompt** and navigate to the project folder:

```bash
cd path\to\pc-tuneup
python -m pip install -r requirements.txt
```

If `python` doesn't work, try `py` instead:

```bash
py -m pip install -r requirements.txt
```

### Step 3: Run the App

**Option A — Normal mode:**

```bash
python app.py
```

**Option B — Admin mode (recommended for full features):**

Right-click `start-as-admin.bat` and select **"Run as administrator"**.

Or from an admin Command Prompt:

```bash
python app.py
```

### Step 4: Open in Browser

The app opens automatically. If it doesn't, go to:

```
http://localhost:5555
```

### Stopping the App

Press `Ctrl+C` in the terminal window.

---

## Quick Start (Easiest Method)

1. Download or clone this repo
2. Double-click **`start.bat`** (or right-click **`start-as-admin.bat`** → Run as administrator)
3. The browser opens automatically to `http://localhost:5555`
4. Click **"Fix All Automatically"** on the dashboard

That's it.

---

## Normal Mode vs Admin Mode

| Feature | Normal Mode | Admin Mode |
|---|---|---|
| System diagnostics | Yes | Yes |
| Clean temp files | Yes | Yes |
| Clean browser cache | Yes | Yes |
| Free cached memory | Yes | Yes |
| Kill processes | Partial | Yes |
| Clean Windows Update cache | No | Yes |
| Stop background services | No | Yes |
| Clean `C:\Windows\Temp` | No | Yes |
| Read system-level startup entries | No | Yes |

**How to run as Admin:** Right-click `start-as-admin.bat` → **"Run as administrator"**

---

## Project Structure

```
pc-tuneup/
├── app.py                 # Flask backend with all API endpoints
├── requirements.txt       # Python dependencies
├── start.bat              # Double-click launcher (normal mode)
├── start-as-admin.bat     # Double-click launcher (admin mode)
├── templates/
│   └── index.html         # Frontend (single-page app)
└── data/
    └── snapshots.json     # Local health history (auto-generated)
```

---

## Tech Stack

- **Backend:** Python 3, Flask, psutil, WMI
- **Frontend:** Vanilla HTML/CSS/JavaScript (no build step, no npm)
- **Data:** Local JSON file (no database needed)
- **Hosting:** 100% local (`localhost:5555`), zero cloud dependencies

---

## API Endpoints

All endpoints are local-only (`127.0.0.1`).

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/system-overview` | CPU, RAM, disk usage, uptime |
| `GET` | `/api/diagnose` | Full diagnosis with issues, severity, fix instructions |
| `GET` | `/api/processes` | Top 30 processes by memory |
| `POST` | `/api/kill-process` | Terminate a process by PID |
| `POST` | `/api/clean-temp` | Delete temporary files |
| `POST` | `/api/clean-browser-cache` | Clean Chrome/Edge/Firefox cache |
| `POST` | `/api/clean-wu-cache` | Clean Windows Update cache (admin) |
| `POST` | `/api/run-disk-cleanup` | Launch Windows Disk Cleanup |
| `GET` | `/api/startup-programs` | List startup programs |
| `POST` | `/api/open-task-manager` | Open Task Manager to Startup tab |
| `POST` | `/api/flush-dns` | Flush DNS cache |
| `POST` | `/api/clear-standby-memory` | Free cached/standby memory |
| `GET` | `/api/power-plan` | Get current power plan |
| `POST` | `/api/set-high-performance` | Switch to High Performance plan |
| `POST` | `/api/disable-visual-effects` | Set visual effects to Best Performance |
| `GET` | `/api/disk-health` | S.M.A.R.T. disk health status |
| `GET` | `/api/thermal` | CPU temperature and throttle status |
| `GET` | `/api/memory-leaks` | Detect processes with growing memory |
| `GET` | `/api/bloat-services` | List non-essential running services |
| `POST` | `/api/stop-service` | Stop a background service (admin) |
| `GET` | `/api/network-usage` | Per-process network activity |
| `POST` | `/api/find-duplicates` | Scan folder for duplicate files |
| `POST` | `/api/delete-file` | Delete a single file |
| `POST` | `/api/delete-files` | Delete multiple files |
| `GET` | `/api/browser-cache-info` | Browser cache sizes |
| `GET` | `/api/wu-cache-info` | Windows Update cache size |
| `GET` | `/api/temp-files-info` | Temp files total size |
| `POST` | `/api/snapshot` | Save system metrics snapshot |
| `GET` | `/api/snapshots` | Get historical snapshots |

---

## Safety & Security

- **100% local** — runs on `127.0.0.1` only, not exposed to the network
- **No data collection** — nothing is sent anywhere, ever
- **No telemetry** — no analytics, no tracking, no phone-home
- **Protected system processes** — critical Windows processes (explorer.exe, svchost.exe, etc.) cannot be killed
- **Protected folders** — file deletion is restricted to user directories; AppData and system folders are blocked
- **Safe service stopping** — only stops known non-essential services; they auto-restart on reboot
- **Confirmation dialogs** — destructive actions (kill process, delete files) always ask for confirmation

---

## Troubleshooting

### `python` is not recognized

Python isn't in your PATH. Either:
- Reinstall Python and check **"Add Python to PATH"** during setup
- Use `py` instead of `python` in all commands

### `pip` is not recognized

Use `python -m pip` or `py -m pip` instead of `pip`:

```bash
py -m pip install -r requirements.txt
```

### `pywin32` fails to install

Make sure you're using a supported Python version. Check your version:

```bash
py --version
```

Then update `requirements.txt` to use the pywin32 version available for your Python version.

### Port 5555 is already in use

Another app is using port 5555. Either close that app, or edit `app.py` and change the `port = 5555` line to another port (e.g., `port = 8080`).

### Some features say "Needs Admin"

Run the app as administrator:
1. Right-click `start-as-admin.bat`
2. Select **"Run as administrator"**

### Temperature shows "N/A"

Some PCs don't expose CPU temperature through WMI. This is a hardware/driver limitation, not a bug.

---

## Contributing

Contributions are welcome! Some ideas:

- [ ] Add GPU temperature monitoring
- [ ] Add disk defragmentation analysis (HDD only)
- [ ] Add scheduled scans
- [ ] Add system restore point creation
- [ ] Add driver update checking
- [ ] Add dark/light theme toggle
- [ ] Add export health report as PDF
- [ ] Add tray icon for background monitoring

---

## License

MIT License — free to use, modify, and distribute.

---

## Acknowledgments

Built with [Flask](https://flask.palletsprojects.com/), [psutil](https://github.com/giampaolo/psutil), and [WMI](https://github.com/tjguk/wmi).
