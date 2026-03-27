# -*- coding: utf-8 -*-
"""
Clean Booking.com review exports for analysis / ML.

- nr_nights: parse "1 night ·" / "4 nights ·" → integer
- date: "February 2026" → datetime (first day of that month)
- country, traveler_type, room_type: pandas categorical dtype
- score: float

Usage:
  python clean_reviews.py [--in INPUT.csv] [--out OUTPUT.csv]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


def _detect_sep(path: Path) -> str:
    line = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[0]
    return ";" if line.count(";") > line.count(",") else ","


def parse_nr_nights(raw: object) -> float:
    """Extract integer nights from strings like '1 night ·' or '4 nights ·'."""
    if pd.isna(raw) or raw is None:
        return float("nan")
    s = str(raw).strip()
    if not s:
        return float("nan")
    m = re.search(r"(\d+)\s*night", s, re.IGNORECASE)
    if m:
        return float(int(m.group(1)))
    return float("nan")


def parse_stay_date(raw: object) -> pd.Timestamp | pd.NaT:
    """Parse 'February 2026' style → first day of month as datetime."""
    if pd.isna(raw) or raw is None:
        return pd.NaT
    s = str(raw).strip()
    if not s:
        return pd.NaT
    ts = pd.to_datetime(s, format="%B %Y", errors="coerce")
    if pd.isna(ts):
        ts = pd.to_datetime(s, errors="coerce")
    return ts


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "nr_nights" in out.columns:
        out["nr_nights"] = out["nr_nights"].map(parse_nr_nights)
        out["nr_nights"] = pd.to_numeric(out["nr_nights"], errors="coerce").astype("Int64")

    if "date" in out.columns:
        out["date"] = out["date"].map(parse_stay_date)
        out["date"] = pd.to_datetime(out["date"], errors="coerce")

    if "score" in out.columns:
        out["score"] = pd.to_numeric(out["score"], errors="coerce")

    cat_cols = [c for c in ("country", "traveler_type", "room_type") if c in out.columns]
    for c in cat_cols:
        s = out[c].replace("", pd.NA).astype("string")
        out[c] = s.astype("category")

    text_cols = [
        c
        for c in (
            "name",
            "title_review",
            "pos_review",
            "neg_review",
            "hotel_response",
        )
        if c in out.columns
    ]
    for c in text_cols:
        out[c] = out[c].astype("string")

    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Clean review CSV for ML / analysis")
    p.add_argument(
        "--in",
        dest="in_path",
        default="reviews_paodeacucar_porto.csv",
        help="Input CSV path",
    )
    p.add_argument(
        "--out",
        dest="out_path",
        default="reviews_cleaned.csv",
        help="Output CSV path",
    )
    args = p.parse_args()

    in_path = Path(args.in_path)
    if not in_path.is_file():
        raise SystemExit(f"Input not found: {in_path}")

    sep = _detect_sep(in_path)
    df = pd.read_csv(in_path, sep=sep, encoding="utf-8-sig")
    n_before = len(df)
    df = clean_dataframe(df)

    out_path = Path(args.out_path)
    if out_path.suffix.lower() != ".csv":
        out_path = out_path.with_suffix(".csv")
    df.to_csv(
        out_path,
        index=False,
        encoding="utf-8-sig",
        sep=",",
        date_format="%Y-%m-%d",
    )
    print(f"Wrote {len(df)} rows to {out_path} (dates as YYYY-MM-DD)")

    print(f"Rows: {n_before} | Columns: {list(df.columns)}")
    print(f"date dtype: {df['date'].dtype if 'date' in df.columns else 'n/a'}")
    print(f"nr_nights dtype: {df['nr_nights'].dtype if 'nr_nights' in df.columns else 'n/a'}")


if __name__ == "__main__":
    main()
