#!/bin/bash
#
# Unity Logcat Viewer - Mac Installer
# Installs Python 3, ADB, and dependencies automatically
#

set -e

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║     Unity Logcat Viewer - Mac Installer               ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "${YELLOW}○${NC} $1 not found"
        return 1
    fi
}

# Check for Homebrew
echo "Checking dependencies..."
echo ""

if ! check_command brew; then
    echo ""
    echo -e "${YELLOW}Installing Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi

# Check for Python 3
if ! check_command python3; then
    echo ""
    echo -e "${YELLOW}Installing Python 3...${NC}"
    brew install python3
fi

# Check for ADB
if ! check_command adb; then
    echo ""
    echo -e "${YELLOW}Installing Android Platform Tools (ADB)...${NC}"
    brew install --cask android-platform-tools
fi

# Install Python dependencies
echo ""
echo -e "${YELLOW}Installing Python dependencies...${NC}"
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet aiohttp

echo ""
echo -e "${GREEN}✓ All dependencies installed!${NC}"
echo ""

# Create launcher script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cat > "$SCRIPT_DIR/run.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/logcat-web.py"
EOF

chmod +x "$SCRIPT_DIR/run.sh"

# Create .command file for double-click launching
cat > "$SCRIPT_DIR/Unity Logcat Viewer.command" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 logcat-web.py
EOF

chmod +x "$SCRIPT_DIR/Unity Logcat Viewer.command"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║                 Installation Complete!                ║"
echo "╠═══════════════════════════════════════════════════════╣"
echo "║                                                       ║"
echo "║  To run the viewer:                                   ║"
echo "║                                                       ║"
echo "║  Option 1: Double-click 'Unity Logcat Viewer.command' ║"
echo "║                                                       ║"
echo "║  Option 2: Run in terminal:                           ║"
echo "║            ./run.sh                                   ║"
echo "║                                                       ║"
echo "║  Option 3: Run directly:                              ║"
echo "║            python3 logcat-web.py                      ║"
echo "║                                                       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Ask if user wants to run now
read -p "Do you want to run the viewer now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 "$SCRIPT_DIR/logcat-web.py"
fi
