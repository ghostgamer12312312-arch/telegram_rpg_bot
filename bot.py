from __future__ import annotations

import os
import random
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

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

EXPLORE_STATES: dict[int, dict] = {}


# =============================================================
# Helpers
# =============================================================
def is_owner(uid: int) -> bool:
    return uid == OWNER_ID


def is_admin(uid: int) -> bool:
    p = db.player(uid)
    return bool(p and p["admin"])


def ensure_player_for_update(update: Update):
    uid = update.effective_user.id
    db.ensure_player(uid, update.effective_user.first_name or "Player",
                     update.effective_user.username)
    db.ensure_quests_current(uid)


def resolve_target_id(args: list[str], update: Update):
    if update.message and update.message.reply_to_message:
        u = update.message.reply_to_message.from_user
        if u and not u.is_bot:
            return u.id
    if not args:
        return None
    tok = args[0]
    if tok.startswith("@"):
        row = db.player_by_username(tok[1:])
        return row["user_id"] if row else None
    if tok.isdigit():
        return int(tok)
    return None


def parse_amount(v: str) -> int:
    try:
        return max(1, int(v))
    except (TypeError, ValueError):
        return 0


def resource_name(name: str) -> str | None:
    aliases = {
        "yen": "yens", "yens": "yens", "money": "yens",
        "gem": "gems", "gems": "gems",
        "crystal": "crystals", "crystals": "crystals",
        "ticket": "tickets", "tickets": "tickets",
        "skill_point": "skill_points", "skill_points": "skill_points",
        "sp": "skill_points",
        "elite_key": "keys_elite", "elite_keys": "keys_elite",
        "boss_key": "keys_boss", "boss_keys": "keys_boss",
        "exp": "exp",
    }
    return aliases.get((name or "").strip().lower())


def get_world_multiplier(uid: int) -> float:
    p = db.player(uid)
    if not p:
        return 1.0
    return G.PLANETS.get(p["travel"] or "Earth",
                         G.PLANETS["Earth"])["multiplier"]


def _char_stats_by_name(name: str) -> tuple[int, int, int, int]:
    """Return (hp, atk, spd, crit) for a character name (fallback to rarity)."""
    for row in G.CHARACTERS:
        if row[0] == name:
            return (row[2], row[3], row[4], row[5])
    return (0, 0, 0, 0)


def player_stats(uid: int) -> dict:
    p = db.player(uid)
    if not p:
        return {"atk": 0, "hp": 0, "spd": 0, "crit": 0,
                "level": 1, "rank": 1, "char_rarity": None,
                "current_hp": 0, "max_hp": 0}
    lvl = db.level_of(p["exp"])
    atk = 10 + lvl * 3
    hp = 100 + lvl * 12
    spd = 10 + lvl // 3
    crit = 5

    if p["weapon"] in G.EQUIPMENT:
        atk += G.EQUIPMENT[p["weapon"]][1]
    if p["armor"] in G.EQUIPMENT:
        hp += G.EQUIPMENT[p["armor"]][1] * 2

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

    atk += sum(G.SKILL_ATK.get(s, 0) for s in db.skills(uid))
    rank = int(p["rank"] or 1)
    rank_mult = 1 + (rank - 1) * G.RANK_BONUS
    atk = int(atk * rank_mult)
    hp = int(hp * rank_mult)

    current_hp = db.get_current_hp(uid, hp)
    return {"atk": atk, "hp": hp, "spd": spd, "crit": crit,
            "level": lvl, "rank": rank, "char_rarity": char_rarity,
            "current_hp": current_hp, "max_hp": hp}


def run_battle(uid: int, enemy_name: str, enemy_hp: int, enemy_dmg: int,
               enrage: bool = False, is_boss: bool = False,
               is_summon: bool = False, skip_hp: bool = False) -> dict:
    """Run battle using current HP, log to CombatHistory."""
    s = player_stats(uid)
    start_hp = s["max_hp"] if skip_hp else s["current_hp"]
    if start_hp <= 0:
        start_hp = s["max_hp"]
    eng = combat.CombatEngine(s["atk"], start_hp, crit=s["crit"], speed=s["spd"])
    won, left, log = eng.fight(enemy_name, enemy_hp, enemy_dmg, enrage)
    outcome = "victory" if won else "defeat"
    hist = combat.CombatHistory(uid)
    hist.log(enemy_name, enemy_hp, eng.damage_dealt, eng.damage_taken,
             outcome, eng.rounds)
    # Persist HP: on defeat, leave at 1 HP
    if skip_hp:
        db.set_current_hp(uid, s["max_hp"])
    else:
        new_hp = 1 if (not won and left <= 0) else left
        db.set_current_hp(uid, max(1, new_hp))
    return {
        "won": won, "left_hp": left, "log": log,
        "dealt": eng.damage_dealt, "taken": eng.damage_taken,
        "rounds": eng.rounds,
    }


def apply_drops(uid: int, is_boss: bool, is_summon: bool = False) -> list[str]:
    drops = []
    drop_chance = 0.35 if (is_boss or is_summon) else 0.15
    if random.random() < drop_chance:
        item = random.choice(list(G.EQUIPMENT))
        db.add_item(uid, item)
        drops.append(f"📦 {item}")
    if random.random() < (0.45 if (is_boss or is_summon) else 0.10):
        star = random.choice(G.DRAGON_BALL_STARS)
        db.add_dragon_ball(uid, star)
        drops.append(f"🐉 Dragon Ball {star}★")
    if random.random() < (0.30 if (is_boss or is_summon) else 0.05):
        db.give(uid, tickets=1)
        drops.append("🎫 Ticket")
    if random.random() < (0.20 if is_boss else 0.02):
        skill = random.choice(list(G.SKILLS))
        if db.add_skill(uid, skill):
            drops.append(f"🌟 Skill: {skill}")
    return drops


def _hp_bar(cur: int, mx: int) -> str:
    if mx <= 0:
        return "▯▯▯▯▯▯▯▯▯▯ 0%"
    pct = max(0, min(100, int(cur * 100 / mx)))
    filled = pct // 10
    return "█" * filled + "▯" * (10 - filled) + f" {pct}%"


# =============================================================
# START / HELP
# =============================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    # Starter pack for new players
    if p and int(p["exp"] or 0) == 0 and int(p["total_battles"] or 0) == 0:
        rarity = random.choice(G.STARTER_PACK["pool"])
        pool = [n for n, r, *_ in G.CHARACTERS if r == rarity]
        if pool:
            name = random.choice(pool)
            db.add_character(uid, name, rarity)
            db.set_field(uid, "equipped_char", name)
        db.give(uid, yens=G.STARTER_PACK["bonus_yens"],
                gems=G.STARTER_PACK["bonus_gems"],
                tickets=G.STARTER_PACK["bonus_tickets"])
        await update.message.reply_text(
            f"🎁 **Starter Pack** — you got {name} ({rarity})!\n"
            f"Equipped automatically. +1000 yens, +50 gems, +3 tickets.\n",
            parse_mode=ParseMode.MARKDOWN,
        )

    await update.message.reply_text(
        "🐉 **Dragon Battle RPG**\n\n"
        "⚔️ Combat:\n"
        "/explore — 3-option patrol (Battle / Run / Info)\n"
        "/combathistory — last 10 battles\n"
        "/achievements — milestone tracker\n"
        "/quests — daily / weekly / monthly\n"
        "/heal — use senzu beans & potions\n\n"
        "👤 Player:\n"
        "/profile — full profile + HP bar\n"
        "/team — equipped setup\n"
        "/inventory — bag\n"
        "/mycharacters — warriors grouped by rank\n"
        "/equip <name> — equip weapon/armor/char\n\n"
        "🛒 Economy:\n"
        "/shop — 6-category market\n"
        "/shop <category> — view items\n"
        "/buy <id> [qty] — bulk buy\n"
        "/gacha [qty] [banner] — roll warriors\n"
        "/skills, /learn <skill>\n"
        "/wish — Shenron\n"
        "/fusion <char1> + <char2>\n\n"
        "🏰 Clans:\n"
        "/clan — full clan menu\n"
        "/leaderboard\n\n"
        "🌍 Travel:\n"
        "/travel — 6 planet realms\n"
        "/travel <n> — travel\n"
        "/rankup — ascension\n"
        "/daily, /weekly\n\n"
        "🔱 Bosses:\n"
        "/summon <elite|mythical|legendary>\n"
        "/raid — world raid status\n"
        "/raid_attack — hit raid boss\n"
        "/raid_start — (owner only) start\n",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **How to Play**\n\n"
        "1. /explore → 1 (Battle). Every 15 NPC wins = world boss.\n"
        "2. Losing sets HP to 1. Use /heal → Senzu Bean to restore.\n"
        "3. /rankup multiplies all stats +15% per rank.\n"
        "4. /summon bosses grant 5x rewards, drop dragon balls.\n"
        "5. /raid is a 120k HP world boss, 0 cooldown, 10x rewards.\n"
        "6. /clan raid bosses persist HP across members.\n"
        "7. /wish → Shenron needs all 7 dragon balls.\n"
        "8. /quests auto-track daily/weekly/monthly progress.",
        parse_mode=ParseMode.MARKDOWN,
    )


# =============================================================
# PROFILE / TEAM
# =============================================================
async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    p = db.player(uid)
    if not p:
        return
    s = player_stats(uid)
    stats = db.combat_stats(uid)
    clan = clans.membership(uid)
    bar = _hp_bar(s["current_hp"], s["max_hp"])
    text = (
        f"👤 <b>{escape(p['first_name'])}</b>\n"
        f"🆔 <code>{uid}</code>\n"
        f"Level: <b>{s['level']}</b>  Rank: <b>{s['rank']}</b> "
        f"({G.RANKS.get(s['rank'], '?')})\n"
        f"World: {p['travel'] or 'Earth'} "
        f"(x{get_world_multiplier(uid)})\n"
        f"\n❤️ HP: {s['current_hp']}/{s['max_hp']} {bar}\n"
        f"💪 ATK: <b>{s['atk']}</b>  ⚡ SPD: {s['spd']}  "
        f"🎯 CRIT: {s['crit']}%\n"
        f"\n💴 {p['yens']:,} yens · 💎 {p['gems']:,} gems · "
        f"🔮 {p['crystals']:,} crystals\n"
        f"🎫 {p['tickets']} tickets · 🌟 {p['skill_points']} SP · "
        f"🔑 {p['keys_elite']} elite · 🗝️ {p['keys_boss']} boss\n"
        f"\n⚔️ Weapon: {escape(p['weapon'] or 'none')}\n"
        f"🛡️ Armor: {escape(p['armor'] or 'none')}\n"
        f"🧙 Character: {escape(p['equipped_char'] or 'none')}\n"
        f"\n📊 {stats['battles']} battles · {stats['wins']}W / "
        f"{stats['losses']}L\n"
        f"🩸 {stats['dealt']:,} dealt · 🩹 {stats['taken']:,} taken\n"
        f"🏰 Clan: {escape(clan['name']) if clan else 'none'}\n"
        f"EXP: {p['exp']}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    s = player_stats(uid)
    p = db.player(uid)
    if not p:
        return
    await update.message.reply_text(
        f"🛡️ **Team Setup**\n"
        f"Character: {p['equipped_char'] or 'none'}\n"
        f"Weapon: {p['weapon'] or 'none'}\n"
        f"Armor: {p['armor'] or 'none'}\n"
        f"\nATK: {s['atk']} · HP: {s['max_hp']}\n"
        f"SPD: {s['spd']} · CRIT: {s['crit']}%\n"
        f"Rank: {s['rank']}\n",
        parse_mode=ParseMode.MARKDOWN,
    )


# =============================================================
# EXPLORE — 3-option patrol
# =============================================================
async def cmd_explore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    EXPLORE_STATES[uid] = {"mode": "explore"}
    p = db.player(uid)
    if not p:
        return
    world = p["travel"] or "Earth"
    mult = get_world_multiplier(uid)
    streak = int(p["npc_streak"] or 0)
    s = player_stats(uid)
    bar = _hp_bar(s["current_hp"], s["max_hp"])
    await update.message.reply_text(
        f"🧭 **Explore — {world}** (x{mult} rewards)\n"
        f"❤️ HP: {s['current_hp']}/{s['max_hp']} {bar}\n"
        f"Boss in {G.NPC_STREAK_FOR_BOSS - streak} more NPC wins\n\n"
        "1. ⚔️ Battle\n"
        "2. 🏃 Run away\n"
        "3. ℹ️ Info",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_explore_reply(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
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

    if choice == "3":
        world = p["travel"] or "Earth"
        data = G.PLANETS[world]
        streak = int(p["npc_streak"] or 0)
        await update.message.reply_text(
            f"ℹ️ **Info: {world}**\n"
            f"Level gate: {data['level_min']} – {data['level_max']}\n"
            f"Multiplier: x{data['multiplier']}\n"
            f"Lore: {data['desc']}\n"
            f"Boss in {G.NPC_STREAK_FOR_BOSS - streak} NPC wins.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if choice == "2":
        await update.message.reply_text("You used Instant Transmission — no damage taken.")
        return

    # --- Battle ---
    s = player_stats(uid)
    if s["current_hp"] <= 1:
        await update.message.reply_text(
            "⚠️ HP is critically low! Use /heal → Senzu Bean to restore "
            "before battling again."
        )
        return

    streak = int(p["npc_streak"] or 0) + 1
    is_boss = streak >= G.NPC_STREAK_FOR_BOSS
    world_mult = get_world_multiplier(uid)
    rank_mult = 1 + int(p["rank"] or 1) * 0.2

    if is_boss:
        boss = random.choice(G.BOSSES)
        result = run_battle(uid, boss["name"], boss["hp"], boss["dmg"],
                            enrage=True, is_boss=True)
        if result["won"]:
            yens = int(boss["yens"] * world_mult * rank_mult * 5)  # boss 5x
            db.give(uid, yens=yens, gems=boss["gems"], crystals=boss["crystals"],
                    tickets=boss["tickets"], skill_points=boss["skill_points"],
                    exp=200)
            drops = apply_drops(uid, is_boss=True)
            db.set_field(uid, "npc_streak", 0)
            ach = combat.CombatAchievements(uid)
            ach.check_after_battle(True, result["taken"], is_boss=True)
            quest = combat.QuestTracker(uid)
            quest.on_boss_kill()
            quest.on_yens_earned(yens)
            quest.on_battle_win()
            text = (
                f"🏆 **BOSS VICTORY: {boss['name']}**\n"
                f"Reward: {yens:,} yens + {boss['gems']} gems + "
                f"{boss['crystals']} crystals + {boss['tickets']} tickets + "
                f"{boss['skill_points']} SP\n"
                f"{' · '.join(drops) if drops else ''}\n"
                f"Damage: {result['dealt']:,} dealt / {result['taken']:,} taken\n"
                f"\n{chr(10).join(result['log'][-4:])}"
                + ach.reward_text()
            )
        else:
            text = (
                f"❌ Boss {boss['name']} defeated you!\n"
                f"HP restored to 1. Use /heal → Senzu Bean.\n"
                f"Damage: {result['dealt']:,} dealt / {result['taken']:,} taken"
            )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return

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
        text = (
            f"✅ Victory vs {npc['name']}!\n"
            f"+{yens:,} yens + 60 exp + 5 SP\n"
            f"{' · '.join(drops) if drops else ''}\n"
            f"Damage: {result['dealt']:,} dealt / {result['taken']:,} taken\n"
            f"Boss in {G.NPC_STREAK_FOR_BOSS - streak} more wins"
            + ach.reward_text()
        )
    else:
        text = (
            f"❌ Defeat by {npc['name']}!\n"
            f"HP restored to 1. Use /heal → Senzu Bean.\n"
            f"Damage: {result['dealt']:,} dealt / {result['taken']:,} taken"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# =============================================================
# HEAL
# =============================================================
async def cmd_heal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    s = player_stats(uid)
    inv = {row["item"]: row["qty"] for row in db.items(uid)}
    healing = [(name, inv.get(name, 0)) for name in G.HEALING]
    lines = [f"❤️ HP: {s['current_hp']}/{s['max_hp']} "
             f"{_hp_bar(s['current_hp'], s['max_hp'])}\n",
             "🧪 **Healing Items** (use /heal <item>):"]
    for name, qty in healing:
        frac = int(G.HEALING[name] * 100)
        lines.append(f"• {name} ×{qty} — restores {frac}% HP")
    lines.append("\nExample: /heal Senzu Bean")
    await update.message.reply_text("\n".join(lines),
                                     parse_mode=ParseMode.MARKDOWN)

    if context.args:
        item_name = " ".join(context.args)
        for name in G.HEALING:
            if name.lower() == item_name.lower():
                ok, new_hp = db.apply_heal(uid, s["max_hp"], name)
                if not ok:
                    await update.message.reply_text(
                        f"You don't have {name}."
                    )
                else:
                    await update.message.reply_text(
                        f"❤️ Used {name}. HP: {new_hp}/{s['max_hp']} "
                        f"{_hp_bar(new_hp, s['max_hp'])}",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                return
        await update.message.reply_text("Unknown healing item.")


# =============================================================
# COMBAT HISTORY
# =============================================================
async def cmd_combathistory(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    hist = combat.CombatHistory(uid)
    await update.message.reply_text(hist.render(),
                                     parse_mode=ParseMode.MARKDOWN)


# =============================================================
# ACHIEVEMENTS
# =============================================================
async def cmd_achievements(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    ensure_player_for_update(update)
    uid = update.effective_user.id
    unlocked = db.player_achievements(uid)
    have = {row["code"] for row in unlocked}
    lines = ["🏆 **Achievements**\n"]
    for code, info in G.ACHIEVEMENTS.items():
        icon = "✅" if code in have else "▫️"
        lines.append(f"{icon} {info['name']} — {info['desc']}")
    await update.message.reply_text("\n".join(lines),
                                     parse_mode=ParseMode.MARKDOWN)


# =============================================================
# QUESTS
# =============================================================
async def cmd_quests(update: Update, context: ContextTypes
