#!/bin/bash
# OSIN CHAIN QUEBEC ULTIMATE - Installer - Ghost1o1
set -e
TARGET="${1:-/root/supreme}"
echo "[*] Installing OSIN CHAIN QUEBEC ULTIMATE to $TARGET"
mkdir -p "$TARGET"
cp -r . "$TARGET/"
chmod +x "$TARGET/main.py"
echo "[*] Installing Python deps..."
pip3 install --break-system-packages -r "$TARGET/requirements.txt" 2>&1 | tail -3 || \
pip3 install -r "$TARGET/requirements.txt" 2>&1 | tail -3
echo "[OK] Install done. Run: cd $TARGET && python3 main.py"
echo "[OK] Then open http://localhost:8000"
