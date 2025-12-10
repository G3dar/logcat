# Unity Logcat Viewer - Multi-Device Edition

A beautiful, cross-platform web-based logcat viewer for Unity/Meta Quest development. Now with **multi-device support** for viewing logs from multiple Quest headsets over WiFi simultaneously.

![Preview](https://img.shields.io/badge/Platform-Mac%20%7C%20Windows%20%7C%20Linux-blue)
![Python](https://img.shields.io/badge/Python-3.7+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Quick Start (30 seconds)

```bash
# Clone and run
git clone https://github.com/G3dar/logcat.git
cd logcat
python3 logcat-web.py
```

That's it! Your browser opens automatically to `http://localhost:8765`

> **Note:** Requires Python 3.7+ and ADB. See [Installation](#installation) for auto-install scripts.

---

## Screenshots

```
┌─────────────────────────────────────────────────────────────────┐
│  Unity Logcat Viewer                    [Scan] [Add] [USB Setup]│
├─────────────────────────────────────────────────────────────────┤
│  [All Devices] [● Quest 3] [● Quest Pro]                        │
├─────────────────────────────────────────────────────────────────┤
│  [Search...               ]  Level: V D [I] W E   [Clear][Pause]│
├─────────────────────────────────────────────────────────────────┤
│  Q3  12:00:01  I  [ConnectionManager] Creating public lobby     │
│  QP  12:00:02  W  [Vivox] QuantumRunner not available           │
│  Q3  12:00:03  E  [Network] Connection timeout                  │
│  ...                                                            │
├─────────────────────────────────────────────────────────────────┤
│  Total: 1,234  Errors: 5  Warnings: 23     2/2 devices  45/sec │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

### Core Features
- **Live log streaming** - Real-time logs via WebSocket
- **Color-coded levels** - Red (errors), Yellow (warnings), Green (info), Blue (debug)
- **Level filter** - Click V/D/I/W/E to set minimum level
- **Category detection** - Auto-detects Quantum, Vivox, Network, Analytics, Camera, Player
- **Search** - Real-time search with highlighting (Ctrl+K)
- **Pause/Resume** - Freeze display to read (Space key)
- **Export** - Download filtered logs as .txt
- **Stats bar** - Error/warning/total counts + logs/sec
- **Dark theme** - GitHub-style dark UI

### Multi-Device Features
- **Network Scanner** - Automatically discover Quest headsets on your WiFi network
- **Multiple Devices** - View logs from multiple Quest headsets simultaneously
- **Device Tabs** - Switch between individual devices or view "All Devices" combined
- **Color-Coded Logs** - Each device gets a unique color badge in combined view
- **USB Setup Helper** - One-click WiFi ADB setup from USB-connected devices
- **Device Management** - Add, remove, rename devices with right-click menu
- **Persistent Config** - Remembered devices auto-reconnect on startup
- **Per-Device Stats** - Track errors/warnings per device

---

## Installation

### Option 1: Quick Run (if you have Python + ADB)

```bash
git clone https://github.com/G3dar/logcat.git
cd logcat
python3 logcat-web.py
```

### Option 2: Full Install (Mac)

```bash
git clone https://github.com/G3dar/logcat.git
cd logcat
chmod +x install-mac.sh
./install-mac.sh
```

The installer will:
- Install Homebrew (if needed)
- Install Python 3 (if needed)
- Install ADB (if needed)
- Install Python dependencies (aiohttp)
- Create double-click launcher

### Option 3: Full Install (Windows)

1. Clone or download this repository
2. Right-click `install-windows.bat` → **Run as administrator**
3. Follow the prompts

The installer will:
- Install Python 3 via winget (if needed)
- Download and install ADB (if needed)
- Install Python dependencies
- Create double-click launcher

---

## Running the Viewer

### Mac
```bash
# Option 1: Double-click
open "Unity Logcat Viewer.command"

# Option 2: Terminal
./run.sh

# Option 3: Direct
python3 logcat-web.py
```

### Windows
```batch
# Option 1: Double-click "Unity Logcat Viewer.vbs"

# Option 2: Command prompt
run.bat

# Option 3: Direct
python logcat-web.py
```

### Linux
```bash
python3 logcat-web.py
```

---

## Usage Guide

### Single Device (USB) - Simplest Setup

1. **Enable Developer Mode** on your Quest (via Meta app on phone)
2. **Connect Quest via USB** to your computer
3. **Accept USB debugging** prompt in the headset
4. **Run the viewer**: `python3 logcat-web.py`
5. Browser opens to `http://localhost:8765`
6. Click **"USB Setup"** → **"Enable WiFi ADB"** (optional, for wireless)

### Multiple Devices (WiFi) - Full Setup

#### Step 1: Enable WiFi ADB (one-time per device)

For each Quest headset:

1. Connect Quest via USB
2. Run the viewer
3. Click **"USB Setup"** button
4. Click **"Enable WiFi ADB"** next to your device
5. Note the IP address shown (e.g., `192.168.1.42`)
6. Disconnect USB - device stays connected wirelessly!

> **Technical note:** This runs `adb tcpip 5555` which enables ADB over WiFi on port 5555. The setting persists until the Quest restarts.

#### Step 2: Add More Devices

**Automatic Discovery:**
- Click **"Scan Network"**
- All Quest devices with WiFi ADB enabled appear
- Click **"Add & Connect"** on each one

**Manual Add:**
- Click **"Add Device"**
- Enter the Quest's IP address (find it in Quest Settings → Wi-Fi → Connected network)
- Click **"Add"**

#### Step 3: View Logs

- **"All Devices" tab** - Combined view with color-coded device badges
- **Individual device tabs** - Filter to single device
- **Right-click any tab** - Connect/Disconnect, Rename, Remove

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+K` / `Cmd+K` | Focus search box |
| `Space` | Pause/Resume log stream |
| `Escape` | Close modal dialogs |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Web Browser                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Device Dashboard                         │ │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │ │
│  │  │Quest 1  │  │Quest 2  │  │Quest 3  │  │ + Add   │       │ │
│  │  │ Online  │  │ Online  │  │Offline  │  │ Device  │       │ │
│  │  └────┬────┘  └────┬────┘  └─────────┘  └─────────┘       │ │
│  └───────┼────────────┼──────────────────────────────────────┘ │
│          │            │                                         │
│  ┌───────▼────────────▼──────────────────────────────────────┐ │
│  │              Tabbed Log Viewer                             │ │
│  │  [All Devices] [Quest 1] [Quest 2]                        │ │
│  │  ─────────────────────────────────────────────────────    │ │
│  │  Q1  12:00:01 I [ConnectionManager] creating public Lobby │ │
│  │  Q2  12:00:02 W [Vivox] QuantumRunner not available       │ │
│  │  ...                                                       │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                    WebSocket (single connection)
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                     Python Server (port 8765)                    │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │Device Manager│  │Network Scanner│  │Config Store │          │
│  │ - track all  │  │ - scan LAN   │  │ - persist   │          │
│  │ - status     │  │ - find 5555  │  │ - nicknames │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │adb -s IP1    │  │adb -s IP2    │  │adb -s IP3    │          │
│  │logcat Unity:V│  │logcat Unity:V│  │logcat Unity:V│          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
          │WiFi             │WiFi             │WiFi
          ▼                 ▼                 ▼
     ┌─────────┐       ┌─────────┐       ┌─────────┐
     │ Quest 1 │       │ Quest 2 │       │ Quest 3 │
     │192.168.x│       │192.168.y│       │192.168.z│
     └─────────┘       └─────────┘       └─────────┘
```

---

## API Reference

The viewer exposes a WebSocket API at `/ws` for real-time communication:

### WebSocket Messages (Client → Server)

```javascript
// Scan network for devices
{action: 'scan'}

// Add device by IP
{action: 'add_device', device_id: '192.168.1.42:5555'}

// Connect to device
{action: 'connect', device_id: '192.168.1.42:5555'}

// Disconnect from device
{action: 'disconnect', device_id: '192.168.1.42:5555'}

// Remove device
{action: 'remove', device_id: '192.168.1.42:5555'}

// Set device nickname
{action: 'set_nickname', device_id: '192.168.1.42:5555', nickname: 'Dev Quest'}

// Get USB-connected devices
{action: 'get_usb_devices'}

// Enable WiFi ADB on USB device
{action: 'enable_wifi', device_id: 'SERIAL123'}

// Clear device stats
{action: 'clear_stats', device_id: '192.168.1.42:5555'}
```

### WebSocket Messages (Server → Client)

```javascript
// Device list on connect
{type: 'device_list', data: [{id, name, status, color, stats, ...}]}

// Device added/updated
{type: 'device_update', data: {id, name, status, color, stats, ...}}

// Device removed
{type: 'device_removed', data: {id}}

// Log line
{type: 'log', data: {timestamp, level, tag, message, category, device_id, device_name, device_color}}

// Scan results
{type: 'scan_result', data: {devices: [{id, ip, known}]}}

// USB devices
{type: 'usb_devices', data: [{id, type: 'usb'}]}

// WiFi enabled result
{type: 'wifi_enabled', data: {success, ip, device_id} | {success: false, error}}
```

### REST API

```
GET  /              # Web UI
GET  /ws            # WebSocket endpoint
GET  /api/devices   # List all devices (JSON)
POST /api/devices/scan  # Trigger network scan
```

---

## Configuration

### Config File Location

```
~/.logcat-viewer/devices.json
```

### Config Format

```json
{
  "devices": [
    {
      "id": "192.168.1.42:5555",
      "nickname": "Dev Quest",
      "connection_type": "wifi"
    },
    {
      "id": "192.168.1.50:5555",
      "nickname": "Test Quest",
      "connection_type": "wifi"
    }
  ]
}
```

### Reset Config

Delete the config file to start fresh:

```bash
rm -rf ~/.logcat-viewer
```

---

## Requirements

| Requirement | Version | Auto-installed |
|-------------|---------|----------------|
| Python | 3.7+ | Yes (via installer) |
| ADB | Any | Yes (via installer) |
| aiohttp | Any | Yes (auto on first run) |
| Browser | Modern | - |

### Network Requirements (for multi-device)

- All devices on same WiFi network
- Port 5555 not blocked by firewall
- Quest devices must have WiFi ADB enabled (one-time USB setup)

---

## Troubleshooting

### "Device not found"

```bash
# Check if ADB sees the device
adb devices

# Should show something like:
# 2G0YC1ZF8108J4    device
# 192.168.1.42:5555 device
```

If empty:
- Reconnect USB cable
- Accept USB debugging prompt in headset
- Enable Developer Mode via Meta phone app

### WiFi ADB not connecting

```bash
# Manual connection test
adb connect 192.168.1.42:5555

# Should show: "connected to 192.168.1.42:5555"
```

If fails:
- Ensure same WiFi network
- Re-enable WiFi ADB: connect USB, run `adb tcpip 5555`
- Check Quest IP in Settings → Wi-Fi → Connected network
- Disable VPN if active

### Logs not appearing

- Ensure Unity app is running on Quest
- Check app uses `Debug.Log()` statements
- Verify filter isn't hiding logs (try clicking "V" level)
- Check device shows green "online" status

### Network scan finds no devices

- WiFi ADB must be enabled on each device first
- Use USB Setup to enable WiFi ADB
- Some corporate networks block discovery - add manually

### Port 8765 already in use

Edit `logcat-web.py` line 35:
```python
PORT = 8766  # Change to any available port
```

### Python/ADB not found

Run the installer script for your platform, or install manually:

**Mac:**
```bash
brew install python android-platform-tools
pip3 install aiohttp
```

**Windows:**
```batch
winget install Python.Python.3.11
# Download ADB from https://developer.android.com/tools/releases/platform-tools
pip install aiohttp
```

**Linux:**
```bash
sudo apt install python3 python3-pip adb
pip3 install aiohttp
```

---

## Files

```
logcat/
├── logcat-web.py              # Main application (single file, ~1400 lines)
├── install-mac.sh             # Mac auto-installer
├── install-windows.bat        # Windows auto-installer
├── README.md                  # This documentation
├── .gitignore                 # Git ignore rules
│
# Created by installer:
├── run.sh                     # Mac launcher script
├── run.bat                    # Windows launcher script
├── Unity Logcat Viewer.command # Mac double-click launcher
└── Unity Logcat Viewer.vbs    # Windows double-click launcher
```

---

## Development

### Running in Development

```bash
# Run with auto-reload (manual restart needed)
python3 logcat-web.py

# The server runs at http://localhost:8765
# All HTML/CSS/JS is embedded in logcat-web.py
```

### Code Structure

```python
# logcat-web.py structure:

# Configuration
PORT = 8765
DEVICE_COLORS = [...]

# Data Classes
@dataclass
class DeviceInfo:
    id, ip, port, name, nickname, status, color, stats, last_seen

# Device Manager
class DeviceManager:
    add_device(), remove_device()
    connect_device(), disconnect_device()
    run_logcat()           # Per-device log streaming
    scan_network()         # Async port scanner
    get_usb_devices()      # List USB devices
    enable_wifi_adb()      # Run adb tcpip 5555
    save_config(), load_config()

# HTTP Handlers
index_handler()            # Serve HTML
websocket_handler()        # WebSocket API

# Embedded Frontend
HTML_PAGE = '''...'''      # ~800 lines of HTML/CSS/JS

# Entry Point
main()                     # Start server, open browser
```

### Contributing

1. Fork the repository
2. Make changes to `logcat-web.py`
3. Test with multiple devices if possible
4. Submit a pull request

---

## License

MIT License - Free to use, modify, and distribute.

---

## Credits

Built with:
- [aiohttp](https://docs.aiohttp.org/) - Async HTTP server
- [Tailwind CSS](https://tailwindcss.com/) - Styling (via CDN)
- [ADB](https://developer.android.com/tools/adb) - Android Debug Bridge

Created for Unity/Meta Quest VR development.
