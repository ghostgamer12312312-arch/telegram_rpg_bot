from __future__ import annotations

"""Combat engine, CombatHistory, CombatAchievements, QuestTracker."""

import random

import db
import game_data as G


# =============================================================
# CombatEngine — turn-based fight simulation
# =============================================================
class CombatEngine:
    def __init__(self, player_atk: int, player_hp: int,
                 crit: int = 5, speed: int = 10):
        self.p_atk = player_atk
        self.p_hp = player_hp
        self.crit = crit
        self.speed = speed
        self.damage_dealt = 0
        self.damage_taken = 0
        self.rounds = 0
        self.log: list[str] = []

    def _roll_hit(self, base: int, spread: tuple[float, float] = (0.8, 1.35)) -> int:
        hit = int(base * random.uniform(*spread))
        if random.randint(1, 100) <= self.crit:
            hit = int(hit * 1.6)
            self.log.append("  >> CRITICAL HIT!")
        return max(1, hit)

    def fight(self, enemy_name: str, enemy_hp: int, enemy_dmg: int,
              enrage: bool = False) -> tuple[bool, int, list[str]]:
        p_hp = self.p_hp
        e_hp = enemy_hp
        e_max = enemy_hp
        for rnd in range(1, 61):
            self.rounds = rnd
            first = self.speed > 25 or random.random() < 0.5
            if first:
                hit = self._roll_hit(self.p_atk)
                e_hp -= hit
                self.damage_dealt += hit
                self.log.append(f"Round {rnd}: You hit {enemy_name} for {hit}")
                if e_hp <= 0:
                    self.log.append("Victory!")
                    return True, max(1, p_hp), self.log
            mult = 1.3 if enrage and e_hp <= e_max // 2 else 1.0
            taken = self._roll_hit(int(enemy_dmg * mult), (0.8, 1.25))
            p_hp -= taken
            self.damage_taken += taken
            self.log.append(f"Round {rnd}: {enemy_name} hits for {taken}")
            if p_hp <= 0:
                return False, 0, self.log
            if not first:
                hit = self._roll_hit(self.p_atk)
                e_hp -= hit
                self.damage_dealt += hit
                self.log.append(f"Round {rnd}: You hit {enemy_name} for {hit}")
                if e_hp <= 0:
                    self.log.append("Victory!")
                    return True, max(1, p_hp), self.log
        return False, max(0, p_hp), self.log + ["Battle dragged on."]


def quick_fight(player_atk: int, player_hp: int, enemy_hp: int,
                enemy_dmg: int, crit: int = 5, enrage: bool = False):
    eng = CombatEngine(player_atk, player_hp, crit)
    won, left, log = eng.fight("Enemy", enemy_hp, enemy_dmg, enrage)
    return won, left, log, eng.damage_dealt, eng.damage_taken, eng.rounds


# =============================================================
# CombatHistory — last 10 fight logs
# =============================================================
class CombatHistory:
    def __init__(self, uid: int, limit: int = 10):
        self.uid = uid
        self.limit = limit

    def log(self, enemy_name: str, enemy_max_hp: int,
            damage_dealt: int, damage_taken: int,
            outcome: str, rounds: int, rewards_text: str = "") -> None:
        db.add_combat_log(self.uid, enemy_name, enemy_max_hp,
                          damage_dealt, damage_taken, outcome,
                          rounds, rewards_text)

    def recent(self) -> list:
        return db.get_combat_history(self.uid, self.limit)

    def render(self, title: str = "📜 Combat History — Last 10 Battles") -> str:
        rows = self.recent()
        if not rows:
            return "No battles recorded yet. Try /explore → 1 (Battle)."
        lines = [title, ""]
        for row in rows:
            icon = "✅" if row["outcome"] == "victory" else "❌"
            lines.append(
                f"{icon} vs {row['enemy_name']}"
                f" — dealt {row['damage_dealt']:,}, "
                f"taken {row['damage_taken']:,}"
                f" · {row['rounds']} rounds"
                + (f" · {row['rewards_text']}" if row["rewards_text"] else "")
            )
        s = db.combat_stats(self.uid)
        lines.append("")
        lines.append(f"Record: {s['wins']}W / {s['losses']}L "
                     f"({s['battles']} total)")
        lines.append(f"Damage: {s['dealt']:,} dealt · {s['taken']:,} taken")
        return "\n".join(lines)

    def render_recent(self, n: int = 3, title: str = "Recent Battles") -> str:
        rows = db.get_combat_history(self.uid, n)
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


# =============================================================
# CombatAchievements
# =============================================================
class CombatAchievements:
    def __init__(self, uid: int):
        self.uid = uid
        self.newly_unlocked: list[dict] = []

    def _unlock(self, code: str) -> None:
        info = db.unlock_achievement(self.uid, code)
        if info:
            self.newly_unlocked.append(info)

    def check_after_battle(self, won: bool, damage_taken: int,
                           is_boss: bool = False,
                           is_summon: bool = False) -> None:
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
        have = db.dragon_balls(self.uid)
        if all(have.get(s, 0) >= 1 for s in G.DRAGON_BALL_STARS):
            self._unlock("dragon_collector")

    def check_character(self, rarity: str) -> None:
        if rarity == "mythical":
            self._unlock("mythical_owner")
        elif rarity == "omni":
            self._unlock("omni_owner")

    def check_clan(self, leader: bool = False) -> None:
        self._unlock("clan_founder")
        if leader:
            self._unlock("clan_leader")

    def check_raid_cleared(self) -> None:
        self._unlock("raid_warrior")

    def reward_text(self) -> str:
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
            lines.append(f"• {info['name']} — {', '.join(parts) or 'unlocked'}")
        return "\n".join(lines)


# =============================================================
# QuestTracker — auto-increments progress
# =============================================================
class QuestTracker:
    def __init__(self, uid: int):
        self.uid = uid

    def on_npc_kill(self) -> None:
        db.quest_increment(self.uid, "daily", "daily_npc_10")
        db.quest_increment(self.uid, "weekly", "weekly_npc_100")
        db.quest_increment(self.uid, "monthly", "monthly_npc_500")

    def on_battle_win(self) -> None:
        db.quest_increment(self.uid, "daily", "daily_win_5")
        db.quest_increment(self.uid, "weekly", "weekly_win_250"
                           if False else "weekly_boss_3")  # boss 3 tracked separately
        db.quest_increment(self.uid, "monthly", "monthly_win_250")

    def on_boss_kill(self) -> None:
        db.quest_increment(self.uid, "weekly", "weekly_boss_3")

    def on_yens_earned(self, amount: int) -> None:
        db.quest_increment(self.uid, "daily", "daily_earn_5000", amount)
        db.quest_increment(self.uid, "weekly", "weekly_earn_50k", amount)
        db.quest_increment(self.uid, "monthly", "monthly_earn_500k", amount)

    def on_gacha(self, rolls: int) -> None:
        db.quest_increment(self.uid, "daily", "daily_gacha_1", rolls)
        db.quest_increment(self.uid, "weekly", "weekly_gacha_10", rolls)

    def on_summon_kill(self) -> None:
        db.quest_increment(self.uid, "monthly", "monthly_summon_5")
