#!/bin/bash
# setup.sh — Run this once to set up the entire project
set -e

echo "=== PR Review Agent Setup ==="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python $python_version found"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ Dependencies installed"

# Copy .env if it doesn't exist
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  Created .env from template."
    echo "    Edit .env and fill in GITHUB_TOKEN and GITHUB_WEBHOOK_SECRET before running."
else
    echo "✅ .env file already exists"
fi

# Check Ollama
echo ""
if command -v ollama &> /dev/null; then
    echo "✅ Ollama is installed"
    # Check if llama3.1 is pulled
    if ollama list 2>/dev/null | grep -q "llama3.1"; then
        echo "✅ llama3.1 model is ready"
    else
        echo "⬇️  Pulling llama3.1 model (this is a ~5GB download, please wait)..."
        ollama pull llama3.1
        echo "✅ llama3.1 model ready"
    fi
else
    echo "⚠️  Ollama not found. Install it from https://ollama.com/download"
    echo "   Then run: ollama pull llama3.1"
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env — add your GITHUB_TOKEN and GITHUB_WEBHOOK_SECRET"
echo "  2. Start Ollama: ollama serve"
echo "  3. Start the server: python -m app.main"
echo "  4. Start ngrok (new terminal): ngrok http 8000"
echo "  5. Add the ngrok URL as a webhook in your GitHub repo settings"
echo ""
