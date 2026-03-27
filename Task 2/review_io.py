# -*- coding: utf-8 -*-
"""Shared helpers to load cleaned review CSVs and build text fields."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def detect_sep(path: Path) -> str:
    line = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[0]
    return ";" if line.count(";") > line.count(",") else ","


def load_reviews(path: Path) -> pd.DataFrame:
    sep = detect_sep(path)
    df = pd.read_csv(path, sep=sep, encoding="utf-8-sig")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "score" in df.columns:
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
    if "nr_nights" in df.columns:
        df["nr_nights"] = pd.to_numeric(df["nr_nights"], errors="coerce")
    return df


def combined_review_text(df: pd.DataFrame) -> pd.Series:
    """Concatenate title + positive + negative fields for NLP."""
    cols = [c for c in ("title_review", "pos_review", "neg_review") if c in df.columns]
    if not cols:
        return pd.Series([""] * len(df), index=df.index, dtype="string")
    acc = df[cols[0]].fillna("").astype(str)
    for c in cols[1:]:
        acc = acc + " " + df[c].fillna("").astype(str)
    return acc.str.strip()
