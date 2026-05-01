#!/bin/bash
set -e

echo "============================================"
echo "  Market Chart — One-Click Deploy"
echo "============================================"
echo ""

# Check conda
if ! command -v conda &> /dev/null; then
    echo "[ERROR] conda not found. Please install Miniconda first:"
    echo "  https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi
echo "[OK] conda found"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Create conda env if not exists
if ! conda info --envs 2>/dev/null | grep -q "^nasdaq "; then
    echo "[INFO] Creating conda environment 'nasdaq'..."
    conda create -n nasdaq python=3.12 -y
    echo "[OK] Environment 'nasdaq' created"
else
    echo "[OK] Environment 'nasdaq' already exists"
fi

# Install / update dependencies
echo "[INFO] Installing dependencies..."
conda run -n nasdaq pip install -r requirements.txt -q
echo "[OK] Dependencies installed"

# Launch browser (background, after a short delay)
sleep 2 && (xdg-open http://localhost:5000 2>/dev/null || open http://localhost:5000 2>/dev/null || echo "Please open http://localhost:5000 in your browser") &

# Start Flask
echo ""
echo "============================================"
echo "  Server running. Press Ctrl+C to stop."
echo "============================================"
conda run -n nasdaq python app/app.py
