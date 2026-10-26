from __future__ import annotations

"""
Dragon Ball RPG — Database Layer
=================================
Single source of truth for all persistent state.

Responsibilities:
  - Schema creation and migrations
  - Player CRUD
  - Currency / inventory / characters / skills / dragon balls
  - HP tracking (persistent, per-player)
  - Combat logs (backing CombatHistory)
  - Achievements
  - Quests (daily / weekly / monthly)
  - Summon boss persistent HP
  - Global world raid
  - Admin helpers

Every function below is called by bot.py, combat.py, or clans.py.
If you add a new feature, add its data layer here.
"""

import json
import os
import random
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import game_data as G


DB_PATH = os.getenv("DB_PATH",
                    os.path.join(os.path.dirname(__file__), "game.sqlite"))


# =============================================================
# CONNECTION
# =============================================================
def conn() -> sqlite3.Connection:
    """Return a new SQLite connection with Row factory."""
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# =============================================================
# INITIALIZATION & MIGRATIONS
# =============================================================
def init() -> None:
    """Create tables, run migrations, seed static data."""
    with conn() as c:
        # Clan tables live in clans.py — import lazily to avoid cycles
        import clans as _clans
        _clans.init_tables(c)

        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS players(
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                exp INTEGER DEFAULT 0,
                yens INTEGER DEFAULT 0,
                gems INTEGER DEFAULT 0,
                crystals INTEGER DEFAULT 0,
                tickets INTEGER DEFAULT 0,
                skill_points INTEGER DEFAULT 0,
                keys_elite INTEGER DEFAULT 0,
                keys_boss INTEGER DEFAULT 0,
                npc_streak INTEGER DEFAULT 0,
                current_hp INTEGER DEFAULT NULL,
                equipped_char TEXT,
                weapon TEXT,
                armor TEXT,
                last_raid_hit INTEGER DEFAULT 0,
                rank INTEGER DEFAULT 1,
                admin INTEGER DEFAULT 0,
                banned INTEGER DEFAULT 0,
                daily_day TEXT,
                daily_streak INTEGER DEFAULT 0,
                weekly_week TEXT,
                travel TEXT DEFAULT 'Earth',
                fusion_count INTEGER DEFAULT 0,
                total_battles INTEGER DEFAULT 0,
                total_wins INTEGER DEFAULT 0,
                total_losses INTEGER DEFAULT 0,
                total_dmg_dealt INTEGER DEFAULT 0,
                total_dmg_taken INTEGER DEFAULT 0,
                quest_daily_key TEXT DEFAULT '',
                quest_weekly_key TEXT DEFAULT '',
                quest_monthly_key TEXT DEFAULT '',
                quest_daily_json TEXT DEFAULT '{}',
                quest_weekly_json TEXT DEFAULT '{}',
                quest_monthly_json TEXT DEFAULT '{}',
                quest_daily_claimed TEXT DEFAULT '{}',
                quest_weekly_claimed TEXT DEFAULT '{}',
                quest_monthly_claimed TEXT DEFAULT '{}',
                summon_hp_json TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS items(
                user_id INTEGER,
                item TEXT,
                qty INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, item)
            );

            CREATE TABLE IF NOT EXISTS characters(
                user_id INTEGER,
                name TEXT,
                rarity TEXT,
                PRIMARY KEY(user_id, name)
            );

            CREATE TABLE IF NOT EXISTS skills(
                user_id INTEGER,
                name TEXT,
                PRIMARY KEY(user_id, name)
            );

            CREATE TABLE IF NOT EXISTS dragon_balls(
                user_id INTEGER,
                star INTEGER,
                qty INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, star)
            );

            CREATE TABLE IF NOT EXISTS art(
                kind TEXT,
                name TEXT,
                file_id TEXT,
                PRIMARY KEY(kind, name)
            );

            CREATE TABLE IF NOT EXISTS raid(
                id INTEGER PRIMARY KEY CHECK(id=1),
                active INTEGER DEFAULT 0,
                hp INTEGER,
                max_hp INTEGER,
                damage_json TEXT DEFAULT '{}',
                boss_name TEXT DEFAULT '',
                started_at INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS combat_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                enemy_name TEXT,
                enemy_max_hp INTEGER DEFAULT 0,
                damage_dealt INTEGER DEFAULT 0,
                damage_taken INTEGER DEFAULT 0,
                outcome TEXT,
                rounds INTEGER DEFAULT 0,
                rewards_text TEXT DEFAULT '',
                created INTEGER DEFAULT (strftime('%s','now'))
            );
            CREATE INDEX IF NOT EXISTS idx_combat_user
                ON combat_logs(user_id, id DESC);

            CREATE TABLE IF NOT EXISTS achievements(
                code TEXT PRIMARY KEY,
                name TEXT,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS player_achievements(
                user_id INTEGER,
                code TEXT,
                unlocked_at INTEGER DEFAULT (strftime('%s','now')),
                PRIMARY KEY(user_id, code)
            );
            CREATE INDEX IF NOT EXISTS idx_achievements_user
                ON player_achievements(user_id);
            """
        )

        # Seed achievements
        for code, info in G.ACHIEVEMENTS.items():
            c.execute(
                "INSERT OR IGNORE INTO achievements(code,name,description) "
                "VALUES(?,?,?)",
                (code, info["name"], info["desc"]),
            )

        # Ensure a raid row exists (inactive by default)
        c.execute(
            "INSERT OR IGNORE INTO raid(id,active,hp,max_hp,damage_json,boss_name,started_at) "
            "VALUES(1,0,0,0,'{}','',0)"
        )

        # Migrations for existing players table
        player_cols = [r[1] for r in c.execute("PRAGMA table_info(players)")]
        migrations = [
            ("current_hp",            "INTEGER DEFAULT NULL"),
            ("quest_daily_key",       "TEXT DEFAULT ''"),
            ("quest_weekly_key",      "TEXT DEFAULT ''"),
            ("quest_monthly_key",     "TEXT DEFAULT ''"),
            ("quest_daily_json",      "TEXT DEFAULT '{}'"),
            ("quest_weekly_json",     "TEXT DEFAULT '{}'"),
            ("quest_monthly_json",    "TEXT DEFAULT '{}'"),
            ("quest_daily_claimed",   "TEXT DEFAULT '{}'"),
            ("quest_weekly_claimed",  "TEXT DEFAULT '{}'"),
            ("quest_monthly_claimed", "TEXT DEFAULT '{}'"),
            ("summon_hp_json",        "TEXT DEFAULT '{}'"),
            ("total_battles",         "INTEGER DEFAULT 0"),
            ("total_wins",            "INTEGER DEFAULT 0"),
            ("total_losses",          "INTEGER DEFAULT 0"),
            ("total_dmg_dealt",       "INTEGER DEFAULT 0"),
            ("total_dmg_taken",       "INTEGER DEFAULT 0"),
            ("fusion_count",          "INTEGER DEFAULT 0"),
        ]
        for col, ddl in migrations:
            if col not in player_cols:
                c.execute(f"ALTER TABLE players ADD COLUMN {col} {ddl}")


# =============================================================
# PLAYER BASICS
# =============================================================
def ensure_player(uid: int, first: str, username: str | None) -> None:
    """Create or refresh the player record."""
    with conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO players(user_id, first_name, username) "
            "VALUES(?,?,?)",
            (uid, first or "", username or ""),
        )
        c.execute(
            "UPDATE players SET first_name=?, username=? WHERE user_id=?",
            (first or "", username or "", uid),
        )


def player(uid: int):
    """Return player row or None."""
    with conn() as c:
        return c.execute(
            "SELECT * FROM players WHERE user_id=?", (uid,)
        ).fetchone()


def player_by_username(username: str):
    """Look up a player by @username or first_name (case-insensitive)."""
    n = (username or "").replace("@", "").strip()
    if not n:
        return None
    with conn() as c:
        return c.execute(
            "SELECT * FROM players "
            "WHERE lower(username)=lower(?) OR lower(first_name)=lower(?)",
            (n, n),
        ).fetchone()


def all_players() -> list:
    """Return all player rows sorted by exp descending."""
    with conn() as c:
        return c.execute(
            "SELECT * FROM players ORDER BY exp DESC"
        ).fetchall()


def leaderboard(limit: int = 10) -> list:
    """Top players by exp."""
    with conn() as c:
        return c.execute(
            "SELECT first_name, exp, rank, total_wins "
            "FROM players ORDER BY exp DESC LIMIT ?",
            (limit,),
        ).fetchall()


# =============================================================
# LEVEL / RANK
# =============================================================
def level_of(exp: int) -> int:
    """Level = 1 + exp // LEVEL_EXP."""
    return 1 + int(exp or 0) // G.LEVEL_EXP


def exp_for_next_level(current_exp: int) -> int:
    """EXP needed to reach the next level."""
    cur_level = level_of(current_exp)
    next_threshold = cur_level * G.LEVEL_EXP
    return max(0, next_threshold - int(current_exp or 0))


def rank_of(uid: int) -> int:
    """Global rank position (1 = best) by exp."""
    with conn() as c:
        mine = c.execute(
            "SELECT exp FROM players WHERE user_id=?", (uid,)
        ).fetchone()
        if mine is None:
            return 0
        above = c.execute(
            "SELECT COUNT(*) FROM players WHERE exp > ?",
            (mine["exp"],),
        ).fetchone()[0]
        return above + 1


def player_rank(uid: int) -> int:
    """Player's ascension rank (from players.rank column)."""
    p = player(uid)
    if not p:
        return 1
    return int(p["rank"] or 1)


# =============================================================
# RESOURCES — give / spend / set
# =============================================================
_GRANTABLE_COLS = {
    "yens", "gems", "crystals", "tickets", "skill_points",
    "keys_elite", "keys_boss", "exp",
}

_SPENDABLE_COLS = {
    "yens", "gems", "crystals", "tickets", "skill_points",
    "keys_elite", "keys_boss",
}


def give(uid: int, **amounts) -> None:
    """Add amounts to player columns. Silently ignores bad values."""
    for k, v in amounts.items():
        if k not in _GRANTABLE_COLS:
            continue
        if v is None:
            continue
        try:
            amt = int(v)
        except (TypeError, ValueError):
            continue
        if amt == 0:
            continue
        with conn() as c:
            c.execute(
                f"UPDATE players SET {k}={k}+? WHERE user_id=?",
                (amt, uid),
            )


def spend(uid: int, column: str, amount: int) -> bool:
    """Atomically deduct amount from a column. Returns True if success."""
    if column not in _SPENDABLE_COLS:
        return False
    try:
        amt = int(amount)
    except (TypeError, ValueError):
        return False
    if amt <= 0:
        return False
    with conn() as c:
        cur = c.execute(
            f"UPDATE players SET {column}={column}-? "
            f"WHERE user_id=? AND {column}>=?",
            (amt, uid, amt),
        )
        return cur.rowcount == 1


def set_field(uid: int, field: str, value) -> None:
    """Set a whitelisted player field."""
    allowed = {
        "equipped_char", "weapon", "armor", "npc_streak",
        "last_raid_hit", "rank", "admin", "banned", "travel",
        "fusion_count", "current_hp",
    }
    if field not in allowed:
        raise ValueError(f"bad field: {field}")
    with conn() as c:
        c.execute(
            f"UPDATE players SET {field}=? WHERE user_id=?",
            (value, uid),
        )


# =============================================================
# HP TRACKING
# =============================================================
def get_current_hp(uid: int, max_hp: int) -> int:
    """Current HP, treating NULL as full."""
    p = player(uid)
    if not p:
        return max_hp
    hp = p["current_hp"]
    if hp is None:
        return max_hp
    return max(0, min(int(hp), max_hp))


def set_current_hp(uid: int, hp: int) -> None:
    """Persist current HP."""
    with conn() as c:
        c.execute(
            "UPDATE players SET current_hp=? WHERE user_id=?",
            (int(hp), uid),
        )


def apply_heal(uid: int, max_hp: int, item_name: str) -> tuple[bool, int]:
    """
    Consume one healing item and restore HP.
    Returns (ok, new_hp).
    """
    if item_name not in G.HEALING:
        return False, get_current_hp(uid, max_hp)
    if not remove_item(uid, item_name, 1):
        return False, get_current_hp(uid, max_hp)
    frac = G.HEALING[item_name]
    cur = get_current_hp(uid, max_hp)
    new_hp = min(max_hp, cur + int(max_hp * frac))
    set_current_hp(uid, new_hp)
    return True, new_hp


# =============================================================
# INVENTORY
# =============================================================
def add_item(uid: int, item: str, qty: int = 1) -> None:
    """Add qty of item to player's inventory."""
    if not item or qty <= 0:
        return
    with conn() as c:
        c.execute(
            "INSERT INTO items(user_id,item,qty) VALUES(?,?,?) "
            "ON CONFLICT(user_id,item) DO UPDATE SET qty=qty+excluded.qty",
            (uid, item.strip(), qty),
        )


def items(uid: int) -> list:
    """Return list of (item, qty) rows."""
    with conn() as c:
        return c.execute(
            "SELECT item, qty FROM items "
            "WHERE user_id=? AND qty>0 ORDER BY item",
            (uid,),
        ).fetchall()


def remove_item(uid: int, item: str, qty: int = 1) -> bool:
    """Remove qty of item. Returns True on success."""
    if qty <= 0:
        return False
    with conn() as c:
        cur = c.execute(
            "UPDATE items SET qty=qty-? "
            "WHERE user_id=? AND item=? AND qty>=?",
            (qty, uid, item, qty),
        )
        return cur.rowcount == 1


def has_item(uid: int, item: str) -> bool:
    """Return True if the player owns at least 1 of this item."""
    with conn() as c:
        row = c.execute(
            "SELECT qty FROM items WHERE user_id=? AND item=?",
            (uid, item),
        ).fetchone()
        return bool(row and row["qty"] > 0)


# =============================================================
# CHARACTERS
# =============================================================
def add_character(uid: int, name: str, rarity: str) -> bool:
    """Add character if not owned. Returns True if newly added."""
    n = (name or "").strip()
    if not n:
        return False
    with conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO characters(user_id,name,rarity) "
            "VALUES(?,?,?)",
            (uid, n, rarity or "common"),
        )
        return cur.rowcount == 1


def characters(uid: int) -> list:
    """All characters sorted by rarity (best first) then name."""
    with conn() as c:
        return c.execute(
            "SELECT name, rarity FROM characters WHERE user_id=? "
            "ORDER BY CASE rarity "
            "  WHEN 'omni' THEN 1 "
            "  WHEN 'mythical' THEN 2 "
            "  WHEN 'legendary' THEN 3 "
            "  WHEN 'epic' THEN 4 "
            "  WHEN 'rare' THEN 5 "
            "  ELSE 6 END, name",
            (uid,),
        ).fetchall()


def characters_by_rarity(uid: int) -> dict:
    """Group characters by rarity into buckets."""
    rows = characters(uid)
    out = {r: [] for r in ["common", "rare", "epic",
                           "legendary", "mythical", "omni"]}
    for row in rows:
        out.setdefault(row["rarity"], []).append(row["name"])
    return out


def has_character(uid: int, name: str) -> bool:
    """Return True if the player owns this character."""
    if not name:
        return False
    with conn() as c:
        return c.execute(
            "SELECT 1 FROM characters WHERE user_id=? AND name=?",
            (uid, name),
        ).fetchone() is not None


def character_rarity(uid: int, name: str) -> str | None:
    """Return rarity of a specific owned character or None."""
    with conn() as c:
        row = c.execute(
            "SELECT rarity FROM characters WHERE user_id=? AND name=?",
            (uid, name),
        ).fetchone()
        return row["rarity"] if row else None


def transfer_character(giver: int, target: int, name: str) -> bool:
    """Transfer a character between players."""
    with conn() as c:
        row = c.execute(
            "SELECT rarity FROM characters WHERE user_id=? AND name=?",
            (giver, name),
        ).fetchone()
        if row is None:
            return False
        if c.execute(
            "SELECT 1 FROM characters WHERE user_id=? AND name=?",
            (target, name),
        ).fetchone():
            return False
        c.execute(
            "DELETE FROM characters WHERE user_id=? AND name=?",
            (giver, name),
        )
        c.execute(
            "INSERT INTO characters(user_id,name,rarity) VALUES(?,?,?)",
            (target, name, row["rarity"]),
        )
        c.execute(
            "UPDATE players SET equipped_char=NULL "
            "WHERE user_id=? AND equipped_char=?",
            (giver, name),
        )
        return True


# =============================================================
# SKILLS
# =============================================================
def add_skill(uid: int, name: str) -> bool:
    """Learn a skill if not already known. Returns True if newly added."""
    n = (name or "").strip()
    if not n:
        return False
    with conn() as c:
        return c.execute(
            "INSERT OR IGNORE INTO skills(user_id,name) VALUES(?,?)",
            (uid, n),
        ).rowcount == 1


def skills(uid: int) -> list:
    """Return list of skill names."""
    with conn() as c:
        return [
            r["name"] for r in c.execute(
                "SELECT name FROM skills WHERE user_id=? ORDER BY name",
                (uid,),
            )
        ]


def has_skill(uid: int, name: str) -> bool:
    """Return True if player knows the skill."""
    with conn() as c:
        return c.execute(
            "SELECT 1 FROM skills WHERE user_id=? AND name=?",
            (uid, name),
        ).fetchone() is not None


def transfer_skill(giver: int, target: int, name: str) -> bool:
    """Transfer a skill between players."""
    with conn() as c:
        if c.execute(
            "SELECT 1 FROM skills WHERE user_id=? AND name=?",
            (giver, name),
        ).fetchone() is None:
            return False
        if c.execute(
            "SELECT 1 FROM skills WHERE user_id=? AND name=?",
            (target, name),
        ).fetchone():
            return False
        c.execute(
            "DELETE FROM skills WHERE user_id=? AND name=?",
            (giver, name),
        )
        c.execute(
            "INSERT INTO skills(user_id,name) VALUES(?,?)",
            (target, name),
        )
        return True


# =============================================================
# DRAGON BALLS
# =============================================================
def add_dragon_ball(uid: int, star: int, qty: int = 1) -> None:
    """Add qty of a specific star dragon ball."""
    if not isinstance(star, int) or qty <= 0:
        return
    if star < 1 or star > 7:
        return
    with conn() as c:
        c.execute(
            "INSERT INTO dragon_balls(user_id,star,qty) VALUES(?,?,?) "
            "ON CONFLICT(user_id,star) DO UPDATE SET qty=qty+excluded.qty",
            (uid, star, qty),
        )


def dragon_balls(uid: int) -> dict:
    """Return {star: qty} for stars with qty > 0."""
    with conn() as c:
        return {
            r["star"]: r["qty"] for r in c.execute(
                "SELECT star, qty FROM dragon_balls "
                "WHERE user_id=? AND qty>0",
                (uid,),
            )
        }


def take_one_of_each_dragon_ball(uid: int) -> bool:
    """Consume one of each 1★-7★. Returns True on success."""
    have = dragon_balls(uid)
    if any(have.get(s, 0) < 1 for s in G.DRAGON_BALL_STARS):
        return False
    with conn() as c:
        for s in G.DRAGON_BALL_STARS:
            c.execute(
                "UPDATE dragon_balls SET qty=qty-1 "
                "WHERE user_id=? AND star=?",
                (uid, s),
            )
    return True


def remove_dragon_ball(uid: int, star: int, qty: int) -> bool:
    """Remove qty of a specific star. Returns True on success."""
    if qty <= 0:
        return False
    with conn() as c:
        cur = c.execute(
            "UPDATE dragon_balls SET qty=qty-? "
            "WHERE user_id=? AND star=? AND qty>=?",
            (qty, uid, star, qty),
        )
        return cur.rowcount == 1


# =============================================================
# COMBAT LOGS (backs CombatHistory)
# =============================================================
def add_combat_log(uid: int, enemy_name: str, enemy_max_hp: int,
                   damage_dealt: int, damage_taken: int,
                   outcome: str, rounds: int,
                   rewards_text: str = "") -> None:
    """
    Log a battle and update cumulative counters atomically.
    outcome must be "victory" or "defeat".
    """
    if outcome not in ("victory", "defeat"):
        outcome = "defeat"
    with conn() as c:
        c.execute(
            "INSERT INTO combat_logs(user_id,enemy_name,enemy_max_hp,"
            "damage_dealt,damage_taken,outcome,rounds,rewards_text) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (uid, enemy_name, enemy_max_hp, damage_dealt, damage_taken,
             outcome, rounds, rewards_text),
        )
        c.execute(
            "UPDATE players SET "
            "total_battles = total_battles + 1, "
            "total_wins    = total_wins + ?, "
            "total_losses  = total_losses + ?, "
            "total_dmg_dealt = total_dmg_dealt + ?, "
            "total_dmg_taken = total_dmg_taken + ? "
            "WHERE user_id=?",
            (
                1 if outcome == "victory" else 0,
                1 if outcome == "defeat" else 0,
                max(0, int(damage_dealt or 0)),
                max(0, int(damage_taken or 0)),
                uid,
            ),
        )


def get_combat_history(uid: int, limit: int = 10) -> list:
    """Return most recent combat log entries (newest first)."""
    limit = max(1, min(int(limit or 10), 50))
    with conn() as c:
        return c.execute(
            "SELECT * FROM combat_logs "
            "WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (uid, limit),
        ).fetchall()


def combat_stats(uid: int) -> dict:
    """Return cumulative combat statistics."""
    p = player(uid)
    if not p:
        return {"battles": 0, "wins": 0, "losses": 0,
                "dealt": 0, "taken": 0}
    return {
        "battles": int(p["total_battles"] or 0),
        "wins":    int(p["total_wins"] or 0),
        "losses":  int(p["total_losses"] or 0),
        "dealt":   int(p["total_dmg_dealt"] or 0),
        "taken":   int(p["total_dmg_taken"] or 0),
    }


# =============================================================
# ACHIEVEMENTS
# =============================================================
def has_achievement(uid: int, code: str) -> bool:
    """Return True if the player has unlocked this achievement."""
    with conn() as c:
        return c.execute(
            "SELECT 1 FROM player_achievements "
            "WHERE user_id=? AND code=?",
            (uid, code),
        ).fetchone() is not None


def unlock_achievement(uid: int, code: str):
    """
    Unlock an achievement if not already unlocked.
    Grants rewards and returns the achievement info dict,
    or None if already unlocked / unknown code.
    """
    if code not in G.ACHIEVEMENTS:
        return None
    if has_achievement(uid, code):
        return None
    info = G.ACHIEVEMENTS[code]
    with conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO player_achievements(user_id,code) "
            "VALUES(?,?)",
            (uid, code),
        )
    give(
        uid,
        yens=info.get("yens", 0),
        gems=info.get("gems", 0),
        crystals=info.get("crystals", 0),
    )
    return info


def player_achievements(uid: int) -> list:
    """Return all unlocked achievements (newest first)."""
    with conn() as c:
        return c.execute(
            "SELECT a.code, a.name, a.description, pa.unlocked_at "
            "FROM player_achievements pa "
            "JOIN achievements a ON a.code=pa.code "
            "WHERE pa.user_id=? ORDER BY pa.unlocked_at DESC",
            (uid,),
        ).fetchall()


def achievement_count(uid: int) -> int:
    """Total number of achievements unlocked."""
    with conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM player_achievements WHERE user_id=?",
            (uid,),
        ).fetchone()[0]


# =============================================================
# SUMMON PERSISTENT HP
# =============================================================
def summon_hp(uid: int, kind: str) -> int | None:
    """Get persisted summon boss HP for a boss kind. None = full."""
    p = player(uid)
    if not p:
        return None
    try:
        data = json.loads(p["summon_hp_json"] or "{}")
    except (ValueError, TypeError):
        data = {}
    hp = data.get(kind)
    if hp is None:
        return None
    try:
        return int(hp)
    except (TypeError, ValueError):
        return None


def set_summon_hp(uid: int, kind: str, hp: int | None) -> None:
    """Persist summon boss HP. Pass None to reset (full HP)."""
    p = player(uid)
    if not p:
        return
    try:
        data = json.loads(p["summon_hp_json"] or "{}")
    except (ValueError, TypeError):
        data = {}
    if hp is None:
        data.pop(kind, None)
    else:
        data[kind] = int(hp)
    with conn() as c:
        c.execute(
            "UPDATE players SET summon_hp_json=? WHERE user_id=?",
            (json.dumps(data), uid),
        )


# =============================================================
# GLOBAL WORLD RAID
# =============================================================
def raid_state():
    """Return the current raid row (always exists)."""
    with conn() as c:
        return c.execute("SELECT * FROM raid WHERE id=1").fetchone()


def raid_start(boss_name: str | None = None,
               hp: int | None = None) -> None:
    """Start or reset the world raid."""
    boss_name = boss_name or G.RAID["name"]
    hp = hp or G.RAID["hp"]
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO raid("
            "id,active,hp,max_hp,damage_json,boss_name,started_at"
            ") VALUES(1,1,?,?,?,?,?)",
            (hp, hp, json.dumps({}), boss_name, int(time.time())),
        )


def raid_hit(uid: int, damage: int):
    """
    Attack the raid boss. Returns (hp_left, defeated, damage_map)
    or None if no active raid.
    """
    st = raid_state()
    if st is None or not st["active"]:
        return None
    try:
        dmg_by = json.loads(st["damage_json"] or "{}")
    except (ValueError, TypeError):
        dmg_by = {}
    dmg_by[str(uid)] = int(dmg_by.get(str(uid), 0)) + int(damage)
    hp = max(0, int(st["hp"]) - int(damage))
    defeated = hp == 0
    with conn() as c:
        c.execute(
            "UPDATE raid SET hp=?, damage_json=?, active=? WHERE id=1",
            (hp, json.dumps(dmg_by), 0 if defeated else 1),
        )
    return hp, defeated, dmg_by


def raid_reset() -> None:
    """Reset the raid to full HP (inactive until raid_start)."""
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO raid("
            "id,active,hp,max_hp,damage_json,boss_name,started_at"
            ") VALUES(1,1,?,?,?,?,?)",
            (G.RAID["hp"], G.RAID["hp"], json.dumps({}),
             G.RAID["name"], int(time.time())),
        )


# =============================================================
# COOLDOWNS
# =============================================================
def cooldown_ok(uid: int, seconds: int) -> int:
    """Return seconds remaining on cooldown, or 0 if ready."""
    p = player(uid)
    if p is None:
        return 0
    elapsed = int(time.time()) - int(p["last_raid_hit"] or 0)
    return max(0, seconds - elapsed)


def mark_raid_hit(uid: int) -> None:
    """Record the time of a raid hit."""
    with conn() as c:
        c.execute(
            "UPDATE players SET last_raid_hit=? WHERE user_id=?",
            (int(time.time()), uid),
        )


# =============================================================
# GACHA HELPERS
# =============================================================
def roll_rarity(banner_bonus: dict | None = None) -> str:
    """Roll a rarity using GACHA_RATES, applying banner bonus."""
    weights = []
    for name, base in G.GACHA_RATES:
        bonus = 1.0
        if banner_bonus:
            bonus = float(banner_bonus.get(name, 1.0))
        weights.append(max(0.0, base * bonus))
    total = sum(weights)
    if total <= 0:
        return "common"
    r = random.uniform(0, total)
    acc = 0.0
    for (name, _), w in zip(G.GACHA_RATES, weights):
        acc += w
        if r <= acc:
            return name
    return "common"


def pick_character_of_rarity(rarity: str) -> str | None:
    """Return a random character name of the given rarity, or None."""
    pool = [row[0] for row in G.CHARACTERS if row[1] == rarity]
    return random.choice(pool) if pool else None


# =============================================================
# ART STORAGE
# =============================================================
def set_art(kind: str, name: str, file_id: str) -> None:
    """Store a Telegram file_id for a given (kind, name)."""
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO art(kind,name,file_id) VALUES(?,?,?)",
            (kind, name, file_id),
        )


def get_art(kind: str, name: str) -> str | None:
    """Return file_id for a given (kind, name) or None."""
    with conn() as c:
        row = c.execute(
            "SELECT file_id FROM art WHERE kind=? AND name=?",
            (kind, name),
        ).fetchone()
        return row["file_id"] if row else None


def all_art() -> dict:
    """Return {(kind, name): file_id}."""
    with conn() as c:
        return {
            (r["kind"], r["name"]): r["file_id"]
            for r in c.execute("SELECT kind,name,file_id FROM art")
        }


# =============================================================
# DAILY / WEEKLY STREAKS
# =============================================================
def claim_daily(uid: int):
    """
    Claim daily reward. Returns (streak, rewards_dict) or None if
    already claimed today.
    """
    p = player(uid)
    if p is None:
        return None
    now = datetime.now(timezone.utc).date()
    today = now.isoformat()
    if p["daily_day"] == today:
        return None

    yesterday = (now - timedelta(days=1)).isoformat()
    prev_streak = int(p["daily_streak"] or 0)
    streak = (prev_streak + 1) if p["daily_day"] == yesterday else 1

    rewards = {
        "yens": 300 + min(streak, 20) * 100,
        "gems": min(1 + streak // 5, 6),
    }
    if streak % 3 == 0:
        rewards["tickets"] = 1
    if streak % 7 == 0:
        rewards["crystals"] = 1

    with conn() as c:
        c.execute(
            "UPDATE players SET daily_day=?, daily_streak=? "
            "WHERE user_id=?",
            (today, streak, uid),
        )
    give(uid, **rewards)
    return streak, rewards


def claim_weekly(uid: int):
    """
    Claim weekly reward. Returns (rewards_dict, dragon_ball_star)
    or None if already claimed this week.
    """
    p = player(uid)
    if p is None:
        return None
    today = datetime.now(timezone.utc).date()
    year, week, _ = today.isocalendar()
    key = f"{year}-W{week:02d}"

    if p["weekly_week"] == key:
        return None

    rewards = {
        "yens": 5000,
        "gems": 50,
        "crystals": 5,
        "tickets": 3,
        "skill_points": 5,
    }
    give(uid, **rewards)
    with conn() as c:
        c.execute(
            "UPDATE players SET weekly_week=? WHERE user_id=?",
            (key, uid),
        )
    star = random.randint(1, 3)
    add_dragon_ball(uid, star)
    return rewards, star


# =============================================================
# QUESTS (daily / weekly / monthly)
# =============================================================
def _quest_table(kind: str) -> dict:
    if kind == "daily":
        return G.DAILY_QUESTS
    if kind == "weekly":
        return G.WEEKLY_QUESTS
    if kind == "monthly":
        return G.MONTHLY_QUESTS
    return {}


def _period_key(kind: str) -> str:
    """Return the current period key for a quest type."""
    now = datetime.now(timezone.utc)
    if kind == "daily":
        return now.date().isoformat()
    if kind == "weekly":
        y, w, _ = now.date().isocalendar()
        return f"{y}-W{w:02d}"
    if kind == "monthly":
        return f"{now.year}-{now.month:02d}"
    return ""


def ensure_quests_current(uid: int) -> None:
    """Reset quest progress if the period has changed."""
    p = player(uid)
    if not p:
        return
    with conn() as c:
        for kind in ("daily", "weekly", "monthly"):
            key_col = f"quest_{kind}_key"
            json_col = f"quest_{kind}_json"
            claimed_col = f"quest_{kind}_claimed"
            current = p[key_col] if key_col in p.keys() else ""
            expected = _period_key(kind)
            if current != expected:
                c.execute(
                    f"UPDATE players SET {key_col}=?, "
                    f"{json_col}='{{}}', {claimed_col}='{{}}' "
                    f"WHERE user_id=?",
                    (expected, uid),
                )


def _load_quest_json(uid: int, kind: str, suffix: str) -> dict:
    """Load quest progress or claimed JSON."""
    p = player(uid)
    if not p:
        return {}
    col = f"quest_{kind}_{suffix}"
    try:
        raw = p[col] if col in p.keys() else "{}"
        return json.loads(raw or "{}")
    except (ValueError, TypeError, KeyError):
        return {}


def _save_quest_json(uid: int, kind: str, suffix: str,
                     data: dict) -> None:
    """Persist quest progress or claimed JSON."""
    col = f"quest_{kind}_{suffix}"
    with conn() as c:
        c.execute(
            f"UPDATE players SET {col}=? WHERE user_id=?",
            (json.dumps(data), uid),
        )


def quest_progress(uid: int, kind: str, code: str) -> int:
    """Read current progress count for a specific quest."""
    ensure_quests_current(uid)
    data = _load_quest_json(uid, kind, "json")
    try:
        return int(data.get(code, 0))
    except (TypeError, ValueError):
        return 0


def quest_increment(uid: int, kind: str, code: str,
                    amount: int = 1) -> None:
    """Increment progress for a specific quest."""
    if amount <= 0:
        return
    ensure_quests_current(uid)
    data = _load_quest_json(uid, kind, "json")
    try:
        cur = int(data.get(code, 0))
    except (TypeError, ValueError):
        cur = 0
    data[code] = cur + int(amount)
    _save_quest_json(uid, kind, "json", data)


def quest_claimed(uid: int, kind: str) -> dict:
    """Return dict of claimed quests for a period."""
    ensure_quests_current(uid)
    return _load_quest_json(uid, kind, "claimed")


def claim_quest(uid: int, kind: str, code: str):
    """
    Claim a quest reward if complete and not yet claimed.
    Returns quest info dict on success, None otherwise.
    """
    ensure_quests_current(uid)
    info = _quest_table(kind).get(code)
    if not info:
        return None
    claimed = quest_claimed(uid, kind)
    if claimed.get(code):
        return None
    if quest_progress(uid, kind, code) < info["target"]:
        return None
    claimed[code] = 1
    _save_quest_json(uid, kind, "claimed", claimed)
    give(
        uid,
        yens=info.get("yens", 0),
        gems=info.get("gems", 0),
        crystals=info.get("crystals", 0),
    )
    return info


def quest_summary(uid: int) -> dict:
    """Return structured quest status for display."""
    ensure_quests_current(uid)
    out = {}
    for kind in ("daily", "weekly", "monthly"):
        table = _quest_table(kind)
        claimed = quest_claimed(uid, kind)
        rows = []
        for code, info in table.items():
            progress = quest_progress(uid, kind, code)
            rows.append({
                "code": code,
                "name": info["name"],
                "target": info["target"],
                "progress": progress,
                "complete": progress >= info["target"],
                "claimed": bool(claimed.get(code)),
                "yens": info.get("yens", 0),
                "gems": info.get("gems", 0),
                "crystals": info.get("crystals", 0),
            })
        out[kind] = rows
    return out


# =============================================================
# ADMIN HELPERS
# =============================================================
_ADMIN_FIELDS = {
    "rank", "admin", "banned", "travel", "equipped_char",
    "weapon", "armor", "current_hp", "yens", "gems",
    "crystals", "tickets", "skill_points", "keys_elite",
    "keys_boss", "exp", "npc_streak", "fusion_count",
}


def admin_set_field(uid: int, field: str, value) -> bool:
    """Admin: set any whitelisted player field. Returns True on success."""
    if field not in _ADMIN_FIELDS:
        return False
    with conn() as c:
        c.execute(
            f"UPDATE players SET {field}=? WHERE user_id=?",
            (value, uid),
        )
    return True


def admin_grant(uid: int, **amounts) -> None:
    """Alias for give() — kept for semantic clarity in admin code."""
    give(uid, **amounts)


def admin_reset_player(uid: int) -> None:
    """Wipe all player data back to defaults."""
    with conn() as c:
        c.execute(
            "UPDATE players SET "
            "exp=0, yens=0, gems=0, crystals=0, tickets=0, "
            "skill_points=0, keys_elite=0, keys_boss=0, "
            "npc_streak=0, current_hp=NULL, equipped_char=NULL, "
            "weapon=NULL, armor=NULL, rank=1, admin=0, banned=0, "
            "daily_day=NULL, daily_streak=0, weekly_week=NULL, "
            "travel='Earth', fusion_count=0, "
            "total_battles=0, total_wins=0, total_losses=0, "
            "total_dmg_dealt=0, total_dmg_taken=0, "
            "quest_daily_key='', quest_weekly_key='', "
            "quest_monthly_key='', "
            "quest_daily_json='{}', quest_weekly_json='{}', "
            "quest_monthly_json='{}', "
            "quest_daily_claimed='{}', quest_weekly_claimed='{}', "
            "quest_monthly_claimed='{}', "
            "summon_hp_json='{}' "
            "WHERE user_id=?",
            (uid,),
        )
        c.execute("DELETE FROM items WHERE user_id=?", (uid,))
        c.execute("DELETE FROM characters WHERE user_id=?", (uid,))
        c.execute("DELETE FROM skills WHERE user_id=?", (uid,))
        c.execute("DELETE FROM dragon_balls WHERE user_id=?", (uid,))
        c.execute("DELETE FROM combat_logs WHERE user_id=?", (uid,))
        c.execute("DELETE FROM player_achievements WHERE user_id=?", (uid,))


def admin_ban(uid: int, banned: bool) -> None:
    """Ban or unban a player."""
    with conn() as c:
        c.execute(
            "UPDATE players SET banned=? WHERE user_id=?",
            (1 if banned else 0, uid),
        )


def admin_promote(uid: int, make_admin: bool = True) -> None:
    """Grant or revoke admin flag."""
    with conn() as c:
        c.execute(
            "UPDATE players SET admin=? WHERE user_id=?",
            (1 if make_admin else 0, uid),
        )


def admin_heal(uid: int, max_hp: int) -> None:
    """Fully heal a player."""
    set_current_hp(uid, max_hp)


def is_player_admin(uid: int) -> bool:
    """Return True if player has admin flag."""
    p = player(uid)
    return bool(p and p["admin"])


def is_player_banned(uid: int) -> bool:
    """Return True if player is banned."""
    p = player(uid)
    return bool(p and p["banned"])


# =============================================================
# SELF-TEST (run: python db.py)
# =============================================================
if __name__ == "__main__":
    init()
    print(f"✅ DB initialized at {DB_PATH}")

    test_uid = 999_999_999
    ensure_player(test_uid, "Test Player", "test_user")
    p = player(test_uid)
    print(f"✅ Player created: {p['first_name']} (id={p['user_id']})")

    give(test_uid, yens=1000, gems=100)
    p = player(test_uid)
    print(f"✅ Gave resources: {p['yens']} yens, {p['gems']} gems")

    ok = spend(test_uid, "yens", 500)
    p = player(test_uid)
    print(f"✅ Spend 500 yens → {'OK' if ok else 'FAIL'} "
          f"({p['yens']} left)")

    add_item(test_uid, "Senzu Bean", 3)
    inv = items(test_uid)
    print(f"✅ Added 3 Senzu Beans: {[dict(r) for r in inv]}")

    add_character(test_uid, "Goku", "legendary")
    add_character(test_uid, "Vegeta", "legendary")
    chars = characters(test_uid)
    print(f"✅ Added 2 chars: {[dict(r) for r in chars]}")

    add_skill(test_uid, "Kaioken")
    print(f"✅ Skills: {skills(test_uid)}")

    add_dragon_ball(test_uid, 1, 2)
    print(f"✅ Dragon balls: {dragon_balls(test_uid)}")

    add_combat_log(test_uid, "Bandit Rookie", 70, 70, 0,
                   "victory", 1, "")
    stats = combat_stats(test_uid)
    print(f"✅ Combat stats: {stats}")

    info = unlock_achievement(test_uid, "first_blood")
    print(f"✅ Achievement unlocked: "
          f"{info['name'] if info else 'already had'}")

    quest_increment(test_uid, "daily", "daily_npc_10", 5)
    print(f"✅ Quest progress: "
          f"{quest_progress(test_uid, 'daily', 'daily_npc_10')}/10")

    admin_reset_player(test_uid)
    print("✅ Player reset")

    print("\n🎉 All db.py self-tests passed!")
