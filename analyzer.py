"""Step 3 + 4: COUNT and RANK. Plain pandas, no LLM involved.

Expected dataframe columns: paper, year, q_no, question, marks, topic, unit
"""
import pandas as pd

UNMAPPED = "UNMAPPED"


def n_papers(df):
    return df["paper"].nunique()


def _summary(df, key):
    """How many papers asked this unit/topic, plus total marks."""
    total = n_papers(df)
    good = df[df[key] != UNMAPPED]
    out = (
        good.groupby(key)
        .agg(papers_asked=("paper", "nunique"), questions=("question", "count"),
             total_marks=("marks", "sum"))
        .reset_index()
    )
    out["asked_in"] = out["papers_asked"].astype(int).astype(str) + " of " + str(total)
    out["share"] = out["papers_asked"] / total if total else 0
    return out.sort_values(["papers_asked", "total_marks"], ascending=False).reset_index(drop=True)


def unit_summary(df):
    return _summary(df, "unit")


def topic_summary(df):
    return _summary(df, "topic")


def heatmap_data(df):
    """Long table: topic x paper with total marks, for the heatmap."""
    good = df[df["topic"] != UNMAPPED]
    grid = good.groupby(["topic", "paper"]).agg(marks=("marks", "sum"),
                                                questions=("question", "count")).reset_index()
    return grid


def study_first(df, k=3):
    """Top k units. Rule (shown to the user): more papers first, then more marks."""
    return unit_summary(df).head(k)


def unmapped_count(df):
    return int((df["topic"] == UNMAPPED).sum())


def sources_for(df, topic):
    """Every question under a topic, with its paper and year, so students can verify."""
    sub = df[df["topic"] == topic][["paper", "year", "q_no", "marks", "question"]]
    return sub.sort_values(["year", "paper", "q_no"]).reset_index(drop=True)
