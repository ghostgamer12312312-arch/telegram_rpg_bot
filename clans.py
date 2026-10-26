from __future__ import annotations

"""
Dragon Ball RPG — Clan System
==============================
Full 9-subcommand clan system + raids + perks + territory.

Functions used by bot.py:
  membership, create, join, add, remove, promote, demote,
  transfer, leave, disband, top_clans, members,
  set_announcement, get_announcement,
  add_treasure, withdraw_treasure,
  get_perks, buy_perk,
  capture_planet, list_territory,
  clan_raid_state, clan_raid_start, clan_raid_hit,
  clan_by_name, clan_by_id, init_tables
"""

import json
import re
import time

import db
import game_data as G

CREATE_COST = G.CLAN_CREATE_CRYSTALS


class ClanError(Exception):
    """Raised for user-facing clan errors."""
    pass


# =============================================================
# SCHEMA
# =============================================================
def init_tables(c) -> None:
    """Create clan tables. Called from db.init()."""
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS clans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE COLLATE NOCASE,
            created INTEGER DEFAULT (strftime('%s','now')),
            treasure_yens INTEGER DEFAULT 0,
            treasure_gems INTEGER DEFAULT 0,
            treasure_crystals INTEGER DEFAULT 0,
            announcement TEXT DEFAULT '',
            perks_json TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS clan_members(
            user_id INTEGER PRIMARY KEY,
            clan_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            joined_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE INDEX IF NOT EXISTS idx_members_clan
            ON clan_members(clan_id);

        CREATE TABLE IF NOT EXISTS clan_raids(
            clan_id INTEGER NOT NULL,
            boss_name TEXT NOT NULL,
            hp INTEGER,
            max_hp INTEGER,
            damage_json TEXT DEFAULT '{}',
            active INTEGER DEFAULT 0,
            started_at INTEGER DEFAULT (strftime('%s','now')),
            PRIMARY KEY(clan_id, boss_name)
        );

        CREATE TABLE IF NOT EXISTS clan_territory(
            clan_id INTEGER,
            planet TEXT,
            captured_at INTEGER DEFAULT (strftime('%s','now')),
            PRIMARY KEY(clan_id, planet)
        );
        """
    )
    # Migrate older schemas
    cols = [r[1] for r in c.execute("PRAGMA table_info(clans)")]
    if "perks_json" not in cols:
        c.execute("ALTER TABLE clans ADD COLUMN perks_json TEXT DEFAULT '{}'")
    if "announcement" not in cols:
        c.execute("ALTER TABLE clans ADD COLUMN announcement TEXT DEFAULT ''")


# =============================================================
# VALIDATION
# =============================================================
def _valid_name(name: str) -> str:
    """Validate and normalize a clan name."""
    n = " ".join((name or "").split())
    if not re.fullmatch(r"[A-Za-z0-9 ]{3,20}", n):
        raise ClanError(
            "Clan name must be 3 to 20 letters, numbers, or spaces."
        )
    return n


# =============================================================
# LOOKUPS
# =============================================================
def membership(user_id: int):
    """Return the player's clan row (with merged clan data), or None."""
    with db.conn() as c:
        return c.execute(
            "SELECT m.clan_id, m.role, m.joined_at, "
            "k.name, k.created, k.treasure_yens, k.treasure_gems, "
            "k.treasure_crystals, k.announcement, k.perks_json "
            "FROM clan_members m "
            "JOIN clans k ON k.id=m.clan_id "
            "WHERE m.user_id=?",
            (user_id,),
        ).fetchone()


def clan_by_name(name: str):
    """Return a clan row by name (case-insensitive) or None."""
    if not name:
        return None
    with db.conn() as c:
        return c.execute(
            "SELECT * FROM clans WHERE name=? COLLATE NOCASE",
            (name.strip(),),
        ).fetchone()


def clan_by_id(clan_id: int):
    """Return a clan row by id or None."""
    with db.conn() as c:
        return c.execute(
            "SELECT * FROM clans WHERE id=?", (clan_id,),
        ).fetchone()


def members(clan_id: int) -> list:
    """Return all members with role and player info."""
    with db.conn() as c:
        return c.execute(
            "SELECT m.user_id, m.role, m.joined_at, "
            "p.first_name, p.username, p.exp "
            "FROM clan_members m "
            "LEFT JOIN players p ON p.user_id=m.user_id "
            "WHERE m.clan_id=? "
            "ORDER BY CASE m.role "
            "  WHEN 'leader' THEN 0 "
            "  WHEN 'officer' THEN 1 "
            "  ELSE 2 END, p.first_name",
            (clan_id,),
        ).fetchall()


def member_count(clan_id: int) -> int:
    """Total number of members in a clan."""
    with db.conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM clan_members WHERE clan_id=?",
            (clan_id,),
        ).fetchone()[0]


def _role_of(user_id: int, clan_id: int):
    """Return the role of a user in a clan or None if not a member."""
    with db.conn() as c:
        row = c.execute(
            "SELECT role FROM clan_members "
            "WHERE user_id=? AND clan_id=?",
            (user_id, clan_id),
        ).fetchone()
        return row["role"] if row else None


def _require(actor: int, clan_id: int, allowed: tuple) -> str:
    """Ensure actor has an allowed role. Returns the role."""
    role = _role_of(actor, clan_id)
    if role not in allowed:
        raise ClanError("You don't have permission for that.")
    return role


# =============================================================
# LIFECYCLE
# =============================================================
def create(user_id: int, name: str) -> int:
    """Create a new clan. Returns the new clan ID."""
    name = _valid_name(name)
    if membership(user_id):
        raise ClanError("Leave your current clan before creating a new one.")
    if clan_by_name(name):
        raise ClanError("That clan name is already taken.")
    if not db.spend(user_id, "crystals", CREATE_COST):
        raise ClanError(f"A clan costs {CREATE_COST} crystals.")
    with db.conn() as c:
        cur = c.execute(
            "INSERT INTO clans(name,treasure_yens,treasure_gems,"
            "treasure_crystals,perks_json,announcement) "
            "VALUES(?,0,0,0,'{}','')",
            (name,),
        )
        clan_id = cur.lastrowid
        c.execute(
            "INSERT INTO clan_members(user_id,clan_id,role) "
            "VALUES(?,?,'leader')",
            (user_id, clan_id),
        )
    return clan_id


def join(user_id: int, name: str) -> int:
    """Join an existing clan. Returns the clan ID."""
    if membership(user_id):
        raise ClanError("Leave your current clan first.")
    clan = clan_by_name(name)
    if clan is None:
        raise ClanError("No clan with that name.")
    with db.conn() as c:
        c.execute(
            "INSERT INTO clan_members(user_id,clan_id,role) "
            "VALUES(?,?,'member')",
            (user_id, clan["id"]),
        )
    return clan["id"]


def leave(user_id: int) -> str:
    """
    Leave the current clan.
    Returns 'left' or 'disbanded'.
    """
    m = membership(user_id)
    if m is None:
        raise ClanError("You are not in a clan.")
    others = [
        r for r in members(m["clan_id"])
        if r["user_id"] != user_id
    ]
    if _role_of(user_id, m["clan_id"]) == "leader" and others:
        raise ClanError(
            "Give leadership away first with "
            "/clan transfer <target>."
        )
    with db.conn() as c:
        c.execute(
            "DELETE FROM clan_members WHERE user_id=?", (user_id,),
        )
        if not others:
            c.execute(
                "DELETE FROM clan_raids WHERE clan_id=?", (m["clan_id"],),
            )
            c.execute(
                "DELETE FROM clan_territory WHERE clan_id=?",
                (m["clan_id"],),
            )
            c.execute(
                "DELETE FROM clans WHERE id=?", (m["clan_id"],),
            )
            return "disbanded"
    return "left"


def disband(user_id: int) -> None:
    """Disband the entire clan. Only leader can do this."""
    m = membership(user_id)
    if m is None:
        raise ClanError("You are not in a clan.")
    _require(user_id, m["clan_id"], ("leader",))
    with db.conn() as c:
        c.execute(
            "DELETE FROM clan_members WHERE clan_id=?", (m["clan_id"],),
        )
        c.execute(
            "DELETE FROM clan_raids WHERE clan_id=?", (m["clan_id"],),
        )
        c.execute(
            "DELETE FROM clan_territory WHERE clan_id=?",
            (m["clan_id"],),
        )
        c.execute(
            "DELETE FROM clans WHERE id=?", (m["clan_id"],),
        )


# =============================================================
# MEMBER MANAGEMENT
# =============================================================
def add(actor: int, target: int) -> None:
    """Add a member to the actor's clan. Leader/officer only."""
    m = membership(actor)
    if m is None:
        raise ClanError("You are not in a clan.")
    _require(actor, m["clan_id"], ("leader", "officer"))
    if membership(target):
        raise ClanError("That player is already in a clan.")
    with db.conn() as c:
        c.execute(
            "INSERT INTO clan_members(user_id,clan_id,role) "
            "VALUES(?,?,'member')",
            (target, m["clan_id"]),
        )


def remove(actor: int, target: int) -> None:
    """Kick a member from the clan."""
    m = membership(actor)
    if m is None:
        raise ClanError("You are not in a clan.")
    tm = membership(target)
    if tm is None or tm["clan_id"] != m["clan_id"]:
        raise ClanError("That player is not in your clan.")
    if actor == target:
        raise ClanError("Use /clan leave to leave.")
    my_role = _require(actor, m["clan_id"], ("leader", "officer"))
    their_role = _role_of(target, m["clan_id"])
    if their_role == "leader":
        raise ClanError("You cannot remove the leader.")
    if my_role == "officer" and their_role != "member":
        raise ClanError("Officers can only remove members.")
    with db.conn() as c:
        c.execute(
            "DELETE FROM clan_members WHERE user_id=?", (target,),
        )


def promote(actor: int, target: int) -> None:
    """Promote a member to officer. Leader only."""
    m = membership(actor)
    if m is None:
        raise ClanError("You are not in a clan.")
    tm = membership(target)
    if tm is None or tm["clan_id"] != m["clan_id"]:
        raise ClanError("That player is not in your clan.")
    _require(actor, m["clan_id"], ("leader",))
    if _role_of(target, m["clan_id"]) != "member":
        raise ClanError("Only members can be promoted to officer.")
    with db.conn() as c:
        c.execute(
            "UPDATE clan_members SET role='officer' WHERE user_id=?",
            (target,),
        )


def demote(actor: int, target: int) -> None:
    """Demote an officer to member. Leader only."""
    m = membership(actor)
    if m is None:
        raise ClanError("You are not in a clan.")
    tm = membership(target)
    if tm is None or tm["clan_id"] != m["clan_id"]:
        raise ClanError("That player is not in your clan.")
    _require(actor, m["clan_id"], ("leader",))
    if _role_of(target, m["clan_id"]) != "officer":
        raise ClanError("Only officers can be demoted.")
    with db.conn() as c:
        c.execute(
            "UPDATE clan_members SET role='member' WHERE user_id=?",
            (target,),
        )


def transfer(actor: int, target: int) -> None:
    """Transfer clan leadership. Leader only."""
    m = membership(actor)
    if m is None:
        raise ClanError("You are not in a clan.")
    tm = membership(target)
    if tm is None or tm["clan_id"] != m["clan_id"]:
        raise ClanError("That player is not in your clan.")
    _require(actor, m["clan_id"], ("leader",))
    with db.conn() as c:
        c.execute(
            "UPDATE clan_members SET role='officer' WHERE user_id=?",
            (actor,),
        )
        c.execute(
            "UPDATE clan_members SET role='leader' WHERE user_id=?",
            (target,),
        )


# =============================================================
# LEADERBOARD
# =============================================================
def top_clans(limit: int = 10) -> list:
    """Top clans by member count."""
    with db.conn() as c:
        return c.execute(
            "SELECT k.name, COUNT(m.user_id) AS n "
            "FROM clans k "
            "LEFT JOIN clan_members m ON m.clan_id=k.id "
            "GROUP BY k.id ORDER BY n DESC, k.name LIMIT ?",
            (limit,),
        ).fetchall()


def all_clans() -> list:
    """Return all clans sorted by name."""
    with db.conn() as c:
        return c.execute(
            "SELECT * FROM clans ORDER BY name"
        ).fetchall()


# =============================================================
# ANNOUNCEMENTS
# =============================================================
def set_announcement(clan_id: int, text: str) -> None:
    """Update the clan announcement (truncated to 300 chars)."""
    with db.conn() as c:
        c.execute(
            "UPDATE clans SET announcement=? WHERE id=?",
            ((text or "")[:300], clan_id),
        )


def get_announcement(clan_id: int) -> str:
    """Return the clan announcement or empty string."""
    with db.conn() as c:
        row = c.execute(
            "SELECT announcement FROM clans WHERE id=?", (clan_id,),
        ).fetchone()
        return row["announcement"] if row else ""


# =============================================================
# TREASURE
# =============================================================
def add_treasure(clan_id: int, yens: int = 0, gems: int = 0,
                 crystals: int = 0) -> None:
    """Add resources to the clan vault."""
    yens = max(0, int(yens or 0))
    gems = max(0, int(gems or 0))
    crystals = max(0, int(crystals or 0))
    if yens == 0 and gems == 0 and crystals == 0:
        return
    with db.conn() as c:
        c.execute(
            "UPDATE clans SET "
            "treasure_yens=treasure_yens+?, "
            "treasure_gems=treasure_gems+?, "
            "treasure_crystals=treasure_crystals+? "
            "WHERE id=?",
            (yens, gems, crystals, clan_id),
        )


def withdraw_treasure(actor: int, yens: int = 0, gems: int = 0,
                      crystals: int = 0) -> None:
    """Withdraw from clan vault. Leader only."""
    m = membership(actor)
    if m is None:
        raise ClanError("You are not in a clan.")
    _require(actor, m["clan_id"], ("leader",))

    yens = max(0, int(yens or 0))
    gems = max(0, int(gems or 0))
    crystals = max(0, int(crystals or 0))

    with db.conn() as c:
        row = c.execute(
            "SELECT treasure_yens, treasure_gems, treasure_crystals "
            "FROM clans WHERE id=?",
            (m["clan_id"],),
        ).fetchone()
        if (yens > row["treasure_yens"]
                or gems > row["treasure_gems"]
                or crystals > row["treasure_crystals"]):
            raise ClanError("Not enough treasure in the vault.")
        c.execute(
            "UPDATE clans SET "
            "treasure_yens=treasure_yens-?, "
            "treasure_gems=treasure_gems-?, "
            "treasure_crystals=treasure_crystals-? "
            "WHERE id=?",
            (yens, gems, crystals, m["clan_id"]),
        )
    db.give(actor, yens=yens, gems=gems, crystals=crystals)


# =============================================================
# PERKS
# =============================================================
def get_perks(clan_id: int) -> dict:
    """Return the perk dict for a clan (empty if none)."""
    with db.conn() as c:
        row = c.execute(
            "SELECT perks_json FROM clans WHERE id=?", (clan_id,),
        ).fetchone()
        if not row:
            return {}
        try:
            return json.loads(row["perks_json"] or "{}")
        except (ValueError, TypeError):
            return {}


def has_perk(clan_id: int, code: str) -> bool:
    """Return True if the clan has researched this perk."""
    return code in get_perks(clan_id)


def buy_perk(actor: int, code: str) -> None:
    """Research a perk using vault crystals. Leader only."""
    m = membership(actor)
    if m is None:
        raise ClanError("You are not in a clan.")
    _require(actor, m["clan_id"], ("leader",))
    if code not in G.CLAN_PERKS:
        raise ClanError("Unknown perk.")
    perks = get_perks(m["clan_id"])
    if code in perks:
        raise ClanError("Perk already researched.")
    cost = G.CLAN_PERKS[code]["cost"]
    if m["treasure_crystals"] < cost:
        raise ClanError(
            f"Not enough crystals in clan vault (need {cost})."
        )
    perks[code] = 1
    with db.conn() as c:
        c.execute(
            "UPDATE clans SET "
            "treasure_crystals=treasure_crystals-?, perks_json=? "
            "WHERE id=?",
            (cost, json.dumps(perks), m["clan_id"]),
        )


# =============================================================
# TERRITORY
# =============================================================
def capture_planet(actor: int, planet: str) -> None:
    """Capture a planet for the clan. Leader only."""
    m = membership(actor)
    if m is None:
        raise ClanError("You are not in a clan.")
    _require(actor, m["clan_id"], ("leader",))
    if planet not in G.PLANETS:
        raise ClanError("Unknown planet.")
    with db.conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO clan_territory(clan_id,planet) "
            "VALUES(?,?)",
            (m["clan_id"], planet),
        )


def list_territory(clan_id: int) -> list:
    """Return all territories held by a clan."""
    with db.conn() as c:
        return c.execute(
            "SELECT planet, captured_at FROM clan_territory "
            "WHERE clan_id=?",
            (clan_id,),
        ).fetchall()


def planet_owner(planet: str):
    """Return the clan that owns a planet, or None."""
    with db.conn() as c:
        return c.execute(
            "SELECT clan_id FROM clan_territory WHERE planet=?",
            (planet,),
        ).fetchone()


# =============================================================
# CLAN RAIDS
# =============================================================
def clan_raid_state(clan_id: int):
    """Return the currently active raid row or None."""
    with db.conn() as c:
        return c.execute(
            "SELECT * FROM clan_raids "
            "WHERE clan_id=? AND active=1",
            (clan_id,),
        ).fetchone()


def clan_raid_all(clan_id: int) -> list:
    """Return all raid rows (active + completed) for a clan."""
    with db.conn() as c:
        return c.execute(
            "SELECT * FROM clan_raids WHERE clan_id=?",
            (clan_id,),
        ).fetchall()


def clan_raid_start(clan_id: int, boss_name: str,
                    hp: int, dmg: int) -> None:
    """Start (or restart) a raid boss for this clan."""
    with db.conn() as c:
        c.execute(
            "INSERT INTO clan_raids("
            "clan_id,boss_name,hp,max_hp,damage_json,active,started_at"
            ") VALUES(?,?,?,?,?,1,?) "
            "ON CONFLICT(clan_id,boss_name) DO UPDATE SET "
            "hp=excluded.hp, max_hp=excluded.max_hp, "
            "damage_json=excluded.damage_json, active=1, "
            "started_at=excluded.started_at",
            (clan_id, boss_name, hp, hp, json.dumps({}),
             int(time.time())),
        )


def clan_raid_hit(clan_id: int, user_id: int, damage: int):
    """
    Apply damage to the active clan raid.
    Returns (hp_left, defeated, damage_map, boss_name) or None.
    """
    damage = max(0, int(damage))
    with db.conn() as c:
        row = c.execute(
            "SELECT * FROM clan_raids "
            "WHERE clan_id=? AND active=1",
            (clan_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            dmg_by = json.loads(row["damage_json"] or "{}")
        except (ValueError, TypeError):
            dmg_by = {}
        key = str(user_id)
        dmg_by[key] = int(dmg_by.get(key, 0)) + damage
        hp = max(0, int(row["hp"]) - damage)
        defeated = hp == 0
        c.execute(
            "UPDATE clan_raids SET "
            "hp=?, damage_json=?, active=? "
            "WHERE clan_id=? AND boss_name=?",
            (hp, json.dumps(dmg_by), 0 if defeated else 1,
             clan_id, row["boss_name"]),
        )
        return hp, defeated, dmg_by, row["boss_name"]


def clan_raid_reset(clan_id: int, boss_name: str) -> None:
    """Mark a raid as inactive and reset HP for next run."""
    with db.conn() as c:
        c.execute(
            "UPDATE clan_raids SET active=0 "
            "WHERE clan_id=? AND boss_name=?",
            (clan_id, boss_name),
        )


def clan_raid_damage_report(clan_id: int) -> list:
    """Return sorted damage report for the active raid."""
    st = clan_raid_state(clan_id)
    if not st:
        return []
    try:
        dmg_by = json.loads(st["damage_json"] or "{}")
    except (ValueError, TypeError):
        dmg_by = {}
    rows = []
    for uid_str, dmg in dmg_by.items():
        try:
            uid_int = int(uid_str)
            p = db.player(uid_int)
            name = p["first_name"] if p else uid_str
        except (ValueError, TypeError):
            name = uid_str
        rows.append({"name": name, "damage": int(dmg)})
    rows.sort(key=lambda r: r["damage"], reverse=True)
    return rows


# =============================================================
# SELF-TEST (run: python clans.py)
# =============================================================
if __name__ == "__main__":
    db.init()
    print("✅ Clans tables initialized")

    test_uid = 999_999_998
    db.ensure_player(test_uid, "Clan Tester", "clan_test")
    db.give(test_uid, crystals=500)
    print(f"✅ Test player ready, crystals={db.player(test_uid)['crystals']}")

    # Clean up any prior test clan
    m = membership(test_uid)
    if m:
        try:
            leave(test_uid)
        except ClanError:
            pass

    clan_id = create(test_uid, "Testclan")
    print(f"✅ Created clan id={clan_id}")

    m = membership(test_uid)
    print(f"✅ Membership: {dict(m)}")

    top = top_clans(5)
    print(f"✅ Top clans: {[dict(r) for r in top]}")

    set_announcement(clan_id, "Welcome to the test clan!")
    print(f"✅ Announcement: {get_announcement(clan_id)}")

    add_treasure(clan_id, yens=1000, gems=50, crystals=10)
    m = membership(test_uid)
    print(f"✅ Treasure: yens={m['treasure_yens']}, "
          f"crystals={m['treasure_crystals']}")

    buy_perk(test_uid, "war_drums")
    print(f"✅ Perks: {get_perks(clan_id)}")

    capture_planet(test_uid, "Earth")
    print(f"✅ Territories: {[dict(r) for r in list_territory(clan_id)]}")

    clan_raid_start(clan_id, "Perfect Cell", 40000, 399)
    st = clan_raid_state(clan_id)
    print(f"✅ Raid started: {st['boss_name']} "
          f"HP={st['hp']}/{st['max_hp']}")

    result = clan_raid_hit(clan_id, test_uid, 5000)
    print(f"✅ Raid hit: hp={result[0]}, defeated={result[1]}")

    print(f"✅ Damage report: {clan_raid_damage_report(clan_id)}")

    leave(test_uid)
    print("✅ Left clan (disbanded)")

    print("\n🎉 All clans.py self-tests passed!")
