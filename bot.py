from __future__ import annotations

"""
Dragon Ball RPG Telegram Bot — Main Entry
==========================================
This file is delivered in 3 parts. All parts combine into a single
complete bot.py of ~2,400 lines.

Part 1 (this file block):  helpers, /start, /help, /profile, /team,
                            /explore (3 options), /heal, /combathistory,
                            /achievements, /quests
Part 2 (say "continue part 2"): /shop, /buy, /inventory, /gacha,
                            /mycharacters, /equip, /skills, /learn, /wish
Part 3 (say "continue part 3"): /summon, /daily, /weekly, /rankup,
                            /travel, /fusion, /clan (all subcommands),
                            /leaderboard, /raid, /raid_start, /raid_attack,
                            all /admin_* commands, main()
"""

import os
import random
import time
from html import escape

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters,
)

import clans
import combat
import db
import game_data as G


# =============================================================
# CONSTANTS & GLOBAL STATE
# =============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

# Tracks users who are mid-menu in /explore
EXPLORE_STATES: dict[int, dict] = {}

# Tracks users mid-purchase in /buy (multi-step)
BUY_STATES: dict[int, dict] = {}

# Tracks users mid-fusion selection
FUSION_STATES: dict[int, dict] = {}

# Tracks users mid-clan management
CLAN_MGMT_STATES: dict[int, dict] = {}


# =============================================================
# PERMISSION HELPERS
# =============================================================
def is_owner(uid: int) -> bool:
    """Return True if the user is the bot owner."""
    return uid == OWNER_ID


def is_admin(uid: int) -> bool:
    """Return True if the user has admin flag in the database."""
    p = db.player(uid)
    return bool(p and p["admin"])


def is_banned(uid: int) -> bool:
    """Return True if the user is banned from the bot."""
    p = db.player(uid)
    return bool(p and p["banned"])


def require_admin(func):
    """Decorator: reject command unless caller is admin or owner."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not (is_owner(uid) or is_admin(uid)):
            await update.message.reply_text(
                "⛔ You are not allowed to use admin commands."
            )
            return
        await func(update, context)
    return wrapper


def require_owner(func):
    """Decorator: reject command unless caller is owner."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not is_owner(uid):
            await update.message.reply_text(
                "⛔ Only the bot owner can use this command."
            )
            return
        await func(update, context)
    return wrapper


def require_not_banned(func):
    """Decorator: reject command if caller is banned."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if is_banned(uid):
            await update.message.reply_text(
                "🚫 You are banned from using this bot."
            )
            return
        await func(update, context)
    return wrapper


# =============================================================
# PLAYER CREATION / LOOKUP HELPERS
# =============================================================
def ensure_player_for_update(update: Update) -> None:
    """Create or refresh the player record for this Telegram user."""
    user = update.effective_user
    if user is None:
        return
    db.ensure_player(
        user.id,
        user.first_name or "Player",
        user.username,
    )
    db.ensure_quests_current(user.id)


def get_player_or_none(uid: int):
    """Return the player row or None if not registered yet."""
    return db.player(uid)


def resolve_target_id(args: list[str], update: Update) -> int | None:
    """Resolve a target user from reply, @username, or numeric id."""
    # 1. Reply-to message takes priority
    if update.message and update.message.reply_to_message:
        u = update.message.reply_to_message.from_user
        if u and not u.is_bot:
            return u.id
    if not args:
        return None
    tok = args[0].strip()
    if not tok:
        return None
    # 2. @username lookup
    if tok.startswith("@"):
        row = db.player_by_username(tok[1:])
        return row["user_id"] if row else None
    # 3. Numeric id
    if tok.isdigit():
        return int(tok)
    return None


def parse_amount(value: str) -> int:
    """Parse a positive integer amount, return 0 on failure."""
    try:
        amt = int(value)
    except (TypeError, ValueError):
        return 0
    return max(1, amt) if amt > 0 else 0


def parse_amount_zero_ok(value: str) -> int:
    """Parse a non-negative integer amount (0 allowed)."""
    try:
        amt = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, amt)


def resource_name(name: str) -> str | None:
    """Map user-facing resource alias to database column name."""
    aliases = {
        "yen": "yens", "yens": "yens", "money": "yens",
        "gem": "gems", "gems": "gems",
        "crystal": "crystals", "crystals": "crystals",
        "ticket": "tickets", "tickets": "tickets",
        "skill_point": "skill_points",
        "skill_points": "skill_points",
        "sp": "skill_points",
        "elite_key": "keys_elite", "elite_keys": "keys_elite",
        "boss_key": "keys_boss", "boss_keys": "keys_boss",
        "exp": "exp",
    }
    return aliases.get((name or "").strip().lower())


# =============================================================
# WORLD / STATS HELPERS
# =============================================================
def get_world_multiplier(uid: int) -> float:
    """Return the reward multiplier of the player's current world."""
    p = db.player(uid)
    if not p:
        return 1.0
    world = p["travel"] or "Earth"
    return G.PLANETS.get(world, G.PLANETS["Earth"])["multiplier"]


def _char_stats_by_name(name: str) -> tuple[int, int, int, int]:
    """Return (hp, atk, spd, crit) for a character name."""
    for row in G.CHARACTERS:
        # row = (name, rarity, hp, atk, spd, crit)
        if row[0] == name:
            return (row[2], row[3], row[4], row[5])
    return (0, 0, 0, 0)


def player_stats(uid: int) -> dict:
    """Compute full player stats including HP tracking."""
    p = db.player(uid)
    if not p:
        return {
            "atk": 0, "hp": 0, "spd": 0, "crit": 0,
            "level": 1, "rank": 1, "char_rarity": None,
            "current_hp": 0, "max_hp": 0,
        }

    lvl = db.level_of(p["exp"])
    atk = 10 + lvl * 3
    hp = 100 + lvl * 12
    spd = 10 + lvl // 3
    crit = 5

    # Weapon / armor bonuses
    if p["weapon"] in G.EQUIPMENT:
        atk += G.EQUIPMENT[p["weapon"]][1]
    if p["armor"] in G.EQUIPMENT:
        hp += G.EQUIPMENT[p["armor"]][1] * 2

    # Character bonus
    char_rarity = None
    if p["equipped_char"]:
        for name, rarity in db.characters(uid):
            if name == p["equipped_char"]:
                char_rarity = rarity
                chp, catk, cspd, ccrit = _char_stats_by_name(name)
                hp += chp
                atk += catk
                spd += cspd
                crit += ccrit
                break

    # Skills bonus
    atk += sum(G.SKILL_ATK.get(s, 0) for s in db.skills(uid))

    # Rank multiplier
    rank = int(p["rank"] or 1)
    rank_mult = 1 + (rank - 1) * G.RANK_BONUS
    atk = int(atk * rank_mult)
    hp = int(hp * rank_mult)

    current_hp = db.get_current_hp(uid, hp)

    return {
        "atk": atk, "hp": hp, "spd": spd, "crit": crit,
        "level": lvl, "rank": rank, "char_rarity": char_rarity,
        "current_hp": current_hp, "max_hp": hp,
    }


def _hp_bar(cur: int, mx: int) -> str:
    """Render a 10-segment HP bar."""
    if mx <= 0:
        return "▯▯▯▯▯▯▯▯▯▯ 0%"
    pct = max(0, min(100, int(cur * 100 / mx)))
    filled = pct // 10
    return "█" * filled + "▯" * (10 - filled) + f" {pct}%"


def _progress_bar(cur: int, target: int) -> str:
    """Render a quest progress bar."""
    if target <= 0:
        return "0%"
    pct = min(100, int(cur * 100 / target))
    filled = pct // 10
    return f"{'█' * filled}{'▯' * (10 - filled)} {min(cur, target)}/{target}"


# =============================================================
# BATTLE EXECUTION
# =============================================================
def run_battle(
    uid: int,
    enemy_name: str,
    enemy_hp: int,
    enemy_dmg: int,
    enrage: bool = False,
    is_boss: bool = False,
    is_summon: bool = False,
    skip_hp: bool = False,
) -> dict:
    """
    Run a battle using the player's CURRENT HP.
    Logs the fight to CombatHistory.
    Persists HP back to the database (floor 1 on defeat).
    """
    s = player_stats(uid)
    start_hp = s["max_hp"] if skip_hp else s["current_hp"]
    if start_hp <= 0:
        start_hp = s["max_hp"]

    eng = combat.CombatEngine(
        s["atk"], start_hp, crit=s["crit"], speed=s["spd"]
    )
    won, left, log = eng.fight(enemy_name, enemy_hp, enemy_dmg, enrage)

    outcome = "victory" if won else "defeat"

    # Log to CombatHistory
    hist = combat.CombatHistory(uid)
    hist.log(
        enemy_name, enemy_hp,
        eng.damage_dealt, eng.damage_taken,
        outcome, eng.rounds,
    )

    # Persist HP: on defeat, leave at 1 HP
    if skip_hp:
        db.set_current_hp(uid, s["max_hp"])
    else:
        new_hp = 1 if (not won and left <= 0) else left
        db.set_current_hp(uid, max(1, new_hp))

    return {
        "won": won,
        "left_hp": left,
        "log": log,
        "dealt": eng.damage_dealt,
        "taken": eng.damage_taken,
        "rounds": eng.rounds,
    }


def apply_drops(uid: int, is_boss: bool, is_summon: bool = False) -> list[str]:
    """
    Random loot drop after a fight.
    Bosses/summons get higher drop rates.
    Returns list of human-readable drop strings.
    """
    drops = []

    # Equipment
    drop_chance = 0.35 if (is_boss or is_summon) else 0.15
    if random.random() < drop_chance:
        item = random.choice(list(G.EQUIPMENT))
        db.add_item(uid, item)
        drops.append(f"📦 {item}")

    # Dragon Ball
    db_chance = 0.45 if (is_boss or is_summon) else 0.10
    if random.random() < db_chance:
        star = random.choice(G.DRAGON_BALL_STARS)
        db.add_dragon_ball(uid, star)
        drops.append(f"🐉 Dragon Ball {star}★")

    # Gacha Ticket
    ticket_chance = 0.30 if (is_boss or is_summon) else 0.05
    if random.random() < ticket_chance:
        db.give(uid, tickets=1)
        drops.append("🎫 Ticket")

    # Skill
    skill_chance = 0.20 if is_boss else 0.02
    if random.random() < skill_chance:
        skill = random.choice(list(G.SKILLS))
        if db.add_skill(uid, skill):
            drops.append(f"🌟 Skill: {skill}")

    # Fusion material on boss only
    if is_boss and random.random() < 0.25:
        mat = random.choice(list(G.FUSION_MATERIALS))
        db.add_item(uid, mat)
        drops.append(f"🧬 {mat}")

    return drops


# =============================================================
# /start — Main entry, gives starter pack on first run
# =============================================================
@require_not_banned
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)

    # Give starter pack to brand-new players only
    if p and int(p["exp"] or 0) == 0 and int(p["total_battles"] or 0) == 0:
        rarity = random.choice(G.STARTER_PACK["pool"])
        pool = [n for n, r, *_ in G.CHARACTERS if r == rarity]
        if pool:
            name = random.choice(pool)
            db.add_character(uid, name, rarity)
            db.set_field(uid, "equipped_char", name)
            db.give(
                uid,
                yens=G.STARTER_PACK["bonus_yens"],
                gems=G.STARTER_PACK["bonus_gems"],
                tickets=G.STARTER_PACK["bonus_tickets"],
            )
            await update.message.reply_text(
                f"🎁 <b>Starter Pack Unlocked!</b>\n\n"
                f"You received <b>{escape(name)}</b> ({rarity})!\n"
                f"Automatically equipped as your lead warrior.\n"
                f"+{G.STARTER_PACK['bonus_yens']} yens, "
                f"+{G.STARTER_PACK['bonus_gems']} gems, "
                f"+{G.STARTER_PACK['bonus_tickets']} tickets.",
                parse_mode=ParseMode.HTML,
            )

    await update.message.reply_text(
        "🐉 <b>Dragon Battle RPG</b>\n\n"
        "<b>⚔️ Combat</b>\n"
        "/explore — 3-option patrol (Battle / Run / Info)\n"
        "/combathistory — last 10 battles\n"
        "/achievements — milestone tracker\n"
        "/quests — daily / weekly / monthly\n"
        "/heal — use Senzu Beans & potions\n\n"
        "<b>👤 Player</b>\n"
        "/profile — full profile + HP bar\n"
        "/team — equipped setup\n"
        "/inventory — bag contents\n"
        "/mycharacters — warriors grouped by rank\n"
        "/equip &lt;name&gt; — equip weapon/armor/char\n\n"
        "<b>🛒 Economy</b>\n"
        "/shop — 6-category market\n"
        "/shop &lt;category&gt; — view items\n"
        "/buy &lt;id&gt; [qty] — bulk purchase\n"
        "/gacha [qty] [banner] — roll warriors\n"
        "/skills — view learnable skills\n"
        "/learn &lt;skill&gt; — learn a skill\n"
        "/wish — Shenron wish (7 dragon balls)\n"
        "/fusion &lt;char1&gt; + &lt;char2&gt;\n\n"
        "<b>🏰 Clans</b>\n"
        "/clan — full clan menu (9 subcommands)\n"
        "/leaderboard — top 10 players\n\n"
        "<b>🌍 Travel & Progression</b>\n"
        "/travel — 6 planet realms\n"
        "/travel &lt;n&gt; — travel to planet\n"
        "/rankup — ascension (costs crystals)\n"
        "/daily, /weekly\n\n"
        "<b>🔱 Bosses</b>\n"
        "/summon &lt;elite|mythical|legendary&gt;\n"
        "/raid — world raid status\n"
        "/raid_attack — hit raid boss (0 cooldown)\n"
        "/raid_start — (owner only) start raid",
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# /help — How to play
# =============================================================
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 <b>How to Play</b>\n\n"
        "<b>Combat</b>\n"
        "1. /explore → 1 (Battle) to fight NPCs.\n"
        "2. Every 15 NPC wins = world boss encounter.\n"
        "3. On defeat, HP drops to 1. Use /heal → Senzu Bean.\n"
        "4. HP persists across battles until healed.\n\n"
        "<b>Progression</b>\n"
        "5. /rankup multiplies all stats by +15% per rank.\n"
        "6. Travel to higher planets for bigger rewards.\n"
        "7. Complete /quests for daily/weekly/monthly bonuses.\n\n"
        "<b>Bosses</b>\n"
        "8. /summon bosses grant 5x rewards, drop dragon balls.\n"
        "9. /raid is a 120k HP world boss with 0 cooldown.\n"
        "10. Clan raids share HP across all members.\n\n"
        "<b>Special</b>\n"
        "11. /wish → Shenron needs all 7 dragon balls.\n"
        "12. /fusion combines two warriors for higher tier.\n"
        "13. Achievements unlock automatically when met.",
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# /profile — Full player profile with HP bar
# =============================================================
@require_not_banned
async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    s = player_stats(uid)
    stats = db.combat_stats(uid)
    clan = clans.membership(uid)
    bar = _hp_bar(s["current_hp"], s["max_hp"])
    world = p["travel"] or "Earth"
    world_mult = get_world_multiplier(uid)

    text = (
        f"👤 <b>{escape(p['first_name'])}</b>\n"
        f"🆔 <code>{uid}</code>\n"
        f"Level: <b>{s['level']}</b>  "
        f"Rank: <b>{s['rank']}</b> ({G.RANKS.get(s['rank'], '?')})\n"
        f"World: {world} (x{world_mult})\n\n"
        f"❤️ HP: {s['current_hp']}/{s['max_hp']}\n"
        f"   {bar}\n"
        f"💪 ATK: <b>{s['atk']}</b>\n"
        f"⚡ SPD: {s['spd']}\n"
        f"🎯 CRIT: {s['crit']}%\n\n"
        f"💴 Yens: {p['yens']:,}\n"
        f"💎 Gems: {p['gems']:,}\n"
        f"🔮 Crystals: {p['crystals']:,}\n"
        f"🎫 Tickets: {p['tickets']}\n"
        f"🌟 Skill Points: {p['skill_points']}\n"
        f"🔑 Elite Keys: {p['keys_elite']}\n"
        f"🗝️ Boss Keys: {p['keys_boss']}\n\n"
        f"⚔️ Weapon: {escape(p['weapon'] or 'none')}\n"
        f"🛡️ Armor: {escape(p['armor'] or 'none')}\n"
        f"🧙 Character: {escape(p['equipped_char'] or 'none')}\n\n"
        f"📊 Battles: {stats['battles']}\n"
        f"   {stats['wins']}W / {stats['losses']}L\n"
        f"🩸 Dealt: {stats['dealt']:,}\n"
        f"🩹 Taken: {stats['taken']:,}\n\n"
        f"🏰 Clan: {escape(clan['name']) if clan else 'none'}\n"
        f"✨ EXP: {p['exp']}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# =============================================================
# /team — Equipped setup overview
# =============================================================
@require_not_banned
async def cmd_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    s = player_stats(uid)
    bar = _hp_bar(s["current_hp"], s["max_hp"])

    await update.message.reply_text(
        f"🛡️ <b>Team Setup</b>\n\n"
        f"Character: {escape(p['equipped_char'] or 'none')}\n"
        f"Weapon: {escape(p['weapon'] or 'none')}\n"
        f"Armor: {escape(p['armor'] or 'none')}\n\n"
        f"❤️ HP: {s['current_hp']}/{s['max_hp']}\n"
        f"   {bar}\n"
        f"💪 ATK: {s['atk']}\n"
        f"⚡ SPD: {s['spd']}\n"
        f"🎯 CRIT: {s['crit']}%\n"
        f"⭐ Rank: {s['rank']} ({G.RANKS.get(s['rank'], '?')})\n\n"
        f"Use /equip &lt;name&gt; to change equipment.\n"
        f"Use /mycharacters to see your roster.",
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# /explore — 3-option patrol menu
# =============================================================
@require_not_banned
async def cmd_explore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    EXPLORE_STATES[uid] = {"mode": "explore"}
    world = p["travel"] or "Earth"
    mult = get_world_multiplier(uid)
    streak = int(p["npc_streak"] or 0)
    to_boss = G.NPC_STREAK_FOR_BOSS - streak
    s = player_stats(uid)
    bar = _hp_bar(s["current_hp"], s["max_hp"])

    await update.message.reply_text(
        f"🧭 <b>Explore — {escape(world)}</b> "
        f"(x{mult} rewards)\n\n"
        f"❤️ HP: {s['current_hp']}/{s['max_hp']}\n"
        f"   {bar}\n"
        f"👹 Boss in {to_boss} more NPC wins\n\n"
        f"<b>1.</b> ⚔️ Battle\n"
        f"<b>2.</b> 🏃 Run away\n"
        f"<b>3.</b> ℹ️ Info\n\n"
        f"Send a number (1, 2, or 3).",
        parse_mode=ParseMode.HTML,
    )


async def handle_explore_reply(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    """Handles the 1/2/3 reply after /explore."""
    if update.message is None:
        return
    uid = update.effective_user.id
    if uid not in EXPLORE_STATES:
        return

    choice = (update.message.text or "").strip()
    if choice not in {"1", "2", "3"}:
        return

    p = db.player(uid)
    if not p:
        return

    EXPLORE_STATES.pop(uid, None)
    ensure_player_for_update(update)

    # ----- Option 3: INFO -----
    if choice == "3":
        world = p["travel"] or "Earth"
        data = G.PLANETS[world]
        streak = int(p["npc_streak"] or 0)
        to_boss = G.NPC_STREAK_FOR_BOSS - streak
        s = player_stats(uid)
        bar = _hp_bar(s["current_hp"], s["max_hp"])

        await update.message.reply_text(
            f"ℹ️ <b>Info: {escape(world)}</b>\n\n"
            f"Level gate: {data['level_min']} – {data['level_max']}\n"
            f"Reward multiplier: x{data['multiplier']}\n"
            f"Lore: {data['desc']}\n\n"
            f"❤️ Your HP: {s['current_hp']}/{s['max_hp']}\n"
            f"   {bar}\n"
            f"👹 Boss in {to_boss} NPC wins.\n\n"
            f"Drop rates:\n"
            f"• Equipment: 15%\n"
            f"• Dragon Ball: 10%\n"
            f"• Ticket: 5%",
            parse_mode=ParseMode.HTML,
        )
        return

    # ----- Option 2: RUN AWAY -----
    if choice == "2":
        await update.message.reply_text(
            "🏃 You used Instant Transmission and escaped safely.\n"
            "No HP lost. No streak reset."
        )
        return

    # ----- Option 1: BATTLE -----
    s = player_stats(uid)
    if s["current_hp"] <= 1:
        await update.message.reply_text(
            "⚠️ <b>HP Critical!</b>\n\n"
            f"Your HP is {s['current_hp']}/{s['max_hp']}.\n"
            f"Use <code>/heal Senzu Bean</code> to restore before battling.",
            parse_mode=ParseMode.HTML,
        )
        return

    streak = int(p["npc_streak"] or 0) + 1
    is_boss = streak >= G.NPC_STREAK_FOR_BOSS
    world_mult = get_world_multiplier(uid)
    rank_mult = 1 + int(p["rank"] or 1) * 0.2

    # ---- Boss encounter ----
    if is_boss:
        boss = random.choice(G.BOSSES)
        result = run_battle(
            uid, boss["name"], boss["hp"], boss["dmg"],
            enrage=True, is_boss=True,
        )

        if result["won"]:
            yens = int(boss["yens"] * world_mult * rank_mult * 5)
            db.give(
                uid,
                yens=yens,
                gems=boss["gems"],
                crystals=boss["crystals"],
                tickets=boss["tickets"],
                skill_points=boss["skill_points"],
                exp=200,
            )
            drops = apply_drops(uid, is_boss=True)
            db.set_field(uid, "npc_streak", 0)

            ach = combat.CombatAchievements(uid)
            ach.check_after_battle(True, result["taken"], is_boss=True)

            quest = combat.QuestTracker(uid)
            quest.on_boss_kill()
            quest.on_yens_earned(yens)
            quest.on_battle_win()

            s2 = player_stats(uid)
            bar = _hp_bar(s2["current_hp"], s2["max_hp"])
            text = (
                f"🏆 <b>BOSS VICTORY: {escape(boss['name'])}</b>\n\n"
                f"💴 +{yens:,} yens\n"
                f"💎 +{boss['gems']} gems\n"
                f"🔮 +{boss['crystals']} crystals\n"
                f"🎫 +{boss['tickets']} tickets\n"
                f"🌟 +{boss['skill_points']} SP\n"
                f"✨ +200 exp\n"
            )
            if drops:
                text += f"\n<b>Drops:</b>\n" + "\n".join(f"• {d}" for d in drops)
            text += (
                f"\n\n⚔️ Damage: {result['dealt']:,} dealt / "
                f"{result['taken']:,} taken\n"
                f"❤️ HP: {s2['current_hp']}/{s2['max_hp']}\n"
                f"   {bar}\n"
            )
            text += ach.reward_text()
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        else:
            s2 = player_stats(uid)
            text = (
                f"❌ <b>Defeat by {escape(boss['name'])}!</b>\n\n"
                f"❤️ HP restored to 1.\n"
                f"Use /heal → Senzu Bean to recover.\n\n"
                f"⚔️ Damage: {result['dealt']:,} dealt / "
                f"{result['taken']:,} taken\n"
                f"Boss stays at full HP for next attempt."
            )
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    # ---- NPC encounter ----
    npc = random.choice(G.NPCS)
    result = run_battle(uid, npc["name"], npc["hp"], npc["dmg"])

    if result["won"]:
        yens = int(npc["reward"] * world_mult * rank_mult)
        db.give(uid, yens=yens, exp=60, skill_points=5)
        drops = apply_drops(uid, is_boss=False)
        db.set_field(uid, "npc_streak", streak)

        ach = combat.CombatAchievements(uid)
        ach.check_after_battle(True, result["taken"])

        quest = combat.QuestTracker(uid)
        quest.on_npc_kill()
        quest.on_battle_win()
        quest.on_yens_earned(yens)

        s2 = player_stats(uid)
        bar = _hp_bar(s2["current_hp"], s2["max_hp"])
        to_next = G.NPC_STREAK_FOR_BOSS - streak
        text = (
            f"✅ <b>Victory vs {escape(npc['name'])}!</b>\n\n"
            f"💴 +{yens:,} yens\n"
            f"✨ +60 exp\n"
            f"🌟 +5 SP\n"
        )
        if drops:
            text += f"\n<b>Drops:</b>\n" + "\n".join(f"• {d}" for d in drops)
        text += (
            f"\n\n⚔️ Damage: {result['dealt']:,} dealt / "
            f"{result['taken']:,} taken\n"
            f"❤️ HP: {s2['current_hp']}/{s2['max_hp']}\n"
            f"   {bar}\n"
            f"👹 Boss in {to_next} more wins\n"
        )
        text += ach.reward_text()
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        text = (
            f"❌ <b>Defeat by {escape(npc['name'])}!</b>\n\n"
            f"❤️ HP restored to 1.\n"
            f"Use /heal → Senzu Bean to recover.\n\n"
            f"⚔️ Damage: {result['dealt']:,} dealt / "
            f"{result['taken']:,} taken"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# =============================================================
# /heal — Consume healing items
# =============================================================
@require_not_banned
async def cmd_heal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    s = player_stats(uid)
    inv = {row["item"]: row["qty"] for row in db.items(uid)}
    bar = _hp_bar(s["current_hp"], s["max_hp"])

    # If no argument: show inventory of healing items
    if not context.args:
        lines = [
            f"❤️ <b>HP:</b> {s['current_hp']}/{s['max_hp']}",
            f"   {bar}\n",
            "🧪 <b>Healing Items in Bag:</b>",
        ]
        any_items = False
        for name, frac in G.HEALING.items():
            qty = inv.get(name, 0)
            if qty > 0:
                any_items = True
                lines.append(
                    f"• {name} ×{qty} — restores {int(frac * 100)}% HP"
                )
        if not any_items:
            lines.append("• <i>You have no healing items.</i>")
            lines.append(
                "\n💡 Buy some with /shop → Healing"
            )
        lines.append("\nUsage: <code>/heal Senzu Bean</code>")
        await update.message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )
        return

    # If argument: consume that item
    item_name = " ".join(context.args).strip()
    matched = None
    for name in G.HEALING:
        if name.lower() == item_name.lower():
            matched = name
            break

    if matched is None:
        await update.message.reply_text(
            f"❓ Unknown healing item: <b>{escape(item_name)}</b>\n"
            f"Try: /heal Senzu Bean",
            parse_mode=ParseMode.HTML,
        )
        return

    ok, new_hp = db.apply_heal(uid, s["max_hp"], matched)
    if not ok:
        await update.message.reply_text(
            f"❌ You don't have <b>{escape(matched)}</b> in your bag.",
            parse_mode=ParseMode.HTML,
        )
        return

    bar2 = _hp_bar(new_hp, s["max_hp"])
    await update.message.reply_text(
        f"💚 <b>Used {escape(matched)}!</b>\n\n"
        f"❤️ HP: {new_hp}/{s['max_hp']}\n"
        f"   {bar2}",
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# /combathistory — Last 10 battles
# =============================================================
@require_not_banned
async def cmd_combathistory(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    hist = combat.CombatHistory(uid)

    rows = hist.recent()
    if not rows:
        await update.message.reply_text(
            "📜 <b>Combat History</b>\n\n"
            "No battles recorded yet.\n"
            "Use /explore → 1 (Battle) to start fighting.",
            parse_mode=ParseMode.HTML,
        )
        return

    stats = db.combat_stats(uid)
    lines = ["📜 <b>Combat History — Last 10 Battles</b>\n"]

    for i, row in enumerate(rows, 1):
        icon = "✅" if row["outcome"] == "victory" else "❌"
        lines.append(
            f"{i}. {icon} vs {escape(row['enemy_name'])}\n"
            f"   ⚔️ {row['damage_dealt']:,} dealt · "
            f"{row['damage_taken']:,} taken\n"
            f"   🔄 {row['rounds']} rounds"
        )
        if row["rewards_text"]:
            lines.append(f"   🎁 {escape(row['rewards_text'])}")

    lines.append("")
    lines.append("─" * 20)
    lines.append(
        f"📊 <b>Overall Record</b>\n"
        f"Battles: {stats['battles']}\n"
        f"Wins: {stats['wins']}\n"
        f"Losses: {stats['losses']}\n"
        f"Damage dealt: {stats['dealt']:,}\n"
        f"Damage taken: {stats['taken']:,}"
    )

    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML
    )


# =============================================================
# /achievements — Milestone tracker
# =============================================================
@require_not_banned
async def cmd_achievements(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    unlocked = db.player_achievements(uid)
    have = {row["code"] for row in unlocked}
    stats = db.combat_stats(uid)

    lines = [
        "🏆 <b>Achievements</b>\n",
        f"Unlocked: {len(have)} / {len(G.ACHIEVEMENTS)}\n",
    ]

    # Group achievements by rough category
    categories = {
        "Combat": ["first_blood", "battle_10", "battle_50",
                   "battle_100", "battle_500", "flawless",
                   "explore_vet"],
        "Bosses": ["boss_slayer", "summon_hunter", "raid_warrior",
                   "clan_raid_clear"],
        "Clans": ["clan_founder", "clan_leader"],
        "Collection": ["dragon_collector", "mythical_owner",
                       "omni_owner"],
        "Wealth": ["rich", "gem_hoarder"],
        "Progression": ["rank_5", "rank_10", "fusion_master",
                        "traveler"],
    }

    for cat, codes in categories.items():
        lines.append(f"\n<b>{cat}</b>")
        for code in codes:
            if code not in G.ACHIEVEMENTS:
                continue
            info = G.ACHIEVEMENTS[code]
            icon = "✅" if code in have else "▫️"
            lines.append(f"{icon} {info['name']} — {info['desc']}")

    lines.append(
        f"\n📊 Your stats: {stats['battles']} battles · "
        f"{stats['wins']} wins"
    )

    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML
    )


# =============================================================
# /quests — Daily / Weekly / Monthly quest tracking
# =============================================================
@require_not_banned
async def cmd_quests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    db.ensure_quests_current(uid)

    lines = ["📋 <b>Active Quests</b>\n"]

    # Helper to render a quest group
    def render_group(kind: str, title: str, table: dict) -> list[str]:
        out = [f"<b>{title}</b>"]
        claimed = db.quest_claimed(uid, kind)
        for code, info in table.items():
            cur = db.quest_progress(uid, kind, code)
            target = info["target"]
            done = cur >= target
            claimed_flag = claimed.get(code, 0) == 1
            bar = _progress_bar(cur, target)

            if claimed_flag:
                icon = "✅"
            elif done:
                icon = "🎁"
            else:
                icon = "▫️"

            out.append(
                f"{icon} {info['name']} — {bar}"
                f"\n   Reward: {info.get('yens', 0):,} yens · "
                f"{info.get('gems', 0)} gems · "
                f"{info.get('crystals', 0)} crystals"
            )
            if done and not claimed_flag:
                out.append(
                    f"   → <code>/claim_{kind} {code}</code>"
                )
        out.append("")
        return out

    lines += render_group("daily", "☀️ Daily Quests",
                          G.DAILY_QUESTS)
    lines += render_group("weekly", "📅 Weekly Quests",
                          G.WEEKLY_QUESTS)
    lines += render_group("monthly", "🌙 Monthly Quests",
                          G.MONTHLY_QUESTS)

    lines.append(
        "<i>Quests reset automatically at midnight UTC (daily), "
        "Monday (weekly), and month start (monthly).</i>"
    )

    # Split into chunks to avoid Telegram 4096-char limit
    text = "\n".join(lines)
    if len(text) < 4000:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            "\n".join(lines[:25]), parse_mode=ParseMode.HTML
        )
        await update.message.reply_text(
            "\n".join(lines[25:50]), parse_mode=ParseMode.HTML
        )
        if len(lines) > 50:
            await update.message.reply_text(
                "\n".join(lines[50:]), parse_mode=ParseMode.HTML
            )


# =============================================================
# /claim_daily, /claim_weekly, /claim_monthly — Quest claimers
# =============================================================
@require_not_banned
async def cmd_claim_daily(update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Usage: /claim_daily <quest_code>\n"
            "Example: /claim_daily daily_npc_10"
        )
        return
    code = context.args[0]
    info = db.claim_quest(uid, "daily", code)
    if info is None:
        await update.message.reply_text(
            "❌ Quest not complete or already claimed."
        )
        return
    await update.message.reply_text(
        f"🎁 <b>Quest claimed: {info['name']}</b>\n\n"
        f"💴 +{info.get('yens', 0):,} yens\n"
        f"💎 +{info.get('gems', 0)} gems\n"
        f"🔮 +{info.get('crystals', 0)} crystals",
        parse_mode=ParseMode.HTML,
    )


@require_not_banned
async def cmd_claim_weekly(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Usage: /claim_weekly <quest_code>\n"
            "Example: /claim_weekly weekly_npc_100"
        )
        return
    code = context.args[0]
    info = db.claim_quest(uid, "weekly", code)
    if info is None:
        await update.message.reply_text(
            "❌ Quest not complete or already claimed."
        )
        return
    await update.message.reply_text(
        f"🎁 <b>Quest claimed: {info['name']}</b>\n\n"
        f"💴 +{info.get('yens', 0):,} yens\n"
        f"💎 +{info.get('gems', 0)} gems\n"
        f"🔮 +{info.get('crystals', 0)} crystals",
        parse_mode=ParseMode.HTML,
    )


@require_not_banned
async def cmd_claim_monthly(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Usage: /claim_monthly <quest_code>\n"
            "Example: /claim_monthly monthly_npc_500"
        )
        return
    code = context.args[0]
    info = db.claim_quest(uid, "monthly", code)
    if info is None:
        await update.message.reply_text(
            "❌ Quest not complete or already claimed."
        )
        return
    await update.message.reply_text(
        f"🎁 <b>Quest claimed: {info['name']}</b>\n\n"
        f"💴 +{info.get('yens', 0):,} yens\n"
        f"💎 +{info.get('gems', 0)} gems\n"
        f"🔮 +{info.get('crystals', 0)} crystals",
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# END OF PART 1
# =============================================================
# Part 2 will continue with:
#   /shop, /buy, /inventory, /gacha, /mycharacters, /equip,
#   /skills, /learn, /wish
# Part 3 will continue with:
#   /summon, /daily, /weekly, /rankup, /travel, /fusion,
#   /clan (all subcommands), /leaderboard, /raid, /raid_start,
#   /raid_attack, all /admin_* commands, main()
# =============================================================
# PART 2 — SHOP / BUY / INVENTORY / GACHA / CHARACTERS / EQUIP
# =============================================================
# This block continues bot.py from Part 1. Append directly after
# the "# END OF PART 1" comment.
# =============================================================


# =============================================================
# SHOP CATEGORY KEY MAP
# =============================================================
SHOP_CATEGORY_ALIASES = {
    "weapon": "weapon", "weapons": "weapon", "1": "weapon",
    "armor": "armor", "armors": "armor", "armour": "armor",
    "armours": "armor", "2": "armor",
    "crystal": "crystal", "crystals": "crystal", "3": "crystal",
    "heal": "heal", "healing": "heal", "potion": "heal",
    "potions": "heal", "4": "heal",
    "fusion": "fusion", "fusion_material": "fusion",
    "fusion_materials": "fusion", "5": "fusion",
    "ticket": "ticket", "tickets": "ticket", "key": "key",
    "keys": "key", "6": "key",
}


def normalize_shop_category(token: str) -> str | None:
    """Map user input to a shop category key."""
    return SHOP_CATEGORY_ALIASES.get((token or "").strip().lower())


def shop_items_in_category(category: str) -> list[tuple[int, tuple]]:
    """Return list of (shop_id, item_tuple) for a category."""
    results = []
    for sid, item in G.SHOP.items():
        name, price, currency, kind, amount = item
        if category == "key":
            if kind in ("key_elite", "key_boss"):
                results.append((sid, item))
        elif category == "weapon":
            if kind == "weapon":
                results.append((sid, item))
        elif category == "armor":
            if kind == "armor":
                results.append((sid, item))
        elif category == "crystal":
            if kind == "crystal":
                results.append((sid, item))
        elif category == "heal":
            if kind == "heal":
                results.append((sid, item))
        elif category == "fusion":
            if kind == "fusion":
                results.append((sid, item))
        elif category == "ticket":
            if kind == "ticket":
                results.append((sid, item))
    return results


# =============================================================
# /shop — 6-category marketplace
# =============================================================
@require_not_banned
async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    # No argument: show 6-category menu
    if not context.args:
        lines = [
            "🛒 <b>Capsule Corp Marketplace</b>\n",
            f"💴 {p['yens']:,} yens · "
            f"💎 {p['gems']:,} gems · "
            f"🔮 {p['crystals']:,} crystals\n",
            "Choose a department:\n",
            "<b>1.</b> ⚔️ Weapons",
            "<b>2.</b> 🛡️ Armors",
            "<b>3.</b> 🔮 Crystals",
            "<b>4.</b> 🧪 Healing Potions & Senzu Beans",
            "<b>5.</b> 🧬 Fusion Materials",
            "<b>6.</b> 🎫 Tickets & Summon Keys\n",
            "<i>Usage:</i> <code>/shop weapons</code>",
            "<i>Buy:</i> <code>/buy 1 10</code> (item 1, x10)",
        ]
        await update.message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )
        return

    # With argument: show that category's items
    category = normalize_shop_category(context.args[0])
    if category is None:
        await update.message.reply_text(
            "❓ Unknown category.\n"
            "Try: weapons, armors, crystals, healing, fusion, tickets"
        )
        return

    items = shop_items_in_category(category)
    if not items:
        await update.message.reply_text("No items in that category.")
        return

    # Build category header
    cat_names = {
        "weapon": "⚔️ Weapons",
        "armor": "🛡️ Armors",
        "crystal": "🔮 Crystals",
        "heal": "🧪 Healing",
        "fusion": "🧬 Fusion Materials",
        "ticket": "🎫 Gacha Tickets",
        "key": "🗝️ Summon Keys",
    }
    lines = [
        f"🛒 <b>{cat_names[category]}</b>\n",
        f"💴 {p['yens']:,} · 💎 {p['gems']:,} · "
        f"🔮 {p['crystals']:,}\n",
    ]

    for sid, item in items:
        name, price, currency, kind, amount = item
        cur_icon = {"yens": "💴", "gems": "💎",
                    "crystals": "🔮"}.get(currency, "•")
        qty_text = f" ×{amount}" if amount > 1 else ""
        lines.append(
            f"<b>#{sid}</b> {escape(name)}{qty_text}\n"
            f"   {cur_icon} {price:,} {currency}"
        )

    lines.append(
        "\n💡 <b>Buy:</b> <code>/buy &lt;id&gt; [qty]</code>"
    )
    lines.append(
        "<i>Bulk discounts auto-applied for qty ≥ 5.</i>"
    )

    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML
    )


# =============================================================
# /buy — Purchase with bulk quantity
# =============================================================
def _bulk_price(base_price: int, qty: int) -> int:
    """Apply bulk discount: 5% off for 5+, 10% for 10+, 15% for 50+."""
    total = base_price * qty
    if qty >= 50:
        total = int(total * 0.85)
    elif qty >= 10:
        total = int(total * 0.90)
    elif qty >= 5:
        total = int(total * 0.95)
    return total


@require_not_banned
async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    # Parse args: /buy <id> [qty]
    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/buy &lt;item_id&gt; [quantity]</code>\n"
            "Example: <code>/buy 5 10</code> — buy item #5 ×10\n\n"
            "First use <code>/shop</code> to see item IDs.",
            parse_mode=ParseMode.HTML,
        )
        return

    item_id_str = context.args[0]
    if not item_id_str.isdigit():
        await update.message.reply_text(
            "❌ Item ID must be a number.\n"
            "Example: <code>/buy 5 10</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    sid = int(item_id_str)
    item = G.SHOP.get(sid)
    if item is None:
        await update.message.reply_text(
            f"❌ No item with ID #{sid}.\n"
            f"Use /shop to browse items.",
        )
        return

    # Parse qty (default 1, max 100)
    qty = 1
    if len(context.args) >= 2:
        qty_parsed = parse_amount(context.args[1])
        if qty_parsed <= 0:
            await update.message.reply_text(
                "❌ Quantity must be a positive number."
            )
            return
        qty = min(qty_parsed, 100)  # Cap at 100 per purchase

    name, price, currency, kind, amount = item
    total_price = _bulk_price(price, qty)

    # Try to spend
    if not db.spend(uid, currency, total_price):
        # Insufficient funds message
        p = db.player(uid)
        have = p[currency] if p else 0
        await update.message.reply_text(
            f"❌ <b>Not enough {currency}.</b>\n\n"
            f"Need: {total_price:,} {currency}\n"
            f"Have: {have:,} {currency}\n\n"
            f"{'💡 Bulk discount applied!' if qty >= 5 else ''}",
            parse_mode=ParseMode.HTML,
        )
        return

    # Deliver the item
    delivered_text = ""
    total_amount = amount * qty

    if kind == "weapon":
        db.add_item(uid, name, qty)
        delivered_text = f"⚔️ {name} ×{qty} added to inventory"
    elif kind == "armor":
        db.add_item(uid, name, qty)
        delivered_text = f"🛡️ {name} ×{qty} added to inventory"
    elif kind == "crystal":
        db.give(uid, crystals=total_amount)
        delivered_text = f"🔮 +{total_amount} crystals"
    elif kind == "ticket":
        db.give(uid, tickets=total_amount)
        delivered_text = f"🎫 +{total_amount} gacha tickets"
    elif kind == "heal":
        db.add_item(uid, name, qty)
        delivered_text = f"🧪 {name} ×{qty} added to inventory"
    elif kind == "fusion":
        db.add_item(uid, name, qty)
        delivered_text = f"🧬 {name} ×{qty} added to inventory"
    elif kind == "key_elite":
        db.give(uid, keys_elite=total_amount)
        delivered_text = f"🔑 +{total_amount} Elite Keys"
    elif kind == "key_boss":
        db.give(uid, keys_boss=total_amount)
        delivered_text = f"🗝️ +{total_amount} Boss Keys"
    else:
        delivered_text = f"✅ {name} ×{qty}"

    # Show discount if applied
    discount_text = ""
    if qty >= 50:
        discount_text = "\n🎉 15% bulk discount applied!"
    elif qty >= 10:
        discount_text = "\n🎉 10% bulk discount applied!"
    elif qty >= 5:
        discount_text = "\n🎉 5% bulk discount applied!"

    await update.message.reply_text(
        f"✅ <b>Purchase Complete</b>\n\n"
        f"🛒 {escape(name)} ×{qty}\n"
        f"💴 Paid: {total_price:,} {currency}\n"
        f"{discount_text}\n\n"
        f"{delivered_text}",
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# /inventory — Full bag view
# =============================================================
@require_not_banned
async def cmd_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    rows = db.items(uid)

    if not rows:
        await update.message.reply_text(
            "🎒 <b>Inventory Empty</b>\n\n"
            "Buy items with /shop or earn them from battles.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Group items
    groups = {
        "⚔️ Weapons": [],
        "🛡️ Armors": [],
        "🧪 Healing": [],
        "🧬 Fusion": [],
        "📦 Other": [],
    }
    for row in rows:
        item_name = row["item"]
        qty = row["qty"]
        if item_name in G.WEAPONS:
            groups["⚔️ Weapons"].append((item_name, qty))
        elif item_name in G.ARMORS:
            groups["🛡️ Armors"].append((item_name, qty))
        elif item_name in G.HEALING:
            groups["🧪 Healing"].append((item_name, qty))
        elif item_name in G.FUSION_MATERIALS:
            groups["🧬 Fusion"].append((item_name, qty))
        else:
            groups["📦 Other"].append((item_name, qty))

    lines = ["🎒 <b>Inventory</b>\n"]
    for header, items in groups.items():
        if not items:
            continue
        lines.append(f"\n<b>{header}</b>")
        for item_name, qty in items:
            lines.append(f"• {escape(item_name)} ×{qty}")

    lines.append(
        "\n💡 Use <code>/equip &lt;name&gt;</code> to equip "
        "weapons/armors.\n"
        "Use <code>/heal &lt;item&gt;</code> to consume potions."
    )

    # Split if too long
    text = "\n".join(lines)
    if len(text) < 4000:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            "\n".join(lines[:25]), parse_mode=ParseMode.HTML
        )
        await update.message.reply_text(
            "\n".join(lines[25:]), parse_mode=ParseMode.HTML
        )


# =============================================================
# /gacha — Roll warriors with banners
# =============================================================
@require_not_banned
async def cmd_gacha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    # Parse args: /gacha [qty] [banner]
    qty = 1
    banner_key = "standard"

    if context.args:
        # First arg: quantity (if numeric)
        if context.args[0].isdigit():
            qty = min(int(context.args[0]), 50)
            if qty < 1:
                qty = 1
            # Second arg: banner
            if len(context.args) >= 2:
                banner_key = context.args[1].lower()
        else:
            # First arg is banner name
            banner_key = context.args[0].lower()

    banner = G.GACHA_BANNERS.get(banner_key)
    if banner is None:
        await update.message.reply_text(
            f"❓ Unknown banner: <b>{escape(banner_key)}</b>\n\n"
            f"Available banners:\n"
            f"• <code>standard</code> — Normal rates (1 ticket)\n"
            f"• <code>hero</code> — Boosted Legendary & Mythical (1 ticket)\n"
            f"• <code>god</code> — Boosted Mythical & Omni (2 tickets)\n"
            f"• <code>omni</code> — Boosted Omni x3 (3 tickets)",
            parse_mode=ParseMode.HTML,
        )
        return

    ticket_cost = banner["cost"] * qty
    if p["tickets"] < ticket_cost:
        await update.message.reply_text(
            f"❌ <b>Not enough tickets.</b>\n\n"
            f"Need: {ticket_cost} tickets ({qty} roll{'s' if qty > 1 else ''} "
            f"× {banner['cost']} per roll)\n"
            f"Have: {p['tickets']} tickets\n\n"
            f"💡 Buy more with <code>/shop tickets</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    if not db.spend(uid, "tickets", ticket_cost):
        await update.message.reply_text("❌ Failed to spend tickets.")
        return

    # Roll
    rolls = []
    rarity_counts = {}
    for _ in range(qty):
        rarity = db.roll_rarity(banner["bonus"])
        name = db.pick_character_of_rarity(rarity)
        if name is None:
            continue
        db.add_character(uid, name, rarity)
        rolls.append((name, rarity))
        rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1

    # Quest tracking
    quest = combat.QuestTracker(uid)
    quest.on_gacha(qty)

    # Achievement checks
    ach = combat.CombatAchievements(uid)
    for name, rarity in rolls:
        ach.check_character(rarity)

    # Format result
    rarity_icons = {
        "common": "⚪", "rare": "🔵", "epic": "🟣",
        "legendary": "🟡", "mythical": "🔴", "omni": "👑",
    }
    lines = [
        f"🎰 <b>Gacha Results — {escape(banner['name'])}</b>\n",
        f"Rolled {qty} × cost {banner['cost']} = "
        f"-{ticket_cost} tickets\n",
    ]

    if qty <= 20:
        for i, (name, rarity) in enumerate(rolls, 1):
            icon = rarity_icons.get(rarity, "•")
            lines.append(
                f"{i}. {icon} <b>{escape(name)}</b> "
                f"({rarity.capitalize()})"
            )
    else:
        # Compact format for large rolls
        lines.append("<b>Summary:</b>")
        for rarity in ["omni", "mythical", "legendary",
                       "epic", "rare", "common"]:
            count = rarity_counts.get(rarity, 0)
            if count:
                icon = rarity_icons.get(rarity, "•")
                lines.append(f"{icon} {rarity.capitalize()}: {count}")
        # Show legendary+ characters individually
        high_value = [(n, r) for n, r in rolls
                      if r in ("omni", "mythical", "legendary")]
        if high_value:
            lines.append("\n<b>High-value pulls:</b>")
            for name, rarity in high_value:
                icon = rarity_icons.get(rarity, "•")
                lines.append(f"{icon} {escape(name)} ({rarity.capitalize()})")

    lines.append(
        f"\n💎 Check /mycharacters to see your full roster."
    )
    lines.append(ach.reward_text())

    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML
    )


# =============================================================
# /mycharacters — Strict rank-grouped roster
# =============================================================
@require_not_banned
async def cmd_mycharacters(update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    groups = db.characters_by_rarity(uid)
    total = sum(len(v) for v in groups.values())

    if total == 0:
        await update.message.reply_text(
            "🧙 <b>Your Warriors</b>\n\n"
            "You have no characters yet.\n"
            "Roll the gacha with /gacha to get warriors!",
            parse_mode=ParseMode.HTML,
        )
        return

    # Header
    lines = [
        f"🧙 <b>Your Warriors</b> — {total} total\n",
        f"Equipped: <b>{escape(p['equipped_char'] or 'none')}</b>\n",
    ]

    # Strict rank order with headers
    rank_order = [
        ("omni", "👑 OMNI KINGS", "═══"),
        ("mythical", "🔴 MYTHICAL", "───"),
        ("legendary", "🟡 LEGENDARY", "───"),
        ("epic", "🟣 EPIC", "───"),
        ("rare", "🔵 RARE", "───"),
        ("common", "⚪ COMMON", "───"),
    ]

    for rarity, header, divider in rank_order:
        names = groups.get(rarity, [])
        if not names:
            continue
        lines.append(f"\n<b>{divider} {header} {divider}</b>")
        lines.append(f"<i>{len(names)} warrior{'s' if len(names) != 1 else ''}</i>")
        for name in names:
            marker = " ⭐" if name == p["equipped_char"] else ""
            # Show stats inline
            chp, catk, cspd, ccrit = _char_stats_by_name(name)
            lines.append(
                f"• <b>{escape(name)}</b>{marker}\n"
                f"   ❤️{chp} ⚔️{catk} ⚡{cspd} 🎯{ccrit}%"
            )

    lines.append(
        f"\n💡 <code>/equip &lt;name&gt;</code> to set lead warrior"
    )

    # Split if too long
    text = "\n".join(lines)
    if len(text) < 4000:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        # Send in chunks
        chunk = []
        chunk_len = 0
        for line in lines:
            if chunk_len + len(line) > 3800:
                await update.message.reply_text(
                    "\n".join(chunk), parse_mode=ParseMode.HTML
                )
                chunk = []
                chunk_len = 0
            chunk.append(line)
            chunk_len += len(line) + 1
        if chunk:
            await update.message.reply_text(
                "\n".join(chunk), parse_mode=ParseMode.HTML
            )


# =============================================================
# /equip — Equip weapon / armor / character
# =============================================================
@require_not_banned
async def cmd_equip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    if not context.args:
        await update.message.reply_text(
            "⚔️ <b>Equip</b>\n\n"
            f"Current weapon: {escape(p['weapon'] or 'none')}\n"
            f"Current armor: {escape(p['armor'] or 'none')}\n"
            f"Current character: {escape(p['equipped_char'] or 'none')}\n\n"
            "Usage: <code>/equip &lt;name&gt;</code>\n"
            "Example: <code>/equip Z Sword</code>\n"
            "Example: <code>/equip Ultra Instinct Goku</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Join all args to support multi-word names
    name = " ".join(context.args).strip()

    # Case 1: Equipment (weapon or armor)
    if name in G.EQUIPMENT:
        # Check ownership
        owned = {row["item"] for row in db.items(uid)}
        if name not in owned:
            await update.message.reply_text(
                f"❌ You don't own <b>{escape(name)}</b>.\n"
                f"Buy it with /shop or get it from battles.",
                parse_mode=ParseMode.HTML,
            )
            return

        slot = G.EQUIPMENT[name][0]  # "weapon" or "armor"
        old = p[slot] if p else None
        db.set_field(uid, slot, name)

        slot_icon = "⚔️" if slot == "weapon" else "🛡️"
        old_text = f"\n<i>Replaced: {escape(old)}</i>" if old else ""
        await update.message.reply_text(
            f"{slot_icon} <b>Equipped {escape(name)}</b>{old_text}",
            parse_mode=ParseMode.HTML,
        )
        return

    # Case 2: Character
    if db.has_character(uid, name):
        old = p["equipped_char"] if p else None
        db.set_field(uid, "equipped_char", name)
        old_text = f"\n<i>Replaced: {escape(old)}</i>" if old else ""

        # Look up rarity for display
        rarity = "common"
        for cname, crarity in db.characters(uid):
            if cname == name:
                rarity = crarity
                break

        await update.message.reply_text(
            f"🧙 <b>Equipped {escape(name)}</b> "
            f"({rarity.capitalize()}){old_text}\n\n"
            f"Use /team to see updated stats.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Case 3: Not found
    await update.message.reply_text(
        f"❌ You don't own <b>{escape(name)}</b> "
        f"(not in inventory or character roster).\n\n"
        f"• Check /inventory for gear\n"
        f"• Check /mycharacters for warriors",
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# /skills — View learnable skills
# =============================================================
@require_not_banned
async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    learned = set(db.skills(uid))
    sp = p["skill_points"]

    lines = [
        f"🌟 <b>Ki Dojo — Skills</b>\n",
        f"Your SP: <b>{sp}</b>\n",
        f"Learned: {len(learned)} / {len(G.SKILLS)}\n",
    ]

    # Show learned first
    if learned:
        lines.append("\n<b>✅ Learned:</b>")
        for skill_name in sorted(learned):
            atk = G.SKILL_ATK.get(skill_name, 0)
            lines.append(f"• {skill_name} (+{atk} ATK)")

    # Then available
    available = [
        (name, cost) for name, cost in G.SKILLS.items()
        if name not in learned
    ]
    if available:
        lines.append("\n<b>📖 Available to Learn:</b>")
        for name, cost in sorted(available, key=lambda x: x[1]):
            atk = G.SKILL_ATK.get(name, 0)
            can_learn = "✨" if sp >= cost else "🔒"
            lines.append(
                f"{can_learn} <b>{escape(name)}</b>\n"
                f"   {cost} SP → +{atk} ATK"
            )

    lines.append(
        "\n💡 <code>/learn &lt;skill name&gt;</code> to learn"
    )

    # Chunk if needed
    text = "\n".join(lines)
    if len(text) < 4000:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            "\n".join(lines[:25]), parse_mode=ParseMode.HTML
        )
        await update.message.reply_text(
            "\n".join(lines[25:]), parse_mode=ParseMode.HTML
        )


# =============================================================
# /learn — Learn a skill
# =============================================================
@require_not_banned
async def cmd_learn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/learn &lt;skill name&gt;</code>\n"
            "Example: <code>/learn Kaioken</code>\n\n"
            "Use /skills to see the full list.",
            parse_mode=ParseMode.HTML,
        )
        return

    skill_name = " ".join(context.args).strip()

    # Case-insensitive lookup
    matched = None
    for name in G.SKILLS:
        if name.lower() == skill_name.lower():
            matched = name
            break

    if matched is None:
        await update.message.reply_text(
            f"❓ Unknown skill: <b>{escape(skill_name)}</b>\n"
            f"Use /skills to see the full list.",
            parse_mode=ParseMode.HTML,
        )
        return

    if matched in db.skills(uid):
        await update.message.reply_text(
            f"✅ You already know <b>{escape(matched)}</b>.",
            parse_mode=ParseMode.HTML,
        )
        return

    cost = G.SKILLS[matched]
    if p["skill_points"] < cost:
        await update.message.reply_text(
            f"❌ <b>Not enough SP.</b>\n\n"
            f"<b>{escape(matched)}</b> costs {cost} SP.\n"
            f"You have {p['skill_points']} SP.\n\n"
            f"💡 Earn SP from battles and daily rewards.",
            parse_mode=ParseMode.HTML,
        )
        return

    if not db.spend(uid, "skill_points", cost):
        await update.message.reply_text("❌ Failed to spend SP.")
        return

    db.add_skill(uid, matched)
    atk_bonus = G.SKILL_ATK.get(matched, 0)
    new_sp = p["skill_points"] - cost

    await update.message.reply_text(
        f"🌟 <b>Skill Learned: {escape(matched)}</b>\n\n"
        f"⚔️ +{atk_bonus} ATK added permanently\n"
        f"🌟 SP remaining: {new_sp}\n\n"
        f"<i>Your attacks now hit harder in battle!</i>",
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# /wish — Shenron wish with 7 dragon balls
# =============================================================
@require_not_banned
async def cmd_wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    have = db.dragon_balls(uid)
    missing = [s for s in G.DRAGON_BALL_STARS if have.get(s, 0) < 1]

    # Show ball status
    ball_line = []
    for s in G.DRAGON_BALL_STARS:
        if have.get(s, 0) >= 1:
            ball_line.append(f"{s}★")
        else:
            ball_line.append(f"▫️")
    balls_text = " ".join(ball_line)

    if missing:
        missing_text = ", ".join(f"{s}★" for s in missing)
        await update.message.reply_text(
            f"🐉 <b>Shenron Altar</b>\n\n"
            f"Your dragon balls: {balls_text}\n\n"
            f"❌ Missing: {missing_text}\n\n"
            f"You need all 7 dragon balls to summon Shenron.\n\n"
            f"💡 Bosses and summons drop dragon balls at "
            f"higher rates.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Consume balls
    if not db.take_one_of_each_dragon_ball(uid):
        await update.message.reply_text(
            "❌ Failed to consume dragon balls."
        )
        return

    # Roll the wish
    roll = random.random()
    result_text = ""

    if roll < 0.12:
        # Mythical character
        rarity = "mythical"
        names = [n for n, r, *_ in G.CHARACTERS if r == rarity]
        name = random.choice(names)
        db.add_character(uid, name, rarity)
        result_text = f"🔴 <b>Mythical Character:</b> {escape(name)}"
        ach = combat.CombatAchievements(uid)
        ach.check_character("mythical")
    elif roll < 0.22:
        # Omni King (rare!)
        rarity = "omni"
        names = [n for n, r, *_ in G.CHARACTERS if r == rarity]
        name = random.choice(names)
        db.add_character(uid, name, rarity)
        result_text = f"👑 <b>OMNI KING:</b> {escape(name)}"
        ach = combat.CombatAchievements(uid)
        ach.check_character("omni")
    elif roll < 0.40:
        db.add_item(uid, "Deadly Divine Sword")
        result_text = "⚔️ <b>Weapon:</b> Deadly Divine Sword"
    elif roll < 0.55:
        # Random skill
        skill = random.choice(list(G.SKILLS))
        db.add_skill(uid, skill)
        result_text = f"🌟 <b>Skill:</b> {escape(skill)}"
    elif roll < 0.80:
        db.give(uid, yens=100000, gems=250, crystals=15,
                skill_points=20)
        result_text = (
            "💴 <b>Treasure:</b> 100,000 yens, 250 gems, "
            "15 crystals, 20 SP"
        )
    else:
        db.give(uid, gems=500, crystals=20)
        result_text = "💎 <b>Treasure:</b> 500 gems, 20 crystals"

    ach = combat.CombatAchievements(uid)
    ach.check_dragon_balls()

    await update.message.reply_text(
        f"🐉 <b>Shenron has awakened!</b>\n\n"
        f"Your wish is granted:\n\n"
        f"{result_text}\n\n"
        f"<i>All 7 dragon balls consumed and scattered "
        f"across the multiverse.</i>"
        + ach.reward_text(),
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# END OF PART 2
# =============================================================
# Part 3 will continue with:
#   /summon, /daily, /weekly, /rankup, /travel, /fusion,
#   /clan (all subcommands), /leaderboard, /raid, /raid_start,
#   /raid_attack, all /admin_* commands, and main()
#
# Say "continue part 3" to receive the final part.
# =============================================================
# =============================================================
# PART 3 — SUMMON / DAILY / RANKUP / TRAVEL / FUSION / CLAN /
#          LEADERBOARD / RAID / ADMIN / MAIN
# =============================================================
# This is the final block. Append after "# END OF PART 2".
# After this, bot.py is complete and runnable.
# =============================================================


# =============================================================
# /summon — Key-based boss battle with PERSISTENT HP
# =============================================================
@require_not_banned
async def cmd_summon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    if not context.args:
        lines = ["🔱 <b>Summon Gate</b>\n"]
        for key, info in G.SUMMONS.items():
            persisted = db.summon_hp(uid, key)
            hp_text = (f"{persisted:,}/{info['hp']:,} HP remaining"
                       if persisted else "full HP")
            lines.append(
                f"<b>{key.capitalize()}</b>\n"
                f"  Boss: {info['name']}\n"
                f"  Cost: 1 {info['key'].replace('keys_', '').capitalize()} Key\n"
                f"  Rewards: 5× normal\n"
                f"  Status: {hp_text}\n"
                f"  <code>/summon {key}</code>"
            )
        lines.append(
            "\n<i>💡 If defeated, boss HP is preserved — "
            "eat a Senzu and try again!</i>"
        )
        await update.message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )
        return

    kind = context.args[0].lower()
    data = G.SUMMONS.get(kind)
    if data is None:
        await update.message.reply_text(
            "❓ Unknown summon.\n"
            "Use: <code>/summon elite</code>, "
            "<code>/summon mythical</code>, or "
            "<code>/summon legendary</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    key_col = data["key"]
    if p[key_col] <= 0:
        await update.message.reply_text(
            f"🔑 <b>No keys!</b>\n\n"
            f"You need 1 {key_col.replace('keys_', '').capitalize()} Key.\n"
            f"Buy with <code>/shop tickets</code> or defeat bosses.",
            parse_mode=ParseMode.HTML,
        )
        return

    # HP check
    s = player_stats(uid)
    if s["current_hp"] <= 1:
        await update.message.reply_text(
            "⚠️ <b>HP Critical!</b>\n\n"
            f"Your HP is {s['current_hp']}/{s['max_hp']}.\n"
            f"Use <code>/heal Senzu Bean</code> first.",
            parse_mode=ParseMode.HTML,
        )
        return

    if not db.spend(uid, key_col, 1):
        await update.message.reply_text("❌ Failed to consume key.")
        return

    # Persistent HP — check if boss was already damaged
    boss_name = data["name"]
    boss_max_hp = data["hp"]
    persisted_hp = db.summon_hp(uid, kind)
    current_boss_hp = persisted_hp if persisted_hp else boss_max_hp

    result = run_battle(
        uid, boss_name, current_boss_hp, data["dmg"],
        enrage=True, is_boss=True, is_summon=True,
    )

    if result["won"]:
        # Big rewards
        mult = data["reward_mult"]
        yens = 20000 * mult
        gems = 50 * mult
        crystals = 6 * mult
        sp = 20 * mult
        exp = 500 * mult
        db.give(uid, yens=yens, gems=gems, crystals=crystals,
                skill_points=sp, exp=exp)

        drops = apply_drops(uid, is_boss=True, is_summon=True)
        # Extra dragon ball chance for summons
        if random.random() < 0.6:
            star = random.choice(G.DRAGON_BALL_STARS)
            db.add_dragon_ball(uid, star)
            drops.append(f"🐉 Dragon Ball {star}★")
        if random.random() < 0.4:
            skill = random.choice(list(G.SKILLS))
            if db.add_skill(uid, skill):
                drops.append(f"🌟 Skill: {skill}")

        # Reset persisted HP
        db.set_summon_hp(uid, kind, None)

        ach = combat.CombatAchievements(uid)
        ach.check_after_battle(True, result["taken"],
                               is_boss=True, is_summon=True)
        ach.check_dragon_balls()

        quest = combat.QuestTracker(uid)
        quest.on_summon_kill()
        quest.on_yens_earned(yens)

        s2 = player_stats(uid)
        bar = _hp_bar(s2["current_hp"], s2["max_hp"])
        lines = [
            f"🏆 <b>SUMMON VICTORY: {escape(boss_name)}</b>\n",
            f"💴 +{yens:,} yens",
            f"💎 +{gems} gems",
            f"🔮 +{crystals} crystals",
            f"🎫 +{sp} SP",
            f"✨ +{exp} exp",
        ]
        if drops:
            lines.append("\n<b>Bonus drops:</b>")
            for d in drops:
                lines.append(f"• {d}")
        lines.append(
            f"\n⚔️ {result['dealt']:,} dealt / "
            f"{result['taken']:,} taken\n"
            f"❤️ HP: {s2['current_hp']}/{s2['max_hp']}\n"
            f"   {bar}"
        )
        lines.append(ach.reward_text())
        await update.message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )
    else:
        # Store remaining boss HP
        boss_hp_left = max(0, current_boss_hp - result["dealt"])
        if boss_hp_left > 0:
            db.set_summon_hp(uid, kind, boss_hp_left)

        await update.message.reply_text(
            f"❌ <b>Defeated by {escape(boss_name)}!</b>\n\n"
            f"❤️ HP restored to 1. Use /heal Senzu Bean.\n\n"
            f"⚔️ {result['dealt']:,} dealt / "
            f"{result['taken']:,} taken\n\n"
            f"👹 <b>Boss HP preserved:</b> "
            f"{boss_hp_left:,}/{boss_max_hp:,}\n"
            f"<i>Heal up and finish it off!</i>",
            parse_mode=ParseMode.HTML,
        )


# =============================================================
# /daily, /weekly — Streak rewards
# =============================================================
@require_not_banned
async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    result = db.claim_daily(uid)
    if result is None:
        await update.message.reply_text(
            "📅 <b>Daily already claimed.</b>\n\n"
            "Come back tomorrow for your next reward!",
            parse_mode=ParseMode.HTML,
        )
        return

    streak, rewards = result
    parts = []
    for k, v in rewards.items():
        icon = {"yens": "💴", "gems": "💎",
                "crystals": "🔮", "tickets": "🎫",
                "skill_points": "🌟"}.get(k, "•")
        parts.append(f"{icon} +{v:,} {k}")

    await update.message.reply_text(
        f"📅 <b>Daily Reward Claimed!</b>\n\n"
        f"🔥 Streak: <b>{streak} day{'s' if streak != 1 else ''}</b>\n\n"
        + "\n".join(parts),
        parse_mode=ParseMode.HTML,
    )


@require_not_banned
async def cmd_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    result = db.claim_weekly(uid)
    if result is None:
        await update.message.reply_text(
            "📅 <b>Weekly already claimed.</b>\n\n"
            "Come back next week!",
            parse_mode=ParseMode.HTML,
        )
        return

    rewards, star = result
    parts = []
    for k, v in rewards.items():
        icon = {"yens": "💴", "gems": "💎",
                "crystals": "🔮", "tickets": "🎫",
                "skill_points": "🌟"}.get(k, "•")
        parts.append(f"{icon} +{v:,} {k}")

    await update.message.reply_text(
        f"📅 <b>Weekly Reward Claimed!</b>\n\n"
        + "\n".join(parts)
        + f"\n\n🐉 Bonus: Dragon Ball {star}★",
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# /rankup — Ascension with +15% permanent stat boost
# =============================================================
@require_not_banned
async def cmd_rankup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    rank = int(p["rank"] or 1)
    max_rank = max(G.RANKS.keys())

    if rank >= max_rank:
        await update.message.reply_text(
            f"👑 <b>You are already at the maximum rank!</b>\n\n"
            f"Rank: {max_rank} ({G.RANKS[max_rank]})\n"
            f"You've achieved godhood!",
            parse_mode=ParseMode.HTML,
        )
        return

    cost = G.RANKUP_CRYSTALS.get(rank)
    if cost is None:
        await update.message.reply_text(
            "❌ Rank system not configured for this rank."
        )
        return

    if p["crystals"] < cost:
        await update.message.reply_text(
            f"🔮 <b>Not enough crystals.</b>\n\n"
            f"Rank {rank} → {rank + 1}\n"
            f"Cost: <b>{cost:,} crystals</b>\n"
            f"You have: {p['crystals']:,} crystals\n\n"
            f"💡 Earn crystals from bosses, daily rewards, "
            f"and /wish.",
            parse_mode=ParseMode.HTML,
        )
        return

    if not db.spend(uid, "crystals", cost):
        await update.message.reply_text("❌ Failed to spend crystals.")
        return

    new_rank = rank + 1
    db.set_field(uid, "rank", new_rank)
    bonus_yens = 250 * rank
    bonus_sp = 30 * rank
    db.give(uid, yens=bonus_yens, skill_points=bonus_sp)

    ach = combat.CombatAchievements(uid)
    ach.check_after_battle(True, 0)  # triggers rank achievement checks

    await update.message.reply_text(
        f"🌟 <b>RANK UP!</b>\n\n"
        f"<b>{G.RANKS[rank]}</b> → <b>{G.RANKS[new_rank]}</b>\n\n"
        f"🎁 +{bonus_yens:,} yens\n"
        f"🌟 +{bonus_sp} SP\n"
        f"⚔️ All stats multiplied by "
        f"+{int(G.RANK_BONUS * 100)}% permanently!\n\n"
        f"<i>Total rank bonus: +{int((new_rank - 1) * G.RANK_BONUS * 100)}%</i>"
        + ach.reward_text(),
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# /travel — 6 planet realms with level gates
# =============================================================
@require_not_banned
async def cmd_travel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    if not context.args:
        current = p["travel"] or "Earth"
        level = db.level_of(p["exp"])
        lines = [
            f"🌍 <b>Travel — 6 Planet Realms</b>\n",
            f"You are on: <b>{escape(current)}</b>\n",
            f"Level: {level}\n",
        ]
        for i, name in enumerate(G.PLANET_ORDER, 1):
            data = G.PLANETS[name]
            locked = level < data["level_min"]
            marker = "📍" if name == current else ("🔒" if locked else "▫️")
            lines.append(
                f"{marker} <b>{i}. {name}</b>\n"
                f"   Lv {data['level_min']}–{data['level_max']} · "
                f"x{data['multiplier']} rewards\n"
                f"   <i>{data['desc']}</i>"
            )
        lines.append(
            "\n💡 <code>/travel &lt;number&gt;</code> to travel"
        )
        await update.message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )
        return

    # Travel to specific planet
    idx_str = context.args[0]
    if not idx_str.isdigit():
        await update.message.reply_text(
            "❌ Usage: <code>/travel &lt;number 1-6&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    idx = int(idx_str)
    if idx < 1 or idx > len(G.PLANET_ORDER):
        await update.message.reply_text(
            f"❌ Planet number must be 1-{len(G.PLANET_ORDER)}."
        )
        return

    name = G.PLANET_ORDER[idx - 1]
    data = G.PLANETS[name]
    level = db.level_of(p["exp"])

    if level < data["level_min"]:
        await update.message.reply_text(
            f"🔒 <b>Level too low for {escape(name)}</b>\n\n"
            f"Required: Lv {data['level_min']}\n"
            f"Your level: {level}\n\n"
            f"💡 Keep exploring {p['travel'] or 'Earth'} "
            f"to level up.",
            parse_mode=ParseMode.HTML,
        )
        return

    db.set_field(uid, "travel", name)
    ach = combat.CombatAchievements(uid)
    ach.check_after_battle(True, 0)

    await update.message.reply_text(
        f"🌍 <b>Traveled to {escape(name)}!</b>\n\n"
        f"Reward multiplier: <b>x{data['multiplier']}</b>\n"
        f"<i>{data['desc']}</i>\n\n"
        f"Use /explore to start fighting here."
        + ach.reward_text(),
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# /fusion — Metamoran fusion
# =============================================================
@require_not_banned
async def cmd_fusion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    if not context.args:
        # Show current fusion materials
        inv = {row["item"]: row["qty"] for row in db.items(uid)}
        mats = []
        for mat in G.FUSION_MATERIALS:
            qty = inv.get(mat, 0)
            if qty > 0:
                mats.append(f"• {mat} ×{qty}")

        mat_text = "\n".join(mats) if mats else "<i>None</i>"

        await update.message.reply_text(
            f"🧬 <b>Metamoran Fusion Chamber</b>\n\n"
            f"Fusion combines two of your warriors into one "
            f"stronger hybrid (inherits highest rarity).\n\n"
            f"<b>Materials:</b>\n{mat_text}\n\n"
            f"<b>Usage:</b>\n"
            f"<code>/fusion &lt;char1&gt; + &lt;char2&gt;</code>\n"
            f"Example: <code>/fusion Goku + Vegeta</code>\n\n"
            f"<b>Rules:</b>\n"
            f"• Both characters must be in your roster\n"
            f"• Cannot fuse same character twice\n"
            f"• Consumes 1 fusion material",
            parse_mode=ParseMode.HTML,
        )
        return

    # Parse args: look for "+" separator OR take first 2 as chars
    raw = " ".join(context.args)
    if " + " in raw:
        parts = raw.split(" + ", 1)
        char1 = parts[0].strip()
        char2 = parts[1].strip()
    elif "+" in raw:
        parts = raw.split("+", 1)
        char1 = parts[0].strip()
        char2 = parts[1].strip()
    else:
        await update.message.reply_text(
            "❌ Format: <code>/fusion &lt;char1&gt; + &lt;char2&gt;</code>\n"
            "Example: <code>/fusion Goku + Vegeta</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    if not char1 or not char2:
        await update.message.reply_text(
            "❌ Both character names required."
        )
        return

    if char1.lower() == char2.lower():
        await update.message.reply_text(
            "❌ Cannot fuse the same character."
        )
        return

    # Verify ownership
    if not db.has_character(uid, char1):
        await update.message.reply_text(
            f"❌ You don't own <b>{escape(char1)}</b>.",
            parse_mode=ParseMode.HTML,
        )
        return
    if not db.has_character(uid, char2):
        await update.message.reply_text(
            f"❌ You don't own <b>{escape(char2)}</b>.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Verify material
    inv = {row["item"]: row["qty"] for row in db.items(uid)}
    material = None
    for mat in G.FUSION_MATERIALS:
        if inv.get(mat, 0) > 0:
            material = mat
            break

    if material is None:
        await update.message.reply_text(
            "🧬 <b>No fusion material!</b>\n\n"
            "Buy Fusion Material with <code>/shop fusion</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Consume material
    db.remove_item(uid, material, 1)

    # Determine result rarity
    r1, r2 = "common", "common"
    for cname, crarity in db.characters(uid):
        if cname == char1:
            r1 = crarity
        if cname == char2:
            r2 = crarity

    higher_rarity = r1 if G.RARITY_ORDER[r1] >= G.RARITY_ORDER[r2] else r2

    # Result name (combined)
    result_name = f"{char1} & {char2}"

    db.add_character(uid, result_name, higher_rarity)
    db.set_field(uid, "fusion_count", int(p["fusion_count"] or 0) + 1)

    ach = combat.CombatAchievements(uid)
    ach.check_after_battle(True, 0)

    rarity_icon = {
        "common": "⚪", "rare": "🔵", "epic": "🟣",
        "legendary": "🟡", "mythical": "🔴", "omni": "👑",
    }.get(higher_rarity, "•")

    chp, catk, cspd, ccrit = _char_stats_by_name(result_name)
    stat_line = ""
    if chp:
        stat_line = (
            f"\n\n📊 Stats: ❤️{chp} ⚔️{catk} "
            f"⚡{cspd} 🎯{ccrit}%"
        )

    await update.message.reply_text(
        f"🧬 <b>Fusion Successful!</b>\n\n"
        f"{escape(char1)} + {escape(char2)}\n"
        f"→ {rarity_icon} <b>{escape(result_name)}</b> "
        f"({higher_rarity.capitalize()})"
        f"{stat_line}\n\n"
        f"<i>Consumed: {material} ×1</i>"
        + ach.reward_text(),
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# /clan — Full 9-subcommand clan system
# =============================================================
@require_not_banned
async def cmd_clan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        await update.message.reply_text("Use /start first.")
        return

    if not context.args:
        await update.message.reply_text(
            f"🏰 <b>Clan Hall</b>\n\n"
            f"<b>Menu:</b>\n"
            f"<code>/clan create &lt;name&gt;</code> — 100 crystals\n"
            f"<code>/clan join &lt;name&gt;</code> — enlist\n"
            f"<code>/clan info</code> — clan dossier\n"
            f"<code>/clan members</code> — roster\n"
            f"<code>/clan manage</code> — officer commands\n"
            f"<code>/clan treasure</code> — vault\n"
            f"<code>/clan raid [boss]</code> — raid boss\n"
            f"<code>/clan announce &lt;text&gt;</code> — bulletin\n"
            f"<code>/clan invite @user</code> — recruit\n"
            f"<code>/clan leave</code> — exit clan\n"
            f"<code>/clan list</code> — top clans\n"
            f"<code>/clan perks</code> — research tree",
            parse_mode=ParseMode.HTML,
        )
        return

    action = context.args[0].lower()
    sub_args = context.args[1:]

    # ----- Create -----
    if action == "create":
        if not sub_args:
            await update.message.reply_text(
                "Usage: <code>/clan create &lt;name&gt;</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        name = " ".join(sub_args)
        try:
            clans.create(uid, name)
            ach = combat.CombatAchievements(uid)
            ach.check_clan(leader=True)
            await update.message.reply_text(
                f"🏰 <b>Clan created: {escape(name)}</b>\n\n"
                f"You are now the leader!\n"
                f"Invite members with <code>/clan invite @user</code>"
                + ach.reward_text(),
                parse_mode=ParseMode.HTML,
            )
        except clans.ClanError as exc:
            await update.message.reply_text(f"❌ {escape(str(exc))}",
                                            parse_mode=ParseMode.HTML)
        return

    # ----- Join -----
    if action == "join":
        if not sub_args:
            await update.message.reply_text(
                "Usage: <code>/clan join &lt;name&gt;</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        name = " ".join(sub_args)
        try:
            clans.join(uid, name)
            await update.message.reply_text(
                f"🏰 <b>Joined {escape(name)}!</b>\n\n"
                f"Use <code>/clan info</code> to see details.",
                parse_mode=ParseMode.HTML,
            )
        except clans.ClanError as exc:
            await update.message.reply_text(f"❌ {escape(str(exc))}",
                                            parse_mode=ParseMode.HTML)
        return

    # ----- List -----
    if action == "list":
        tops = clans.top_clans(10)
        if not tops:
            await update.message.reply_text("No clans exist yet.")
            return
        lines = ["🏆 <b>Top Clans</b>\n"]
        for i, row in enumerate(tops, 1):
            lines.append(f"{i}. <b>{escape(row['name'])}</b> — "
                         f"{row['n']} member{'s' if row['n'] != 1 else ''}")
        await update.message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )
        return

    # All other actions require membership
    m = clans.membership(uid)
    if m is None:
        await update.message.reply_text(
            "❌ You are not in a clan.\n"
            "Use <code>/clan create &lt;name&gt;</code> or "
            "<code>/clan join &lt;name&gt;</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    # ----- Info -----
    if action == "info":
        await update.message.reply_text(
            f"🏰 <b>Clan: {escape(m['name'])}</b>\n\n"
            f"Your role: <b>{m['role'].capitalize()}</b>\n"
            f"Treasury:\n"
            f"  💴 {m['treasure_yens']:,} yens\n"
            f"  💎 {m['treasure_gems']:,} gems\n"
            f"  🔮 {m['treasure_crystals']:,} crystals\n\n"
            f"<b>Announcement:</b>\n"
            f"<i>{escape(m['announcement']) if m['announcement'] else 'No announcement'}</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    # ----- Members -----
    if action == "members":
        rows = clans.members(m["clan_id"])
        lines = [f"🏰 <b>Members of {escape(m['name'])}</b>\n"]
        for r in rows:
            role_icon = {"leader": "👑", "officer": "⚔️",
                         "member": "•"}.get(r["role"], "•")
            exp = r["exp"] or 0
            lines.append(
                f"{role_icon} {escape(r['first_name'] or 'Unknown')} "
                f"({r['role']}) — {exp:,} exp"
            )
        await update.message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )
        return

    # ----- Manage -----
    if action == "manage":
        if m["role"] not in ("leader", "officer"):
            await update.message.reply_text(
                "❌ Only leader/officer can manage clan."
            )
            return
        lines = ["⚔️ <b>Clan Management</b>\n"]
        if m["role"] == "leader":
            lines += [
                "<code>/clan promote @user</code> — member → officer",
                "<code>/clan demote @user</code> — officer → member",
                "<code>/clan transfer @user</code> — give leadership",
                "<code>/clan kick @user</code> — remove member",
                "<code>/clan disband</code> — destroy clan",
            ]
        else:
            lines += [
                "<code>/clan kick @user</code> — remove member",
            ]
        await update.message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )
        return

    # ----- Promote -----
    if action == "promote":
        target_id = resolve_target_id(sub_args, update)
        if target_id is None:
            await update.message.reply_text("❌ Target user not found.")
            return
        try:
            clans.promote(uid, target_id)
            await update.message.reply_text(
                f"✅ Promoted {target_id} to officer."
            )
        except clans.ClanError as exc:
            await update.message.reply_text(f"❌ {escape(str(exc))}",
                                            parse_mode=ParseMode.HTML)
        return

    # ----- Demote -----
    if action == "demote":
        target_id = resolve_target_id(sub_args, update)
        if target_id is None:
            await update.message.reply_text("❌ Target user not found.")
            return
        try:
            clans.demote(uid, target_id)
            await update.message.reply_text(
                f"✅ Demoted {target_id} to member."
            )
        except clans.ClanError as exc:
            await update.message.reply_text(f"❌ {escape(str(exc))}",
                                            parse_mode=ParseMode.HTML)
        return

    # ----- Transfer -----
    if action == "transfer":
        target_id = resolve_target_id(sub_args, update)
        if target_id is None:
            await update.message.reply_text("❌ Target user not found.")
            return
        try:
            clans.transfer(uid, target_id)
            await update.message.reply_text(
                f"✅ Transferred leadership to {target_id}."
            )
        except clans.ClanError as exc:
            await update.message.reply_text(f"❌ {escape(str(exc))}",
                                            parse_mode=ParseMode.HTML)
        return

    # ----- Kick -----
    if action == "kick" or action == "remove":
        target_id = resolve_target_id(sub_args, update)
        if target_id is None:
            await update.message.reply_text("❌ Target user not found.")
            return
        try:
            clans.remove(uid, target_id)
            await update.message.reply_text(
                f"✅ Kicked {target_id} from clan."
            )
        except clans.ClanError as exc:
            await update.message.reply_text(f"❌ {escape(str(exc))}",
                                            parse_mode=ParseMode.HTML)
        return

    # ----- Leave -----
    if action == "leave":
        try:
            result = clans.leave(uid)
            if result == "disbanded":
                await update.message.reply_text(
                    "✅ You left and the clan was disbanded."
                )
            else:
                await update.message.reply_text(
                    "✅ You left the clan."
                )
        except clans.ClanError as exc:
            await update.message.reply_text(f"❌ {escape(str(exc))}",
                                            parse_mode=ParseMode.HTML)
        return

    # ----- Disband -----
    if action == "disband":
        try:
            clans.disband(uid)
            await update.message.reply_text(
                "💥 Clan disbanded."
            )
        except clans.ClanError as exc:
            await update.message.reply_text(f"❌ {escape(str(exc))}",
                                            parse_mode=ParseMode.HTML)
        return

    # ----- Announce -----
    if action == "announce":
        if m["role"] not in ("leader", "officer"):
            await update.message.reply_text(
                "❌ Only leader/officer can announce."
            )
            return
        if not sub_args:
            await update.message.reply_text(
                "Usage: <code>/clan announce &lt;text&gt;</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        text = " ".join(sub_args)
        clans.set_announcement(m["clan_id"], text)
        await update.message.reply_text(
            f"📢 Announcement posted:\n<i>{escape(text[:280])}</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    # ----- Invite -----
    if action == "invite":
        if m["role"] not in ("leader", "officer"):
            await update.message.reply_text(
                "❌ Only leader/officer can invite."
            )
            return
        target_id = resolve_target_id(sub_args, update)
        if target_id is None:
            await update.message.reply_text("❌ Target user not found.")
            return
        try:
            clans.add(uid, target_id)
            await update.message.reply_text(
                f"✅ Invited {target_id} to the clan."
            )
        except clans.ClanError as exc:
            await update.message.reply_text(f"❌ {escape(str(exc))}",
                                            parse_mode=ParseMode.HTML)
        return

    # ----- Treasure (view) -----
    if action == "treasure":
        await update.message.reply_text(
            f"🏛️ <b>Clan Vault</b>\n\n"
            f"💴 Yens: {m['treasure_yens']:,}\n"
            f"💎 Gems: {m['treasure_gems']:,}\n"
            f"🔮 Crystals: {m['treasure_crystals']:,}\n\n"
            f"<b>Deposit</b> (any member):\n"
            f"<code>/clan donate &lt;yens|gems|crystals&gt; &lt;amount&gt;</code>\n\n"
            f"<b>Withdraw</b> (leader only):\n"
            f"<code>/clan withdraw &lt;yens|gems|crystals&gt; &lt;amount&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # ----- Donate -----
    if action == "donate":
        if len(sub_args) < 2:
            await update.message.reply_text(
                "Usage: <code>/clan donate &lt;yens|gems|crystals&gt; &lt;amount&gt;</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        col = resource_name(sub_args[0])
        if col not in ("yens", "gems", "crystals"):
            await update.message.reply_text(
                "❌ Only yens, gems, or crystals can be donated."
            )
            return
        amt = parse_amount(sub_args[1])
        if amt <= 0:
            await update.message.reply_text("❌ Invalid amount.")
            return
        if not db.spend(uid, col, amt):
            await update.message.reply_text(
                f"❌ Not enough {col}."
            )
            return
        clans.add_treasure(m["clan_id"], **{col: amt})
        await update.message.reply_text(
            f"✅ Donated {amt:,} {col} to clan vault."
        )
        return

    # ----- Withdraw -----
    if action == "withdraw":
        if m["role"] != "leader":
            await update.message.reply_text(
                "❌ Only leader can withdraw from vault."
            )
            return
        if len(sub_args) < 2:
            await update.message.reply_text(
                "Usage: <code>/clan withdraw &lt;yens|gems|crystals&gt; &lt;amount&gt;</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        col = resource_name(sub_args[0])
        if col not in ("yens", "gems", "crystals"):
            await update.message.reply_text(
                "❌ Only yens, gems, or crystals can be withdrawn."
            )
            return
        amt = parse_amount(sub_args[1])
        if amt <= 0:
            await update.message.reply_text("❌ Invalid amount.")
            return
        try:
            clans.withdraw_treasure(uid, **{col: amt})
            await update.message.reply_text(
                f"✅ Withdrew {amt:,} {col} from clan vault."
            )
        except clans.ClanError as exc:
            await update.message.reply_text(f"❌ {escape(str(exc))}",
                                            parse_mode=ParseMode.HTML)
        return

    # ----- Perks -----
    if action == "perks":
        perks = clans.get_perks(m["clan_id"])
        lines = [
            f"⚗️ <b>Clan Research Tree</b>\n",
            f"Crystals in vault: {m['treasure_crystals']:,}\n",
        ]
        for code, info in G.CLAN_PERKS.items():
            owned = "✅" if code in perks else "▫️"
            lines.append(
                f"{owned} <b>{info['name']}</b> — {info['cost']} crystals\n"
                f"   <i>{info['desc']}</i>"
            )
        if m["role"] == "leader":
            lines.append(
                "\n💡 <code>/clan research &lt;perk_code&gt;</code>"
            )
        await update.message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )
        return

    # ----- Research -----
    if action == "research":
        if m["role"] != "leader":
            await update.message.reply_text(
                "❌ Only leader can research perks."
            )
            return
        if not sub_args:
            await update.message.reply_text(
                "Usage: <code>/clan research &lt;perk_code&gt;</code>"
            )
            return
        code = sub_args[0].lower()
        try:
            clans.buy_perk(uid, code)
            await update.message.reply_text(
                f"✅ Researched perk: {G.CLAN_PERKS[code]['name']}"
            )
        except (clans.ClanError, KeyError) as exc:
            await update.message.reply_text(f"❌ {escape(str(exc))}",
                                            parse_mode=ParseMode.HTML)
        return

    # ----- Raid -----
    if action == "raid":
        # Start raid if boss name given
        if sub_args:
            boss = " ".join(sub_args)
            if boss not in G.CLAN_RAIDS:
                await update.message.reply_text(
                    "❌ Available raid bosses: "
                    + ", ".join(G.CLAN_RAIDS.keys())
                )
                return
            data = G.CLAN_RAIDS[boss]
            state = clans.clan_raid_state(m["clan_id"])
            if state and state["boss_name"] == boss:
                await update.message.reply_text(
                    f"⚔️ <b>{boss} Raid Already Active</b>\n\n"
                    f"❤️ HP: {state['hp']:,}/{state['max_hp']:,}\n"
                    f"<code>/clan raidhit &lt;damage&gt;</code> to attack.",
                    parse_mode=ParseMode.HTML,
                )
                return
            clans.clan_raid_start(m["clan_id"], boss, data["hp"], data["dmg"])
            await update.message.reply_text(
                f"🔱 <b>Clan Raid Started: {boss}</b>\n\n"
                f"❤️ HP: {data['hp']:,}\n"
                f"⚔️ Boss damage: {data['dmg']}\n\n"
                f"<code>/clan raidhit &lt;damage&gt;</code> to attack.\n"
                f"<i>All members can attack — HP is shared!</i>",
                parse_mode=ParseMode.HTML,
            )
            return

        # Show current raid status
        state = clans.clan_raid_state(m["clan_id"])
        if not state:
            bosses = "\n".join(
                f"• <code>/clan raid {b}</code> — {d['hp']:,} HP"
                for b, d in G.CLAN_RAIDS.items()
            )
            await update.message.reply_text(
                f"🔱 <b>No active clan raid.</b>\n\n"
                f"Available bosses:\n{bosses}",
                parse_mode=ParseMode.HTML,
            )
            return

        pct = int(state["hp"] * 100 / state["max_hp"])
        await update.message.reply_text(
            f"🔱 <b>Clan Raid: {state['boss_name']}</b>\n\n"
            f"❤️ HP: {state['hp']:,}/{state['max_hp']:,} ({pct}%)\n\n"
            f"<code>/clan raidhit &lt;damage&gt;</code> to attack.\n"
            f"<i>No cooldown — attack as much as you want!</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    # ----- Raid Hit -----
    if action == "raidhit":
        state = clans.clan_raid_state(m["clan_id"])
        if not state:
            await update.message.reply_text("❌ No active raid.")
            return
        s = player_stats(uid)
        damage = s["atk"] * 3  # full clan raid hit is 3x normal atk

        result = clans.clan_raid_hit(m["clan_id"], uid, damage)
        if result is None:
            await update.message.reply_text("❌ Raid ended.")
            return

        new_hp, defeated, dmg_by, boss_name = result

        if defeated:
            # Grant rewards from boss config
            info = G.CLAN_RAIDS.get(boss_name, {})
            db.give(uid,
                    yens=info.get("reward_yens", 0),
                    gems=info.get("reward_gems", 0),
                    crystals=info.get("reward_crystals", 0),
                    tickets=info.get("reward_tickets", 0),
                    skill_points=info.get("reward_skill_points", 0))
            clans.add_treasure(m["clan_id"],
                               yens=info.get("reward_yens", 0),
                               gems=info.get("reward_gems", 0),
                               crystals=info.get("reward_crystals", 0))
            await update.message.reply_text(
                f"🏆 <b>CLAN RAID CLEARED!</b>\n\n"
                f"<b>{boss_name}</b> defeated!\n\n"
                f"🎁 Rewards:\n"
                f"💴 +{info.get('reward_yens', 0):,} yens\n"
                f"💎 +{info.get('reward_gems', 0)} gems\n"
                f"🔮 +{info.get('reward_crystals', 0)} crystals\n"
                f"🎫 +{info.get('reward_tickets', 0)} tickets\n"
                f"🌟 +{info.get('reward_skill_points', 0)} SP",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(
                f"⚔️ You hit <b>{boss_name}</b> for <b>{damage:,}</b>!\n\n"
                f"❤️ Boss HP: {new_hp:,}/{state['max_hp']:,}",
                parse_mode=ParseMode.HTML,
            )
        return

    await update.message.reply_text(
        f"❓ Unknown clan command: <b>{escape(action)}</b>\n"
        f"Use <code>/clan</code> to see the menu.",
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# /leaderboard — Top 10 players
# =============================================================
async def cmd_leaderboard(update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
    rows = db.leaderboard(10)
    if not rows:
        await update.message.reply_text("No players yet.")
        return
    lines = ["🏆 <b>Leaderboard — Top 10</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows, 1):
        medal = medals[i - 1] if i <= 3 else f"{i}."
        rank_icon = G.RANKS.get(int(row["rank"] or 1), "?")
        lines.append(
            f"{medal} <b>{escape(row['first_name'] or 'Player')}</b>\n"
            f"   {row['exp']:,} EXP · Rank {row['rank']} ({rank_icon})\n"
            f"   {row['total_wins']} wins"
        )
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML
    )


# =============================================================
# /raid, /raid_start, /raid_attack — Global world raid
# =============================================================
async def cmd_raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    st = db.raid_state()
    if st is None or not st["active"]:
        await update.message.reply_text(
            f"🔱 <b>World Raid</b>\n\n"
            f"<i>No active raid.</i>\n\n"
            f"Admins can start one with <code>/raid_start</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    import json
    dmg_by = json.loads(st["damage_json"] or "{}")
    total_dmg = sum(dmg_by.values())
    pct = int(st["hp"] * 100 / st["max_hp"])

    # Top damage dealers
    top = sorted(dmg_by.items(), key=lambda x: -x[1])[:5]
    top_lines = []
    for i, (uid_str, dmg) in enumerate(top, 1):
        pl = db.player(int(uid_str))
        name = pl["first_name"] if pl else f"User {uid_str}"
        top_lines.append(f"{i}. {escape(name)} — {dmg:,} dmg")

    await update.message.reply_text(
        f"🔱 <b>World Raid: {escape(st['boss_name'] or 'Omega Dragon')}</b>\n\n"
        f"❤️ HP: {st['hp']:,}/{st['max_hp']:,} ({pct}%)\n"
        f"⚔️ Total damage: {total_dmg:,}\n\n"
        f"<b>Top damage:</b>\n" + "\n".join(top_lines) +
        f"\n\n<code>/raid_attack</code> to hit the boss "
        f"(no cooldown!).",
        parse_mode=ParseMode.HTML,
    )


@require_owner
async def cmd_raid_start(update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
    boss_name = G.RAID["name"]
    if context.args:
        boss_name = " ".join(context.args)
    db.raid_start(boss_name=boss_name)
    await update.message.reply_text(
        f"🔱 <b>World Raid Started!</b>\n\n"
        f"Boss: <b>{escape(boss_name)}</b>\n"
        f"❤️ HP: {G.RAID['hp']:,}\n"
        f"⚔️ Drops: x{G.RAID['reward_mult']} rewards\n\n"
        f"All players can attack with <code>/raid_attack</code>.",
        parse_mode=ParseMode.HTML,
    )


@require_not_banned
async def cmd_raid_attack(update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    st = db.raid_state()
    if st is None or not st["active"]:
        await update.message.reply_text(
            "❌ No active world raid. Ask an admin to start one."
        )
        return

    s = player_stats(uid)
    if s["current_hp"] <= 1:
        await update.message.reply_text(
            "⚠️ HP critical! Use /heal Senzu Bean first."
        )
        return

    # Damage dealt per hit (not a full battle, just a strike)
    damage = s["atk"] * 5
    if random.random() < 0.15:
        damage = int(damage * 1.6)  # crit
    result = db.raid_hit(uid, damage)
    if result is None:
        await update.message.reply_text("❌ Raid ended.")
        return

    new_hp, defeated, dmg_by = result

    if defeated:
        # Grant rewards to top damage dealer + bonus to all
        mult = G.RAID["reward_mult"]
        base_yens = 100000 * mult
        db.give(uid, yens=base_yens, gems=500 * mult,
                crystals=50 * mult, tickets=10 * mult,
                skill_points=100 * mult)
        ach = combat.CombatAchievements(uid)
        ach.check_raid_cleared()

        await update.message.reply_text(
            f"🏆 <b>WORLD RAID DEFEATED!</b>\n\n"
            f"You dealt the killing blow!\n\n"
            f"🎁 Rewards:\n"
            f"💴 +{base_yens:,} yens\n"
            f"💎 +{500 * mult:,} gems\n"
            f"🔮 +{50 * mult:,} crystals\n"
            f"🎫 +{10 * mult} tickets\n"
            f"🌟 +{100 * mult} SP"
            + ach.reward_text(),
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"⚔️ You hit for <b>{damage:,}</b>!\n\n"
            f"❤️ Boss HP: {new_hp:,}/{st['max_hp']:,}",
            parse_mode=ParseMode.HTML,
        )


# =============================================================
# ADMIN COMMANDS (owner or admin only)
# =============================================================

@require_admin
async def cmd_admin_give(update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
    """Give resources to any player.
    Usage: /admin_give <target> <resource> <amount>"""
    ensure_player_for_update(update)
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: <code>/admin_give &lt;target&gt; &lt;resource&gt; &lt;amount&gt;</code>\n"
            "Resources: yens, gems, crystals, tickets, skill_points, "
            "keys_elite, keys_boss, exp",
            parse_mode=ParseMode.HTML,
        )
        return
    target_id = resolve_target_id(context.args[:1], update)
    if target_id is None:
        await update.message.reply_text("❌ Target not found.")
        return
    col = resource_name(context.args[1])
    if col is None:
        await update.message.reply_text("❌ Unknown resource.")
        return
    amt = parse_amount(context.args[2])
    if amt <= 0:
        await update.message.reply_text("❌ Invalid amount.")
        return
    db.give(target_id, **{col: amt})
    await update.message.reply_text(
        f"✅ Gave {amt:,} {col} to {target_id}."
    )


@require_admin
async def cmd_admin_set(update: Update,
                         context: ContextTypes.DEFAULT_TYPE):
    """Set a player field to exact value.
    Usage: /admin_set <target> <field> <value>"""
    ensure_player_for_update(update)
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: <code>/admin_set &lt;target&gt; &lt;field&gt; &lt;value&gt;</code>\n"
            "Fields: rank, yens, gems, crystals, tickets, skill_points, "
            "keys_elite, keys_boss, exp, equipped_char, weapon, armor, travel",
            parse_mode=ParseMode.HTML,
        )
        return
    target_id = resolve_target_id(context.args[:1], update)
    if target_id is None:
        await update.message.reply_text("❌ Target not found.")
        return
    field = context.args[1].lower()
    # String fields (equipped_char, weapon, armor, travel)
    if field in ("equipped_char", "weapon", "armor", "travel"):
        value = " ".join(context.args[2:])
    else:
        value = parse_amount_zero_ok(context.args[2])
    ok = db.admin_set_field(target_id, field, value)
    if not ok:
        await update.message.reply_text("❌ Invalid field.")
        return
    await update.message.reply_text(
        f"✅ Set {field} = {value} for {target_id}."
    )


@require_admin
async def cmd_admin_item(update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
    """Give an item to a player.
    Usage: /admin_item <target> <qty> <item name>"""
    ensure_player_for_update(update)
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: <code>/admin_item &lt;target&gt; &lt;qty&gt; &lt;item name&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    target_id = resolve_target_id(context.args[:1], update)
    if target_id is None:
        await update.message.reply_text("❌ Target not found.")
        return
    qty = parse_amount(context.args[1])
    if qty <= 0:
        await update.message.reply_text("❌ Invalid qty.")
        return
    item_name = " ".join(context.args[2:])
    db.add_item(target_id, item_name, qty)
    await update.message.reply_text(
        f"✅ Gave {qty}x {item_name} to {target_id}."
    )


@require_admin
async def cmd_admin_char(update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
    """Give a character to a player.
    Usage: /admin_char <target> <character name> [rarity]"""
    ensure_player_for_update(update)
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: <code>/admin_char &lt;target&gt; &lt;name&gt; [rarity]</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    target_id = resolve_target_id(context.args[:1], update)
    if target_id is None:
        await update.message.reply_text("❌ Target not found.")
        return
    # Last arg might be rarity
    last = context.args[-1].lower()
    if last in G.RARITY_ORDER:
        rarity = last
        name = " ".join(context.args[1:-1])
    else:
        rarity = "legendary"
        name = " ".join(context.args[1:])
    db.add_character(target_id, name, rarity)
    await update.message.reply_text(
        f"✅ Gave {name} ({rarity}) to {target_id}."
    )


@require_admin
async def cmd_admin_skill(update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
    """Give a skill to a player.
    Usage: /admin_skill <target> <skill name>"""
    ensure_player_for_update(update)
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: <code>/admin_skill &lt;target&gt; &lt;skill name&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    target_id = resolve_target_id(context.args[:1], update)
    if target_id is None:
        await update.message.reply_text("❌ Target not found.")
        return
    name = " ".join(context.args[1:])
    db.add_skill(target_id, name)
    await update.message.reply_text(
        f"✅ Gave skill {name} to {target_id}."
    )


@require_admin
async def cmd_admin_dball(update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
    """Give dragon balls.
    Usage: /admin_dball <target> <star 1-7> <qty>"""
    ensure_player_for_update(update)
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: <code>/admin_dball &lt;target&gt; &lt;star 1-7&gt; &lt;qty&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    target_id = resolve_target_id(context.args[:1], update)
    if target_id is None:
        await update.message.reply_text("❌ Target not found.")
        return
    try:
        star = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Star must be 1-7.")
        return
    if star < 1 or star > 7:
        await update.message.reply_text("❌ Star must be 1-7.")
        return
    qty = parse_amount(context.args[2])
    if qty <= 0:
        await update.message.reply_text("❌ Invalid qty.")
        return
    db.add_dragon_ball(target_id, star, qty)
    await update.message.reply_text(
        f"✅ Gave {qty}x {star}★ dragon balls to {target_id}."
    )


@require_admin
async def cmd_admin_promote(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    """Toggle admin flag for a player.
    Usage: /admin_promote <target>"""
    ensure_player_for_update(update)
    target_id = resolve_target_id(context.args, update)
    if target_id is None:
        await update.message.reply_text("❌ Target not found.")
        return
    target = db.player(target_id)
    if target is None:
        await update.message.reply_text("❌ Target not registered.")
        return
    new_val = 0 if target["admin"] else 1
    db.admin_set_field(target_id, "admin", new_val)
    state = "promoted to admin" if new_val else "demoted from admin"
    await update.message.reply_text(
        f"✅ {target_id} {state}."
    )


@require_admin
async def cmd_admin_ban(update: Update,
                         context: ContextTypes.DEFAULT_TYPE):
    """Ban a player.
    Usage: /admin_ban <target>"""
    ensure_player_for_update(update)
    target_id = resolve_target_id(context.args, update)
    if target_id is None:
        await update.message.reply_text("❌ Target not found.")
        return
    if target_id == OWNER_ID:
        await update.message.reply_text("❌ Cannot ban owner.")
        return
    db.admin_ban(target_id, True)
    await update.message.reply_text(f"🚫 Banned {target_id}.")


@require_admin
async def cmd_admin_unban(update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
    """Unban a player.
    Usage: /admin_unban <target>"""
    ensure_player_for_update(update)
    target_id = resolve_target_id(context.args, update)
    if target_id is None:
        await update.message.reply_text("❌ Target not found.")
        return
    db.admin_ban(target_id, False)
    await update.message.reply_text(f"✅ Unbanned {target_id}.")


@require_owner
async def cmd_admin_reset(update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
    """Reset a player's data.
    Usage: /admin_reset <target>"""
    ensure_player_for_update(update)
    target_id = resolve_target_id(context.args, update)
    if target_id is None:
        await update.message.reply_text("❌ Target not found.")
        return
    if target_id == OWNER_ID:
        await update.message.reply_text("❌ Cannot reset owner.")
        return
    db.admin_reset_player(target_id)
    await update.message.reply_text(
        f"🔄 Reset player {target_id}."
    )


@require_owner
async def cmd_admin_broadcast(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    """Broadcast a message to all players.
    Usage: /admin_broadcast <message>"""
    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/admin_broadcast &lt;message&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    msg = " ".join(context.args)
    sent = 0
    failed = 0
    for row in db.all_players():
        try:
            await context.bot.send_message(
                chat_id=row["user_id"],
                text=f"📢 <b>Broadcast:</b>\n\n{escape(msg)}",
                parse_mode=ParseMode.HTML,
            )
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"📢 Broadcast sent to {sent} users ({failed} failed)."
    )


@require_admin
async def cmd_admin_info(update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
    """View detailed info for a player.
    Usage: /admin_info <target>"""
    ensure_player_for_update(update)
    target_id = resolve_target_id(context.args, update)
    if target_id is None:
        await update.message.reply_text("❌ Target not found.")
        return
    p = db.player(target_id)
    if p is None:
        await update.message.reply_text("❌ Not registered.")
        return
    stats = db.combat_stats(target_id)
    await update.message.reply_text(
        f"<b>Player Info: {target_id}</b>\n\n"
        f"Name: {escape(p['first_name'] or '?')}\n"
        f"Rank: {p['rank']}\n"
        f"EXP: {p['exp']:,}\n"
        f"Admin: {'yes' if p['admin'] else 'no'}\n"
        f"Banned: {'yes' if p['banned'] else 'no'}\n"
        f"Yens: {p['yens']:,}\n"
        f"Gems: {p['gems']:,}\n"
        f"Crystals: {p['crystals']:,}\n"
        f"Battles: {stats['battles']}\n"
        f"Wins: {stats['wins']}\n"
        f"Losses: {stats['losses']}\n"
        f"World: {escape(p['travel'] or 'Earth')}",
        parse_mode=ParseMode.HTML,
    )


@require_owner
async def cmd_admin_raidreset(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    """Force reset the world raid to full HP."""
    db.raid_reset()
    await update.message.reply_text("✅ World raid reset to full HP.")


@require_admin
async def cmd_admin_heal(update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
    """Fully heal a player.
    Usage: /admin_heal <target>"""
    ensure_player_for_update(update)
    target_id = resolve_target_id(context.args, update)
    if target_id is None:
        await update.message.reply_text("❌ Target not found.")
        return
    s = player_stats(target_id)
    db.set_current_hp(target_id, s["max_hp"])
    await update.message.reply_text(
        f"✅ Fully healed {target_id} to {s['max_hp']} HP."
    )


@require_admin
async def cmd_admin_bonus(update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
    """Give ALL players a bonus.
    Usage: /admin_bonus <resource> <amount>"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: <code>/admin_bonus &lt;resource&gt; &lt;amount&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    col = resource_name(context.args[0])
    if col is None:
        await update.message.reply_text("❌ Unknown resource.")
        return
    amt = parse_amount(context.args[1])
    if amt <= 0:
        await update.message.reply_text("❌ Invalid amount.")
        return
    players = db.all_players()
    for row in players:
        db.give(row["user_id"], **{col: amt})
    await update.message.reply_text(
        f"✅ Gave {amt:,} {col} to all {len(players)} players."
    )


@require_admin
async def cmd_admin_list(update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
    """List registered players."""
    rows = db.all_players()
    if not rows:
        await update.message.reply_text("No players yet.")
        return
    lines = [f"👥 <b>Players ({len(rows)})</b>\n"]
    for r in rows[:50]:
        lines.append(
            f"• <code>{r['user_id']}</code> "
            f"{escape(r['first_name'] or '?')} — "
            f"Rank {r['rank']} · {r['exp']:,} exp"
        )
    if len(rows) > 50:
        lines.append(f"\n<i>...and {len(rows) - 50} more</i>")
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML
    )


@require_admin
async def cmd_admin_help(update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
    """List all admin commands."""
    await update.message.reply_text(
        "🔐 <b>Admin Commands</b>\n\n"
        "<b>Player Management</b>\n"
        "<code>/admin_give &lt;target&gt; &lt;resource&gt; &lt;amt&gt;</code>\n"
        "<code>/admin_set &lt;target&gt; &lt;field&gt; &lt;value&gt;</code>\n"
        "<code>/admin_heal &lt;target&gt;</code>\n"
        "<code>/admin_info &lt;target&gt;</code>\n"
        "<code>/admin_list</code>\n\n"
        "<b>Item Grants</b>\n"
        "<code>/admin_item &lt;target&gt; &lt;qty&gt; &lt;name&gt;</code>\n"
        "<code>/admin_char &lt;target&gt; &lt;name&gt; [rarity]</code>\n"
        "<code>/admin_skill &lt;target&gt; &lt;name&gt;</code>\n"
        "<code>/admin_dball &lt;target&gt; &lt;star&gt; &lt;qty&gt;</code>\n"
        "<code>/admin_bonus &lt;resource&gt; &lt;amt&gt;</code> (all players)\n\n"
        "<b>Permissions (owner only)</b>\n"
        "<code>/admin_promote &lt;target&gt;</code>\n"
        "<code>/admin_ban &lt;target&gt;</code>\n"
        "<code>/admin_unban &lt;target&gt;</code>\n"
        "<code>/admin_reset &lt;target&gt;</code>\n\n"
        "<b>System (owner only)</b>\n"
        "<code>/admin_broadcast &lt;msg&gt;</code>\n"
        "<code>/admin_raidreset</code>",
        parse_mode=ParseMode.HTML,
    )


# =============================================================
# ERROR HANDLER
# =============================================================
async def error_handler(update: object,
                        context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors but keep the bot running."""
    import traceback
    print("⚠️ Bot exception:", context.error)
    traceback.print_exc(context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Something went wrong. Please try again."
            )
        except Exception:
            pass


# =============================================================
# MAIN — Register all handlers and start bot
# =============================================================
def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is required."
        )

    print("🔧 Initializing database...")
    db.init()
    print("✅ Database ready")

    print("🔧 Building application...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ---- Basic commands ----
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("team", cmd_team))

    # ---- Combat ----
    app.add_handler(CommandHandler("explore", cmd_explore))
    app.add_handler(CommandHandler("heal", cmd_heal))
    app.add_handler(CommandHandler("combathistory", cmd_combathistory))
    app.add_handler(CommandHandler("achievements", cmd_achievements))

    # ---- Quests ----
    app.add_handler(CommandHandler("quests", cmd_quests))
    app.add_handler(CommandHandler("claim_daily", cmd_claim_daily))
    app.add_handler(CommandHandler("claim_weekly", cmd_claim_weekly))
    app.add_handler(CommandHandler("claim_monthly", cmd_claim_monthly))

    # ---- Shop / Economy ----
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CommandHandler("inventory", cmd_inventory))
    app.add_handler(CommandHandler("gacha", cmd_gacha))

    # ---- Character management ----
    app.add_handler(CommandHandler("mycharacters", cmd_mycharacters))
    app.add_handler(CommandHandler("equip", cmd_equip))
    app.add_handler(CommandHandler("skills", cmd_skills))
    app.add_handler(CommandHandler("learn", cmd_learn))
    app.add_handler(CommandHandler("wish", cmd_wish))

    # ---- Summon ----
    app.add_handler(CommandHandler("summon", cmd_summon))

    # ---- Rewards / Progression ----
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CommandHandler("weekly", cmd_weekly))
    app.add_handler(CommandHandler("rankup", cmd_rankup))
    app.add_handler(CommandHandler("travel", cmd_travel))
    app.add_handler(CommandHandler("fusion", cmd_fusion))

    # ---- Clans ----
    app.add_handler(CommandHandler("clan", cmd_clan))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))

    # ---- Raids ----
    app.add_handler(CommandHandler("raid", cmd_raid))
    app.add_handler(CommandHandler("raid_start", cmd_raid_start))
    app.add_handler(CommandHandler("raid_attack", cmd_raid_attack))

    # ---- Admin commands ----
    app.add_handler(CommandHandler("admin_give", cmd_admin_give))
    app.add_handler(CommandHandler("admin_set", cmd_admin_set))
    app.add_handler(CommandHandler("admin_item", cmd_admin_item))
    app.add_handler(CommandHandler("admin_char", cmd_admin_char))
    app.add_handler(CommandHandler("admin_skill", cmd_admin_skill))
    app.add_handler(CommandHandler("admin_dball", cmd_admin_dball))
    app.add_handler(CommandHandler("admin_promote", cmd_admin_promote))
    app.add_handler(CommandHandler("admin_ban", cmd_admin_ban))
    app.add_handler(CommandHandler("admin_unban", cmd_admin_unban))
    app.add_handler(CommandHandler("admin_reset", cmd_admin_reset))
    app.add_handler(CommandHandler("admin_broadcast", cmd_admin_broadcast))
    app.add_handler(CommandHandler("admin_info", cmd_admin_info))
    app.add_handler(CommandHandler("admin_raidreset", cmd_admin_raidreset))
    app.add_handler(CommandHandler("admin_heal", cmd_admin_heal))
    app.add_handler(CommandHandler("admin_bonus", cmd_admin_bonus))
    app.add_handler(CommandHandler("admin_list", cmd_admin_list))
    app.add_handler(CommandHandler("admin_help", cmd_admin_help))

    # ---- Message handler for /explore reply (1/2/3) ----
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_explore_reply,
    ))

    # ---- Error handler ----
    app.add_error_handler(error_handler)

    print("🚀 Bot starting — press Ctrl+C to stop")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
