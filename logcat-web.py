#!/usr/bin/env python3
"""
Unity Logcat Web Viewer - Multi-Device Edition
==============================================

A beautiful, cross-platform web-based logcat viewer for Unity/Meta Quest development.
Supports multiple Quest headsets over WiFi with auto-discovery.

QUICK START:
    python3 logcat-web.py
    # Browser opens automatically to http://localhost:8765

FEATURES:
    - Multi-device support: View logs from multiple Quest headsets simultaneously
    - Network scanner: Auto-discover devices with WiFi ADB enabled
    - USB setup helper: One-click WiFi ADB setup from USB-connected devices
    - Real-time streaming: WebSocket-based live log updates
    - Filtering: By level (V/D/I/W/E), search text, and device
    - Persistent config: Remembers devices and nicknames across restarts

ARCHITECTURE:
    Browser <--WebSocket--> Python Server <--ADB--> Quest Devices

    The server spawns one `adb -s <ip>:5555 logcat` process per device
    and streams parsed log lines to all connected browser clients.

REQUIREMENTS:
    - Python 3.7+
    - ADB (Android Debug Bridge) in PATH
    - aiohttp (auto-installed on first run)

CONFIGURATION:
    - PORT: Change the server port (default 8765)
    - CONFIG_FILE: Device config stored at ~/.logcat-viewer/devices.json
    - SCAN_TIMEOUT: Network scan timeout per IP (default 0.5s)

API ENDPOINTS:
    GET  /           - Web UI
    GET  /ws         - WebSocket for logs and device updates
    GET  /api/devices - List all devices (JSON)
    POST /api/devices/scan - Trigger network scan

WEBSOCKET ACTIONS (send JSON):
    {action: 'scan'}                    - Scan network for devices
    {action: 'add_device', device_id}   - Add device by IP
    {action: 'connect', device_id}      - Connect to device
    {action: 'disconnect', device_id}   - Disconnect from device
    {action: 'remove', device_id}       - Remove device
    {action: 'set_nickname', device_id, nickname} - Set device nickname
    {action: 'get_usb_devices'}         - List USB-connected devices
    {action: 'enable_wifi', device_id}  - Enable WiFi ADB on USB device
    {action: 'clear_stats', device_id}  - Reset device error/warning counts

LICENSE: MIT

REPOSITORY: https://github.com/G3dar/logcat
"""

import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import webbrowser
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set

# Auto-install aiohttp if missing
try:
    from aiohttp import web
except ImportError:
    print("Installing aiohttp...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
    from aiohttp import web

# Configuration
PORT = 8765
HOST = "0.0.0.0"
CONFIG_FILE = Path.home() / ".logcat-viewer" / "devices.json"
SCAN_TIMEOUT = 0.5  # seconds per port check
DEVICE_COLORS = [
    "#3b82f6",  # blue
    "#10b981",  # green
    "#f59e0b",  # amber
    "#ef4444",  # red
    "#8b5cf6",  # purple
    "#ec4899",  # pink
    "#06b6d4",  # cyan
    "#84cc16",  # lime
]

# Regex for parsing logcat
LOG_PATTERN = re.compile(
    r'^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+'
    r'(\d+)\s+(\d+)\s+'
    r'([VDIWEF])\s+'
    r'(\S+)\s*:\s*'
    r'(.*)$'
)

UNITY_TAG_PATTERN = re.compile(r'\[([^\]]+)\]')
COLOR_TAG_PATTERN = re.compile(r'<color=([^>]+)>([^<]*)</color>')


@dataclass
class DeviceInfo:
    """Information about a connected device"""
    id: str                     # e.g., "192.168.1.42:5555" or serial for USB
    ip: str = ""
    port: int = 5555
    name: str = "Unknown Device"
    nickname: str = ""
    status: str = "offline"     # online, offline, connecting
    connection_type: str = "wifi"  # wifi or usb
    color: str = "#3b82f6"
    stats: Dict = field(default_factory=lambda: {'E': 0, 'W': 0, 'I': 0, 'D': 0, 'V': 0, 'total': 0})
    last_seen: Optional[str] = None

    def to_dict(self):
        return asdict(self)


class DeviceManager:
    """Manages multiple ADB devices"""

    def __init__(self):
        self.devices: Dict[str, DeviceInfo] = {}
        self.processes: Dict[str, asyncio.subprocess.Process] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.color_index = 0
        self.clients: Set[web.WebSocketResponse] = set()

    def get_next_color(self) -> str:
        color = DEVICE_COLORS[self.color_index % len(DEVICE_COLORS)]
        self.color_index += 1
        return color

    async def broadcast(self, message: dict):
        """Send message to all connected WebSocket clients"""
        if not self.clients:
            return
        msg_str = json.dumps(message)
        await asyncio.gather(
            *[client.send_str(msg_str) for client in self.clients],
            return_exceptions=True
        )

    async def add_device(self, device_id: str, name: str = "", connection_type: str = "wifi") -> DeviceInfo:
        """Add a new device to track"""
        if device_id in self.devices:
            return self.devices[device_id]

        # Parse IP from device_id
        ip = device_id.split(":")[0] if ":" in device_id else device_id
        port = int(device_id.split(":")[1]) if ":" in device_id else 5555

        device = DeviceInfo(
            id=device_id,
            ip=ip,
            port=port,
            name=name or f"Device ({ip})",
            connection_type=connection_type,
            color=self.get_next_color(),
            status="offline"
        )

        self.devices[device_id] = device
        await self.broadcast({'type': 'device_added', 'data': device.to_dict()})
        return device

    async def remove_device(self, device_id: str):
        """Remove a device"""
        if device_id in self.devices:
            await self.disconnect_device(device_id)
            del self.devices[device_id]
            await self.broadcast({'type': 'device_removed', 'data': {'id': device_id}})

    async def connect_device(self, device_id: str):
        """Connect to a device and start logcat"""
        if device_id not in self.devices:
            return False

        device = self.devices[device_id]
        device.status = "connecting"
        await self.broadcast({'type': 'device_update', 'data': device.to_dict()})

        # Try to connect via ADB
        try:
            if device.connection_type == "wifi":
                # Connect to wireless device
                proc = await asyncio.create_subprocess_exec(
                    'adb', 'connect', device_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                output = stdout.decode() + stderr.decode()

                if "connected" not in output.lower() and "already" not in output.lower():
                    device.status = "offline"
                    await self.broadcast({'type': 'device_update', 'data': device.to_dict()})
                    return False

            # Get device name
            device.name = await self.get_device_name(device_id)

            # Start logcat
            device.status = "online"
            device.last_seen = datetime.now().isoformat()
            await self.broadcast({'type': 'device_update', 'data': device.to_dict()})

            # Start logcat task
            task = asyncio.create_task(self.run_logcat(device_id))
            self.tasks[device_id] = task

            return True

        except Exception as e:
            print(f"Error connecting to {device_id}: {e}")
            device.status = "offline"
            await self.broadcast({'type': 'device_update', 'data': device.to_dict()})
            return False

    async def disconnect_device(self, device_id: str):
        """Disconnect from a device"""
        # Cancel logcat task
        if device_id in self.tasks:
            self.tasks[device_id].cancel()
            try:
                await self.tasks[device_id]
            except asyncio.CancelledError:
                pass
            del self.tasks[device_id]

        # Kill process
        if device_id in self.processes:
            self.processes[device_id].terminate()
            del self.processes[device_id]

        # Update status
        if device_id in self.devices:
            self.devices[device_id].status = "offline"
            await self.broadcast({'type': 'device_update', 'data': self.devices[device_id].to_dict()})

    async def get_device_name(self, device_id: str) -> str:
        """Get device model name via adb"""
        try:
            proc = await asyncio.create_subprocess_exec(
                'adb', '-s', device_id, 'shell', 'getprop', 'ro.product.model',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            name = stdout.decode().strip()
            return name if name else "Unknown Device"
        except:
            return "Unknown Device"

    async def run_logcat(self, device_id: str):
        """Run logcat for a specific device"""
        device = self.devices[device_id]

        while True:
            try:
                print(f"Starting logcat for {device_id} ({device.name})...")
                process = await asyncio.create_subprocess_exec(
                    'adb', '-s', device_id, 'logcat', '-s', 'Unity:V',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )

                self.processes[device_id] = process

                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break

                    line = line.decode('utf-8', errors='replace')
                    parsed = parse_log_line(line)

                    if parsed:
                        parsed['device_id'] = device_id
                        parsed['device_name'] = device.nickname or device.name
                        parsed['device_color'] = device.color

                        # Update device stats
                        device.stats[parsed['level']] = device.stats.get(parsed['level'], 0) + 1
                        device.stats['total'] += 1
                        device.last_seen = datetime.now().isoformat()

                        await self.broadcast({'type': 'log', 'data': parsed})

                print(f"Logcat ended for {device_id}, restarting in 2 seconds...")
                device.status = "connecting"
                await self.broadcast({'type': 'device_update', 'data': device.to_dict()})
                await asyncio.sleep(2)

            except asyncio.CancelledError:
                print(f"Logcat cancelled for {device_id}")
                break
            except Exception as e:
                print(f"Error in logcat for {device_id}: {e}")
                device.status = "offline"
                await self.broadcast({'type': 'device_update', 'data': device.to_dict()})
                await asyncio.sleep(2)

    async def scan_network(self) -> list:
        """Scan local network for ADB devices"""
        local_ip = get_local_ip()
        if not local_ip:
            return []

        subnet = local_ip.rsplit('.', 1)[0]
        found_devices = []

        print(f"Scanning network {subnet}.0/24 for ADB devices...")
        await self.broadcast({'type': 'scan_status', 'data': {'status': 'scanning', 'subnet': subnet}})

        # Scan in batches for better performance
        async def check_host(ip):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, 5555),
                    timeout=SCAN_TIMEOUT
                )
                writer.close()
                await writer.wait_closed()
                return ip
            except:
                return None

        # Scan all IPs in parallel
        tasks = [check_host(f"{subnet}.{i}") for i in range(1, 255)]
        results = await asyncio.gather(*tasks)

        for ip in results:
            if ip:
                device_id = f"{ip}:5555"
                found_devices.append({
                    'id': device_id,
                    'ip': ip,
                    'known': device_id in self.devices
                })

        print(f"Found {len(found_devices)} devices with port 5555 open")
        await self.broadcast({'type': 'scan_result', 'data': {'devices': found_devices}})

        return found_devices

    async def get_usb_devices(self) -> list:
        """Get list of USB-connected devices"""
        try:
            proc = await asyncio.create_subprocess_exec(
                'adb', 'devices',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()

            devices = []
            for line in stdout.decode().split('\n')[1:]:
                if '\tdevice' in line:
                    serial = line.split('\t')[0]
                    # Skip WiFi devices (they have IP:port format)
                    if ':' not in serial:
                        devices.append({
                            'id': serial,
                            'type': 'usb'
                        })
            return devices
        except:
            return []

    async def enable_wifi_adb(self, device_id: str) -> dict:
        """Enable WiFi ADB on a USB-connected device"""
        try:
            # Enable TCP/IP mode
            proc = await asyncio.create_subprocess_exec(
                'adb', '-s', device_id, 'tcpip', '5555',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            # Get device IP
            await asyncio.sleep(1)  # Wait for tcpip to take effect

            proc = await asyncio.create_subprocess_exec(
                'adb', '-s', device_id, 'shell', 'ip', 'addr', 'show', 'wlan0',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode()

            # Parse IP from output
            import re
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', output)
            if match:
                ip = match.group(1)
                return {'success': True, 'ip': ip, 'device_id': f"{ip}:5555"}

            return {'success': False, 'error': 'Could not get device IP'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_all_devices(self) -> list:
        """Get list of all devices"""
        return [d.to_dict() for d in self.devices.values()]

    def save_config(self):
        """Save known devices to config file"""
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        config = {
            'devices': [
                {
                    'id': d.id,
                    'nickname': d.nickname,
                    'connection_type': d.connection_type
                }
                for d in self.devices.values()
            ]
        }
        CONFIG_FILE.write_text(json.dumps(config, indent=2))

    async def load_config(self):
        """Load known devices from config file"""
        if CONFIG_FILE.exists():
            try:
                config = json.loads(CONFIG_FILE.read_text())
                for d in config.get('devices', []):
                    await self.add_device(
                        d['id'],
                        connection_type=d.get('connection_type', 'wifi')
                    )
                    if d.get('nickname'):
                        self.devices[d['id']].nickname = d['nickname']
            except:
                pass


# Global device manager
device_manager = DeviceManager()


def get_local_ip() -> str:
    """Get local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return ""


def parse_log_line(line: str) -> Optional[dict]:
    """Parse a logcat line into a structured object"""
    line = line.strip()
    if not line:
        return None

    match = LOG_PATTERN.match(line)
    if not match:
        return None

    timestamp, pid, tid, level, tag, message = match.groups()

    # Extract Unity tag if present
    unity_tag = None
    tag_match = UNITY_TAG_PATTERN.search(message)
    if tag_match:
        potential_tag = tag_match.group(1)
        if not re.match(r'\d+hs?\s+\d+m', potential_tag):
            unity_tag = potential_tag

    # Detect category
    msg_lower = message.lower()
    category = None
    if 'quantum' in msg_lower:
        category = 'quantum'
    elif 'vivox' in msg_lower:
        category = 'vivox'
    elif 'connection' in msg_lower or 'network' in msg_lower or 'http' in msg_lower:
        category = 'network'
    elif 'analytics' in msg_lower or 'firebase' in msg_lower:
        category = 'analytics'
    elif 'camera' in msg_lower or 'follower' in msg_lower:
        category = 'camera'
    elif 'player' in msg_lower or 'roy' in msg_lower:
        category = 'player'

    # Clean Unity color tags for display
    clean_message = COLOR_TAG_PATTERN.sub(r'\2', message)

    return {
        'timestamp': timestamp,
        'level': level,
        'tag': unity_tag or tag,
        'message': clean_message,
        'category': category,
        'raw': line
    }


# HTTP Handlers
async def index_handler(request):
    """Serve the HTML page"""
    return web.Response(text=HTML_PAGE, content_type='text/html')


async def websocket_handler(request):
    """Handle WebSocket connections"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    device_manager.clients.add(ws)
    print(f"Client connected. Total: {len(device_manager.clients)}")

    # Send current device list
    await ws.send_str(json.dumps({
        'type': 'device_list',
        'data': device_manager.get_all_devices()
    }))

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                action = data.get('action')

                if action == 'scan':
                    await device_manager.scan_network()
                elif action == 'add_device':
                    device_id = data.get('device_id')
                    if device_id:
                        if ':' not in device_id:
                            device_id = f"{device_id}:5555"
                        await device_manager.add_device(device_id)
                elif action == 'connect':
                    device_id = data.get('device_id')
                    if device_id:
                        await device_manager.connect_device(device_id)
                elif action == 'disconnect':
                    device_id = data.get('device_id')
                    if device_id:
                        await device_manager.disconnect_device(device_id)
                elif action == 'remove':
                    device_id = data.get('device_id')
                    if device_id:
                        await device_manager.remove_device(device_id)
                elif action == 'set_nickname':
                    device_id = data.get('device_id')
                    nickname = data.get('nickname', '')
                    if device_id and device_id in device_manager.devices:
                        device_manager.devices[device_id].nickname = nickname
                        await device_manager.broadcast({
                            'type': 'device_update',
                            'data': device_manager.devices[device_id].to_dict()
                        })
                elif action == 'get_usb_devices':
                    usb_devices = await device_manager.get_usb_devices()
                    await ws.send_str(json.dumps({
                        'type': 'usb_devices',
                        'data': usb_devices
                    }))
                elif action == 'enable_wifi':
                    device_id = data.get('device_id')
                    if device_id:
                        result = await device_manager.enable_wifi_adb(device_id)
                        await ws.send_str(json.dumps({
                            'type': 'wifi_enabled',
                            'data': result
                        }))
                elif action == 'clear_stats':
                    device_id = data.get('device_id')
                    if device_id and device_id in device_manager.devices:
                        device_manager.devices[device_id].stats = {
                            'E': 0, 'W': 0, 'I': 0, 'D': 0, 'V': 0, 'total': 0
                        }
                        await device_manager.broadcast({
                            'type': 'device_update',
                            'data': device_manager.devices[device_id].to_dict()
                        })

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        device_manager.clients.discard(ws)
        print(f"Client disconnected. Total: {len(device_manager.clients)}")

    return ws


async def api_devices_handler(request):
    """GET /api/devices - List all devices"""
    return web.json_response(device_manager.get_all_devices())


async def api_scan_handler(request):
    """POST /api/devices/scan - Scan network"""
    devices = await device_manager.scan_network()
    return web.json_response(devices)


# Embedded HTML/CSS/JS
HTML_PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unity Logcat Viewer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --border-color: #30363d;
        }

        body {
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
        }

        .log-container {
            height: calc(100vh - 220px);
            overflow-y: auto;
        }

        .log-line {
            border-bottom: 1px solid var(--border-color);
            padding: 4px 8px;
            font-size: 12px;
            display: flex;
            gap: 8px;
            align-items: flex-start;
        }

        .log-line:hover {
            background: var(--bg-tertiary);
        }

        .log-line.error {
            background: rgba(248, 81, 73, 0.15);
            border-left: 3px solid #f85149;
        }

        .log-line.warning {
            background: rgba(210, 153, 34, 0.1);
            border-left: 3px solid #d29922;
        }

        .level-badge {
            font-size: 10px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
            min-width: 20px;
            text-align: center;
        }

        .level-E { background: #f85149; color: white; }
        .level-W { background: #d29922; color: black; }
        .level-I { background: #238636; color: white; }
        .level-D { background: #388bfd; color: white; }
        .level-V { background: #6e7681; color: white; }

        .tag {
            color: #a371f7;
            font-weight: 500;
            min-width: 150px;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .timestamp {
            color: var(--text-secondary);
            font-size: 11px;
            min-width: 85px;
        }

        .message {
            flex: 1;
            word-break: break-word;
        }

        .message .highlight {
            background: #634d00;
            color: #ffdf5d;
            padding: 0 2px;
            border-radius: 2px;
        }

        .device-badge {
            font-size: 9px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
            color: white;
            min-width: 30px;
            text-align: center;
        }

        .category-quantum { color: #3fb950; }
        .category-vivox { color: #58a6ff; }
        .category-network { color: #f0883e; }
        .category-analytics { color: #a371f7; }
        .category-camera { color: #56d4dd; }
        .category-player { color: #f9c513; }

        .filter-btn, .tab-btn {
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.15s;
            border: 1px solid var(--border-color);
            background: var(--bg-secondary);
            cursor: pointer;
        }

        .filter-btn:hover, .tab-btn:hover {
            background: var(--bg-tertiary);
        }

        .filter-btn.active, .tab-btn.active {
            background: #238636;
            border-color: #238636;
            color: white;
        }

        input[type="text"] {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 6px 12px;
            color: var(--text-primary);
            font-size: 13px;
        }

        input[type="text"]:focus {
            outline: none;
            border-color: #388bfd;
            box-shadow: 0 0 0 3px rgba(56, 139, 253, 0.3);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .status-dot.online {
            background: #3fb950;
            animation: pulse 2s infinite;
        }

        .status-dot.offline {
            background: #6e7681;
        }

        .status-dot.connecting {
            background: #d29922;
            animation: pulse 0.5s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .device-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 12px;
            cursor: pointer;
            transition: all 0.15s;
        }

        .device-card:hover {
            border-color: #388bfd;
        }

        .device-card.selected {
            border-color: #238636;
            background: rgba(35, 134, 54, 0.1);
        }

        .modal {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }

        .modal-content {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }

        .stats-bar {
            background: var(--bg-secondary);
            border-top: 1px solid var(--border-color);
        }

        #log-output::-webkit-scrollbar {
            width: 8px;
        }

        #log-output::-webkit-scrollbar-track {
            background: var(--bg-secondary);
        }

        #log-output::-webkit-scrollbar-thumb {
            background: var(--border-color);
            border-radius: 4px;
        }

        #log-output::-webkit-scrollbar-thumb:hover {
            background: #484f58;
        }

        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: var(--text-secondary);
        }
    </style>
</head>
<body class="h-screen flex flex-col">
    <!-- Header -->
    <header class="bg-[#161b22] border-b border-[#30363d] px-4 py-3">
        <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
                <h1 class="text-lg font-semibold">Unity Logcat Viewer</h1>
                <span class="text-xs text-[#8b949e]">Multi-Device</span>
            </div>
            <div class="flex items-center gap-2">
                <button id="btn-scan" class="filter-btn">Scan Network</button>
                <button id="btn-add" class="filter-btn">Add Device</button>
                <button id="btn-usb" class="filter-btn">USB Setup</button>
            </div>
        </div>
    </header>

    <!-- Device Bar -->
    <div id="device-bar" class="bg-[#161b22] border-b border-[#30363d] px-4 py-2">
        <div class="flex items-center gap-2 overflow-x-auto">
            <button class="tab-btn active" data-device="all">All Devices</button>
            <div id="device-tabs" class="flex items-center gap-2"></div>
        </div>
    </div>

    <!-- Filters -->
    <div class="bg-[#161b22] border-b border-[#30363d] px-4 py-2">
        <div class="flex flex-wrap items-center gap-3">
            <!-- Search -->
            <div class="flex-1 min-w-[200px] max-w-md">
                <input type="text" id="search-input" placeholder="Search logs... (Ctrl+K)" class="w-full">
            </div>

            <!-- Level filters -->
            <div class="flex items-center gap-1">
                <span class="text-xs text-[#8b949e] mr-1">Level:</span>
                <button class="filter-btn level-filter" data-level="V">V</button>
                <button class="filter-btn level-filter" data-level="D">D</button>
                <button class="filter-btn level-filter active" data-level="I">I</button>
                <button class="filter-btn level-filter" data-level="W">W</button>
                <button class="filter-btn level-filter" data-level="E">E</button>
            </div>

            <!-- Actions -->
            <div class="flex items-center gap-2">
                <button id="btn-clear" class="filter-btn">Clear</button>
                <button id="btn-pause" class="filter-btn">Pause</button>
                <button id="btn-export" class="filter-btn">Export</button>
            </div>
        </div>
    </div>

    <!-- Log output -->
    <div id="log-output" class="log-container flex-1 overflow-y-auto">
        <div id="log-content"></div>
        <div id="empty-state" class="empty-state">
            <svg class="w-16 h-16 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
            </svg>
            <p class="text-lg mb-2">No devices connected</p>
            <p class="text-sm">Click "Scan Network" or "Add Device" to get started</p>
        </div>
    </div>

    <!-- Stats bar -->
    <footer class="stats-bar px-4 py-2 flex items-center justify-between text-xs">
        <div class="flex items-center gap-4">
            <span>Total: <strong id="stat-total">0</strong></span>
            <span class="text-[#f85149]">Errors: <strong id="stat-errors">0</strong></span>
            <span class="text-[#d29922]">Warnings: <strong id="stat-warnings">0</strong></span>
            <span class="text-[#3fb950]">Info: <strong id="stat-info">0</strong></span>
        </div>
        <div class="flex items-center gap-4 text-[#8b949e]">
            <span id="device-count">0 devices</span>
            <span><span id="logs-per-sec">0</span> logs/sec</span>
        </div>
    </footer>

    <!-- Modals -->
    <div id="modal-container"></div>

    <script>
        // State
        let devices = {};
        let logs = [];
        let filteredLogs = [];
        let isPaused = false;
        let ws = null;
        let reconnectTimer = null;
        let logsLastSecond = 0;
        let minLevel = 'I';
        let activeDevice = 'all';
        let searchTerm = '';

        const levelPriority = { V: 0, D: 1, I: 2, W: 3, E: 4 };

        // DOM elements
        const logOutput = document.getElementById('log-output');
        const logContent = document.getElementById('log-content');
        const emptyState = document.getElementById('empty-state');
        const deviceTabs = document.getElementById('device-tabs');
        const searchInput = document.getElementById('search-input');
        const modalContainer = document.getElementById('modal-container');

        // Connect WebSocket
        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            ws.onopen = () => {
                console.log('WebSocket connected');
            };

            ws.onclose = () => {
                console.log('WebSocket disconnected, reconnecting...');
                reconnectTimer = setTimeout(connect, 2000);
            };

            ws.onerror = () => ws.close();

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                handleMessage(msg);
            };
        }

        function handleMessage(msg) {
            switch (msg.type) {
                case 'device_list':
                    msg.data.forEach(d => {
                        devices[d.id] = d;
                    });
                    renderDeviceTabs();
                    updateDeviceCount();
                    break;
                case 'device_added':
                case 'device_update':
                    devices[msg.data.id] = msg.data;
                    renderDeviceTabs();
                    updateDeviceCount();
                    break;
                case 'device_removed':
                    delete devices[msg.data.id];
                    renderDeviceTabs();
                    updateDeviceCount();
                    break;
                case 'log':
                    handleLog(msg.data);
                    break;
                case 'scan_status':
                    if (msg.data.status === 'scanning') {
                        showToast(`Scanning ${msg.data.subnet}.0/24...`);
                    }
                    break;
                case 'scan_result':
                    showScanResults(msg.data.devices);
                    break;
                case 'usb_devices':
                    showUsbDevices(msg.data);
                    break;
                case 'wifi_enabled':
                    if (msg.data.success) {
                        showToast(`WiFi ADB enabled! Device IP: ${msg.data.ip}`);
                        // Auto-add the device
                        ws.send(JSON.stringify({ action: 'add_device', device_id: msg.data.device_id }));
                        setTimeout(() => {
                            ws.send(JSON.stringify({ action: 'connect', device_id: msg.data.device_id }));
                        }, 1000);
                    } else {
                        showToast(`Error: ${msg.data.error}`, 'error');
                    }
                    break;
            }
        }

        function handleLog(log) {
            logs.push(log);
            logsLastSecond++;

            if (logs.length > 10000) {
                logs = logs.slice(-8000);
            }

            if (shouldShow(log)) {
                filteredLogs.push(log);
                if (!isPaused) {
                    appendLogLine(log);
                    scrollToBottom();
                }
            }

            updateStats();
            emptyState.style.display = 'none';
        }

        function shouldShow(log) {
            if (levelPriority[log.level] < levelPriority[minLevel]) return false;
            if (activeDevice !== 'all' && log.device_id !== activeDevice) return false;
            if (searchTerm && !log.message.toLowerCase().includes(searchTerm) &&
                !log.tag.toLowerCase().includes(searchTerm)) return false;
            return true;
        }

        function appendLogLine(log) {
            const div = document.createElement('div');
            div.className = `log-line ${log.level === 'E' ? 'error' : ''} ${log.level === 'W' ? 'warning' : ''}`;

            const categoryClass = log.category ? `category-${log.category}` : '';
            let message = escapeHtml(log.message);
            if (searchTerm) {
                const regex = new RegExp(`(${escapeRegex(searchTerm)})`, 'gi');
                message = message.replace(regex, '<span class="highlight">$1</span>');
            }

            const showDeviceBadge = activeDevice === 'all' && Object.keys(devices).length > 1;
            const deviceBadge = showDeviceBadge ?
                `<span class="device-badge" style="background: ${log.device_color}">${getDeviceShortName(log.device_name)}</span>` : '';

            div.innerHTML = `
                ${deviceBadge}
                <span class="timestamp">${log.timestamp.split(' ')[1]}</span>
                <span class="level-badge level-${log.level}">${log.level}</span>
                <span class="tag ${categoryClass}">[${escapeHtml(log.tag)}]</span>
                <span class="message">${message}</span>
            `;

            logContent.appendChild(div);
        }

        function getDeviceShortName(name) {
            if (!name) return '??';
            const words = name.split(' ');
            if (words.length >= 2) {
                return words.map(w => w[0]).join('').substring(0, 3).toUpperCase();
            }
            return name.substring(0, 3).toUpperCase();
        }

        function scrollToBottom() {
            logOutput.scrollTop = logOutput.scrollHeight;
        }

        function updateStats() {
            let total = 0, errors = 0, warnings = 0, info = 0;

            for (const log of filteredLogs) {
                total++;
                if (log.level === 'E') errors++;
                else if (log.level === 'W') warnings++;
                else if (log.level === 'I') info++;
            }

            document.getElementById('stat-total').textContent = total;
            document.getElementById('stat-errors').textContent = errors;
            document.getElementById('stat-warnings').textContent = warnings;
            document.getElementById('stat-info').textContent = info;
        }

        function updateDeviceCount() {
            const online = Object.values(devices).filter(d => d.status === 'online').length;
            const total = Object.keys(devices).length;
            document.getElementById('device-count').textContent =
                `${online}/${total} device${total !== 1 ? 's' : ''}`;
        }

        function renderDeviceTabs() {
            deviceTabs.innerHTML = '';

            for (const [id, device] of Object.entries(devices)) {
                const btn = document.createElement('button');
                btn.className = `tab-btn flex items-center gap-2 ${activeDevice === id ? 'active' : ''}`;
                btn.dataset.device = id;
                btn.innerHTML = `
                    <span class="status-dot ${device.status}"></span>
                    <span>${device.nickname || device.name}</span>
                    ${device.stats.E > 0 ? `<span class="text-[#f85149] text-xs">${device.stats.E}</span>` : ''}
                `;
                btn.onclick = () => selectDevice(id);

                // Right-click for context menu
                btn.oncontextmenu = (e) => {
                    e.preventDefault();
                    showDeviceMenu(id, e);
                };

                deviceTabs.appendChild(btn);
            }
        }

        function selectDevice(deviceId) {
            activeDevice = deviceId;

            // Update tab buttons
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.device === deviceId);
            });

            refilter();
        }

        function refilter() {
            filteredLogs = logs.filter(shouldShow);
            logContent.innerHTML = '';
            filteredLogs.slice(-500).forEach(appendLogLine);
            scrollToBottom();
            updateStats();
        }

        function showDeviceMenu(deviceId, event) {
            const device = devices[deviceId];
            if (!device) return;

            const menu = document.createElement('div');
            menu.className = 'fixed bg-[#161b22] border border-[#30363d] rounded-lg shadow-xl py-2 z-50';
            menu.style.left = `${event.clientX}px`;
            menu.style.top = `${event.clientY}px`;

            const items = [
                { label: device.status === 'online' ? 'Disconnect' : 'Connect', action: () => {
                    ws.send(JSON.stringify({
                        action: device.status === 'online' ? 'disconnect' : 'connect',
                        device_id: deviceId
                    }));
                }},
                { label: 'Rename', action: () => {
                    const name = prompt('Enter nickname:', device.nickname || device.name);
                    if (name !== null) {
                        ws.send(JSON.stringify({ action: 'set_nickname', device_id: deviceId, nickname: name }));
                    }
                }},
                { label: 'Clear Stats', action: () => {
                    ws.send(JSON.stringify({ action: 'clear_stats', device_id: deviceId }));
                }},
                { label: 'Remove', action: () => {
                    if (confirm(`Remove ${device.nickname || device.name}?`)) {
                        ws.send(JSON.stringify({ action: 'remove', device_id: deviceId }));
                    }
                }, danger: true }
            ];

            items.forEach(item => {
                const btn = document.createElement('button');
                btn.className = `w-full text-left px-4 py-2 hover:bg-[#21262d] ${item.danger ? 'text-[#f85149]' : ''}`;
                btn.textContent = item.label;
                btn.onclick = () => {
                    item.action();
                    menu.remove();
                };
                menu.appendChild(btn);
            });

            document.body.appendChild(menu);

            const closeMenu = (e) => {
                if (!menu.contains(e.target)) {
                    menu.remove();
                    document.removeEventListener('click', closeMenu);
                }
            };
            setTimeout(() => document.addEventListener('click', closeMenu), 0);
        }

        function showModal(title, content) {
            modalContainer.innerHTML = `
                <div class="modal" onclick="if(event.target===this)closeModal()">
                    <div class="modal-content">
                        <div class="flex justify-between items-center mb-4">
                            <h2 class="text-lg font-semibold">${title}</h2>
                            <button onclick="closeModal()" class="text-[#8b949e] hover:text-white">&times;</button>
                        </div>
                        <div id="modal-body">${content}</div>
                    </div>
                </div>
            `;
        }

        function closeModal() {
            modalContainer.innerHTML = '';
        }

        function showToast(message, type = 'info') {
            const toast = document.createElement('div');
            toast.className = `fixed bottom-20 right-4 px-4 py-2 rounded-lg ${
                type === 'error' ? 'bg-[#f85149]' : 'bg-[#238636]'
            } text-white z-50`;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }

        function showScanResults(foundDevices) {
            if (foundDevices.length === 0) {
                showToast('No devices found with ADB enabled');
                return;
            }

            const content = `
                <p class="text-sm text-[#8b949e] mb-4">Found ${foundDevices.length} device(s) with port 5555 open:</p>
                <div class="space-y-2">
                    ${foundDevices.map(d => `
                        <div class="flex items-center justify-between p-3 bg-[#21262d] rounded-lg">
                            <span>${d.ip}</span>
                            ${d.known ?
                                '<span class="text-xs text-[#8b949e]">Already added</span>' :
                                `<button onclick="addAndConnect('${d.id}')" class="filter-btn">Add & Connect</button>`
                            }
                        </div>
                    `).join('')}
                </div>
            `;
            showModal('Scan Results', content);
        }

        function addAndConnect(deviceId) {
            ws.send(JSON.stringify({ action: 'add_device', device_id: deviceId }));
            setTimeout(() => {
                ws.send(JSON.stringify({ action: 'connect', device_id: deviceId }));
            }, 500);
            closeModal();
        }

        function showUsbDevices(usbDevices) {
            if (usbDevices.length === 0) {
                showModal('USB Setup', `
                    <p class="text-[#8b949e]">No USB devices found.</p>
                    <p class="text-sm text-[#8b949e] mt-2">Connect your Quest via USB and enable USB debugging.</p>
                `);
                return;
            }

            const content = `
                <p class="text-sm text-[#8b949e] mb-4">Enable WiFi ADB on these USB-connected devices:</p>
                <div class="space-y-2">
                    ${usbDevices.map(d => `
                        <div class="flex items-center justify-between p-3 bg-[#21262d] rounded-lg">
                            <span>${d.id}</span>
                            <button onclick="enableWifi('${d.id}')" class="filter-btn">Enable WiFi ADB</button>
                        </div>
                    `).join('')}
                </div>
                <p class="text-xs text-[#8b949e] mt-4">This will run "adb tcpip 5555" and auto-connect via WiFi.</p>
            `;
            showModal('USB Setup', content);
        }

        function enableWifi(deviceId) {
            ws.send(JSON.stringify({ action: 'enable_wifi', device_id: deviceId }));
            closeModal();
            showToast('Enabling WiFi ADB...');
        }

        function showAddDeviceDialog() {
            showModal('Add Device', `
                <p class="text-sm text-[#8b949e] mb-4">Enter the IP address of the device:</p>
                <input type="text" id="add-device-ip" placeholder="192.168.1.100" class="w-full mb-4">
                <div class="flex justify-end gap-2">
                    <button onclick="closeModal()" class="filter-btn">Cancel</button>
                    <button onclick="addManualDevice()" class="filter-btn active">Add</button>
                </div>
            `);
            document.getElementById('add-device-ip').focus();
        }

        function addManualDevice() {
            const ip = document.getElementById('add-device-ip').value.trim();
            if (ip) {
                ws.send(JSON.stringify({ action: 'add_device', device_id: ip }));
                setTimeout(() => {
                    ws.send(JSON.stringify({ action: 'connect', device_id: ip.includes(':') ? ip : `${ip}:5555` }));
                }, 500);
                closeModal();
            }
        }

        function escapeHtml(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        function escapeRegex(str) {
            return str.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
        }

        // Event listeners
        document.getElementById('btn-scan').onclick = () => {
            ws.send(JSON.stringify({ action: 'scan' }));
        };

        document.getElementById('btn-add').onclick = showAddDeviceDialog;

        document.getElementById('btn-usb').onclick = () => {
            ws.send(JSON.stringify({ action: 'get_usb_devices' }));
        };

        document.getElementById('btn-clear').onclick = () => {
            logs = [];
            filteredLogs = [];
            logContent.innerHTML = '';
            updateStats();
        };

        document.getElementById('btn-pause').onclick = (e) => {
            isPaused = !isPaused;
            e.target.textContent = isPaused ? 'Resume' : 'Pause';
            e.target.classList.toggle('active', isPaused);
            if (!isPaused) refilter();
        };

        document.getElementById('btn-export').onclick = () => {
            const text = filteredLogs.map(l => `[${l.device_name}] ${l.raw}`).join('\\n');
            const blob = new Blob([text], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `logcat-${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.txt`;
            a.click();
            URL.revokeObjectURL(url);
        };

        document.querySelector('[data-device="all"]').onclick = () => selectDevice('all');

        // Level filter buttons
        document.querySelectorAll('.level-filter').forEach(btn => {
            btn.onclick = () => {
                document.querySelectorAll('.level-filter').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                minLevel = btn.dataset.level;
                refilter();
            };
        });

        // Search
        let searchTimeout;
        searchInput.oninput = (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                searchTerm = e.target.value.toLowerCase();
                refilter();
            }, 150);
        };

        // Keyboard shortcuts
        document.onkeydown = (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                searchInput.focus();
                searchInput.select();
            }
            if (e.key === ' ' && document.activeElement !== searchInput) {
                e.preventDefault();
                document.getElementById('btn-pause').click();
            }
            if (e.key === 'Escape') {
                closeModal();
            }
        };

        // Logs per second counter
        setInterval(() => {
            document.getElementById('logs-per-sec').textContent = logsLastSecond;
            logsLastSecond = 0;
        }, 1000);

        // Start
        connect();
    </script>
</body>
</html>
'''


async def on_startup(app):
    """Initialize on startup"""
    await device_manager.load_config()

    # Auto-connect to known devices
    for device_id in list(device_manager.devices.keys()):
        asyncio.create_task(device_manager.connect_device(device_id))


async def on_cleanup(app):
    """Clean up on shutdown"""
    # Disconnect all devices
    for device_id in list(device_manager.devices.keys()):
        await device_manager.disconnect_device(device_id)

    # Save config
    device_manager.save_config()


def main():
    app = web.Application()
    app.router.add_get('/', index_handler)
    app.router.add_get('/ws', websocket_handler)
    app.router.add_get('/api/devices', api_devices_handler)
    app.router.add_post('/api/devices/scan', api_scan_handler)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # Open browser after a short delay
    def open_browser():
        webbrowser.open(f'http://localhost:{PORT}')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.call_later(1.5, open_browser)

    local_ip = get_local_ip()

    print(f"""
╔═══════════════════════════════════════════════════════════╗
║       Unity Logcat Web Viewer - Multi-Device Edition      ║
╠═══════════════════════════════════════════════════════════╣
║  Local:   http://localhost:{PORT}                           ║
║  Network: http://{local_ip}:{PORT}                       ║
║                                                           ║
║  Opening browser automatically...                         ║
║                                                           ║
║  Features:                                                ║
║    • Multi-device support over WiFi                       ║
║    • Network scanner to discover devices                  ║
║    • USB setup helper (adb tcpip 5555)                    ║
║    • Per-device and combined log views                    ║
║                                                           ║
║  Keyboard shortcuts:                                      ║
║    Ctrl+K  - Focus search                                 ║
║    Space   - Pause/Resume                                 ║
║                                                           ║
║  Press Ctrl+C to stop                                     ║
╚═══════════════════════════════════════════════════════════╝
""")

    web.run_app(app, host=HOST, port=PORT, print=None)


if __name__ == '__main__':
    main()
