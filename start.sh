#!/bin/sh
# Starts the bot. Reads your settings from the .env file.
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  echo "No .env file yet. Run: cp .env.example .env   then fill it in (see README)."
  exit 1
fi
export $(grep -v '^#' .env | xargs)
python bot.py
