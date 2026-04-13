#!/usr/bin/env bash
# ============================================================
# FRIDAY AI ASSISTANT - One-command setup
# Run: chmod +x setup.sh && ./setup.sh
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}◈ FRIDAY AI ASSISTANT - Setup${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Check Python ───────────────────────────────────────────
echo -e "${CYAN}Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 not found. Please install Python 3.10+${NC}"
    exit 1
fi
PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}✓ Python ${PYTHON_VER}${NC}"

# ── Create virtual environment ────────────────────────────
echo -e "${CYAN}Creating virtual environment...${NC}"
python3 -m venv .venv
source .venv/bin/activate
echo -e "${GREEN}✓ Virtual environment created${NC}"

# ── Install dependencies ──────────────────────────────────
echo -e "${CYAN}Installing Python dependencies...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Dependencies installed${NC}"

# ── System deps (Linux) ───────────────────────────────────
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo -e "${CYAN}Checking system dependencies (Linux)...${NC}"

    # PortAudio for audio
    if ! dpkg -l | grep -q portaudio19-dev 2>/dev/null; then
        echo "  Installing portaudio..."
        sudo apt-get install -y portaudio19-dev python3-pyaudio -q 2>/dev/null || true
    fi

    # Tesseract for OCR
    if ! command -v tesseract &> /dev/null; then
        echo "  Installing tesseract..."
        sudo apt-get install -y tesseract-ocr -q 2>/dev/null || true
    fi

    # xdotool for window title
    if ! command -v xdotool &> /dev/null; then
        sudo apt-get install -y xdotool -q 2>/dev/null || true
    fi
    echo -e "${GREEN}✓ System dependencies checked${NC}"
fi

# ── Check Ollama ──────────────────────────────────────────
echo ""
echo -e "${CYAN}Checking Ollama...${NC}"
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}✓ Ollama installed${NC}"
    echo -e "${CYAN}Pulling Mistral model (this may take a few minutes)...${NC}"
    ollama pull mistral || echo -e "${YELLOW}⚠ Could not pull Mistral. Run: ollama pull mistral${NC}"
else
    echo -e "${YELLOW}⚠ Ollama not found${NC}"
    echo "  Install Ollama from: https://ollama.ai"
    echo "  Then run: ollama pull mistral"
fi

# ── Setup .env ────────────────────────────────────────────
echo ""
echo -e "${CYAN}Setting up config...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠ Created .env file - add ANTHROPIC_API_KEY if you have one${NC}"
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

# Create data dir
mkdir -p data

# ── Done ──────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}◈ Friday setup complete!${NC}"
echo ""
echo "  Run Friday:"
echo -e "    ${CYAN}source .venv/bin/activate${NC}"
echo -e "    ${CYAN}python main.py${NC}"
echo ""
echo "  Check status:"
echo -e "    ${CYAN}python main.py status${NC}"
echo ""
echo "  CLI mode (no mic/speaker needed):"
echo -e "    ${CYAN}python main.py --cli${NC}"
echo ""
echo -e "${YELLOW}Wake word: say 'Friday' to activate${NC}"
echo -e "${YELLOW}Hotkey: Ctrl+Shift+F${NC}"
echo ""
