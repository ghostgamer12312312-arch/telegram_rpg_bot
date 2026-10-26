# 🐉 Dragon Ball RPG Bot

A Telegram RPG bot with combat, gacha, clans, raids, quests, and achievements.

## Features
- ⚔️ Explore with 3-option patrol (Battle / Run / Info)
- 🧙 90 characters grouped by rarity (Omni → Common)
- 🎰 Gacha with 4 banners
- 🛒 6-category shop with bulk discounts
- 🧬 Metamoran fusion
- 🏰 Full 9-subcommand clan system with raids
- 🔱 World raid + summon bosses (persistent HP, 0 cooldown)
- 📋 Daily / weekly / monthly quests
- 🏆 22 achievements
- 🌍 6 planets with level gates

## Setup

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/telegram_rpg_bot.git
cd telegram_rpg_bot

# 2. Install deps
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
nano .env    # add BOT_TOKEN and OWNER_ID

# 4. Run
chmod +x start.sh
./start.sh
