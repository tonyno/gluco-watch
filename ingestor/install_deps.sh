#!/bin/bash
# Installation script for pystray on macOS with Python 3.9

set -e

echo "Installing dependencies for pystray on macOS..."
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Upgrade pip first
echo "Upgrading pip..."
python3 -m pip install --user --upgrade pip || echo "Warning: pip upgrade failed, continuing..."

# Try installing pyobjc-core 11.x first (compatible with Python 3.9)
echo ""
echo "Installing pyobjc-core 11.x (compatible with Python 3.9)..."
python3 -m pip install --user "pyobjc-core>=11.0,<12.0" --no-cache-dir || {
    echo "Failed to install pyobjc-core 11.x, trying alternative approach..."
    
    # Alternative: try installing pyobjc-core 10.x
    echo "Trying pyobjc-core 10.x..."
    python3 -m pip install --user "pyobjc-core>=10.0,<11.0" --no-cache-dir || {
        echo "Failed to install pyobjc-core 10.x"
        echo ""
        echo "ERROR: Could not install pyobjc-core."
        echo "Recommendation: Use Python 3.10+ or install via Homebrew:"
        echo "  brew install python@3.11"
        echo "  python3.11 -m pip install --user pystray pillow requests"
        exit 1
    }
}

# Install pystray and other dependencies
echo ""
echo "Installing pystray, pillow, and requests..."
python3 -m pip install --user pystray pillow requests --no-cache-dir

echo ""
echo "Installation complete!"
echo "You can now run: python3 test.py"
