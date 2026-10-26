from __future__ import annotations

import json
import os
import random
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import game_data as G

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "game.sqlite"))


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# =============================================================
# Initialization
# =============================================================
def init() -> None:
    with conn() as c:
        import clans as _clans
        _clans.init_tables(c)
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS players(
                user_id INTEGER PRIMARY KEY,
                first_name TEXT, username TEXT,
                exp INTEGER DEFAULT 0,
                yens INTEGER DEFAULT 0, gems INTEGER DEFAULT 0,
                crystals INTEGER DEFAULT 0, tickets INTEGER DEFAULT 0,
                skill_points INTEGER DEFAULT 0,
                keys_elite INTEGER DEFAULT 0, keys_boss INTEGER DEFAULT 0,
                npc_streak INTEGER DEFAULT 0,
                current_hp INTEGER DEFAULT NULL,
                equipped_char TEXT, weapon TEXT, armor TEXT,
                last_raid_hit INTEGER DEFAULT 0,
                rank INTEGER DEFAULT 1, admin INTEGER DEFAULT 0,
                banned INTEGER DEFAULT 0,
                daily_day TEXT, daily_streak INTEGER DEFAULT 0,
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
                user_id INTEGER, item TEXT, qty INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, item)
            );
            CREATE TABLE IF NOT EXISTS characters(
                user_id INTEGER, name TEXT, rarity TEXT,
                PRIMARY KEY(user_id, name)
            );
            CREATE TABLE IF NOT EXISTS skills(
                user_id INTEGER, name TEXT, PRIMARY KEY(user_id, name)
            );
            CREATE TABLE IF NOT EXISTS dragon_balls(
                user_id INTEGER, star INTEGER, qty INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, star)
            );
            CREATE TABLE IF NOT EXISTS art(
                kind TEXT, name TEXT, file_id TEXT,
                PRIMARY KEY(kind, name)
            );
            CREATE TABLE IF NOT EXISTS raid(
                id INTEGER PRIMARY KEY CHECK(id=1),
                active INTEGER, hp INTEGER, max_hp INTEGER,
                damage_json TEXT, boss_name TEXT DEFAULT '',
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
            CREATE TABLE IF NOT EXISTS achievements(
                code TEXT PRIMARY KEY, name TEXT, description TEXT
            );
            CREATE TABLE IF NOT EXISTS player_achievements(
                user_id INTEGER, code TEXT,
                unlocked_at INTEGER DEFAULT (strftime('%s','now')),
                PRIMARY KEY(user_id, code)
            );
            """
        )
        # Seed achievements
        for code, info in G.ACHIEVEMENTS.items():
            c.execute(
                "INSERT OR IGNORE INTO achievements(code,name,description) VALUES(?,?,?)",
                (code, info["name"], info["desc"]),
            )
        # Migration guards
        cols = [r[1] for r in c.execute("PRAGMA table_info(players)")]
        for col, ddl in [
            ("current_hp", "INTEGER DEFAULT NULL"),
            ("quest_daily_key", "TEXT DEFAULT ''"),
            ("quest_weekly_key", "TEXT DEFAULT ''"),
            ("quest_monthly_key", "TEXT DEFAULT ''"),
            ("quest_daily_json", "TEXT DEFAULT '{}'"),
            ("quest_weekly_json", "TEXT DEFAULT '{}'"),
            ("quest_monthly_json", "TEXT DEFAULT '{}'"),
            ("quest_daily_claimed", "TEXT DEFAULT '{}'"),
            ("quest_weekly_claimed", "TEXT DEFAULT '{}'"),
            ("quest_monthly_claimed", "TEXT DEFAULT '{}'"),
            ("summon_hp_json", "TEXT DEFAULT '{}'"),
            ("total_battles", "INTEGER DEFAULT 0"),
            ("total_wins", "INTEGER DEFAULT 0"),
            ("total_losses", "INTEGER DEFAULT 0"),
            ("total_dmg_dealt", "INTEGER DEFAULT 0"),
            ("total_dmg_taken", "INTEGER DEFAULT 0"),
        ]:
            if col not in cols:
                c.execute(f"ALTER TABLE players ADD COLUMN {col} {ddl}")


# =============================================================
# Player
# =============================================================
def ensure_player(uid: int, first: str, username: str | None) -> None:
    with conn() as c:
        c.execute(
            """INSERT OR IGNORE INTO players(
                user_id, first_name, username
            ) VALUES (?,?,?)""",
            (uid, first or "", username or ""),
        )
        c.execute("UPDATE players SET first_name=?, username=? WHERE user_id=?",
                  (first or "", username or "", uid))


def player(uid: int):
    with conn() as c:
        return c.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone()


def player_by_username(username: str):
    n = (username or "").replace("@", "").strip()
    if not n:
        return None
    with conn() as c:
        return c.execute(
            "SELECT * FROM players WHERE lower(username)=lower(?) "
            "OR lower(first_name)=lower(?)", (n, n),
        ).fetchone()


def level_of(exp: int) -> int:
    return 1 + int(exp) // G.LEVEL_EXP


def rank_of(uid: int) -> int:
    with conn() as c:
        mine = c.execute("SELECT exp FROM players WHERE user_id=?", (uid,)).fetchone()
        if mine is None:
            return 0
        above = c.execute("SELECT COUNT(*) FROM players WHERE exp > ?",
                          (mine["exp"],)).fetchone()[0]
        return above + 1


def give(uid: int, **amounts) -> None:
    allowed = {"yens", "gems", "crystals", "tickets", "skill_points",
               "keys_elite", "keys_boss", "exp"}
    for k, v in amounts.items():
        if k not in allowed or v is None:
            continue
        try:
            amt = int(v)
        except (TypeError, ValueError):
            continue
        if amt == 0:
            continue
        with conn() as c:
            c.execute(f"UPDATE players SET {k}={k}+? WHERE user_id=?", (amt, uid))


def spend(uid: int, column: str, amount: int) -> bool:
    allowed = {"yens", "gems", "crystals", "tickets", "skill_points",
               "keys_elite", "keys_boss"}
    if column not in allowed or amount <= 0:
        return False
    with conn() as c:
        cur = c.execute(
            f"UPDATE players SET {column}={column}-? "
            f"WHERE user_id=? AND {column}>=?",
            (amount, uid, amount),
        )
        return cur.rowcount == 1


def set_field(uid: int, field: str, value) -> None:
    allowed = {"equipped_char", "weapon", "armor", "npc_streak",
               "last_raid_hit", "rank", "admin", "banned", "travel",
               "fusion_count", "current_hp"}
    if field not in allowed:
        raise ValueError(f"bad field: {field}")
    with conn() as c:
        c.execute(f"UPDATE players SET {field}=? WHERE user_id=?", (value, uid))


# =============================================================
# HP tracking
# =============================================================
def get_current_hp(uid: int, max_hp: int) -> int:
    """Return current HP, treating NULL as full."""
    p = player(uid)
    if not p:
        return max_hp
    hp = p["current_hp"]
    if hp is None:
        return max_hp
    return max(0, min(int(hp), max_hp))


def set_current_hp(uid: int, hp: int) -> None:
    with conn() as c:
        c.execute("UPDATE players SET current_hp=? WHERE user_id=?", (int(hp), uid))


def apply_heal(uid: int, max_hp: int, item_name: str) -> tuple[bool, int]:
    """Consume one healing item. Return (ok, new_hp)."""
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
# Inventory
# =============================================================
def add_item(uid: int, item: str, qty: int = 1) -> None:
    if not item or qty <= 0:
        return
    with conn() as c:
        c.execute(
            "INSERT INTO items(user_id,item,qty) VALUES(?,?,?) "
            "ON CONFLICT(user_id,item) DO UPDATE SET qty=qty+excluded.qty",
            (uid, item.strip(), qty),
        )


def items(uid: int) -> list:
    with conn() as c:
        return c.execute(
            "SELECT item, qty FROM items WHERE user_id=? AND qty>0 ORDER BY item",
            (uid,),
        ).fetchall()


def remove_item(uid: int, item: str, qty: int = 1) -> bool:
    if qty <= 0:
        return False
    with conn() as c:
        cur = c.execute(
            "UPDATE items SET qty=qty-? WHERE user_id=? AND item=? AND qty>=?",
            (qty, uid, item, qty),
        )
        return cur.rowcount == 1


# =============================================================
# Characters
# =============================================================
def add_character(uid: int, name: str, rarity: str) -> bool:
    n = (name or "").strip()
    if not n:
        return False
    with conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO characters(user_id,name,rarity) VALUES(?,?,?)",
            (uid, n, rarity or "common"),
        )
        return cur.rowcount == 1


def characters(uid: int) -> list:
    with conn() as c:
        return c.execute(
            "SELECT name, rarity FROM characters WHERE user_id=? "
            "ORDER BY CASE rarity WHEN 'omni' THEN 1 WHEN 'mythical' THEN 2 "
            "WHEN 'legendary' THEN 3 WHEN 'epic' THEN 4 "
            "WHEN 'rare' THEN 5 ELSE 6 END, name",
            (uid,),
        ).fetchall()


def characters_by_rarity(uid: int) -> dict:
    rows = characters(uid)
    out = {r: [] for r in ["common", "rare", "epic",
                           "legendary", "mythical", "omni"]}
    for row in rows:
        out.setdefault(row["rarity"], []).append(row["name"])
    return out


def has_character(uid: int, name: str) -> bool:
    if not name:
        return False
    with conn() as c:
        return c.execute(
            "SELECT 1 FROM characters WHERE user_id=? AND name=?",
            (uid, name),
        ).fetchone() is not None


def transfer_character(giver: int, target: int, name: str) -> bool:
    with conn() as c:
        row = c.execute(
            "SELECT rarity FROM characters WHERE user_id=? AND name=?",
            (giver, name),
        ).fetchone()
        if row is None:
            return False
        if c.execute("SELECT 1 FROM characters WHERE user_id=? AND name=?",
                     (target, name)).fetchone():
            return False
        c.execute("DELETE FROM characters WHERE user_id=? AND name=?", (giver, name))
        c.execute("INSERT INTO characters(user_id,name,rarity) VALUES(?,?,?)",
                  (target, name, row["rarity"]))
        c.execute("UPDATE players SET equipped_char=NULL "
                  "WHERE user_id=? AND equipped_char=?", (giver, name))
        return True


# =============================================================
# Skills
# =============================================================
def add_skill(uid: int, name: str) -> bool:
    n = (name or "").strip()
    if not n:
        return False
    with conn() as c:
        return c.execute(
            "INSERT OR IGNORE INTO skills(user_id,name) VALUES(?,?)",
            (uid, n),
        ).rowcount == 1


def skills(uid: int) -> list:
    with conn() as c:
        return [r["name"] for r in c.execute(
            "SELECT name FROM skills WHERE user_id=? ORDER BY name", (uid,))]


def transfer_skill(giver: int, target: int, name: str) -> bool:
    with conn() as c:
        if c.execute("SELECT 1 FROM skills WHERE user_id=? AND name=?",
                     (giver, name)).fetchone() is None:
            return False
        if c.execute("SELECT 1 FROM skills WHERE user_id=? AND name=?",
                     (target, name)).fetchone():
            return False
        c.execute("DELETE FROM skills WHERE user_id=? AND name=?", (giver, name))
        c.execute("INSERT INTO skills(user_id,name) VALUES(?,?)", (target, name))
        return True


# =============================================================
# Dragon Balls
# =============================================================
def add_dragon_ball(uid: int, star: int, qty: int = 1) -> None:
    if not isinstance(star, int) or qty <= 0:
        return
    with conn() as c:
        c.execute(
            "INSERT INTO dragon_balls(user_id,star,qty) VALUES(?,?,?) "
            "ON CONFLICT(user_id,star) DO UPDATE SET qty=qty+excluded.qty",
            (uid, star, qty),
        )


def dragon_balls(uid: int) -> dict:
    with conn() as c:
        return {r["star"]: r["qty"] for r in c.execute(
            "SELECT star, qty FROM dragon_balls WHERE user_id=? AND qty>0",
            (uid,))}


def take_one_of_each_dragon_ball(uid: int) -> bool:
    have = dragon_balls(uid)
    if any(have.get(s, 0) < 1 for s in G.DRAGON_BALL_STARS):
        return False
    with conn() as c:
        for s in G.DRAGON_BALL_STARS:
            c.execute("UPDATE dragon_balls SET qty=qty-1 "
                      "WHERE user_id=? AND star=?", (uid, s))
    return True


def remove_dragon_ball(uid: int, star: int, qty: int) -> bool:
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
# Combat Logs (CombatHistory backing)
# =============================================================
def add_combat_log(uid: int, enemy_name: str, enemy_max_hp: int,
                   damage_dealt: int, damage_taken: int,
                   outcome: str, rounds: int, rewards_text: str = "") -> None:
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
            (1 if outcome == "victory" else 0,
             1 if outcome == "defeat" else 0,
             damage_dealt, damage_taken, uid),
        )


def get_combat_history(uid: int, limit: int = 10) -> list:
    with conn() as c:
        return c.execute(
            "SELECT * FROM combat_logs WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (uid, limit),
        ).fetchall()


def combat_stats(uid: int) -> dict:
    p = player(uid)
    if not p:
        return {"battles": 0, "wins": 0, "losses": 0, "dealt": 0, "taken": 0}
    return {
        "battles": int(p["total_battles"] or 0),
        "wins": int(p["total_wins"] or 0),
        "losses": int(p["total_losses"] or 0),
        "dealt": int(p["total_dmg_dealt"] or 0),
        "taken": int(p["total_dmg_taken"] or 0),
    }


# =============================================================
# Achievements
# =============================================================
def has_achievement(uid: int, code: str) -> bool:
    with conn() as c:
        return c.execute(
            "SELECT 1 FROM player_achievements WHERE user_id=? AND code=?",
            (uid, code),
        ).fetchone() is not None


def unlock_achievement(uid: int, code: str):
    if code not in G.ACHIEVEMENTS:
        return None
    if has_achievement(uid, code):
        return None
    info = G.ACHIEVEMENTS[code]
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO player_achievements(user_id,code) "
                  "VALUES(?,?)", (uid, code))
    give(uid, yens=info.get("yens", 0), gems=info.get("gems", 0),
         crystals=info.get("crystals", 0))
    return info


def player_achievements(uid: int) -> list:
    with conn() as c:
        return c.execute(
            "SELECT a.code, a.name, a.description, pa.unlocked_at "
            "FROM player_achievements pa JOIN achievements a ON a.code=pa.code "
            "WHERE pa.user_id=? ORDER BY pa.unlocked_at DESC",
            (uid,),
        ).fetchall()


# =============================================================
# Global Raid
# =============================================================
def raid_state():
    with conn() as c:
        return c.execute("SELECT * FROM raid WHERE id=1").fetchone()


def raid_start(boss_name: str = G.RAID["name"], hp: int | None = None) -> None:
    hp = hp or G.RAID["hp"]
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO raid(id,active,hp,max_hp,damage_json,boss_name,started_at) "
            "VALUES(1,1,?,?,?,?,?)",
            (hp, hp, json.dumps({}), boss_name, int(time.time())),
        )


def raid_hit(uid: int, damage: int):
    st = raid_state()
    if st is None or not st["active"]:
        return None
    dmg_by = json.loads(st["damage_json"] or "{}")
    dmg_by[str(uid)] = dmg_by.get(str(uid), 0) + damage
    hp = max(0, st["hp"] - damage)
    defeated = hp == 0
    with conn() as c:
        c.execute(
            "UPDATE raid SET hp=?, damage_json=?, active=? WHERE id=1",
            (hp, json.dumps(dmg_by), 0 if defeated else 1),
        )
    return hp, defeated, dmg_by


def raid_reset() -> None:
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO raid(id,active,hp,max_hp,damage_json,boss_name,started_at) "
            "VALUES(1,1,?,?,?,?,0)",
            (G.RAID["hp"], G.RAID["hp"], json.dumps({}), G.RAID["name"]),
        )


# =============================================================
# Cooldowns
# =============================================================
def cooldown_ok(uid: int, seconds: int) -> int:
    p = player(uid)
    if p is None:
        return 0
    left = seconds - (int(time.time()) - int(p["last_raid_hit"] or 0))
    return max(0, left)


def mark_raid_hit(uid: int) -> None:
    with conn() as c:
        c.execute("UPDATE players SET last_raid_hit=? WHERE user_id=?",
                  (int(time.time()), uid))


# =============================================================
# Summon persistent HP
# =============================================================
def summon_hp(uid: int, kind: str) -> int | None:
    p = player(uid)
    if not p:
        return None
    try:
        data = json.loads(p["summon_hp_json"] or "{}")
    except Exception:
        data = {}
    return data.get(kind)


def set_summon_hp(uid: int, kind: str, hp: int | None) -> None:
    p = player(uid)
    if not p:
        return
    try:
        data = json.loads(p["summon_hp_json"] or "{}")
    except Exception:
        data = {}
    if hp is None:
        data.pop(kind, None)
    else:
        data[kind] = int(hp)
    with conn() as c:
        c.execute("UPDATE players SET summon_hp_json=? WHERE user_id=?",
                  (json.dumps(data), uid))


# =============================================================
# Gacha
# =============================================================
def roll_rarity(banner_bonus: dict | None = None) -> str:
    weights = []
    for name, w in G.GACHA_RATES:
        bonus = (banner_bonus or {}).get(name, 1.0)
        weights.append(w * bonus)
    total = sum(weights)
    r = random.uniform(0, total)
    acc = 0
    for (name, _), w in zip(G.GACHA_RATES, weights):
        acc += w
        if r <= acc:
            return name
    return "common"


def pick_character_of_rarity(rarity: str) -> str | None:
    pool = [n for n, r, *_ in G.CHARACTERS if r == rarity]
    return random.choice(pool) if pool else None


# =============================================================
# Art
# =============================================================
def set_art(kind: str, name: str, file_id: str) -> None:
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO art(kind,name,file_id) VALUES(?,?,?)",
                  (kind, name, file_id))


def all_art() -> dict:
    with conn() as c:
        return {(r["kind"], r["name"]): r["file_id"]
                for r in c.execute("SELECT kind,name,file_id FROM art")}


# =============================================================
# Daily / Weekly
# =============================================================
def claim_daily(uid: int):
    p = player(uid)
    if p is None:
        return None
    now = datetime.now(timezone.utc).date()
    today = now.isoformat()
    if p["daily_day"] == today:
        return None
    yesterday = (now - timedelta(days=1)).isoformat()
    streak = (int(p["daily_streak"] or 0) + 1) if p["daily_day"] == yesterday else 1
    rewards = {"yens": 300 + min(streak, 20) * 100,
               "gems": min(1 + streak // 5, 6)}
    if streak % 3 == 0:
        rewards["tickets"] = 1
    if streak % 7 == 0:
        rewards["crystals"] = 1
    with conn() as c:
        c.execute("UPDATE players SET daily_day=?, daily_streak=? "
                  "WHERE user_id=?", (today, streak, uid))
    give(uid, **rewards)
    return streak, rewards


def claim_weekly(uid: int):
    p = player(uid)
    if p is None:
        return None
    today = datetime.now(timezone.utc).date()
    year, week, _ = today.isocalendar()
    key = f"{year}-W{week:02d}"
    if p["weekly_week"] == key:
        return None
    rewards = {"yens": 5000, "gems": 50, "crystals": 5,
               "tickets": 3, "skill_points": 5}
    give(uid, **rewards)
    with conn() as c:
        c.execute("UPDATE players SET weekly_week=? WHERE user_id=?", (key, uid))
    star = random.randint(1, 3)
    add_dragon_ball(uid, star)
    return rewards, star


# =============================================================
# Quests (daily / weekly / monthly)
# =============================================================
def _period_key(kind: str) -> str:
    now = datetime.now(timezone.utc)
    if kind == "daily":
        return now.date().isoformat()
    if kind == "weekly":
        y, w, _ = now.date().isocalendar()
        return f"{y}-W{w:02d}"
    if kind == "monthly":
        return f"{now.year}-{now.month:02d}"
    return ""


def _quest_table(kind: str):
    return {"daily": G.DAILY_QUESTS, "weekly": G.WEEKLY_QUESTS,
            "monthly": G.MONTHLY_QUESTS}.get(kind, {})


def ensure_quests_current(uid: int) -> None:
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
                    f"UPDATE players SET {key_col}=?, {json_col}='{{}}', "
                    f"{claimed_col}='{{}}' WHERE user_id=?",
                    (expected, uid),
                )


def quest_progress(uid: int, kind: str, code: str) -> int:
    ensure_quests_current(uid)
    p = player(uid)
    if not p:
        return 0
    try:
        data = json.loads(p[f"quest_{kind}_json"] or "{}")
    except Exception:
        data = {}
    return int(data.get(code, 0))


def quest_increment(uid: int, kind: str, code: str, amount: int = 1) -> None:
    ensure_quests_current(uid)
    p = player(uid)
    if not p:
        return
    try:
        data = json.loads(p[f"quest_{kind}_json"] or "{}")
    except Exception:
        data = {}
    data[code] = int(data.get(code, 0)) + int(amount)
    with conn() as c:
        c.execute(f"UPDATE players SET quest_{kind}_json=? WHERE user_id=?",
                  (json.dumps(data), uid))


def quest_claimed(uid: int, kind: str) -> dict:
    p = player(uid)
    if not p:
        return {}
    try:
        return json.loads(p[f"quest_{kind}_claimed"] or "{}")
    except Exception:
        return {}


def claim_quest(uid: int, kind: str, code: str) -> dict | None:
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
    with conn() as c:
        c.execute(f"UPDATE players SET quest_{kind}_claimed=? WHERE user_id=?",
                  (json.dumps(claimed), uid))
    give(uid, yens=info.get("yens", 0), gems=info.get("gems", 0),
         crystals=info.get("crystals", 0))
    return info


# =============================================================
# Admin helpers
# =============================================================
def admin_set_field(uid: int, field: str, value) -> bool:
    allowed = {"rank", "admin", "banned", "travel", "equipped_char",
               "weapon", "armor", "current_hp", "yens", "gems",
               "crystals", "tickets", "skill_points", "keys_elite",
               "keys_boss", "exp"}
    if field not in allowed:
        return False
    with conn() as c:
        c.execute(f"UPDATE players SET {field}=? WHERE user_id=?", (value, uid))
    return True


def admin_grant(uid: int, **amounts) -> None:
    give(uid, **amounts)


def admin_reset_player(uid: int) -> None:
    with conn() as c:
        c.execute(
            "UPDATE players SET exp=0, yens=0, gems=0, crystals=0, "
            "tickets=0, skill_points=0, keys_elite=0, keys_boss=0, "
            "npc_streak=0, current_hp=NULL, equipped_char=NULL, "
            "weapon=NULL, armor=NULL, rank=1, fusion_count=0, "
            "total_battles=0, total_wins=0, total_losses=0, "
            "total_dmg_dealt=0, total_dmg_taken=0 "
            "WHERE user_id=?", (uid,))
        c.execute("DELETE FROM items WHERE user_id=?", (uid,))
        c.execute("DELETE FROM characters WHERE user_id=?", (uid,))
        c.execute("DELETE FROM skills WHERE user_id=?", (uid,))
        c.execute("DELETE FROM dragon_balls WHERE user_id=?", (uid,))
        c.execute("DELETE FROM combat_logs WHERE user_id=?", (uid,))
        c.execute("DELETE FROM player_achievements WHERE user_id=?", (uid,))


def admin_ban(uid: int, banned: bool) -> None:
    with conn() as c:
        c.execute("UPDATE players SET banned=? WHERE user_id=?",
                  (1 if banned else 0, uid))


def all_players() -> list:
    with conn() as c:
        return c.execute(
            "SELECT user_id, first_name, username, exp, rank "
            "FROM players ORDER BY exp DESC"
        ).fetchall()


def leaderboard(limit: int = 10) -> list:
    with conn() as c:
        return c.execute(
            "SELECT first_name, exp, rank, total_wins "
            "FROM players ORDER BY exp DESC LIMIT ?", (limit,),
        ).fetchall()
