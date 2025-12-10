# Claude Code Instructions for Unity Logcat Viewer

This file helps Claude Code understand and work with this project effectively.

## Project Overview

Unity Logcat Viewer is a single-file Python web application that displays real-time logs from Meta Quest VR headsets. It supports multiple devices over WiFi.

## Quick Commands

```bash
# Run the app
python3 logcat-web.py

# Test if ADB works
adb devices

# Connect to a Quest wirelessly (after USB setup)
adb connect 192.168.1.42:5555
```

## File Structure

```
logcat/
├── logcat-web.py          # THE MAIN FILE - everything is here (~1500 lines)
├── install-mac.sh         # Mac installer script
├── install-windows.bat    # Windows installer script
├── README.md              # User documentation
├── CLAUDE.md              # This file - Claude Code instructions
└── .gitignore
```

## Architecture

The entire application is in `logcat-web.py`:

1. **Backend (Python/aiohttp)**
   - Lines 1-600: Server logic, DeviceManager, ADB handling
   - `DeviceInfo` dataclass: Tracks device state
   - `DeviceManager` class: Manages all devices, spawns ADB processes
   - WebSocket handler: Receives commands, broadcasts logs

2. **Frontend (embedded HTML)**
   - Lines 600-1450: `HTML_PAGE` constant containing full HTML/CSS/JS
   - Uses Tailwind CSS via CDN
   - Vanilla JavaScript, no build step

## Key Classes

### DeviceInfo (dataclass)
```python
@dataclass
class DeviceInfo:
    id: str           # "192.168.1.42:5555"
    ip: str
    port: int = 5555
    name: str         # From getprop ro.product.model
    nickname: str     # User-assigned
    status: str       # "online", "offline", "connecting"
    color: str        # Hex color for UI badge
    stats: Dict       # {E: 0, W: 0, I: 0, D: 0, V: 0, total: 0}
```

### DeviceManager
Main methods:
- `add_device(device_id)` - Track a new device
- `connect_device(device_id)` - Run `adb connect` + start logcat
- `disconnect_device(device_id)` - Stop logcat, update status
- `run_logcat(device_id)` - Async loop reading `adb logcat`
- `scan_network()` - Parallel port 5555 scan on local subnet
- `enable_wifi_adb(device_id)` - Run `adb tcpip 5555` on USB device

## WebSocket Protocol

Client sends:
```javascript
{action: 'scan'}
{action: 'connect', device_id: '192.168.1.42:5555'}
{action: 'add_device', device_id: '192.168.1.42'}
```

Server sends:
```javascript
{type: 'device_list', data: [...]}
{type: 'device_update', data: {...}}
{type: 'log', data: {timestamp, level, tag, message, device_id, ...}}
{type: 'scan_result', data: {devices: [...]}}
```

## Common Tasks

### Adding a new WebSocket action
1. Add handler in `websocket_handler()` around line 530
2. Add corresponding method in `DeviceManager` if needed
3. Add frontend handling in JavaScript `handleMessage()` function

### Modifying the UI
1. Find `HTML_PAGE = '''` around line 600
2. HTML structure, CSS, and JavaScript are all inline
3. Uses Tailwind CSS classes - reference: https://tailwindcss.com/docs

### Adding a new API endpoint
1. Create async handler function like `api_devices_handler()`
2. Register in `main()`: `app.router.add_get('/api/path', handler)`

## Testing

No test suite currently. Test manually:

1. Run `python3 logcat-web.py`
2. Browser opens to http://localhost:8765
3. Connect Quest via USB, click "USB Setup" → "Enable WiFi ADB"
4. Device should appear and logs should stream

## Common Issues

### "adb not found"
```bash
# Mac
brew install android-platform-tools

# Linux
sudo apt install adb
```

### Port 8765 in use
Change `PORT = 8765` at line ~80 to another port

### Logs not appearing
- Quest must have USB debugging enabled (Developer Mode)
- Unity app must be running and using Debug.Log()
- Check device status is "online" (green dot)

## Code Style

- Single file, self-contained
- Async/await throughout (aiohttp)
- Type hints on function signatures
- Docstrings on classes and important methods
- No external UI dependencies (Tailwind via CDN)

## GitHub Repository

https://github.com/G3dar/logcat

## Dependencies

Runtime:
- Python 3.7+
- aiohttp (auto-installed)
- ADB in PATH

No build tools, no npm, no compilation.
