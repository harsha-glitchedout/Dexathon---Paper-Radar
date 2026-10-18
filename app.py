"""Paper Radar: Streamlit web page.  Run:  streamlit run app.py"""
import html
import os
import re

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import analyzer
import gamify
from extractor import extract_text
from syllabus import load_syllabus
from tagger import tag_paper

load_dotenv()
st.set_page_config(page_title="Paper Radar", page_icon="📡", layout="wide")

try:
    with open("style.css", "r", encoding="utf-8") as _f:
        st.markdown(f"<style>{_f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass  # app still works without the stylesheet, just looks plain

COLUMNS = ["paper", "year", "q_no", "question", "marks", "topic", "unit"]

# ---------------- sidebar ----------------
st.sidebar.title("📡 Paper Radar")
st.sidebar.caption("Team Infinite Loopers")

mode = st.sidebar.radio("Data source", ["Demo data (no API key)", "Upload my papers"])

syl_file = st.sidebar.file_uploader("Syllabus JSON (optional)", type="json")
try:
    syllabus = load_syllabus(syl_file) if syl_file else load_syllabus("syllabus/sample_syllabus.json")
except Exception as e:
    st.sidebar.error(f"Syllabus problem: {e}")
    st.stop()

if mode.startswith("Upload"):
    key_box = st.sidebar.text_input("Anthropic API key", type="password",
                                    help="Or put ANTHROPIC_API_KEY in a .env file")
    if key_box:
        os.environ["ANTHROPIC_API_KEY"] = key_box

st.sidebar.markdown(f"**Subject:** {syllabus.get('subject', '-')}")
st.sidebar.markdown(f"**Regulation:** {syllabus.get('regulation', '-')}")

# ---------------- header ----------------
st.markdown(
    '<div class="hero"><div class="radar"></div><div>'
    '<h1 class="hero-title">Paper Radar</h1>'
    '<p class="hero-sub">See what past papers keep asking, then clear it topic by topic. '
    'Pattern analysis from past papers, not a prediction.</p></div></div>',
    unsafe_allow_html=True,
)

if "df" not in st.session_state:
    st.session_state.df = None

# ---------------- load data ----------------
if mode.startswith("Demo"):
    st.info("Showing **synthetic demo data** (made-up questions) so you can try the app. "
            "Switch to 'Upload my papers' to analyze real papers.")
    st.session_state.df = pd.read_csv("data/demo_tagged.csv")
else:
    files = st.file_uploader("Upload past papers for ONE subject and ONE regulation",
                             type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    if st.button("Extract and tag", type="primary", disabled=not files):
        all_rows, bar = [], st.progress(0.0)
        for i, f in enumerate(files):
            label = os.path.splitext(f.name)[0]
            m = re.search(r"(19|20)\d{2}", label)
            year = int(m.group(0)) if m else 0
            try:
                with st.spinner(f"Reading {f.name} ..."):
                    text, used_ocr = extract_text(f.name, f.getvalue())
                    if used_ocr:
                        st.warning(f"{f.name}: scanned, used OCR. Check the tags below carefully.")
                    rows = tag_paper(text, syllabus)
                for r in rows:
                    r.update(paper=label, year=year)
                all_rows.extend(rows)
            except Exception as e:
                st.error(f"{f.name}: {e}")
            bar.progress((i + 1) / len(files))
        if all_rows:
            st.session_state.df = pd.DataFrame(all_rows)[COLUMNS]
        else:
            st.error("No questions found. Check the files and your API key.")

df = st.session_state.df
if df is None or df.empty:
    st.stop()

# ---------------- manual check step ----------------
all_topics = [t for ts in syllabus["units"].values() for t in ts] + [analyzer.UNMAPPED]
t2u = {t: u for u, ts in syllabus["units"].items() for t in ts}

with st.expander("✏️ Check and fix tags (recommended before trusting the results)",
                 expanded=mode.startswith("Upload")):
    st.caption("The LLM can tag wrongly. Change any topic here; unit and counts update automatically.")
    edited = st.data_editor(
        df, use_container_width=True, hide_index=True, num_rows="fixed",
        disabled=["paper", "year", "q_no", "question", "marks", "unit"],
        column_config={"topic": st.column_config.SelectboxColumn("topic", options=all_topics)},
        key="editor",
    )
    edited["unit"] = edited["topic"].map(t2u).fillna(analyzer.UNMAPPED)
    df = edited

# ---------------- tabs ----------------
tab_radar, tab_game = st.tabs(["📡 Radar", "🎮 Quest log"])

with tab_radar:
    total = analyzer.n_papers(df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Papers analyzed", total)
    c2.metric("Questions found", len(df))
    c3.metric("Unmapped questions", analyzer.unmapped_count(df))
    if total < 5:
        st.warning(f"Only {total} papers. Patterns from so few papers are weak.")

    st.subheader("🎯 Study first")
    top = analyzer.study_first(df, 3)
    cols = st.columns(len(top)) if len(top) else []
    for i, (col, (_, r)) in enumerate(zip(cols, top.iterrows()), start=1):
        col.markdown(
            f'<div class="rank-card r{i}"><div class="rank-n">#{i}</div>'
            f'<div class="rank-unit">{html.escape(str(r["unit"]))}</div>'
            f'<div class="rank-meta">Asked in {r["asked_in"]} papers, {int(r["total_marks"])} marks total</div>'
            f'<div class="rank-bar"><span style="width:{int(r["share"] * 100)}%"></span></div></div>',
            unsafe_allow_html=True,
        )
    st.caption("Ranking rule: units asked in more papers come first; ties are broken by total marks.")

    left, right = st.columns([1, 1.4])
    with left:
        st.subheader("Units")
        us = analyzer.unit_summary(df)
        st.dataframe(
            us[["unit", "asked_in", "share", "total_marks"]], hide_index=True, use_container_width=True,
            column_config={"share": st.column_config.ProgressColumn("frequency", min_value=0, max_value=1),
                           "asked_in": "asked in", "total_marks": "total marks"},
        )
    with right:
        st.subheader("Heatmap: marks per topic per paper")
        hm = analyzer.heatmap_data(df)
        chart = (
            alt.Chart(hm).mark_rect().encode(
                x=alt.X("paper:N", title=None, axis=alt.Axis(labelAngle=-40)),
                y=alt.Y("topic:N", title=None, sort=alt.EncodingSortField(field="marks", op="sum", order="descending")),
                color=alt.Color("marks:Q", scale=alt.Scale(range=["#0F2F4A", "#19D3C5", "#FFD27A", "#FF8A5B"]), title="marks"),
                tooltip=["topic", "paper", "marks", "questions"],
            ).properties(height=max(300, 28 * hm["topic"].nunique()))
        )
        chart = chart.configure(background="transparent").configure_view(strokeWidth=0)
        st.altair_chart(chart, use_container_width=True)

    # ---------------- traceable sources ----------------
    st.subheader("🔎 Verify a topic")
    ts = analyzer.topic_summary(df)
    pick = st.selectbox("Pick a topic to see every source question", ts["topic"].tolist())
    row = ts[ts["topic"] == pick].iloc[0]
    st.write(f"**{pick}** was asked in **{row['asked_in']}** papers.")
    st.dataframe(analyzer.sources_for(df, pick), hide_index=True, use_container_width=True)

    st.download_button("⬇️ Download tagged questions (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "paper_radar_tagged.csv", "text/csv")

# ---------------- quest log (game layer) ----------------
quests = gamify.build_quests(analyzer.topic_summary(df), t2u)
pkey = syllabus.get("subject", "subject")
quest_xp = dict(zip(quests["topic"], quests["xp"]))

if st.session_state.get("pkey") != pkey:
    st.session_state.pkey = pkey
    st.session_state.cleared = gamify.load_progress(pkey)
    for t in quests["topic"]:
        st.session_state[f"cb_{t}"] = t in st.session_state.cleared


def toggle_topic(topic):
    """Runs when a checkbox is clicked. Updates progress and queues pop-up messages."""
    cleared = st.session_state.cleared
    xp_before = gamify.total_xp(quests, cleared)
    badges_before = {b[1] for b in gamify.badges(quests, cleared) if b[3]}
    if st.session_state[f"cb_{topic}"]:
        cleared.add(topic)
    else:
        cleared.discard(topic)
    gamify.save_progress(pkey, cleared)
    xp_after = gamify.total_xp(quests, cleared)
    badges_after = {b[1] for b in gamify.badges(quests, cleared) if b[3]}
    msgs = []
    if xp_after > xp_before:
        msgs.append(f"Quest cleared: {topic} (+{quest_xp.get(topic, 0)} XP)")
    for name in sorted(badges_after - badges_before):
        msgs.append(f"Badge unlocked: {name}")
    leveled = gamify.level_info(xp_after)["level"] > gamify.level_info(xp_before)["level"]
    if leveled:
        msgs.append(f"Level up! You are now level {gamify.level_info(xp_after)['level']}")
    st.session_state.event = {"msgs": msgs, "balloons": leveled}


def clear_next(topic):
    st.session_state[f"cb_{topic}"] = True
    toggle_topic(topic)


def reset_progress():
    st.session_state.cleared = set()
    for t in quests["topic"]:
        st.session_state[f"cb_{t}"] = False
    gamify.save_progress(pkey, set())


with tab_game:
    event = st.session_state.pop("event", None)
    if event:
        for m in event["msgs"]:
            st.toast(m, icon="🎮")
        if event["balloons"]:
            st.balloons()

    cleared = st.session_state.cleared
    xp = gamify.total_xp(quests, cleared)
    info = gamify.level_info(xp)
    ready = gamify.readiness(quests, cleared)

    with st.container(border=True, key="card_player"):
        a, b, c = st.columns([1, 2, 2])
        a.markdown(f"### Level {info['level']}\n{info['rank']}")
        with b:
            st.write(f"**XP:** {xp} total")
            st.progress(info["into"] / info["need"],
                        text=f"{info['into']} / {info['need']} XP to level {info['level'] + 1}")
        with c:
            st.write("**Exam readiness**")
            st.progress(ready, text=f"{ready:.0%} of past-paper marks covered")
    st.caption("Readiness only measures how much of the PAST pattern you have studied. "
               "It does not predict your exam.")

    nq = gamify.next_quest(quests, cleared)
    if nq is None:
        st.success("Every quest cleared. Time to revise, not to relax.")
    else:
        with st.container(border=True, key="card_next"):
            n1, n2 = st.columns([4, 1])
            n1.markdown(f"**Next quest:** {nq['icon']} {nq['topic']}  \n"
                        f"{nq['tier']} tier, asked in {nq['asked_in']} papers, +{int(nq['xp'])} XP")
            n2.button("Mark cleared", key="clear_next_btn", type="primary", on_click=clear_next,
                      args=(nq["topic"],), use_container_width=True)

    st.subheader("Badges")
    bcols = st.columns(5)
    for i, (col, (icon, name, how, got)) in enumerate(zip(bcols, gamify.badges(quests, cleared))):
        with col.container(border=True, key=f"card_badge_{'on' if got else 'off'}_{i}"):
            if got:
                st.markdown(f"### {icon}\n**{name}**")
                st.caption("Unlocked")
            else:
                st.markdown(f"### 🔒\n**{name}**")
                st.caption(how)

    st.subheader("Quest board")
    st.caption("Tiers: 👹 Boss = asked in 75%+ of papers, ⚔️ Elite = 50%+, 🗡️ Common = the rest. "
               "XP = 10 per paper it appeared in + 1 per 10 marks it carried.")
    prog = gamify.unit_progress(quests, cleared)
    for i, unit in enumerate([u for u in syllabus["units"] if u in prog]):
        done, count = prog[unit]
        icon = "✅" if done == count else "📂"
        with st.expander(f"{icon} {unit}  ({done}/{count} cleared)", expanded=(i == 0)):
            st.progress(done / count if count else 0.0)
            grp = quests[quests["unit"] == unit].sort_values("xp", ascending=False)
            for _, q in grp.iterrows():
                st.checkbox(
                    f"{q['icon']} **{q['topic']}** | {q['tier']} | asked in {q['asked_in']} | +{int(q['xp'])} XP",
                    key=f"cb_{q['topic']}", on_change=toggle_topic, args=(q["topic"],),
                )

    with st.expander("Reset my progress"):
        st.button("Reset everything", on_click=reset_progress)
