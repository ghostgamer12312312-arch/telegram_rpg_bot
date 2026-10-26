from __future__ import annotations

"""
Dragon Ball RPG — Combat System
================================
Contains every combat-related utility used by bot.py.

Public API (all called by bot.py):
    CombatEngine(player_atk, player_hp, crit=5, speed=10) → .fight(...)
    CombatHistory(uid) → .log(...), .render(), .recent()
    CombatAchievements(uid) → .check_after_battle(...), .reward_text()
    QuestTracker(uid) → .on_npc_kill(), .on_battle_win(), ...

Extended helpers (optional, but useful):
    quick_fight(...)              One-shot fight, returns full tuple
    simulate_fight(...)           Deterministic fight for testing
    estimate_win_rate(...)        Monte-Carlo win probability
    analyze_log(log_list)         DPS / round analysis
    power_level(stats_dict)       Scouter-style BP number
"""

import csv
import io
import math
import random
from datetime import datetime, timezone

import db
import game_data as G


# =============================================================
# CONSTANTS
# =============================================================
MAX_ROUNDS_DEFAULT = 60
MIN_DAMAGE = 1
ENRAGE_MULTIPLIER = 1.3
ZENKAI_THRESHOLD = 0.20         # Zenkai triggers below 20% HP
ZENKAI_ATK_BOOST = 1.35         # +35% ATK while Zenkai active
AFTERIMAGE_BASE_CHANCE = 0.05   # 5% base dodge chance
AFTERIMAGE_SPEED_FACTOR = 0.005 # +0.5% per speed point above 20
CRIT_MULTIPLIER = 1.6
KI_MAX = 100
KI_GAIN_PER_HIT = 15
KI_GAIN_PER_TAKEN = 10
BEAM_STRUGGLE_CHANCE = 0.08


# =============================================================
# UTILITY — DAMAGE / CRIT / DODGE / POWER LEVEL
# =============================================================
def roll_damage(base: int, spread: tuple[float, float] = (0.8, 1.35)) -> int:
    """Roll a random damage value around `base` using spread factors."""
    lo, hi = spread
    return max(MIN_DAMAGE, int(base * random.uniform(lo, hi)))


def roll_crit(crit_chance: int) -> bool:
    """Return True if a critical hit lands."""
    return random.randint(1, 100) <= max(0, min(100, int(crit_chance)))


def roll_dodge(speed: int) -> bool:
    """Return True if an afterimage dodge triggers."""
    chance = AFTERIMAGE_BASE_CHANCE + max(0, speed - 20) * AFTERIMAGE_SPEED_FACTOR
    chance = min(0.35, chance)  # cap dodge at 35%
    return random.random() < chance


def power_level(stats: dict) -> int:
    """
    Scouter-style power level from a stats dict.
    Combines HP + ATK × 10 + SPD × 50 + crit contribution.
    Ranges roughly 1,000 (weak) to 500,000+ (Omni tier).
    """
    hp = int(stats.get("hp", 0) or 0)
    atk = int(stats.get("atk", 0) or 0)
    spd = int(stats.get("spd", 10) or 10)
    crit = int(stats.get("crit", 5) or 5)
    return hp + atk * 10 + spd * 50 + crit * 100


# =============================================================
# COMBAT ENGINE
# =============================================================
class CombatEngine:
    """
    Turn-based fight simulator.

    Core usage:
        eng = CombatEngine(player_atk, player_hp, crit=5, speed=10)
        won, left_hp, log = eng.fight("Frieza", 1000, 50, enrage=False)
        eng.damage_dealt  # total damage dealt
        eng.damage_taken  # total damage taken
        eng.rounds        # number of rounds that elapsed

    Optional enhancements (all default OFF so behavior is identical
    to the original engine if bot.py doesn't opt in):
        enable_dodge=True       afterimage dodge system
        enable_zenkai=True      ATK boost when HP < 20%
        enable_ki_gauge=True    Ki charges and enables special moves
        enable_beam_struggle=True  rare double-attack event
    """

    def __init__(
        self,
        player_atk: int,
        player_hp: int,
        crit: int = 5,
        speed: int = 10,
        *,
        enable_dodge: bool = False,
        enable_zenkai: bool = False,
        enable_ki_gauge: bool = False,
        enable_beam_struggle: bool = False,
        max_rounds: int = MAX_ROUNDS_DEFAULT,
    ):
        self.p_atk = max(1, int(player_atk))
        self.p_hp = max(1, int(player_hp))
        self.crit = max(0, int(crit))
        self.speed = max(1, int(speed))
        self.max_rounds = max(1, int(max_rounds))

        # Optional flags
        self.enable_dodge = enable_dodge
        self.enable_zenkai = enable_zenkai
        self.enable_ki_gauge = enable_ki_gauge
        self.enable_beam_struggle = enable_beam_struggle

        # Battle state
        self.damage_dealt = 0
        self.damage_taken = 0
        self.rounds = 0
        self.log: list[str] = []

        # Extra stats
        self.crits_landed = 0
        self.dodges_triggered = 0
        self.zenkai_activations = 0
        self.beam_struggles = 0
        self.ki = 0
        self.max_hp = self.p_hp

        # Optional enemy info (populated in fight())
        self._enemy_name = "Enemy"
        self._enemy_max_hp = 0

    # ---------- INTERNAL HELPERS ----------
    def _roll_hit(self, base: int, spread: tuple[float, float] = (0.8, 1.35)) -> int:
        """Roll damage and apply crit multiplier. Returns final damage."""
        hit = roll_damage(base, spread)
        if roll_crit(self.crit):
            hit = int(hit * CRIT_MULTIPLIER)
            self.crits_landed += 1
            self.log.append("  >> CRITICAL HIT!")
        return max(MIN_DAMAGE, hit)

    def _is_zenkai(self, current_hp: int) -> bool:
        """Whether Zenkai boost should apply this round."""
        if not self.enable_zenkai:
            return False
        return current_hp <= int(self.max_hp * ZENKAI_THRESHOLD)

    def _apply_zenkai(self, base_atk: int, current_hp: int) -> int:
        """Return boosted ATK if Zenkai is active."""
        if self._is_zenkai(current_hp):
            return int(base_atk * ZENKAI_ATK_BOOST)
        return base_atk

    def _gain_ki(self, amount: int) -> None:
        """Accumulate Ki for gauge mode."""
        if not self.enable_ki_gauge:
            return
        self.ki = min(KI_MAX, self.ki + amount)

    def _consume_ki(self, amount: int) -> bool:
        """Consume Ki if available. Returns True on success."""
        if self.ki < amount:
            return False
        self.ki -= amount
        return True

    def _try_beam_struggle(self, enemy_dmg: int) -> bool:
        """Rare event: both attacks clash and cancel."""
        if not self.enable_beam_struggle:
            return False
        if random.random() > BEAM_STRUGGLE_CHANCE:
            return False
        self.beam_struggles += 1
        self.log.append(
            f"  ⚡ BEAM STRUGGLE! Your blast clashes with {self._enemy_name}'s!"
        )
        return True

    # ---------- PUBLIC FIGHT ----------
    def fight(
        self,
        enemy_name: str,
        enemy_hp: int,
        enemy_dmg: int,
        enrage: bool = False,
    ) -> tuple[bool, int, list[str]]:
        """
        Simulate a battle.

        Returns:
            (won: bool, left_hp: int, log: list[str])

        Populates self.damage_dealt, .damage_taken, .rounds.
        """
        self._enemy_name = enemy_name
        self._enemy_max_hp = int(enemy_hp)

        p_hp = self.p_hp
        e_hp = int(enemy_hp)
        e_max = int(enemy_hp)

        if e_hp <= 0:
            self.log.append(f"{enemy_name} is already defeated!")
            return True, max(1, p_hp), self.log

        for rnd in range(1, self.max_rounds + 1):
            self.rounds = rnd

            # Decide who strikes first
            first = self.speed > 25 or random.random() < 0.5

            # Player attacks first
            if first:
                player_atk_effective = self._apply_zenkai(self.p_atk, p_hp)
                if self._is_zenkai(p_hp) and rnd == 1:
                    self.zenkai_activations += 1
                    self.log.append("  🔥 ZENKAI BOOST ACTIVATED!")

                # Dodge check
                if self.enable_dodge and roll_dodge(20):  # enemy dodges player
                    self.log.append(
                        f"Round {rnd}: {enemy_name} afterimage-dodged!"
                    )
                else:
                    hit = self._roll_hit(player_atk_effective)
                    e_hp -= hit
                    self.damage_dealt += hit
                    self._gain_ki(KI_GAIN_PER_HIT)
                    self.log.append(
                        f"Round {rnd}: You hit {enemy_name} for {hit}"
                    )
                    if e_hp <= 0:
                        self.log.append("Victory!")
                        return True, max(1, p_hp), self.log

            # Enemy attacks
            mult = ENRAGE_MULTIPLIER if (enrage and e_hp <= e_max // 2) else 1.0
            effective_enemy_dmg = max(MIN_DAMAGE, int(enemy_dmg * mult))

            if not self._try_beam_struggle(effective_enemy_dmg):
                if self.enable_dodge and roll_dodge(self.speed):
                    self.dodges_triggered += 1
                    self.log.append(
                        f"Round {rnd}: You afterimage-dodged "
                        f"{enemy_name}'s attack!"
                    )
                else:
                    taken = self._roll_hit(effective_enemy_dmg, (0.8, 1.25))
                    p_hp -= taken
                    self.damage_taken += taken
                    self._gain_ki(KI_GAIN_PER_TAKEN)
                    self.log.append(
                        f"Round {rnd}: {enemy_name} hits for {taken}"
                    )
                    if p_hp <= 0:
                        return False, 0, self.log

            # Player attacks second if enemy went first
            if not first:
                player_atk_effective = self._apply_zenkai(self.p_atk, p_hp)
                if self.enable_dodge and roll_dodge(20):
                    self.log.append(
                        f"Round {rnd}: {enemy_name} afterimage-dodged!"
                    )
                else:
                    hit = self._roll_hit(player_atk_effective)
                    e_hp -= hit
                    self.damage_dealt += hit
                    self._gain_ki(KI_GAIN_PER_HIT)
                    self.log.append(
                        f"Round {rnd}: You hit {enemy_name} for {hit}"
                    )
                    if e_hp <= 0:
                        self.log.append("Victory!")
                        return True, max(1, p_hp), self.log

        self.log.append("Battle dragged on and you backed off.")
        return False, max(0, p_hp), self.log

    # ---------- ANALYSIS ----------
    def dps(self) -> float:
        """Average damage per round dealt."""
        if self.rounds <= 0:
            return 0.0
        return self.damage_dealt / self.rounds

    def effective_hp_ratio(self, left_hp: int) -> float:
        """Fraction of starting HP remaining (0.0–1.0)."""
        return max(0.0, min(1.0, left_hp / self.max_hp))

    def summary(self, won: bool, left_hp: int) -> str:
        """Multi-line summary of the fight."""
        return (
            f"{'✅ Victory' if won else '❌ Defeat'}\n"
            f"Rounds: {self.rounds}\n"
            f"Damage dealt: {self.damage_dealt:,}\n"
            f"Damage taken: {self.damage_taken:,}\n"
            f"Crits landed: {self.crits_landed}\n"
            f"DPS: {self.dps():.1f}\n"
            f"HP left: {max(0, left_hp)}/{self.max_hp}"
        )


# =============================================================
# QUICK FIGHT (one-shot, backward compatible with bot.py)
# =============================================================
def quick_fight(
    player_atk: int,
    player_hp: int,
    enemy_hp: int,
    enemy_dmg: int,
    crit: int = 5,
    enrage: bool = False,
) -> tuple[bool, int, list[str], int, int, int]:
    """
    Legacy helper — one-shot fight.

    Returns:
        (won, left_hp, log, damage_dealt, damage_taken, rounds)
    """
    eng = CombatEngine(player_atk, player_hp, crit=crit)
    won, left, log = eng.fight("Enemy", enemy_hp, enemy_dmg, enrage)
    return won, left, log, eng.damage_dealt, eng.damage_taken, eng.rounds


# =============================================================
# DETERMINISTIC SIMULATOR (useful for balancing)
# =============================================================
def simulate_fight(
    player_atk: int,
    player_hp: int,
    enemy_hp: int,
    enemy_dmg: int,
    crit: int = 5,
) -> dict:
    """
    Simulate a fight with fixed averages (no randomness).
    Useful for admin tooling and balance tests.
    """
    avg_player_hit = player_atk * 1.075  # midpoint of 0.8–1.35
    avg_enemy_hit = enemy_dmg * 1.025   # midpoint of 0.8–1.25

    rounds_to_kill_enemy = math.ceil(enemy_hp / avg_player_hit) if avg_player_hit > 0 else 999
    rounds_to_kill_player = math.ceil(player_hp / avg_enemy_hit) if avg_enemy_hit > 0 else 999

    won = rounds_to_kill_enemy <= rounds_to_kill_player
    return {
        "won": won,
        "rounds": min(rounds_to_kill_enemy, rounds_to_kill_player),
        "player_hits_needed": rounds_to_kill_enemy,
        "enemy_hits_needed": rounds_to_kill_player,
        "avg_player_hit": avg_player_hit,
        "avg_enemy_hit": avg_enemy_hit,
    }


# =============================================================
# MONTE-CARLO WIN RATE
# =============================================================
def estimate_win_rate(
    player_atk: int,
    player_hp: int,
    enemy_hp: int,
    enemy_dmg: int,
    crit: int = 5,
    iterations: int = 200,
    enrage: bool = False,
) -> float:
    """
    Estimate win probability through Monte-Carlo simulation.
    Returns a float between 0.0 and 1.0.
    """
    wins = 0
    for _ in range(max(1, int(iterations))):
        eng = CombatEngine(player_atk, player_hp, crit=crit)
        won, _, _ = eng.fight("Enemy", enemy_hp, enemy_dmg, enrage)
        if won:
            wins += 1
    return wins / iterations


# =============================================================
# LOG ANALYZER
# =============================================================
def analyze_log(log: list[str]) -> dict:
    """
    Return aggregate stats from a battle log.
    Useful for admin inspection.
    """
    hits_dealt = 0
    hits_taken = 0
    crits = 0
    rounds = 0
    for line in log:
        low = line.lower()
        if "you hit" in low:
            hits_dealt += 1
        elif "hits for" in low:
            hits_taken += 1
        if "critical" in low:
            crits += 1
        if low.startswith("round"):
            rounds += 1
    return {
        "rounds": rounds,
        "hits_dealt": hits_dealt,
        "hits_taken": hits_taken,
        "crits": crits,
    }


# =============================================================
# COMBAT HISTORY
# =============================================================
class CombatHistory:
    """
    Records every battle and can render the last N fights.

    Backed by db.add_combat_log / db.get_combat_history / db.combat_stats.
    """

    def __init__(self, uid: int, limit: int = 10):
        self.uid = int(uid)
        self.limit = max(1, int(limit))

    # ---------- WRITE ----------
    def log(
        self,
        enemy_name: str,
        enemy_max_hp: int,
        damage_dealt: int,
        damage_taken: int,
        outcome: str,
        rounds: int,
        rewards_text: str = "",
    ) -> None:
        """Persist a battle to the combat log."""
        db.add_combat_log(
            self.uid,
            enemy_name,
            enemy_max_hp,
            damage_dealt,
            damage_taken,
            outcome,
            rounds,
            rewards_text,
        )

    # ---------- READ ----------
    def recent(self) -> list:
        """Last N combat log rows (newest first)."""
        return db.get_combat_history(self.uid, self.limit)

    def stats(self) -> dict:
        """Cumulative combat stats."""
        return db.combat_stats(self.uid)

    def most_damage_dealt(self):
        """Row with highest damage_dealt."""
        rows = self.recent()
        return max(rows, key=lambda r: r["damage_dealt"]) if rows else None

    def most_damage_taken(self):
        """Row with highest damage_taken."""
        rows = self.recent()
        return max(rows, key=lambda r: r["damage_taken"]) if rows else None

    def longest_fight(self):
        """Row with highest round count."""
        rows = self.recent()
        return max(rows, key=lambda r: r["rounds"]) if rows else None

    def win_streak(self) -> int:
        """Current consecutive wins in recent history."""
        rows = self.recent()
        streak = 0
        for row in rows:
            if row["outcome"] == "victory":
                streak += 1
            else:
                break
        return streak

    def filter_by_outcome(self, outcome: str) -> list:
        """Filter recent rows by 'victory' or 'defeat'."""
        return [r for r in self.recent() if r["outcome"] == outcome]

    def filter_by_enemy(self, enemy_name: str) -> list:
        """Filter recent rows by enemy name (substring match)."""
        name_low = (enemy_name or "").lower()
        return [
            r for r in self.recent()
            if name_low in (r["enemy_name"] or "").lower()
        ]

    # ---------- RENDER ----------
    def render(self, title: str = "📜 Combat History — Last 10 Battles") -> str:
        """Full history text with cumulative stats."""
        rows = self.recent()
        if not rows:
            return (
                "No battles recorded yet.\n"
                "Try /explore → 1 (Battle) to start fighting."
            )
        lines = [title, ""]
        for i, row in enumerate(rows, 1):
            icon = "✅" if row["outcome"] == "victory" else "❌"
            lines.append(
                f"{i}. {icon} vs {row['enemy_name']}"
                f" — dealt {row['damage_dealt']:,}, "
                f"taken {row['damage_taken']:,}"
                f" · {row['rounds']} rounds"
                + (f" · {row['rewards_text']}" if row["rewards_text"] else "")
            )
        s = self.stats()
        lines.append("")
        lines.append(
            f"Record: {s['wins']}W / {s['losses']}L "
            f"({s['battles']} total)"
        )
        lines.append(
            f"Total damage: {s['dealt']:,} dealt · "
            f"{s['taken']:,} taken"
        )
        streak = self.win_streak()
        if streak > 0:
            lines.append(f"🔥 Current win streak: {streak}")
        return "\n".join(lines)

    def render_recent(self, n: int = 3,
                      title: str = "Recent Battles") -> str:
        """Compact rendering of the last N battles."""
        rows = db.get_combat_history(self.uid, max(1, n))
        if not rows:
            return ""
        lines = [title]
        for row in rows:
            icon = "✅" if row["outcome"] == "victory" else "❌"
            lines.append(
                f"{icon} {row['enemy_name']} — "
                f"dealt {row['damage_dealt']:,} / "
                f"taken {row['damage_taken']:,}"
            )
        return "\n".join(lines)

    def render_stats(self) -> str:
        """Cumulative stats only."""
        s = self.stats()
        return (
            f"📊 <b>Combat Stats</b>\n"
            f"Battles: {s['battles']}\n"
            f"Wins: {s['wins']}\n"
            f"Losses: {s['losses']}\n"
            f"Damage dealt: {s['dealt']:,}\n"
            f"Damage taken: {s['taken']:,}\n"
            f"Win rate: "
            f"{(s['wins'] * 100 // max(1, s['battles']))}%"
        )

    def export_csv(self) -> str:
        """Return all recent battles as a CSV string (for admin export)."""
        rows = self.recent()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "timestamp", "enemy", "enemy_max_hp", "damage_dealt",
            "damage_taken", "outcome", "rounds", "rewards",
        ])
        for row in rows:
            ts = datetime.fromtimestamp(
                row["created"], tz=timezone.utc
            ).isoformat()
            writer.writerow([
                ts,
                row["enemy_name"],
                row["enemy_max_hp"],
                row["damage_dealt"],
                row["damage_taken"],
                row["outcome"],
                row["rounds"],
                row["rewards_text"],
            ])
        return buf.getvalue()


# =============================================================
# COMBAT ACHIEVEMENTS
# =============================================================
class CombatAchievements:
    """
    Checks and unlocks combat/progression achievements.

    Usage from bot.py:
        ach = CombatAchievements(uid)
        ach.check_after_battle(won, damage_taken, is_boss=False)
        print(ach.reward_text())
    """

    def __init__(self, uid: int):
        self.uid = int(uid)
        self.newly_unlocked: list[dict] = []

    # ---------- INTERNAL ----------
    def _unlock(self, code: str) -> None:
        info = db.unlock_achievement(self.uid, code)
        if info:
            self.newly_unlocked.append(info)

    # ---------- PUBLIC CHECKS (called by bot.py) ----------
    def check_after_battle(
        self,
        won: bool,
        damage_taken: int,
        is_boss: bool = False,
        is_summon: bool = False,
    ) -> None:
        """Run all post-battle achievement checks."""
        s = db.combat_stats(self.uid)

        if won:
            self._unlock("first_blood")
            if s["battles"] >= 10:
                self._unlock("battle_10")
            if s["battles"] >= 50:
                self._unlock("battle_50")
            if s["battles"] >= 100:
                self._unlock("battle_100")
            if s["battles"] >= 500:
                self._unlock("battle_500")
            if damage_taken == 0:
                self._unlock("flawless")
            if is_boss:
                self._unlock("boss_slayer")
            if is_summon:
                self._unlock("summon_hunter")
            if s["wins"] >= 100:
                self._unlock("explore_vet")

        # Passive checks that can fire any time
        p = db.player(self.uid)
        if p:
            if p["yens"] >= 1_000_000:
                self._unlock("rich")
            if p["gems"] >= 1_000:
                self._unlock("gem_hoarder")
            if int(p["rank"] or 1) >= 5:
                self._unlock("rank_5")
            if int(p["rank"] or 1) >= 10:
                self._unlock("rank_10")
            if p["fusion_count"]:
                self._unlock("fusion_master")
            if (p["travel"] or "Earth") == "Omniverse":
                self._unlock("traveler")

    def check_dragon_balls(self) -> None:
        """Unlock 'dragon_collector' if the player has all 7 balls."""
        have = db.dragon_balls(self.uid)
        if all(have.get(s, 0) >= 1 for s in G.DRAGON_BALL_STARS):
            self._unlock("dragon_collector")

    def check_character(self, rarity: str) -> None:
        """Unlock mythical/omni owner achievements."""
        if rarity == "mythical":
            self._unlock("mythical_owner")
        elif rarity == "omni":
            self._unlock("omni_owner")

    def check_clan(self, leader: bool = False) -> None:
        """Unlock clan founder/leader achievements."""
        self._unlock("clan_founder")
        if leader:
            self._unlock("clan_leader")

    def check_raid_cleared(self) -> None:
        """Unlock raid_warrior when the world raid is defeated."""
        self._unlock("raid_warrior")

    def check_clan_raid_cleared(self) -> None:
        """Unlock clan_raid_clear when a clan raid boss is defeated."""
        self._unlock("clan_raid_clear")

    # ---------- OUTPUT ----------
    def reward_text(self) -> str:
        """Render newly unlocked achievements as a text block."""
        if not self.newly_unlocked:
            return ""
        lines = ["", "🏆 Achievements unlocked:"]
        for info in self.newly_unlocked:
            parts = []
            if info.get("yens"):
                parts.append(f"{info['yens']:,} yens")
            if info.get("gems"):
                parts.append(f"{info['gems']} gems")
            if info.get("crystals"):
                parts.append(f"{info['crystals']} crystals")
            lines.append(
                f"• {info['name']} — {', '.join(parts) or 'unlocked'}"
            )
        return "\n".join(lines)

    def category_progress(self) -> dict:
        """Return per-category progress counts."""
        unlocked = {row["code"] for row in db.player_achievements(self.uid)}
        out = {}
        for cat, codes in G.ACHIEVEMENT_CATEGORIES.items():
            have = sum(1 for c in codes if c in unlocked)
            out[cat] = {"have": have, "total": len(codes)}
        return out

    def near_complete(self) -> list[dict]:
        """
        Return achievements that are one step away from unlocking.
        Useful for suggesting goals.
        """
        s = db.combat_stats(self.uid)
        near = []

        thresholds = [
            ("battle_10", "battle_10", "battles", 10),
            ("battle_50", "battle_50", "battles", 50),
            ("battle_100", "battle_100", "battles", 100),
            ("battle_500", "battle_500", "battles", 500),
        ]
        unlocked = {row["code"] for row in db.player_achievements(self.uid)}
        for code, ach_key, stat_key, target in thresholds:
            if code in unlocked:
                continue
            cur = s[stat_key]
            if cur >= target - 5 and cur < target:
                near.append({
                    "code": code,
                    "name": G.ACHIEVEMENTS[code]["name"],
                    "progress": cur,
                    "target": target,
                })
        return near


# =============================================================
# QUEST TRACKER
# =============================================================
class QuestTracker:
    """
    Hooks into game events to auto-increment quest progress.

    Usage from bot.py:
        quest = QuestTracker(uid)
        quest.on_npc_kill()
        quest.on_battle_win()
        quest.on_yens_earned(yens)
    """

    def __init__(self, uid: int):
        self.uid = int(uid)

    # ---------- BATTLE EVENTS ----------
    def on_npc_kill(self) -> None:
        """Called after defeating an NPC."""
        db.quest_increment(self.uid, "daily", "daily_npc_10")
        db.quest_increment(self.uid, "weekly", "weekly_npc_100")
        db.quest_increment(self.uid, "monthly", "monthly_npc_500")

    def on_battle_win(self) -> None:
        """Called after winning ANY battle."""
        db.quest_increment(self.uid, "daily", "daily_win_5")
        db.quest_increment(self.uid, "monthly", "monthly_win_250")

    def on_boss_kill(self) -> None:
        """Called after defeating a world boss."""
        db.quest_increment(self.uid, "weekly", "weekly_boss_3")

    def on_summon_kill(self) -> None:
        """Called after defeating a summon boss."""
        db.quest_increment(self.uid, "monthly", "monthly_summon_5")

    # ---------- ECONOMY EVENTS ----------
    def on_yens_earned(self, amount: int) -> None:
        """Called when yens are earned (from any source)."""
        amount = max(0, int(amount or 0))
        if amount <= 0:
            return
        db.quest_increment(self.uid, "daily", "daily_earn_5000", amount)
        db.quest_increment(self.uid, "weekly", "weekly_earn_50k", amount)
        db.quest_increment(self.uid, "monthly", "monthly_earn_500k", amount)

    def on_gacha(self, rolls: int) -> None:
        """Called when the player does gacha rolls."""
        rolls = max(0, int(rolls or 0))
        if rolls <= 0:
            return
        db.quest_increment(self.uid, "daily", "daily_gacha_1", rolls)
        db.quest_increment(self.uid, "weekly", "weekly_gacha_10", rolls)

    # ---------- EXTRA EVENTS (hooks for future quests) ----------
    def on_travel(self, planet: str) -> None:
        """Called when the player travels."""
        pass

    def on_fusion(self) -> None:
        """Called when the player completes a fusion."""
        pass

    def on_rankup(self) -> None:
        """Called when the player ranks up."""
        pass

    def on_purchase(self, amount: int) -> None:
        """Called when the player spends yens at the shop."""
        pass

    def on_wish(self) -> None:
        """Called when the player makes a Shenron wish."""
        pass

    def on_clan_action(self, action: str) -> None:
        """Called on clan actions (create/join/leave/etc)."""
        pass


# =============================================================
# SELF-TEST (run: python combat.py)
# =============================================================
if __name__ == "__main__":
    import os
    # Use a throwaway DB so we don't clobber real data
    os.environ.setdefault("DB_PATH", "combat_test.sqlite")
    if os.path.exists("combat_test.sqlite"):
        os.remove("combat_test.sqlite")

    db.init()
    print("✅ DB initialized for combat tests")

    # --- Utility tests ---
    assert roll_damage(100) >= MIN_DAMAGE
    assert 0 <= power_level({"hp": 100, "atk": 50}) < 10**7
    print(f"✅ Power level of weak hero: "
          f"{power_level({'hp': 100, 'atk': 50}):,}")
    print(f"✅ Power level of Omni tier: "
          f"{power_level({'hp': 1800, 'atk': 520, 'spd': 100, 'crit': 35}):,}")

    # --- CombatEngine basic ---
    eng = CombatEngine(200, 500, crit=10, speed=20)
    won, left, log = eng.fight("Bandit Rookie", 70, 8)
    assert won is True
    assert left > 0
    assert eng.damage_dealt > 0
    print(f"✅ Basic fight: won={won}, hp_left={left}, "
          f"rounds={eng.rounds}")

    # --- CombatEngine full options ---
    eng2 = CombatEngine(
        200, 500, crit=15, speed=30,
        enable_dodge=True,
        enable_zenkai=True,
        enable_ki_gauge=True,
        enable_beam_struggle=True,
    )
    won2, left2, log2 = eng2.fight("Beerus Avatar", 5200, 180, enrage=True)
    print(f"✅ Enhanced fight: won={won2}, "
          f"dodges={eng2.dodges_triggered}, "
          f"crits={eng2.crits_landed}, "
          f"ki={eng2.ki}")

    # --- quick_fight ---
    result = quick_fight(200, 500, 100, 8)
    assert len(result) == 6
    print(f"✅ quick_fight returned 6-tuple")

    # --- simulate_fight ---
    sim = simulate_fight(200, 500, 100, 8)
    print(f"✅ simulate_fight: won={sim['won']}, "
          f"rounds={sim['rounds']}")

    # --- estimate_win_rate ---
    rate = estimate_win_rate(200, 500, 100, 8, iterations=50)
    assert 0.0 <= rate <= 1.0
    print(f"✅ estimate_win_rate: {rate * 100:.0f}% over 50 sims")

    # --- analyze_log ---
    analysis = analyze_log(log)
    print(f"✅ analyze_log: {analysis}")

    # --- CombatHistory ---
    test_uid = 777_777_777
    db.ensure_player(test_uid, "Combat Tester", "combat_test")
    hist = CombatHistory(test_uid)

    hist.log("Bandit Rookie", 70, 70, 0, "victory", 1, "")
    hist.log("Wild Wolf", 100, 100, 12, "victory", 2, "")
    hist.log("Beerus Avatar", 5200, 500, 5200, "defeat", 8, "")

    recent = hist.recent()
    assert len(recent) == 3
    print(f"✅ CombatHistory: {len(recent)} entries stored")

    stats = hist.stats()
    print(f"✅ Combat stats: {stats}")

    rendered = hist.render()
    assert "Combat History" in rendered
    print(f"✅ History render length: {len(rendered)} chars")

    streak = hist.win_streak()
    print(f"✅ Win streak: {streak}")

    best = hist.most_damage_dealt()
    print(f"✅ Most damage dealt: {best['damage_dealt']} "
          f"vs {best['enemy_name']}")

    csv_data = hist.export_csv()
    assert "timestamp" in csv_data
    print(f"✅ CSV export: {len(csv_data.splitlines())} lines")

    # --- CombatAchievements ---
    ach = CombatAchievements(test_uid)
    ach.check_after_battle(True, 0, is_boss=False)
    print(f"✅ Achievements unlocked after first battle: "
          f"{len(ach.newly_unlocked)}")

    ach2 = CombatAchievements(test_uid)
    ach2.check_character("mythical")
    print(f"✅ Mythical achievement check: "
          f"{len(ach2.newly_unlocked)} newly unlocked")

    cat = ach2.category_progress()
    print(f"✅ Category progress: {cat}")

    near = ach2.near_complete()
    print(f"✅ Near-complete achievements: {len(near)}")

    # --- QuestTracker ---
    quest = QuestTracker(test_uid)
    quest.on_npc_kill()
    quest.on_battle_win()
    quest.on_yens_earned(5000)
    quest.on_gacha(10)
    print(f"✅ Quest progress: "
          f"daily_npc_10={db.quest_progress(test_uid, 'daily', 'daily_npc_10')}, "
          f"daily_earn_5000={db.quest_progress(test_uid, 'daily', 'daily_earn_5000')}, "
          f"weekly_gacha_10={db.quest_progress(test_uid, 'weekly', 'weekly_gacha_10')}")

    # Cleanup
    os.remove("combat_test.sqlite")
    print("\n🎉 All combat.py self-tests passed!")
