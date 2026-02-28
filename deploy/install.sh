#!/bin/bash
# TOPE Updater Installation Script
# Installs updater service and creates runtime directories

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Installation paths
INSTALL_DIR="/opt/tope/updater"
SERVICE_FILE="/etc/systemd/system/tope-updater.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}=== TOPE Updater Installation ===${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}ERROR: This script must be run as root${NC}"
  echo "Usage: sudo $0"
  exit 1
fi

# Install system dependencies
echo -e "${YELLOW}Installing system dependencies...${NC}"
apt-get install -y libsdl2-ttf-2.0-0 libsdl2-image-2.0-0
echo -e "${GREEN}✓ System dependencies installed${NC}"

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
  echo -e "${RED}ERROR: Python 3 is not installed${NC}"
  exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
REQUIRED_VERSION="3.11"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
  echo -e "${RED}ERROR: Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION OK${NC}"

# Create installation directory
echo -e "${YELLOW}Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
echo -e "${GREEN}✓ Created $INSTALL_DIR${NC}"

# Copy project files
echo -e "${YELLOW}Copying project files...${NC}"
cp -r "$PROJECT_ROOT/src" "$INSTALL_DIR/"
cp -r "$PROJECT_ROOT/requirements.txt" "$INSTALL_DIR/"
cp -r "$PROJECT_ROOT/pyproject.toml" "$INSTALL_DIR/"
echo -e "${GREEN}✓ Project files copied${NC}"

# Create virtual environment with uv
echo -e "${YELLOW}Setting up virtual environment...${NC}"
if ! command -v uv &> /dev/null; then
  echo -e "${YELLOW}Installing uv...${NC}"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

cd "$INSTALL_DIR"
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
deactivate
echo -e "${GREEN}✓ Virtual environment created${NC}"

# Create runtime directories
echo -e "${YELLOW}Creating runtime directories...${NC}"
mkdir -p "$INSTALL_DIR/tmp"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/backups"
chmod 0755 "$INSTALL_DIR/tmp"
chmod 0755 "$INSTALL_DIR/logs"
chmod 0755 "$INSTALL_DIR/backups"
echo -e "${GREEN}✓ Runtime directories created${NC}"

# Install systemd service
echo -e "${YELLOW}Installing systemd service...${NC}"
cp "$SCRIPT_DIR/tope-updater.service" "$SERVICE_FILE"
systemctl daemon-reload
echo -e "${GREEN}✓ Service installed${NC}"

# Set ownership
echo -e "${YELLOW}Setting ownership...${NC}"
chown -R root:root "$INSTALL_DIR"
echo -e "${GREEN}✓ Ownership set to root${NC}"

# Enable service (but don't start yet)
echo -e "${YELLOW}Enabling service...${NC}"
systemctl enable tope-updater.service
echo -e "${GREEN}✓ Service enabled (will start on boot)${NC}"

echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo ""
echo "Service status: $(systemctl is-enabled tope-updater.service)"
echo "Installation directory: $INSTALL_DIR"
echo ""
echo "To start the service now:"
echo "  sudo systemctl start tope-updater"
echo ""
echo "To check service status:"
echo "  sudo systemctl status tope-updater"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u tope-updater -f"
echo ""
