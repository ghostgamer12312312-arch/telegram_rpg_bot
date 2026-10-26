#!/bin/sh
# =============================================================
# Dragon Ball RPG Bot — Startup Script
# =============================================================
# Usage:
#   ./start.sh                       run in foreground
#   nohup ./start.sh > bot.log 2>&1 &   run in background
# =============================================================

cd "$(dirname "$0")" || {
    echo "❌ Could not cd to script directory"
    exit 1
}

# --- Check .env exists ---
if [ ! -f .env ]; then
    echo "❌ No .env file found."
    echo ""
    echo "Create one with:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# --- Load .env ---
set -a
. ./.env
set +a

# --- Validate ---
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ BOT_TOKEN is not set in .env"
    exit 1
fi

if [ -z "$OWNER_ID" ]; then
    echo "⚠️  OWNER_ID not set — admin commands will be disabled."
fi

# --- Check required Python files ---
MISSING=""
for f in bot.py game_data.py db.py combat.py clans.py; do
    [ ! -f "$f" ] && MISSING="$MISSING $f"
done
if [ -n "$MISSING" ]; then
    echo "❌ Missing required files:$MISSING"
    exit 1
fi

# --- Check Python ---
if ! command -v python >/dev/null 2>&1; then
    echo "❌ Python not found. Install: pkg install python -y"
    exit 1
fi

# --- Check python-telegram-bot ---
if ! python -c "import telegram" 2>/dev/null; then
    echo "❌ python-telegram-bot is not installed."
    echo "   Run: pip install -r requirements.txt"
    exit 1
fi

# --- Launch ---
echo "🚀 Starting Dragon Ball RPG Bot..."
echo "   Folder: $(pwd)"
echo "   Owner ID: ${OWNER_ID:-not set}"
echo ""
exec python bot.py
