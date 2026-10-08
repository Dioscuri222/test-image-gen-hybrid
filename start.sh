#!/bin/bash
# Quick start script for local development

set -e

echo "=== Image Generation Hybrid Prototype ==="

# 1. Start backend server
echo ""
echo "1. Starting local backend server..."
echo "   Run: python backend/server.py"
echo "   Then get API key at: http://localhost:8000/api/key"

# 2. Create tunnel
echo ""
echo "2. Create a tunnel (choose one):"
echo "   Option A - ngrok:"
echo "     ngrok http 8000"
echo ""
echo "   Option B - cloudflared (already installed):"
echo "     cloudflared tunnel --url http://localhost:8000"

echo ""
echo "3. Update frontend config:"
echo "   Edit frontend/app.py and set TUNNEL_URL variable"
echo "   Or add environment variable in Hugging Face Space settings"

echo ""
echo "4. For Hugging Face Space deployment:"
echo "   - Use frontend/main.py as app.py in your Space"
echo "   - Set main_function=None to use default launch()"

echo ""
echo "5. Test locally:"
echo "   python test_local.py"

echo ""
echo "=== Done ==="