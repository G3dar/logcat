#!/usr/bin/env python3
"""
Unity Logcat Web Viewer
A beautiful, cross-platform web-based logcat viewer for Unity/Meta Quest development.

Usage:
    python3 logcat-web.py

Opens http://localhost:8765 in your browser with a full-featured log viewer.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import webbrowser
from datetime import datetime

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

# Connected WebSocket clients
clients = set()
stats = {'E': 0, 'W': 0, 'I': 0, 'D': 0, 'V': 0, 'total': 0}


def parse_log_line(line):
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

    # Update stats
    stats[level] = stats.get(level, 0) + 1
    stats['total'] += 1

    return {
        'timestamp': timestamp,
        'level': level,
        'tag': unity_tag or tag,
        'message': clean_message,
        'category': category,
        'raw': line
    }


async def logcat_reader():
    """Read from adb logcat and broadcast to all clients"""
    while True:
        try:
            print("Starting adb logcat...")
            process = await asyncio.create_subprocess_exec(
                'adb', 'logcat', '-s', 'Unity:V',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                line = line.decode('utf-8', errors='replace')
                parsed = parse_log_line(line)

                if parsed and clients:
                    message = json.dumps({'type': 'log', 'data': parsed})
                    await asyncio.gather(
                        *[client.send_str(message) for client in clients],
                        return_exceptions=True
                    )

            print("adb logcat ended, restarting in 2 seconds...")
            await asyncio.sleep(2)

        except Exception as e:
            print(f"Error in logcat reader: {e}")
            await asyncio.sleep(2)


async def websocket_handler(request):
    """Handle WebSocket connections"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    clients.add(ws)
    print(f"Client connected. Total: {len(clients)}")

    # Send current stats
    await ws.send_str(json.dumps({'type': 'stats', 'data': stats}))

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get('action') == 'get_stats':
                    await ws.send_str(json.dumps({'type': 'stats', 'data': stats}))
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        clients.discard(ws)
        print(f"Client disconnected. Total: {len(clients)}")

    return ws


async def index_handler(request):
    """Serve the HTML page"""
    return web.Response(text=HTML_PAGE, content_type='text/html')


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
            height: calc(100vh - 180px);
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
            min-width: 100px;
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

        .category-quantum { color: #3fb950; }
        .category-vivox { color: #58a6ff; }
        .category-network { color: #f0883e; }
        .category-analytics { color: #a371f7; }
        .category-camera { color: #56d4dd; }
        .category-player { color: #f9c513; }

        .filter-btn {
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.15s;
            border: 1px solid var(--border-color);
            background: var(--bg-secondary);
        }

        .filter-btn:hover {
            background: var(--bg-tertiary);
        }

        .filter-btn.active {
            background: #238636;
            border-color: #238636;
            color: white;
        }

        .filter-btn.active-error {
            background: #f85149;
            border-color: #f85149;
        }

        .filter-btn.active-warning {
            background: #d29922;
            border-color: #d29922;
            color: black;
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
            animation: pulse 2s infinite;
        }

        .status-dot.connected {
            background: #3fb950;
        }

        .status-dot.disconnected {
            background: #f85149;
            animation: none;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
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
    </style>
</head>
<body class="h-screen flex flex-col">
    <!-- Header -->
    <header class="bg-[#161b22] border-b border-[#30363d] px-4 py-3">
        <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
                <h1 class="text-lg font-semibold">Unity Logcat Viewer</h1>
                <div class="flex items-center gap-2">
                    <div id="status-dot" class="status-dot disconnected"></div>
                    <span id="status-text" class="text-xs text-[#8b949e]">Connecting...</span>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <button id="btn-clear" class="filter-btn">Clear</button>
                <button id="btn-pause" class="filter-btn">Pause</button>
                <button id="btn-export" class="filter-btn">Export</button>
            </div>
        </div>
    </header>

    <!-- Filters -->
    <div class="bg-[#161b22] border-b border-[#30363d] px-4 py-2">
        <div class="flex flex-wrap items-center gap-3">
            <!-- Search -->
            <div class="flex-1 min-w-[200px] max-w-md">
                <input type="text" id="search-input" placeholder="Search logs... (Ctrl+K)"
                       class="w-full">
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

            <!-- Category filters -->
            <div class="flex items-center gap-1">
                <span class="text-xs text-[#8b949e] mr-1">Show:</span>
                <button class="filter-btn category-filter active" data-category="all">All</button>
                <button class="filter-btn category-filter" data-category="quantum">Quantum</button>
                <button class="filter-btn category-filter" data-category="vivox">Vivox</button>
                <button class="filter-btn category-filter" data-category="network">Network</button>
                <button class="filter-btn category-filter" data-category="analytics">Analytics</button>
            </div>

            <!-- Exclude -->
            <div class="flex items-center gap-2">
                <span class="text-xs text-[#8b949e]">Exclude:</span>
                <input type="text" id="exclude-input" placeholder="MoveNext, spam..."
                       class="w-40 text-xs">
            </div>
        </div>
    </div>

    <!-- Log output -->
    <div id="log-output" class="log-container flex-1 overflow-y-auto">
        <div id="log-content"></div>
    </div>

    <!-- Stats bar -->
    <footer class="stats-bar px-4 py-2 flex items-center justify-between text-xs">
        <div class="flex items-center gap-4">
            <span>Total: <strong id="stat-total">0</strong></span>
            <span class="text-[#f85149]">Errors: <strong id="stat-errors">0</strong></span>
            <span class="text-[#d29922]">Warnings: <strong id="stat-warnings">0</strong></span>
            <span class="text-[#3fb950]">Info: <strong id="stat-info">0</strong></span>
        </div>
        <div class="text-[#8b949e]">
            <span id="logs-per-sec">0</span> logs/sec
        </div>
    </footer>

    <script>
        // State
        let logs = [];
        let filteredLogs = [];
        let isPaused = false;
        let ws = null;
        let reconnectTimer = null;
        let logsLastSecond = 0;
        let minLevel = 'I';
        let selectedCategory = 'all';
        let searchTerm = '';
        let excludeTerms = [];

        const levelPriority = { V: 0, D: 1, I: 2, W: 3, E: 4 };

        // DOM elements
        const logOutput = document.getElementById('log-output');
        const logContent = document.getElementById('log-content');
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        const searchInput = document.getElementById('search-input');
        const excludeInput = document.getElementById('exclude-input');

        // Connect WebSocket
        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            ws.onopen = () => {
                statusDot.className = 'status-dot connected';
                statusText.textContent = 'Connected';
            };

            ws.onclose = () => {
                statusDot.className = 'status-dot disconnected';
                statusText.textContent = 'Disconnected - Reconnecting...';
                reconnectTimer = setTimeout(connect, 2000);
            };

            ws.onerror = () => {
                ws.close();
            };

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'log') {
                    handleLog(msg.data);
                } else if (msg.type === 'stats') {
                    updateStats(msg.data);
                }
            };
        }

        function handleLog(log) {
            logs.push(log);
            logsLastSecond++;

            // Keep only last 5000 logs in memory
            if (logs.length > 5000) {
                logs = logs.slice(-4000);
            }

            if (shouldShow(log)) {
                filteredLogs.push(log);
                if (!isPaused) {
                    appendLogLine(log);
                    scrollToBottom();
                }
            }

            updateStats({
                E: logs.filter(l => l.level === 'E').length,
                W: logs.filter(l => l.level === 'W').length,
                I: logs.filter(l => l.level === 'I').length,
                total: logs.length
            });
        }

        function shouldShow(log) {
            // Level filter
            if (levelPriority[log.level] < levelPriority[minLevel]) {
                return false;
            }

            // Category filter
            if (selectedCategory !== 'all' && log.category !== selectedCategory) {
                return false;
            }

            // Search filter
            if (searchTerm && !log.message.toLowerCase().includes(searchTerm) &&
                !log.tag.toLowerCase().includes(searchTerm)) {
                return false;
            }

            // Exclude filter
            const msgLower = log.message.toLowerCase();
            for (const term of excludeTerms) {
                if (msgLower.includes(term)) {
                    return false;
                }
            }

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

            div.innerHTML = `
                <span class="timestamp">${log.timestamp.split(' ')[1]}</span>
                <span class="level-badge level-${log.level}">${log.level}</span>
                <span class="tag ${categoryClass}">[${escapeHtml(log.tag)}]</span>
                <span class="message">${message}</span>
            `;

            logContent.appendChild(div);
        }

        function scrollToBottom() {
            logOutput.scrollTop = logOutput.scrollHeight;
        }

        function updateStats(stats) {
            document.getElementById('stat-total').textContent = stats.total || 0;
            document.getElementById('stat-errors').textContent = stats.E || 0;
            document.getElementById('stat-warnings').textContent = stats.W || 0;
            document.getElementById('stat-info').textContent = stats.I || 0;
        }

        function refilter() {
            filteredLogs = logs.filter(shouldShow);
            logContent.innerHTML = '';
            filteredLogs.slice(-500).forEach(appendLogLine);
            scrollToBottom();
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
        document.getElementById('btn-clear').addEventListener('click', () => {
            logs = [];
            filteredLogs = [];
            logContent.innerHTML = '';
            updateStats({ E: 0, W: 0, I: 0, total: 0 });
        });

        document.getElementById('btn-pause').addEventListener('click', (e) => {
            isPaused = !isPaused;
            e.target.textContent = isPaused ? 'Resume' : 'Pause';
            e.target.classList.toggle('active', isPaused);
            if (!isPaused) {
                refilter();
            }
        });

        document.getElementById('btn-export').addEventListener('click', () => {
            const text = filteredLogs.map(l => l.raw).join('\\n');
            const blob = new Blob([text], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `logcat-${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.txt`;
            a.click();
            URL.revokeObjectURL(url);
        });

        // Level filter buttons
        document.querySelectorAll('.level-filter').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.level-filter').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                minLevel = btn.dataset.level;
                refilter();
            });
        });

        // Category filter buttons
        document.querySelectorAll('.category-filter').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.category-filter').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                selectedCategory = btn.dataset.category;
                refilter();
            });
        });

        // Search input
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                searchTerm = e.target.value.toLowerCase();
                refilter();
            }, 150);
        });

        // Exclude input
        excludeInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                excludeTerms = e.target.value.toLowerCase().split(',').map(s => s.trim()).filter(Boolean);
                refilter();
            }, 150);
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                searchInput.focus();
                searchInput.select();
            }
            if (e.key === ' ' && document.activeElement !== searchInput && document.activeElement !== excludeInput) {
                e.preventDefault();
                document.getElementById('btn-pause').click();
            }
        });

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
    """Start the logcat reader when the server starts"""
    app['logcat_task'] = asyncio.create_task(logcat_reader())


async def on_cleanup(app):
    """Clean up on shutdown"""
    app['logcat_task'].cancel()
    try:
        await app['logcat_task']
    except asyncio.CancelledError:
        pass


def main():
    app = web.Application()
    app.router.add_get('/', index_handler)
    app.router.add_get('/ws', websocket_handler)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # Open browser after a short delay
    def open_browser():
        webbrowser.open(f'http://localhost:{PORT}')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.call_later(1.5, open_browser)

    print(f"""
╔═══════════════════════════════════════════════════════╗
║         Unity Logcat Web Viewer                       ║
╠═══════════════════════════════════════════════════════╣
║  Server running at: http://localhost:{PORT}             ║
║  Opening browser automatically...                     ║
║                                                       ║
║  Keyboard shortcuts:                                  ║
║    Ctrl+K  - Focus search                             ║
║    Space   - Pause/Resume                             ║
║                                                       ║
║  Press Ctrl+C to stop                                 ║
╚═══════════════════════════════════════════════════════╝
""")

    web.run_app(app, host=HOST, port=PORT, print=None)


if __name__ == '__main__':
    main()
