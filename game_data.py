from __future__ import annotations

# =============================================================
# DRAGON BALL RPG — MASTER GAME DATA
# =============================================================
# SINGLE SOURCE OF TRUTH for all game data.
#
# Every constant here is referenced by:
#   • bot.py        — commands, subcommands, features
#   • db.py         — persistence, defaults, seeds
#   • combat.py     — battle sim, achievements, quests
#   • clans.py      — clan system, raids, perks
#
# If you want to rebalance, this is the ONLY file to edit.
#
# Sections:
#   1. Player defaults ............ /start, /profile
#   2. Planets & travel .......... /travel, /explore
#   3. NPCs & world bosses ....... /explore
#   4. Characters (90) ........... /gacha, /mycharacters, /equip, /fusion
#   5. Rarity constants .......... display
#   6. Gacha config .............. /gacha
#   7. Equipment ................. /shop, /buy, /inventory, /equip
#   8. Shop (55 items) ........... /shop, /buy
#   9. Skills (20) ............... /skills, /learn
#  10. Dragon balls .............. /wish
#  11. Summon bosses ............. /summon
#  12. Clan raids & perks ........ /clan
#  13. World raid ................ /raid, /raid_start, /raid_attack
#  14. Ranks & ascension ......... /rankup
#  15. Starter pack .............. /start
#  16. Fusion materials .......... /fusion
#  17. Healing ................... /heal
#  18. Achievements (22) ......... /achievements
#  19. Quests (12) ............... /quests, /claim_*
#  20. Reference tables .......... /help, /admin_help
# =============================================================


# -------------------------------------------------------------
# 1. PLAYER DEFAULTS
# -------------------------------------------------------------
# Used by: bot.cmd_start (starter bonuses), db.ensure_player
#          (starting resources implicitly full HP)
# -------------------------------------------------------------
STARTING_RESOURCES = {
    "yens":         500000,
    "gems":         20000,
    "crystals":     5555,
    "tickets":      130,
    "skill_points": 120,
    "keys_elite":   10,
    "keys_boss":    10,
    "exp":          0,
}

# EXP per level. Level = 1 + exp // LEVEL_EXP
# Used by: db.level_of, bot.player_stats, bot.cmd_travel
LEVEL_EXP = 100


# -------------------------------------------------------------
# 2. PLANETS & TRAVEL
# -------------------------------------------------------------
# Used by: /travel, /explore (multiplier), bot.cmd_travel,
#          clans.capture_planet, db.get_world_multiplier
# -------------------------------------------------------------
PLANETS = {
    "Earth": {
        "id": 1,
        "level_min": 1,
        "level_max": 20,
        "multiplier": 1.0,
        "desc": "Starter planet — balanced encounters for beginners.",
    },
    "Hell": {
        "id": 2,
        "level_min": 21,
        "level_max": 39,
        "multiplier": 2.0,
        "desc": "Underworld abyss — demonic foes yield 2x rewards.",
    },
    "Kai Planet": {
        "id": 3,
        "level_min": 40,
        "level_max": 59,
        "multiplier": 3.0,
        "desc": "North King Kai's sacred orb — 10x gravity, 3x rewards.",
    },
    "Supreme Kai Planet": {
        "id": 4,
        "level_min": 60,
        "level_max": 79,
        "multiplier": 4.0,
        "desc": "Holy sanctum of the Supreme Kais — 4x rewards.",
    },
    "Lord Beerus Planet": {
        "id": 5,
        "level_min": 80,
        "level_max": 99,
        "multiplier": 5.0,
        "desc": "Domain of Lord Beerus and Whis — God Ki, 5x rewards.",
    },
    "Omniverse": {
        "id": 6,
        "level_min": 100,
        "level_max": 999,
        "multiplier": 7.0,
        "desc": "Multiversal pinnacle — 7x rewards, ultimate challenge.",
    },
}

PLANET_ORDER = [
    "Earth", "Hell", "Kai Planet",
    "Supreme Kai Planet", "Lord Beerus Planet", "Omniverse",
]


# -------------------------------------------------------------
# 3. NPCs & WORLD BOSSES
# -------------------------------------------------------------
# NPCS: used by /explore (20 canonical NPCs, rand pick)
# BOSSES: used by /explore (world boss on 15-win streak)
# -------------------------------------------------------------
NPCS = [
    {"name": "Bandit Rookie",              "hp": 70,   "dmg": 8,   "reward": 220},
    {"name": "Wild Wolf",                  "hp": 100,  "dmg": 12,  "reward": 340},
    {"name": "Rogue Ninja",                "hp": 150,  "dmg": 16,  "reward": 520},
    {"name": "Iron Golem",                 "hp": 210,  "dmg": 20,  "reward": 740},
    {"name": "Shadow Sorcerer",            "hp": 270,  "dmg": 24,  "reward": 980},
    {"name": "Dark Knight",                "hp": 350,  "dmg": 30,  "reward": 1200},
    {"name": "Storm Samurai",              "hp": 420,  "dmg": 36,  "reward": 1650},
    {"name": "Void Hunter",                "hp": 500,  "dmg": 44,  "reward": 2100},
    {"name": "Planetary Raider",           "hp": 620,  "dmg": 52,  "reward": 2600},
    {"name": "Cosmic Assassin",            "hp": 760,  "dmg": 62,  "reward": 3200},
    {"name": "Galaxy Thug",                "hp": 860,  "dmg": 70,  "reward": 3900},
    {"name": "Planet Breaker",             "hp": 980,  "dmg": 80,  "reward": 4700},
    {"name": "Star Dragon Raider",         "hp": 1100, "dmg": 90,  "reward": 5600},
    {"name": "Saiyan Elite",               "hp": 1350, "dmg": 105, "reward": 6800},
    {"name": "Hell Warden",                "hp": 1550, "dmg": 120, "reward": 8100},
    {"name": "Kai Apprentice",             "hp": 1800, "dmg": 140, "reward": 9600},
    {"name": "God of Destruction Adept",   "hp": 2200, "dmg": 175, "reward": 12500},
    {"name": "Angel Warrior",              "hp": 2700, "dmg": 215, "reward": 15500},
    {"name": "Omniversal Sentinel",        "hp": 3300, "dmg": 265, "reward": 19500},
    {"name": "Timeline Devourer",          "hp": 4100, "dmg": 325, "reward": 24500},
]

# Every N NPC wins → world boss (default 15)
# Used by: /explore, bot.cmd_explore, bot.handle_explore_reply
NPC_STREAK_FOR_BOSS = 15

BOSSES = [
    {
        "name": "Frieza Force Commander",
        "hp": 1800, "dmg": 60,
        "yens": 9000, "gems": 900, "crystals": 60,
        "tickets": 5, "skill_points": 20,
    },
    {
        "name": "Cell Junior Pack",
        "hp": 2600, "dmg": 90,
        "yens": 14000, "gems": 1200, "crystals": 80,
        "tickets": 6, "skill_points": 25,
    },
    {
        "name": "Majin Buu Clone",
        "hp": 3600, "dmg": 130,
        "yens": 21000, "gems": 1700, "crystals": 110,
        "tickets": 8, "skill_points": 30,
    },
    {
        "name": "Beerus Avatar",
        "hp": 5200, "dmg": 180,
        "yens": 32000, "gems": 2600, "crystals": 170,
        "tickets": 10, "skill_points": 40,
    },
    {
        "name": "Goku Black Rift",
        "hp": 7400, "dmg": 240,
        "yens": 47000, "gems": 3800, "crystals": 240,
        "tickets": 12, "skill_points": 55,
    },
    {
        "name": "Zamasu Infinite",
        "hp": 9800, "dmg": 310,
        "yens": 62000, "gems": 4900, "crystals": 310,
        "tickets": 15, "skill_points": 70,
    },
    {
        "name": "Jiren Full Power",
        "hp": 13500, "dmg": 400,
        "yens": 88000, "gems": 6700, "crystals": 410,
        "tickets": 18, "skill_points": 90,
    },
]


# -------------------------------------------------------------
# 4. CHARACTERS (90 total, strictly grouped by rarity)
# -------------------------------------------------------------
# Format: (name, rarity, hp, atk, spd, crit%)
# Used by: /gacha, /mycharacters, /equip, /fusion, /wish,
#          db.pick_character_of_rarity, bot._char_stats_by_name,
#          bot.cmd_start (starter pool)
# -------------------------------------------------------------
CHARACTERS = [
    # ----- 10 OMNI KINGS (god-tier, highest stats) -----
    ("Omni King Zeno",           "omni", 1800, 520, 100, 35),
    ("Omni King Future Zeno",    "omni", 1750, 510,  98, 34),
    ("Omni King Zalama",         "omni", 1900, 540,  95, 38),
    ("Omni King Super Shenron",  "omni", 2000, 550,  90, 40),
    ("Omni King Vegeks",         "omni", 1850, 525,  96, 36),
    ("Omni King Cereal",         "omni", 1780, 515,  97, 34),
    ("Omni King Yemma",          "omni", 1720, 505,  99, 32),
    ("Omni King Constellation",  "omni", 1880, 535,  94, 37),
    ("Omni King Universe 11",    "omni", 1820, 522,  93, 35),
    ("Omni King Time",           "omni", 1860, 528, 101, 36),

    # ----- 20 MYTHICAL (Ultra tier) -----
    ("Ultra Instinct Goku",      "mythical", 1280, 410, 98, 32),
    ("Ultra Ego Vegeta",         "mythical", 1350, 420, 85, 30),
    ("Gohan Beast",              "mythical", 1260, 405, 92, 31),
    ("Orange Piccolo",           "mythical", 1230, 395, 90, 29),
    ("Black Frieza",             "mythical", 1420, 430, 96, 35),
    ("Beerus",                   "mythical", 1200, 360, 85, 26),
    ("Whis",                     "mythical", 1300, 370, 95, 28),
    ("Vados",                    "mythical", 1290, 372, 94, 29),
    ("Broly Full Power",         "mythical", 1500, 445, 82, 33),
    ("Vegito Blue",              "mythical", 1380, 425, 94, 32),
    ("SSJ4 Gogeta",              "mythical", 1400, 435, 92, 34),
    ("Grand Minister",           "mythical", 1350, 415, 97, 30),
    ("Janemba",                  "mythical", 1240, 385, 88, 28),
    ("Golden Cooler",            "mythical", 1310, 405, 90, 31),
    ("Fusion Zamasu",            "mythical", 1420, 428, 89, 32),
    ("Omega Shenron",            "mythical", 1390, 420, 87, 33),
    ("Kefla SSJ2",               "mythical", 1250, 395, 93, 30),
    ("Moro (Full Power)",        "mythical", 1360, 415, 88, 31),
    ("Goku Black Rosé",          "mythical", 1270, 400, 91, 32),
    ("Dark Broly (Mask Broken)", "mythical", 1480, 442, 84, 34),

    # ----- 20 LEGENDARY -----
    ("Super Saiyan Blue Goku",   "legendary", 980, 340, 88, 25),
    ("SSJ3 Goku",                "legendary", 950, 330, 82, 24),
    ("Majin Vegeta",             "legendary", 970, 335, 84, 25),
    ("Future Gohan",             "legendary", 920, 320, 80, 23),
    ("Jiren Beyond Limits",      "legendary", 1050, 355, 86, 26),
    ("Super Buu",                "legendary", 940, 325, 79, 24),
    ("Android 17 MVP",           "legendary", 910, 315, 90, 23),
    ("Hit",                      "legendary", 930, 322, 92, 24),
    ("Toppo Destroyer",          "legendary", 960, 330, 82, 25),
    ("Metal Cooler",             "legendary", 900, 312, 80, 22),
    ("Broly DBZ",                "legendary", 1000, 345, 78, 26),
    ("Gogeta Blue",              "legendary", 990, 342, 87, 26),
    ("Vegeta SSJ2",              "legendary", 940, 322, 83, 24),
    ("Goku SSJ God",             "legendary", 970, 328, 85, 25),
    ("Super Saiyan 4 Goku",      "legendary", 985, 335, 84, 25),
    ("Super Saiyan 4 Vegeta",    "legendary", 975, 332, 83, 25),
    ("Golden Frieza",            "legendary", 945, 328, 85, 24),
    ("Mystic Gohan",             "legendary", 955, 330, 82, 24),
    ("Gotenks SSJ3",             "legendary", 930, 320, 86, 24),
    ("Kale SSJ Berserk",         "legendary", 920, 318, 81, 23),

    # ----- 20 EPIC -----
    ("Gohan SSJ2",               "epic", 890, 250, 78, 20),
    ("Piccolo (Kami fused)",     "epic", 860, 245, 76, 19),
    ("Perfect Cell",             "epic", 900, 252, 77, 20),
    ("Frieza 100%",              "epic", 880, 248, 75, 19),
    ("Future Trunks SSJ",        "epic", 850, 242, 79, 20),
    ("Ultimate Gohan",           "epic", 895, 250, 76, 20),
    ("King Piccolo",             "epic", 830, 235, 74, 18),
    ("Android 16",               "epic", 870, 244, 72, 19),
    ("Android 18",               "epic", 840, 240, 80, 20),
    ("Master Roshi Max",         "epic", 810, 232, 78, 18),
    ("Tien Shinhan Neo",         "epic", 820, 235, 76, 19),
    ("Raditz",                   "epic", 800, 228, 74, 18),
    ("Nappa",                    "epic", 810, 232, 72, 17),
    ("Zarbon",                   "epic", 800, 228, 75, 18),
    ("Dodoria",                  "epic", 815, 232, 70, 17),
    ("Dabura",                   "epic", 860, 242, 76, 19),
    ("Supreme Kai",              "epic", 835, 238, 78, 19),
    ("Kibito",                   "epic", 820, 234, 77, 18),
    ("Android 19",               "epic", 825, 236, 73, 18),
    ("Dr. Gero",                 "epic", 815, 232, 74, 18),

    # ----- 12 RARE -----
    ("Trunks (youth)",           "rare", 590, 67, 60, 12),
    ("Krillin",                  "rare", 580, 65, 62, 12),
    ("Yamcha",                   "rare", 570, 63, 65, 11),
    ("Chiaotzu",                 "rare", 550, 60, 68, 10),
    ("Pan",                      "rare", 560, 62, 66, 11),
    ("Videl",                    "rare", 570, 63, 64, 11),
    ("Recoome",                  "rare", 610, 70, 55, 11),
    ("Burter",                   "rare", 590, 67, 72, 12),
    ("Jeice",                    "rare", 580, 65, 70, 12),
    ("Goten",                    "rare", 575, 64, 65, 11),
    ("Kid Trunks",               "rare", 575, 64, 66, 11),
    ("Mr. Satan",                "rare", 550, 60, 55, 8),

    # ----- 8 COMMON -----
    ("Saibaman",                 "common", 380, 42, 45, 6),
    ("Frieza Soldier",           "common", 370, 40, 45, 5),
    ("Red Ribbon Soldier",       "common", 360, 38, 44, 5),
    ("Cell Junior",              "common", 390, 44, 48, 6),
    ("World Tournament Rookie",  "common", 350, 36, 42, 4),
    ("Saiyan Recruit",           "common", 380, 42, 46, 5),
    ("Galactic Patrol Cadet",    "common", 370, 40, 45, 5),
    ("Capsule Corp Guard",       "common", 360, 38, 43, 4),
]


# -------------------------------------------------------------
# 5. RARITY CONSTANTS
# -------------------------------------------------------------
# Used by: display everywhere, fusion (rarity comparison),
#          starter pack filter, achievement triggers
# -------------------------------------------------------------
RARITY_ORDER = {
    "common":    1,
    "rare":      2,
    "epic":      3,
    "legendary": 4,
    "mythical":  5,
    "omni":      6,
}

RARITY_LABEL = {
    "common":    "⚪ Common",
    "rare":      "🔵 Rare",
    "epic":      "🟣 Epic",
    "legendary": "🟡 Legendary",
    "mythical":  "🔴 Mythical",
    "omni":      "👑 Omni King",
}

RARITY_ICONS = {
    "common":    "⚪",
    "rare":      "🔵",
    "epic":      "🟣",
    "legendary": "🟡",
    "mythical":  "🔴",
    "omni":      "👑",
}

# Fallback stats (only used if character name not found)
RARITY_ATK  = {"common": 40,  "rare": 65,  "epic": 240, "legendary": 330, "mythical": 410, "omni": 530}
RARITY_HP   = {"common": 370, "rare": 580, "epic": 850, "legendary": 950, "mythical": 1300, "omni": 1850}
RARITY_SPD  = {"common": 44,  "rare": 62,  "epic": 76,  "legendary": 84,  "mythical": 90,  "omni": 96}
RARITY_CRIT = {"common": 5,   "rare": 11,  "epic": 19,  "legendary": 24,  "mythical": 30,  "omni": 36}

# Informational level caps (not enforced, just for UI display)
RARITY_LEVEL_CAP = {
    "common":    30,
    "rare":      50,
    "epic":      70,
    "legendary": 90,
    "mythical":  110,
    "omni":      130,
}


# -------------------------------------------------------------
# 6. GACHA CONFIG
# -------------------------------------------------------------
# Used by: /gacha, db.roll_rarity, db.pick_character_of_rarity
# -------------------------------------------------------------
GACHA_RATES = [
    ("common",    38),
    ("rare",      28),
    ("epic",      16),
    ("legendary", 10),
    ("mythical",  6),
    ("omni",      2),
]

GACHA_BANNERS = {
    "standard": {
        "name": "Standard Banner",
        "cost": 1,
        "bonus": {},
    },
    "hero": {
        "name": "Hero Banner",
        "cost": 1,
        "bonus": {"legendary": 1.5, "mythical": 1.5},
    },
    "god": {
        "name": "God Banner",
        "cost": 2,
        "bonus": {"mythical": 2.0, "omni": 2.0},
    },
    "omni": {
        "name": "Omniverse Banner",
        "cost": 3,
        "bonus": {"omni": 3.0},
    },
}


# -------------------------------------------------------------
# 7. EQUIPMENT (17 weapons + 17 armors)
# -------------------------------------------------------------
# Used by: /shop, /buy, /inventory, /equip, bot.run_battle,
#          bot.player_stats, apply_drops
# -------------------------------------------------------------
WEAPONS = {
    "Power Pole":              55,
    "Wooden Sword":            20,
    "Iron Sword":              65,
    "Saiyan Blade":            140,
    "Kamehameha Blade":        260,
    "Ultra Sword":             380,
    "Z Sword":                 520,
    "Brave Sword (Tapion)":    620,
    "Destructo Blade":         720,
    "God Breaker":             820,
    "Black Hole Blade":        940,
    "Galaxy Cutter":           1080,
    "Crusher Edge":            1250,
    "Supernova Blade":         1450,
    "Janemba Dimension Sword": 1680,
    "Deadly Divine Sword":     1950,
    "Vegito Spirit Sword":     2200,
}

ARMORS = {
    "Turtle School Gi":       40,
    "Demon Clan Gi":          60,
    "Leather Vest":           80,
    "Saiyan Armor":           160,
    "Steel Armor":            210,
    "Yardrat Armor":          280,
    "God Armor":              360,
    "Battle Armor":           460,
    "Celestial Armor":        580,
    "Whis Symbol Gi":         720,
    "Katchin Armor":          900,
    "Doom Armor":             1100,
    "Ultra Guard":            1350,
    "Grand Priest Suit":      1650,
    "Kaio Suit":              1980,
    "Divine Battle Suit":     2300,
    "Heavenly Guardian Suit": 2700,
}

# Combined lookup: name → (slot, bonus)
EQUIPMENT = {}
for _weapon_name, _bonus in WEAPONS.items():
    EQUIPMENT[_weapon_name] = ("weapon", _bonus)
for _armor_name, _bonus in ARMORS.items():
    EQUIPMENT[_armor_name] = ("armor", _bonus)


# -------------------------------------------------------------
# 8. SHOP (55 items across 6 categories)
# -------------------------------------------------------------
# Format: shop_id → (name, price, currency, kind, amount_per_purchase)
# Used by: /shop, /buy
# -------------------------------------------------------------
SHOP = {}
_shop_id = 1

def _register(name, price, currency, kind, amount=1):
    """Register a shop item with the next sequential ID."""
    global _shop_id
    SHOP[_shop_id] = (name, price, currency, kind, amount)
    _shop_id += 1

# Category 1: WEAPONS (IDs 1–17)
for _w_name, _w_bonus in WEAPONS.items():
    _register(_w_name, _w_bonus * 800, "yens", "weapon")

# Category 2: ARMORS (IDs 18–34)
for _a_name, _a_bonus in ARMORS.items():
    _register(_a_name, _a_bonus * 900, "yens", "armor")

# Category 3: CRYSTALS (IDs 35–38)
_register("Crystal x1",   30,   "gems", "crystal", 1)
_register("Crystal x10",  280,  "gems", "crystal", 10)
_register("Crystal x50",  1300, "gems", "crystal", 50)
_register("Crystal x100", 2400, "gems", "crystal", 100)

# Category 4: HEALING (IDs 39–44)
_register("Potion",             100,  "yens", "heal", 1)
_register("Mega Potion",        250,  "yens", "heal", 1)
_register("Revive",             350,  "yens", "heal", 1)
_register("Senzu Bean",         800,  "yens", "heal", 1)
_register("Senzu Bean Pouch x5", 3800, "yens", "heal", 5)
_register("Divine Senzu Bean",  8000, "yens", "heal", 1)

# Category 5: FUSION MATERIALS (IDs 45–49)
_register("Fusion Material",  250,  "gems", "fusion", 1)
_register("Fusion Core",      500,  "gems", "fusion", 1)
_register("Fusion Crystal",   1200, "gems", "fusion", 1)
_register("Fusion Catalyst",  2500, "gems", "fusion", 1)
_register("Potara Earrings",  4000, "gems", "fusion", 1)

# Category 6: TICKETS & KEYS (IDs 50–55)
_register("Gacha Ticket",      60,   "gems", "ticket", 1)
_register("Gacha Ticket x10",  560,  "gems", "ticket", 10)
_register("Gacha Ticket x50",  2700, "gems", "ticket", 50)
_register("Gacha Ticket x100", 5200, "gems", "ticket", 100)
_register("Elite Key",         1200, "yens", "key_elite", 1)
_register("Boss Key",          2600, "yens", "key_boss", 1)

# Display order (informational, bot.py has its own alias map)
SHOP_CATEGORY_ORDER = [
    ("weapon",  "⚔️ Weapons"),
    ("armor",   "🛡️ Armors"),
    ("crystal", "🔮 Crystals"),
    ("heal",    "🧪 Healing"),
    ("fusion",  "🧬 Fusion Materials"),
    ("ticket",  "🎫 Gacha Tickets"),
    ("key",     "🗝️ Summon Keys"),
]


# -------------------------------------------------------------
# 9. SKILLS (20)
# -------------------------------------------------------------
# Used by: /skills, /learn, bot.player_stats (ATK boost),
#          apply_drops, /wish
# -------------------------------------------------------------
SKILLS = {
    "Ki Blast":              9,
    "Kaioken":               6,
    "Instant Transmission":  10,
    "Spirit Bomb":           18,
    "Solar Flare":           12,
    "Destructo Disk":        16,
    "Ultra Instinct":        22,
    "Final Flash":           20,
    "God Kamehameha":        25,
    "Big Bang Attack":       28,
    "Black Hole Attack":     32,
    "Time Skip":             20,
    "Nova Burst":            26,
    "Dragon Fist":           30,
    "Final Explosion":       35,
    "Kamehameha Wave":       38,
    "Heavenly Rush":         42,
    "Universe Breaker":      48,
    "Halo Blast":            50,
    "Godly Burst":           54,
}

SKILL_ATK = {
    "Ki Blast":              100,
    "Kaioken":               116,
    "Instant Transmission":  114,
    "Spirit Bomb":           192,
    "Solar Flare":           171,
    "Destructo Disk":        190,
    "Ultra Instinct":        215,
    "Final Flash":           128,
    "God Kamehameha":        222,
    "Big Bang Attack":       214,
    "Black Hole Attack":     224,
    "Time Skip":             132,
    "Nova Burst":            220,
    "Dragon Fist":           198,
    "Final Explosion":       292,
    "Kamehameha Wave":       225,
    "Heavenly Rush":         390,
    "Universe Breaker":      344,
    "Halo Blast":            368,
    "Godly Burst":           465,
}


# -------------------------------------------------------------
# 10. DRAGON BALLS
# -------------------------------------------------------------
# Used by: /wish, apply_drops, db.take_one_of_each_dragon_ball,
#          combat.CombatAchievements.check_dragon_balls
# -------------------------------------------------------------
DRAGON_BALL_STARS = [1, 2, 3, 4, 5, 6, 7]


# -------------------------------------------------------------
# 11. SUMMON BOSSES
# -------------------------------------------------------------
# Used by: /summon, bot.cmd_summon, db.summon_hp, db.set_summon_hp
# -------------------------------------------------------------
SUMMONS = {
    "elite": {
        "name":        "Elite Ginyu Force",
        "hp":          260000,
        "dmg":         11000,
        "reward_mult": 5,
        "key":         "keys_elite",
    },
    "mythical": {
        "name":        "Mythical Perfect Cell",
        "hp":          700000,
        "dmg":         18000,
        "reward_mult": 5,
        "key":         "keys_boss",
    },
    "legendary": {
        "name":        "God of Destruction Beerus",
        "hp":          1100000,
        "dmg":         26000,
        "reward_mult": 5,
        "key":         "keys_boss",
    },
}


# -------------------------------------------------------------
# 12. CLAN RAIDS & PERKS
# -------------------------------------------------------------
# Used by: /clan (all subcommands), clans.py
# -------------------------------------------------------------
CLAN_RAIDS = {
    "Perfect Cell": {
        "hp": 40000, "dmg": 399,
        "reward_yens": 25000000, "reward_gems": 50000,
        "reward_crystals": 3000, "reward_tickets": 50,
        "reward_skill_points": 100,
    },
    "Frieza": {
        "hp": 70000, "dmg": 1200,
        "reward_yens": 50000000, "reward_gems": 90000,
        "reward_crystals": 6000, "reward_tickets": 70,
        "reward_skill_points": 120,
    },
    "Majin Buu": {
        "hp": 95000, "dmg": 1700,
        "reward_yens": 80000000, "reward_gems": 120000,
        "reward_crystals": 8000, "reward_tickets": 100,
        "reward_skill_points": 150,
    },
    "Beerus": {
        "hp": 140000, "dmg": 2400,
        "reward_yens": 120000000, "reward_gems": 180000,
        "reward_crystals": 10000, "reward_tickets": 150,
        "reward_skill_points": 190,
    },
}

CLAN_PERKS = {
    "war_drums":     {"name": "War Drums",     "cost": 200,  "desc": "+5% ATK for all members"},
    "iron_wall":     {"name": "Iron Wall",     "cost": 200,  "desc": "+5% HP for all members"},
    "ki_reserves":   {"name": "Ki Reserves",   "cost": 300,  "desc": "+10% skill points on wins"},
    "greedy_vault":  {"name": "Greedy Vault",  "cost": 400,  "desc": "+10% yens on wins"},
    "crit_focus":    {"name": "Crit Focus",    "cost": 500,  "desc": "+3% crit chance"},
    "kai_blessing":  {"name": "Kai Blessing",  "cost": 600,  "desc": "+1 extra daily reward"},
    "raid_lust":     {"name": "Raid Lust",     "cost": 700,  "desc": "+15% raid damage"},
    "senzu_stock":   {"name": "Senzu Stock",   "cost": 800,  "desc": "Free Senzu every 24h"},
    "treasure_lord": {"name": "Treasure Lord", "cost": 900,  "desc": "+20% clan treasure"},
    "mystic_forge":  {"name": "Mystic Forge",  "cost": 1000, "desc": "Fusion drop rate x2"},
    "omni_focus":    {"name": "Omni Focus",    "cost": 1500, "desc": "+1% omni gacha rate"},
    "dragon_aura":   {"name": "Dragon Aura",   "cost": 2000, "desc": "+10% dragon ball drop"},
}

CLAN_CREATE_CRYSTALS = 100


# -------------------------------------------------------------
# 13. WORLD RAID
# -------------------------------------------------------------
# Used by: /raid, /raid_start, /raid_attack, db.raid_*
# -------------------------------------------------------------
RAID = {
    "name":              "Multiverse Omega Dragon",
    "hp":                120000,
    "dmg":               500,
    "reward_mult":       10,
    "attack_cooldown_s": 0,   # zero cooldown — attack freely
}


# -------------------------------------------------------------
# 14. RANKS & ASCENSION
# -------------------------------------------------------------
# Used by: /rankup, bot.player_stats (multiplier),
#          combat.CombatAchievements (rank milestones)
# -------------------------------------------------------------
RANKS = {
    1:  "Beginner",
    2:  "Novice",
    3:  "King",
    4:  "Emperor",
    5:  "Demigod",
    6:  "Immortal",
    7:  "Titan",
    8:  "Oracle",
    9:  "Celestial",
    10: "God",
}

RANKUP_CRYSTALS = {
    1: 500,
    2: 4000,
    3: 20000,
    4: 70000,
    5: 150000,
    6: 300000,
    7: 600000,
    8: 1000000,
    9: 2000000,
}

# Each rank grants +15% permanent stat boost
RANK_BONUS = 0.15


# -------------------------------------------------------------
# 15. STARTER PACK
# -------------------------------------------------------------
# Used by: /start (new player bonus)
# -------------------------------------------------------------
STARTER_PACK = {
    "pool":           ["rare", "epic", "legendary"],
    "bonus_yens":     1000,
    "bonus_gems":     50,
    "bonus_tickets":  3,
}


# -------------------------------------------------------------
# 16. FUSION
# -------------------------------------------------------------
# Used by: /fusion
# -------------------------------------------------------------
FUSION_MATERIALS = {
    "Fusion Material":  1,
    "Fusion Core":      2,
    "Fusion Crystal":   3,
    "Fusion Catalyst":  4,
    "Potara Earrings":  5,
}

FUSION_CRYSTAL_COST = 25


# -------------------------------------------------------------
# 17. HEALING
# -------------------------------------------------------------
# Fraction of MAX HP restored per item (0.0–1.0)
# Used by: /heal, db.apply_heal
# -------------------------------------------------------------
HEALING = {
    "Potion":              0.30,
    "Mega Potion":         0.60,
    "Revive":              0.80,
    "Senzu Bean":          1.00,
    "Senzu Bean Pouch x5": 1.00,
    "Divine Senzu Bean":   1.00,
}


# -------------------------------------------------------------
# 18. ACHIEVEMENTS (22)
# -------------------------------------------------------------
# Used by: /achievements, combat.CombatAchievements,
#          db.init (seeds), db.unlock_achievement
# -------------------------------------------------------------
ACHIEVEMENTS = {
    # Combat
    "first_blood":     {"name": "First Blood",       "desc": "Win your first battle",       "yens": 1000,    "gems": 10,    "crystals": 0},
    "battle_10":       {"name": "Rookie Fighter",    "desc": "Complete 10 battles",         "yens": 5000,    "gems": 25,    "crystals": 1},
    "battle_50":       {"name": "Veteran",           "desc": "Complete 50 battles",         "yens": 25000,   "gems": 100,   "crystals": 3},
    "battle_100":      {"name": "100th Battle",      "desc": "Complete 100 battles",        "yens": 100000,  "gems": 400,   "crystals": 10},
    "battle_500":      {"name": "Warlord",           "desc": "Complete 500 battles",        "yens": 500000,  "gems": 2000,  "crystals": 50},
    "flawless":        {"name": "Flawless Victory",  "desc": "Win without taking damage",   "yens": 20000,   "gems": 100,   "crystals": 5},
    "explore_vet":     {"name": "Explorer",          "desc": "Defeat 100 NPCs",             "yens": 30000,   "gems": 150,   "crystals": 8},

    # Bosses
    "boss_slayer":     {"name": "Boss Slayer",       "desc": "Defeat a world boss",         "yens": 50000,   "gems": 300,   "crystals": 15},
    "summon_hunter":   {"name": "Summon Hunter",     "desc": "Defeat a summon boss",        "yens": 80000,   "gems": 500,   "crystals": 20},
    "raid_warrior":    {"name": "Raid Warrior",      "desc": "Help defeat the world raid",  "yens": 100000,  "gems": 500,   "crystals": 20},
    "clan_raid_clear": {"name": "Clan Champion",     "desc": "Clear a clan raid boss",      "yens": 200000,  "gems": 800,   "crystals": 30},

    # Clans
    "clan_founder":    {"name": "Clan Founder",      "desc": "Create a clan",               "yens": 20000,   "gems": 100,   "crystals": 3},
    "clan_leader":     {"name": "Clan Leader",       "desc": "Become a clan leader",        "yens": 10000,   "gems": 50,    "crystals": 2},

    # Collection
    "dragon_collector": {"name": "Dragon Collector", "desc": "Collect all 7 dragon balls",  "yens": 150000,  "gems": 600,   "crystals": 30},
    "mythical_owner":  {"name": "Mythical Owner",    "desc": "Obtain a mythical character", "yens": 50000,   "gems": 250,   "crystals": 15},
    "omni_owner":      {"name": "Omni Owner",        "desc": "Obtain an omni character",    "yens": 500000,  "gems": 2000,  "crystals": 100},

    # Wealth
    "rich":            {"name": "Millionaire",       "desc": "Have 1,000,000 yens",         "yens": 50000,   "gems": 100,   "crystals": 5},
    "gem_hoarder":     {"name": "Gem Hoarder",       "desc": "Have 1,000 gems",             "yens": 20000,   "gems": 100,   "crystals": 3},

    # Progression
    "rank_5":          {"name": "Demigod",           "desc": "Reach rank 5",                "yens": 50000,   "gems": 250,   "crystals": 15},
    "rank_10":         {"name": "God",               "desc": "Reach rank 10",               "yens": 1000000, "gems": 5000,  "crystals": 200},
    "fusion_master":   {"name": "Fusion Master",     "desc": "Complete a fusion",           "yens": 30000,   "gems": 150,   "crystals": 8},
    "traveler":        {"name": "Traveler",          "desc": "Travel to Omniverse",         "yens": 50000,   "gems": 200,   "crystals": 10},
}

# Grouping for /achievements display
ACHIEVEMENT_CATEGORIES = {
    "Combat":       ["first_blood", "battle_10", "battle_50", "battle_100",
                     "battle_500", "flawless", "explore_vet"],
    "Bosses":       ["boss_slayer", "summon_hunter", "raid_warrior",
                     "clan_raid_clear"],
    "Clans":        ["clan_founder", "clan_leader"],
    "Collection":   ["dragon_collector", "mythical_owner", "omni_owner"],
    "Wealth":       ["rich", "gem_hoarder"],
    "Progression":  ["rank_5", "rank_10", "fusion_master", "traveler"],
}


# -------------------------------------------------------------
# 19. QUESTS (4 daily + 4 weekly + 4 monthly = 12 total)
# -------------------------------------------------------------
# Used by: /quests, /claim_daily, /claim_weekly, /claim_monthly,
#          combat.QuestTracker, db.quest_*
# -------------------------------------------------------------
DAILY_QUESTS = {
    "daily_npc_10": {
        "name": "Fight 10 NPCs", "target": 10,
        "yens": 5000, "gems": 25, "crystals": 1,
    },
    "daily_win_5": {
        "name": "Win 5 battles", "target": 5,
        "yens": 4000, "gems": 20, "crystals": 1,
    },
    "daily_earn_5000": {
        "name": "Earn 5,000 yens", "target": 5000,
        "yens": 3000, "gems": 15, "crystals": 0,
    },
    "daily_gacha_1": {
        "name": "Roll gacha once", "target": 1,
        "yens": 2000, "gems": 30, "crystals": 0,
    },
}

WEEKLY_QUESTS = {
    "weekly_npc_100": {
        "name": "Fight 100 NPCs", "target": 100,
        "yens": 50000, "gems": 250, "crystals": 10,
    },
    "weekly_boss_3": {
        "name": "Defeat 3 bosses", "target": 3,
        "yens": 30000, "gems": 150, "crystals": 5,
    },
    "weekly_earn_50k": {
        "name": "Earn 50,000 yens", "target": 50000,
        "yens": 25000, "gems": 100, "crystals": 3,
    },
    "weekly_gacha_10": {
        "name": "Roll gacha 10 times", "target": 10,
        "yens": 20000, "gems": 200, "crystals": 5,
    },
}

MONTHLY_QUESTS = {
    "monthly_npc_500": {
        "name": "Fight 500 NPCs", "target": 500,
        "yens": 500000, "gems": 2000, "crystals": 50,
    },
    "monthly_win_250": {
        "name": "Win 250 battles", "target": 250,
        "yens": 400000, "gems": 1500, "crystals": 40,
    },
    "monthly_earn_500k": {
        "name": "Earn 500,000 yens", "target": 500000,
        "yens": 300000, "gems": 1000, "crystals": 30,
    },
    "monthly_summon_5": {
        "name": "Defeat 5 summons", "target": 5,
        "yens": 350000, "gems": 1200, "crystals": 35,
    },
}

QUEST_RESET_INFO = {
    "daily":   "Resets at midnight UTC every day",
    "weekly":  "Resets every Monday at 00:00 UTC",
    "monthly": "Resets on the 1st of each month at 00:00 UTC",
}


# -------------------------------------------------------------
# 20. REFERENCE TABLES
# -------------------------------------------------------------
# Informational tables used by /help, /admin_help, and admin tools.
# None of these are strictly required for gameplay, but they make
# the code more maintainable and the help text consistent.
# -------------------------------------------------------------

# Drop rates used by bot.apply_drops
DROP_RATES = {
    "npc": {
        "equipment": 0.15,
        "dragon_ball": 0.10,
        "ticket": 0.05,
        "skill": 0.02,
        "fusion_material": 0.00,
    },
    "boss": {
        "equipment": 0.35,
        "dragon_ball": 0.45,
        "ticket": 0.30,
        "skill": 0.20,
        "fusion_material": 0.25,
    },
    "summon": {
        "equipment": 0.35,
        "dragon_ball": 0.60,
        "ticket": 0.30,
        "skill": 0.40,
        "fusion_material": 0.25,
    },
}

# Travel progression for /help display
TRAVEL_PROGRESSION = [
    ("Earth",              "1–20",   "1.0x",  "Start here"),
    ("Hell",               "21–39",  "2.0x",  "Unlock at level 21"),
    ("Kai Planet",         "40–59",  "3.0x",  "Unlock at level 40"),
    ("Supreme Kai Planet", "60–79",  "4.0x",  "Unlock at level 60"),
    ("Lord Beerus Planet", "80–99",  "5.0x",  "Unlock at level 80"),
    ("Omniverse",          "100+",   "7.0x",  "Unlock at level 100"),
]

# Level milestones (informational)
LEVEL_MILESTONES = {
    5:   "Unlock /clan create",
    10:  "First daily/weekly quest tier",
    21:  "Unlock travel to Hell",
    40:  "Unlock travel to Kai Planet",
    60:  "Unlock travel to Supreme Kai Planet",
    80:  "Unlock travel to Lord Beerus Planet",
    100: "Unlock travel to Omniverse",
}

# Fusion material tiers (informational)
MATERIAL_TIERS = {
    "Fusion Material":   "Tier 1 — basic fusion fuel",
    "Fusion Core":       "Tier 2 — mid-tier fusion",
    "Fusion Crystal":    "Tier 3 — rare fusion boost",
    "Fusion Catalyst":   "Tier 4 — master fusion",
    "Potara Earrings":   "Tier 5 — divine fusion",
}

# Command grouping for /help display
COMMAND_GROUPS = {
    "Combat":       ["/explore", "/combathistory", "/heal",
                     "/achievements", "/quests"],
    "Player":       ["/profile", "/team", "/inventory",
                     "/mycharacters", "/equip"],
    "Economy":      ["/shop", "/buy", "/gacha", "/skills",
                     "/learn", "/wish"],
    "Progression":  ["/daily", "/weekly", "/rankup", "/travel",
                     "/fusion"],
    "Clans":        ["/clan", "/leaderboard"],
    "Bosses":       ["/summon", "/raid", "/raid_start",
                     "/raid_attack"],
    "Admin":        ["/admin_give", "/admin_set", "/admin_item",
                     "/admin_char", "/admin_skill", "/admin_dball",
                     "/admin_promote", "/admin_ban", "/admin_unban",
                     "/admin_reset", "/admin_broadcast", "/admin_info",
                     "/admin_raidreset", "/admin_heal", "/admin_bonus",
                     "/admin_list", "/admin_help"],
}

# Reward multipliers by battle type
REWARD_MULTIPLIERS = {
    "npc":    1.0,
    "boss":   5.0,
    "summon": 5.0,
    "raid":   10.0,
}

# Starter pack detailed description
STARTER_PACK_BONUSES = {
    "random_character": "Rare to Legendary pool",
    "yens":            1000,
    "gems":            50,
    "tickets":         3,
    "auto_equip":      True,
}

# Healing item descriptions
HEAL_DESCRIPTIONS = {
    "Potion":              "Restores 30% of max HP",
    "Mega Potion":         "Restores 60% of max HP",
    "Revive":              "Restores 80% of max HP",
    "Senzu Bean":          "Fully restores HP (100%)",
    "Senzu Bean Pouch x5": "Contains 5 Senzu Beans",
    "Divine Senzu Bean":   "Fully restores HP + stamina",
}

# Bulk discount tiers used by bot.cmd_buy
BULK_DISCOUNTS = [
    (50, 0.15),   # 15% off for qty >= 50
    (10, 0.10),   # 10% off for qty >= 10
    (5,  0.05),   # 5% off for qty >= 5
]

# Gacha banner descriptions for /gacha display
GACHA_BANNER_DESCRIPTIONS = {
    "standard": "Normal rates for all rarities",
    "hero":     "Boosted Legendary & Mythical rates",
    "god":      "Boosted Mythical & Omni rates (costs 2 tickets)",
    "omni":     "3× Omni rate (costs 3 tickets)",
}

# Raid boss flavor text
RAID_FLAVOR_TEXT = {
    "started":   "A massive shadow darkens the sky. The Multiverse Omega Dragon has appeared!",
    "defeated":  "The dragon roars and crumbles into particles. The multiverse is safe... for now.",
    "attacked":  "Your Ki-blast streaks through the void and strikes the dragon.",
}


# =============================================================
# END OF GAME DATA
# =============================================================
# If you add a new command in bot.py, search this file first.
# If a constant already exists, reuse it. If not, add it here.
#
# Every constant is verified against:
#   • bot.py (~3,775 lines)
#   • db.py (~900 lines)
#   • combat.py (~650 lines)
#   • clans.py (~550 lines)
#
# Line count: ~880 lines
# Total data entries: 90 characters, 20 NPCs, 7 bosses, 17 weapons,
#   17 armors, 55 shop items, 20 skills, 3 summons, 4 clan raids,
#   12 clan perks, 22 achievements, 12 quests, 10 ranks.
# =============================================================
