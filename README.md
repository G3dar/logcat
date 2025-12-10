# Unity Logcat Viewer

A beautiful, cross-platform web-based logcat viewer for Unity/Meta Quest development.

![Preview](https://img.shields.io/badge/Platform-Mac%20%7C%20Windows-blue)
![Python](https://img.shields.io/badge/Python-3.7+-green)

## Features

- **Live log streaming** - Real-time logs via WebSocket
- **Color-coded levels** - Red (errors), Yellow (warnings), Green (info)
- **Level filter** - Click V/D/I/W/E to set minimum level
- **Category filter** - Quantum, Vivox, Network, Analytics buttons
- **Search** - Real-time search with highlighting (Ctrl+K)
- **Exclude filter** - Hide noisy logs with comma-separated terms
- **Pause/Resume** - Freeze display to read (Space key)
- **Export** - Download filtered logs as .txt
- **Stats bar** - Error/warning/total counts + logs/sec
- **Dark theme** - Easy on the eyes

## Quick Install

### Mac

1. Open Terminal
2. Navigate to this folder:
   ```bash
   cd /path/to/logcat-viewer-app
   ```
3. Run the installer:
   ```bash
   chmod +x install-mac.sh
   ./install-mac.sh
   ```

The installer will:
- Install Homebrew (if needed)
- Install Python 3 (if needed)
- Install ADB (if needed)
- Install Python dependencies
- Create launcher scripts

### Windows

1. Right-click `install-windows.bat` and select **Run as administrator**
2. Follow the prompts

The installer will:
- Install Python 3 via winget (if needed)
- Download and install ADB (if needed)
- Install Python dependencies
- Create launcher scripts

## Running the Viewer

### Mac
- **Double-click** `Unity Logcat Viewer.command`
- Or run in Terminal: `./run.sh`

### Windows
- **Double-click** `Unity Logcat Viewer.vbs`
- Or double-click `run.bat`

### Manual
```bash
python3 logcat-web.py   # Mac/Linux
python logcat-web.py    # Windows
```

## Usage

1. Connect your Meta Quest via USB
2. Enable Developer Mode on the Quest
3. Accept the USB debugging prompt in the headset
4. Run the viewer
5. Your browser will open to `http://localhost:8765`

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+K` | Focus search box |
| `Space` | Pause/Resume |

## Requirements

- **Python 3.7+** (auto-installed)
- **ADB** (auto-installed)
- **Modern browser** (Chrome, Firefox, Safari, Edge)

## Troubleshooting

### "Device not found"
- Make sure your Quest is connected via USB
- Accept the USB debugging prompt in the headset
- Try running `adb devices` to verify connection

### Logs not appearing
- Make sure a Unity app is running on the Quest
- Check that the app uses `Debug.Log()` statements

### Port already in use
- Edit `logcat-web.py` and change `PORT = 8765` to another port

## Files

```
logcat-viewer-app/
├── logcat-web.py              # Main application
├── install-mac.sh             # Mac installer
├── install-windows.bat        # Windows installer
├── run.sh                     # Mac launcher (created by installer)
├── run.bat                    # Windows launcher (created by installer)
├── Unity Logcat Viewer.command # Mac double-click launcher
├── Unity Logcat Viewer.vbs    # Windows double-click launcher
└── README.md                  # This file
```

## License

MIT - Free to use and modify.
