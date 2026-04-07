#!/data/data/com.termux/files/usr/bin/bash
# Termux setup script for dexcom_g7_mcp_server
set -e

echo "==> Updating Termux packages..."
pkg upgrade -y

echo "==> Installing Python and git..."
pkg install -y python git

echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup complete. Run the server with:"
echo ""
echo "  DEXCOM_USERNAME='your-username' \\"
echo "  DEXCOM_PASSWORD='your-password' \\"
echo "  DEXCOM_REGION='us' \\"
echo "  python server.py"
echo ""
echo "The server will listen on http://localhost:8007"
