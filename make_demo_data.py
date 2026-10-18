"""Creates data/demo_tagged.csv: SYNTHETIC questions so the app runs with no API key.
This is made-up data for demo purposes only, not real exam questions.
Run:  python make_demo_data.py
"""
import random

import pandas as pd

from syllabus import load_syllabus, topic_to_unit

random.seed(7)
syl = load_syllabus("syllabus/sample_syllabus.json")
t2u = topic_to_unit(syl)
topics = list(t2u)

# Made-up weights so the heatmap has visible structure
weights = {t: 1 for t in topics}
for t in ["Binary trees", "Binary search trees", "Tree traversals", "Sorting algorithms", "Linked lists"]:
    weights[t] = 5
for t in ["Shortest paths", "Hashing", "Heaps"]:
    weights[t] = 2

sessions = ["Nov 2018", "Apr 2019", "Nov 2019", "Apr 2021", "Nov 2021", "Apr 2022", "Nov 2022", "Apr 2023"]
rows = []
for idx, sess in enumerate(sessions, start=1):
    paper = f"Demo Paper {idx} ({sess})"
    year = int(sess.split()[1])
    q = 1
    for _ in range(10):  # Part A style, 2 marks
        t = random.choices(topics, [weights[x] for x in topics])[0]
        rows.append([paper, year, f"A{q}", 2, t])
        q += 1
    for j in range(5):  # Part B style, 13 marks
        t = random.choices(topics, [weights[x] for x in topics])[0]
        rows.append([paper, year, f"B{j + 11}", 13, t])
    rows.append([paper, year, "C16", 15, random.choices(topics, [weights[x] for x in topics])[0]])

df = pd.DataFrame(rows, columns=["paper", "year", "q_no", "marks", "topic"])
df["unit"] = df["topic"].map(t2u)
df["question"] = "[synthetic demo question] about " + df["topic"].str.lower()
df = df[["paper", "year", "q_no", "question", "marks", "topic", "unit"]]
df.to_csv("data/demo_tagged.csv", index=False)
print(f"Wrote data/demo_tagged.csv with {len(df)} rows across {df['paper'].nunique()} papers")
