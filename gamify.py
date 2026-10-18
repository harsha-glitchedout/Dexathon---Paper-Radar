"""Game layer for Paper Radar. Pure pandas/python, no Streamlit in here.

Idea: every syllabus topic that appeared in past papers is a QUEST.
- The more papers asked it, the tougher the tier (Boss / Elite / Common).
- Clearing a quest (you mark it as studied) gives XP.
- XP gives levels, and cleared marks give an "exam readiness" percentage.
Nothing here predicts the exam. It only measures how much of the PAST pattern you covered.
"""
import json
import os

import pandas as pd

PROGRESS_FILE = "progress.json"
XP_PER_LEVEL = 150
RANKS = ["Rookie", "Scout", "Tracker", "Hunter", "Veteran", "Legend"]

# (minimum share of papers, tier name, icon)
TIERS = [(0.75, "Boss", "👹"), (0.5, "Elite", "⚔️"), (0.0, "Common", "🗡️")]


def tier_for(share):
    for cut, name, icon in TIERS:
        if share >= cut:
            return name, icon
    return "Common", "🗡️"


def build_quests(topic_summary, topic_to_unit):
    """topic_summary comes from analyzer.topic_summary(df). Returns one row per quest."""
    q = topic_summary.copy()
    q["unit"] = q["topic"].map(topic_to_unit)
    q = q.dropna(subset=["unit"])
    q["tier"] = q["share"].map(lambda s: tier_for(s)[0])
    q["icon"] = q["share"].map(lambda s: tier_for(s)[1])
    # XP rule (shown to the user): 10 per paper it appeared in + 1 per 10 marks it carried
    q["xp"] = (q["papers_asked"] * 10 + (q["total_marks"] // 10)).astype(int)
    return q.reset_index(drop=True)


def total_xp(quests, cleared):
    return int(quests[quests["topic"].isin(cleared)]["xp"].sum())


def level_info(xp):
    level = xp // XP_PER_LEVEL + 1
    return {
        "level": level,
        "rank": RANKS[min(level - 1, len(RANKS) - 1)],
        "into": xp % XP_PER_LEVEL,
        "need": XP_PER_LEVEL,
    }


def readiness(quests, cleared):
    """Share of past-paper marks that sit in topics you have cleared (0 to 1)."""
    total = quests["total_marks"].sum()
    if total == 0:
        return 0.0
    return float(quests[quests["topic"].isin(cleared)]["total_marks"].sum() / total)


def next_quest(quests, cleared):
    left = quests[~quests["topic"].isin(cleared)]
    if left.empty:
        return None
    return left.sort_values(["xp", "total_marks"], ascending=False).iloc[0]


def unit_progress(quests, cleared):
    """{unit: (cleared_count, total_count)}"""
    out = {}
    for unit, grp in quests.groupby("unit"):
        out[unit] = (int(grp["topic"].isin(cleared).sum()), len(grp))
    return out


def badges(quests, cleared):
    """List of (icon, name, how to unlock, unlocked?)"""
    ready = readiness(quests, cleared)
    bosses = quests[quests["tier"] == "Boss"]["topic"]
    prog = unit_progress(quests, cleared)
    return [
        ("🩸", "First blood", "Clear your first topic", len(cleared) >= 1),
        ("👹", "Boss slayer", "Clear a Boss topic", bool(len(bosses)) and bool(bosses.isin(cleared).any())),
        ("🏁", "Chapter clear", "Clear every topic in one unit",
         any(c == n and n > 0 for c, n in prog.values())),
        ("🌗", "Halfway", "Cover 50% of past-paper marks", ready >= 0.5),
        ("🏆", "Exam ready", "Cover 80% of past-paper marks", ready >= 0.8),
    ]


# ---------- saving progress to a small file so it survives closing the app ----------

def load_progress(key, path=PROGRESS_FILE):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f).get(key, []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_progress(key, cleared, path=PROGRESS_FILE):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data[key] = sorted(cleared)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
