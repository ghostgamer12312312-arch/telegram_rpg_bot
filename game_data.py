from __future__ import annotations

# =============================================================
# DRAGON BALL RPG — MASTER GAME DATA
# =============================================================

STARTING_RESOURCES = {
    "yens": 500000, "gems": 20000, "crystals": 5555,
    "tickets": 130, "skill_points": 120,
    "keys_elite": 10, "keys_boss": 10, "exp": 0,
}

LEVEL_EXP = 100

# ---------- 6 PLANET REALMS ----------
PLANETS = {
    "Earth":              {"id": 1, "level_min": 1,   "level_max": 20,  "multiplier": 1.0, "desc": "Starter planet — balanced encounters."},
    "Hell":               {"id": 2, "level_min": 21,  "level_max": 39,  "multiplier": 2.0, "desc": "Underworld abyss — demonic foes."},
    "Kai Planet":         {"id": 3, "level_min": 40,  "level_max": 59,  "multiplier": 3.0, "desc": "North King Kai's sacred orb."},
    "Supreme Kai Planet": {"id": 4, "level_min": 60,  "level_max": 79,  "multiplier": 4.0, "desc": "Holy sanctum of the Supreme Kais."},
    "Lord Beerus Planet": {"id": 5, "level_min": 80,  "level_max": 99,  "multiplier": 5.0, "desc": "Domain of Beerus and Whis."},
    "Omniverse":          {"id": 6, "level_min": 100, "level_max": 999, "multiplier": 7.0, "desc": "Multiversal pinnacle of all creation."},
}
PLANET_ORDER = ["Earth", "Hell", "Kai Planet", "Supreme Kai Planet",
                "Lord Beerus Planet", "Omniverse"]

# ---------- 13 CANONICAL NPCS ----------
NPCS = [
    {"name": "Bandit Rookie",       "hp": 70,    "dmg": 8,    "reward": 220},
    {"name": "Wild Wolf",           "hp": 100,   "dmg": 12,   "reward": 340},
    {"name": "Rogue Ninja",         "hp": 150,   "dmg": 16,   "reward": 520},
    {"name": "Iron Golem",          "hp": 210,   "dmg": 20,   "reward": 740},
    {"name": "Shadow Sorcerer",     "hp": 270,   "dmg": 24,   "reward": 980},
    {"name": "Dark Knight",         "hp": 350,   "dmg": 30,   "reward": 1200},
    {"name": "Storm Samurai",       "hp": 420,   "dmg": 36,   "reward": 1650},
    {"name": "Void Hunter",         "hp": 500,   "dmg": 44,   "reward": 2100},
    {"name": "Planetary Raider",    "hp": 620,   "dmg": 52,   "reward": 2600},
    {"name": "Cosmic Assassin",     "hp": 760,   "dmg": 62,   "reward": 3200},
    {"name": "Galaxy Thug",         "hp": 860,   "dmg": 70,   "reward": 3900},
    {"name": "Planet Breaker",      "hp": 980,   "dmg": 80,   "reward": 4700},
    {"name": "Star Dragon Raider",  "hp": 1100,  "dmg": 90,   "reward": 5600},
]
NPC_STREAK_FOR_BOSS = 15

# ---------- WORLD BOSSES ----------
BOSSES = [
    {"name": "Frieza Force Commander", "hp": 1800, "dmg": 60,  "yens": 9000,  "gems": 900,  "crystals": 60,  "tickets": 5,  "skill_points": 20},
    {"name": "Cell Junior Pack",       "hp": 2600, "dmg": 90,  "yens": 14000, "gems": 1200, "crystals": 80,  "tickets": 6,  "skill_points": 25},
    {"name": "Majin Buu Clone",        "hp": 3600, "dmg": 130, "yens": 21000, "gems": 1700, "crystals": 110, "tickets": 8,  "skill_points": 30},
    {"name": "Beerus Avatar",          "hp": 5200, "dmg": 180, "yens": 32000, "gems": 2600, "crystals": 170, "tickets": 10, "skill_points": 40},
    {"name": "Goku Black Rift",        "hp": 7400, "dmg": 240, "yens": 47000, "gems": 3800, "crystals": 240, "tickets": 12, "skill_points": 55},
]

# ---------- 70+ CHARACTERS with full stats ----------
# (name, rarity, hp, atk, spd, crit)
CHARACTERS = [
    # ----- 10 OMNI KINGS (God-tier, highest stats) -----
    ("Omni King Zeno",              "omni", 1800, 520, 100, 35),
    ("Omni King Future Zeno",       "omni", 1750, 510, 98,  34),
    ("Omni King Zalama",            "omni", 1900, 540, 95,  38),
    ("Omni King Super Shenron",     "omni", 2000, 550, 90,  40),
    ("Omni King Vegeks",            "omni", 1850, 525, 96,  36),
    ("Omni King Cereal",            "omni", 1780, 515, 97,  34),
    ("Omni King Yemma",             "omni", 1720, 505, 99,  32),
    ("Omni King Constellation",     "omni", 1880, 535, 94,  37),
    ("Omni King Universe 11",       "omni", 1820, 522, 93,  35),
    ("Omni King Time",              "omni", 1860, 528, 101, 36),

    # ----- 20 MYTHICAL (Ultra tier) -----
    ("Ultra Instinct Goku",         "mythical", 1280, 410, 98, 32),
    ("Ultra Ego Vegeta",            "mythical", 1350, 420, 85, 30),
    ("Gohan Beast",                 "mythical", 1260, 405, 92, 31),
    ("Orange Piccolo",              "mythical", 1230, 395, 90, 29),
    ("Black Frieza",                "mythical", 1420, 430, 96, 35),
    ("Beerus",                      "mythical", 1200, 360, 85, 26),
    ("Whis",                        "mythical", 1300, 370, 95, 28),
    ("Vados",                       "mythical", 1290, 372, 94, 29),
    ("Broly Full Power",            "mythical", 1500, 445, 82, 33),
    ("Vegito Blue",                 "mythical", 1380, 425, 94, 32),
    ("SSJ4 Gogeta",                 "mythical", 1400, 435, 92, 34),
    ("Grand Minister",              "mythical", 1350, 415, 97, 30),
    ("Janemba",                     "mythical", 1240, 385, 88, 28),
    ("Golden Cooler",               "mythical", 1310, 405, 90, 31),
    ("Fusion Zamasu",               "mythical", 1420, 428, 89, 32),
    ("Omega Shenron",               "mythical", 1390, 420, 87, 33),
    ("Kefla SSJ2",                  "mythical", 1250, 395, 93, 30),
    ("Moro (Full Power)",           "mythical", 1360, 415, 88, 31),
    ("Goku Black Rosé",             "mythical", 1270, 400, 91, 32),
    ("Dark Broly (Mask Broken)",    "mythical", 1480, 442, 84, 34),

    # ----- 20 LEGENDARY -----
    ("Super Saiyan Blue Goku",      "legendary", 980, 340, 88, 25),
    ("SSJ3 Goku",                   "legendary", 950, 330, 82, 24),
    ("Majin Vegeta",                "legendary", 970, 335, 84, 25),
    ("Future Gohan",                "legendary", 920, 320, 80, 23),
    ("Jiren Beyond Limits",         "legendary", 1050, 355, 86, 26),
    ("Super Buu",                   "legendary", 940, 325, 79, 24),
    ("Android 17 MVP",              "legendary", 910, 315, 90, 23),
    ("Hit",                         "legendary", 930, 322, 92, 24),
    ("Toppo Destroyer",             "legendary", 960, 330, 82, 25),
    ("Metal Cooler",                "legendary", 900, 312, 80, 22),
    ("Broly DBZ",                   "legendary", 1000, 345, 78, 26),
    ("Gogeta Blue",                 "legendary", 990, 342, 87, 26),
    ("Vegeta SSJ2",                 "legendary", 940, 322, 83, 24),
    ("Goku SSJ God",                "legendary", 970, 328, 85, 25),
    ("Super Saiyan 4 Goku",         "legendary", 985, 335, 84, 25),
    ("Super Saiyan 4 Vegeta",       "legendary", 975, 332, 83, 25),
    ("Golden Frieza",               "legendary", 945, 328, 85, 24),
    ("Mystic Gohan",                "legendary", 955, 330, 82, 24),
    ("Gotenks SSJ3",                "legendary", 930, 320, 86, 24),
    ("Kale SSJ Berserk",            "legendary", 920, 318, 81, 23),

    # ----- 20 EPIC -----
    ("Gohan SSJ2",                  "epic", 890, 250, 78, 20),
    ("Piccolo (Kami fused)",        "epic", 860, 245, 76, 19),
    ("Perfect Cell",                "epic", 900, 252, 77, 20),
    ("Frieza 100%",                 "epic", 880, 248, 75, 19),
    ("Future Trunks SSJ",           "epic", 850, 242, 79, 20),
    ("Ultimate Gohan",              "epic", 895, 250, 76, 20),
    ("King Piccolo",                "epic", 830, 235, 74, 18),
    ("Android 16",                  "epic", 870, 244, 72, 19),
    ("Android 18",                  "epic", 840, 240, 80, 20),
    ("Master Roshi Max",            "epic", 810, 232, 78, 18),
    ("Tien Shinhan Neo",            "epic", 820, 235, 76, 19),
    ("Raditz",                      "epic", 800, 228, 74, 18),
    ("Nappa",                       "epic", 810, 232, 72, 17),
    ("Zarbon",                      "epic", 800, 228, 75, 18),
    ("Dodoria",                     "epic", 815, 232, 70, 17),
    ("Dabura",                      "epic", 860, 242, 76, 19),
    ("Supreme Kai",                 "epic", 835, 238, 78, 19),
    ("Kibito",                      "epic", 820, 234, 77, 18),
    ("Android 19",                  "epic", 825, 236, 73, 18),
    ("Dr. Gero",                    "epic", 815, 232, 74, 18),

    # ----- 12 RARE -----
    ("Trunks (youth)",              "rare", 590, 67, 60, 12),
    ("Krillin",                     "rare", 580, 65, 62, 12),
    ("Yamcha",                      "rare", 570, 63, 65, 11),
    ("Chiaotzu",                    "rare", 550, 60, 68, 10),
    ("Pan",                         "rare", 560, 62, 66, 11),
    ("Videl",                       "rare", 570, 63, 64, 11),
    ("Recoome",                     "rare", 610, 70, 55, 11),
    ("Burter",                      "rare", 590, 67, 72, 12),
    ("Jeice",                       "rare", 580, 65, 70, 12),
    ("Goten",                       "rare", 575, 64, 65, 11),
    ("Kid Trunks",                  "rare", 575, 64, 66, 11),
    ("Mr. Satan",                   "rare", 550, 60, 55, 8),

    # ----- 8 COMMON -----
    ("Saibaman",                    "common", 380, 42, 45, 6),
    ("Frieza Soldier",              "common", 370, 40, 45, 5),
    ("Red Ribbon Soldier",          "common", 360, 38, 44, 5),
    ("Cell Junior",                 "common", 390, 44, 48, 6),
    ("World Tournament Rookie",     "common", 350, 36, 42, 4),
    ("Saiyan Recruit",              "common", 380, 42, 46, 5),
    ("Galactic Patrol Cadet",       "common", 370, 40, 45, 5),
    ("Capsule Corp Guard",          "common", 360, 38, 43, 4),
]

RARITY_ORDER = {"common": 1, "rare": 2, "epic": 3,
                "legendary": 4, "mythical": 5, "omni": 6}
RARITY_LABEL = {
    "common": "⚪ Common", "rare": "🔵 Rare", "epic": "🟣 Epic",
    "legendary": "🟡 Legendary", "mythical": "🔴 Mythical",
    "omni": "👑 Omni King",
}

# Fallback constants (only used if character isn't in CHARACTERS table)
RARITY_ATK = {"common": 40, "rare": 65, "epic": 240, "legendary": 330, "mythical": 410, "omni": 530}
RARITY_HP  = {"common": 370, "rare": 580, "epic": 850, "legendary": 950, "mythical": 1300, "omni": 1850}
RARITY_SPD = {"common": 44, "rare": 62, "epic": 76, "legendary": 84, "mythical": 90, "omni": 96}
RARITY_CRIT = {"common": 5, "rare": 11, "epic": 19, "legendary": 24, "mythical": 30, "omni": 36}

# ---------- GACHA ----------
GACHA_RATES = [("common", 38), ("rare", 28), ("epic", 16),
               ("legendary", 10), ("mythical", 6), ("omni", 2)]
GACHA_BANNERS = {
    "standard": {"name": "Standard Banner", "cost": 1, "bonus": {}},
    "hero":     {"name": "Hero Banner",     "cost": 1, "bonus": {"legendary": 1.5, "mythical": 1.5}},
    "god":      {"name": "God Banner",      "cost": 2, "bonus": {"mythical": 2.0, "omni": 2.0}},
    "omni":     {"name": "Omniverse Banner","cost": 3, "bonus": {"omni": 3.0}},
}

# ---------- 17 WEAPONS ----------
WEAPONS = {
    "Power Pole":             55, "Wooden Sword":          20,
    "Iron Sword":             65, "Saiyan Blade":          140,
    "Kamehameha Blade":       260, "Ultra Sword":          380,
    "Z Sword":                520, "Brave Sword (Tapion)": 620,
    "Destructo Blade":        720, "God Breaker":          820,
    "Black Hole Blade":       940, "Galaxy Cutter":        1080,
    "Crusher Edge":           1250, "Supernova Blade":     1450,
    "Janemba Dimension Sword":1680, "Deadly Divine Sword": 1950,
    "Vegito Spirit Sword":    2200,
}

# ---------- 17 ARMORS ----------
ARMORS = {
    "Turtle School Gi":     40,  "Demon Clan Gi":         60,
    "Leather Vest":         80,  "Saiyan Armor":          160,
    "Steel Armor":          210, "Yardrat Armor":         280,
    "God Armor":            360, "Battle Armor":          460,
    "Celestial Armor":      580, "Whis Symbol Gi":        720,
    "Katchin Armor":        900, "Doom Armor":            1100,
    "Ultra Guard":          1350, "Grand Priest Suit":    1650,
    "Kaio Suit":            1980, "Divine Battle Suit":   2300,
    "Heavenly Guardian Suit": 2700,
}

EQUIPMENT = {}
for _w, _b in WEAPONS.items():
    EQUIPMENT[_w] = ("weapon", _b)
for _a, _b in ARMORS.items():
    EQUIPMENT[_a] = ("armor", _b)

# ---------- SHOP — 6 CATEGORIES, bulk-buy IDs ----------
SHOP = {}
_shop_id = 1

def _register(name, price, currency, kind, amount=1):
    global _shop_id
    SHOP[_shop_id] = (name, price, currency, kind, amount)
    _shop_id += 1

# 1. WEAPONS
for _wname, _wval in WEAPONS.items():
    _register(_wname, _wval * 800, "yens", "weapon")

# 2. ARMORS
for _aname, _aval in ARMORS.items():
    _register(_aname, _aval * 900, "yens", "armor")

# 3. CRYSTALS
_register("Crystal x1",   30,   "gems", "crystal", 1)
_register("Crystal x10",  280,  "gems", "crystal", 10)
_register("Crystal x50",  1300, "gems", "crystal", 50)
_register("Crystal x100", 2400, "gems", "crystal", 100)

# 4. HEALING
_register("Potion",             100,  "yens", "heal", 1)
_register("Mega Potion",        250,  "yens", "heal", 1)
_register("Revive",             350,  "yens", "heal", 1)
_register("Senzu Bean",         800,  "yens", "heal", 1)
_register("Senzu Bean Pouch x5", 3800, "yens", "heal", 5)
_register("Divine Senzu Bean",  8000, "yens", "heal", 1)

# 5. FUSION MATERIALS
_register("Fusion Material",  250,  "gems", "fusion", 1)
_register("Fusion Core",      500,  "gems", "fusion", 1)
_register("Fusion Crystal",   1200, "gems", "fusion", 1)
_register("Fusion Catalyst",  2500, "gems", "fusion", 1)
_register("Potara Earrings",  4000, "gems", "fusion", 1)

# 6. TICKETS & KEYS
_register("Gacha Ticket",     60,   "gems", "ticket", 1)
_register("Gacha Ticket x10", 560,  "gems", "ticket", 10)
_register("Gacha Ticket x50", 2700, "gems", "ticket", 50)
_register("Gacha Ticket x100", 5200, "gems", "ticket", 100)
_register("Elite Key",        1200, "yens", "key_elite", 1)
_register("Boss Key",         2600, "yens", "key_boss", 1)

SHOP_CATEGORY_ORDER = [
    ("weapon",   "⚔️ Weapons"),
    ("armor",    "🛡️ Armors"),
    ("crystal",  "🔮 Crystals"),
    ("heal",     "🧪 Healing"),
    ("fusion",   "🧬 Fusion Materials"),
    ("ticket",   "🎫 Gacha Tickets & Keys"),
]

# ---------- 20 SKILLS ----------
SKILLS = {
    "Ki Blast": 9, "Kaioken": 6, "Instant Transmission": 10,
    "Spirit Bomb": 18, "Solar Flare": 12, "Destructo Disk": 16,
    "Ultra Instinct": 22, "Final Flash": 20, "God Kamehameha": 25,
    "Big Bang Attack": 28, "Black Hole Attack": 32, "Time Skip": 20,
    "Nova Burst": 26, "Dragon Fist": 30, "Final Explosion": 35,
    "Kamehameha Wave": 38, "Heavenly Rush": 42, "Universe Breaker": 48,
    "Halo Blast": 50, "Godly Burst": 54,
}
SKILL_ATK = {
    "Ki Blast": 100, "Kaioken": 116, "Instant Transmission": 114,
    "Spirit Bomb": 192, "Solar Flare": 171, "Destructo Disk": 190,
    "Ultra Instinct": 215, "Final Flash": 128, "God Kamehameha": 222,
    "Big Bang Attack": 214, "Black Hole Attack": 224, "Time Skip": 132,
    "Nova Burst": 220, "Dragon Fist": 198, "Final Explosion": 292,
    "Kamehameha Wave": 225, "Heavenly Rush": 390, "Universe Breaker": 344,
    "Halo Blast": 368, "Godly Burst": 465,
}

# ---------- DRAGON BALLS ----------
DRAGON_BALL_STARS = list(range(1, 8))

# ---------- SUMMONS ----------
SUMMONS = {
    "elite":     {"name": "Elite Ginyu Force",       "hp": 260000,  "dmg": 11000, "reward_mult": 5,  "key": "keys_elite"},
    "mythical":  {"name": "Mythical Perfect Cell",   "hp": 700000,  "dmg": 18000, "reward_mult": 5,  "key": "keys_boss"},
    "legendary": {"name": "God of Destruction Beerus","hp": 1100000, "dmg": 26000, "reward_mult": 5,  "key": "keys_boss"},
}

# ---------- CLAN RAIDS ----------
CLAN_RAIDS = {
    "Perfect Cell": {"hp": 40000, "dmg": 399,   "reward_yens": 25000000, "reward_gems": 50000, "reward_crystals": 3000, "reward_tickets": 50, "reward_skill_points": 100},
    "Frieza":       {"hp": 70000, "dmg": 1200,  "reward_yens": 50000000, "reward_gems": 90000, "reward_crystals": 6000, "reward_tickets": 70, "reward_skill_points": 120},
    "Majin Buu":    {"hp": 95000, "dmg": 1700,  "reward_yens": 80000000, "reward_gems": 120000,"reward_crystals": 8000, "reward_tickets": 100,"reward_skill_points": 150},
    "Beerus":       {"hp": 140000,"dmg": 2400,  "reward_yens": 120000000,"reward_gems": 180000,"reward_crystals": 10000,"reward_tickets": 150,"reward_skill_points": 190},
}

# ---------- CLAN PERKS ----------
CLAN_PERKS = {
    "war_drums":     {"name": "War Drums",       "cost": 200,  "desc": "+5% ATK for all members"},
    "iron_wall":     {"name": "Iron Wall",       "cost": 200,  "desc": "+5% HP for all members"},
    "ki_reserves":   {"name": "Ki Reserves",     "cost": 300,  "desc": "+10% skill points on wins"},
    "greedy_vault":  {"name": "Greedy Vault",    "cost": 400,  "desc": "+10% yens on wins"},
    "crit_focus":    {"name": "Crit Focus",      "cost": 500,  "desc": "+3% crit chance"},
    "kai_blessing":  {"name": "Kai Blessing",    "cost": 600,  "desc": "+1 extra daily reward"},
    "raid_lust":     {"name": "Raid Lust",       "cost": 700,  "desc": "+15% raid damage"},
    "senzu_stock":   {"name": "Senzu Stock",     "cost": 800,  "desc": "Free Senzu every 24h"},
    "treasure_lord": {"name": "Treasure Lord",   "cost": 900,  "desc": "+20% clan treasure donations"},
    "mystic_forge":  {"name": "Mystic Forge",    "cost": 1000, "desc": "Fusion material drop x2"},
    "omni_focus":    {"name": "Omni Focus",      "cost": 1500, "desc": "+1% omni gacha rate"},
    "dragon_aura":   {"name": "Dragon Aura",     "cost": 2000, "desc": "+10% dragon ball drop"},
}

# ---------- WORLD RAID (owner-started, persistent HP, 0 cooldown) ----------
RAID = {"name": "Multiverse Omega Dragon", "hp": 120000, "dmg": 500,
        "reward_mult": 10, "attack_cooldown_s": 0}

# ---------- RANKS ----------
RANKS = {1: "Beginner", 2: "Novice", 3: "King", 4: "Emperor", 5: "Demigod",
         6: "Immortal", 7: "Titan", 8: "Oracle", 9: "Celestial", 10: "God"}
RANKUP_CRYSTALS = {1: 500, 2: 4000, 3: 20000, 4: 70000, 5: 150000,
                   6: 300000, 7: 600000, 8: 1000000, 9: 2000000}
RANK_BONUS = 0.15  # +15% stats per rank (multiplicative)

# ---------- STARTER PACK ----------
STARTER_PACK = {"pool": ["rare", "epic", "legendary"],
                "bonus_yens": 1000, "bonus_gems": 50, "bonus_tickets": 3}

# ---------- FUSION ----------
FUSION_MATERIALS = {"Fusion Material": 1, "Fusion Core": 2,
                    "Fusion Crystal": 3, "Fusion Catalyst": 4,
                    "Potara Earrings": 5}
FUSION_CRYSTAL_COST = 25

# ---------- HEALING (fraction of max HP) ----------
HEALING = {
    "Potion":             0.30,
    "Mega Potion":        0.60,
    "Revive":             0.80,
    "Senzu Bean":         1.00,
    "Divine Senzu Bean":  1.00,
    "Senzu Bean Pouch x5": 1.00,
}

# ---------- ACHIEVEMENTS ----------
ACHIEVEMENTS = {
    "first_blood":      {"name": "First Blood",       "desc": "Win your first battle",       "yens": 1000,   "gems": 10,   "crystals": 0},
    "battle_10":        {"name": "Rookie Fighter",    "desc": "Complete 10 battles",         "yens": 5000,   "gems": 25,   "crystals": 1},
    "battle_50":        {"name": "Veteran",           "desc": "Complete 50 battles",         "yens": 25000,  "gems": 100,  "crystals": 3},
    "battle_100":       {"name": "100th Battle",      "desc": "Complete 100 battles",        "yens": 100000, "gems": 400,  "crystals": 10},
    "battle_500":       {"name": "Warlord",           "desc": "Complete 500 battles",        "yens": 500000, "gems": 2000, "crystals": 50},
    "flawless":         {"name": "Flawless Victory",  "desc": "Win without taking damage",   "yens": 20000,  "gems": 100,  "crystals": 5},
    "boss_slayer":      {"name": "Boss Slayer",       "desc": "Defeat a world boss",         "yens": 50000,  "gems": 300,  "crystals": 15},
    "summon_hunter":    {"name": "Summon Hunter",     "desc": "Defeat a summon boss",        "yens": 80000,  "gems": 500,  "crystals": 20},
    "clan_founder":     {"name": "Clan Founder",      "desc": "Create a clan",               "yens": 20000,  "gems": 100,  "crystals": 3},
    "clan_leader":      {"name": "Clan Leader",       "desc": "Become a clan leader",        "yens": 10000,  "gems": 50,   "crystals": 2},
    "dragon_collector": {"name": "Dragon Collector",  "desc": "Collect all 7 dragon balls",  "yens": 150000, "gems": 600,  "crystals": 30},
    "mythical_owner":   {"name": "Mythical Owner",    "desc": "Obtain a mythical character", "yens": 50000,  "gems": 250,  "crystals": 15},
    "omni_owner":       {"name": "Omni Owner",        "desc": "Obtain an omni character",    "yens": 500000, "gems": 2000, "crystals": 100},
    "rich":             {"name": "Millionaire",       "desc": "Have 1,000,000 yens",         "yens": 50000,  "gems": 100,  "crystals": 5},
    "gem_hoarder":      {"name": "Gem Hoarder",       "desc": "Have 1,000 gems",             "yens": 20000,  "gems": 100,  "crystals": 3},
    "fusion_master":    {"name": "Fusion Master",     "desc": "Complete a fusion",           "yens": 30000,  "gems": 150,  "crystals": 8},
    "rank_5":           {"name": "Demigod",           "desc": "Reach rank 5",                "yens": 50000,  "gems": 250,  "crystals": 15},
    "rank_10":          {"name": "God",               "desc": "Reach rank 10",               "yens": 1000000, "gems": 5000, "crystals": 200},
    "explore_vet":      {"name": "Explorer",          "desc": "Defeat 100 NPCs",             "yens": 30000,  "gems": 150,  "crystals": 8},
    "raid_warrior":     {"name": "Raid Warrior",      "desc": "Help defeat the world raid",  "yens": 100000, "gems": 500,  "crystals": 20},
    "clan_raid_clear":  {"name": "Clan Champion",     "desc": "Clear a clan raid boss",      "yens": 200000, "gems": 800,  "crystals": 30},
    "traveler":         {"name": "Traveler",          "desc": "Travel to Omniverse",         "yens": 50000,  "gems": 200,  "crystals": 10},
}

# ---------- QUESTS ----------
DAILY_QUESTS = {
    "daily_npc_10":     {"name": "Fight 10 NPCs",      "target": 10,  "yens": 5000,  "gems": 25,  "crystals": 1},
    "daily_win_5":      {"name": "Win 5 battles",      "target": 5,   "yens": 4000,  "gems": 20,  "crystals": 1},
    "daily_earn_5000":  {"name": "Earn 5,000 yens",    "target": 5000, "yens": 3000,  "gems": 15,  "crystals": 0},
    "daily_gacha_1":    {"name": "Roll gacha once",    "target": 1,   "yens": 2000,  "gems": 30,  "crystals": 0},
}
WEEKLY_QUESTS = {
    "weekly_npc_100":   {"name": "Fight 100 NPCs",     "target": 100, "yens": 50000, "gems": 250, "crystals": 10},
    "weekly_boss_3":    {"name": "Defeat 3 bosses",    "target": 3,   "yens": 30000, "gems": 150, "crystals": 5},
    "weekly_earn_50k":  {"name": "Earn 50,000 yens",   "target": 50000, "yens": 25000, "gems": 100, "crystals": 3},
    "weekly_gacha_10":  {"name": "Roll gacha 10 times", "target": 10, "yens": 20000, "gems": 200, "crystals": 5},
}
MONTHLY_QUESTS = {
    "monthly_npc_500":  {"name": "Fight 500 NPCs",     "target": 500, "yens": 500000, "gems": 2000, "crystals": 50},
    "monthly_win_250":  {"name": "Win 250 battles",    "target": 250, "yens": 400000, "gems": 1500, "crystals": 40},
    "monthly_earn_500k": {"name": "Earn 500,000 yens", "target": 500000, "yens": 300000, "gems": 1000, "crystals": 30},
    "monthly_summon_5": {"name": "Defeat 5 summons",   "target": 5,   "yens": 350000, "gems": 1200, "crystals": 35},
}
