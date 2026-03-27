# -*- coding: utf-8 -*-
"""
Step 1 — Exploratory data analysis (EDA)

Loads cleaned review CSV, writes summary tables and matplotlib figures under outputs/eda/.

Prerequisites: run clean_reviews.py first (or point --in to a cleaned CSV).

Usage:
  python eda_step1.py
  python eda_step1.py --in reviews_cleaned.csv --out-dir outputs/eda
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def _detect_sep(path: Path) -> str:
    line = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[0]
    return ";" if line.count(";") > line.count(",") else ","


def load_reviews(path: Path) -> pd.DataFrame:
    sep = _detect_sep(path)
    df = pd.read_csv(path, sep=sep, encoding="utf-8-sig")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "score" in df.columns:
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
    if "nr_nights" in df.columns:
        df["nr_nights"] = pd.to_numeric(df["nr_nights"], errors="coerce")
    for c in ("country", "traveler_type", "room_type"):
        if c in df.columns:
            df[c] = df[c].astype("string")
    return df


def _word_count(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.split().str.len()


def write_tables(df: pd.DataFrame, tables_dir: Path) -> None:
    tables_dir.mkdir(parents=True, exist_ok=True)

    # Overview
    overview = pd.DataFrame(
        {
            "metric": ["n_rows", "n_columns", "date_min", "date_max"],
            "value": [
                len(df),
                len(df.columns),
                df["date"].min() if "date" in df.columns else pd.NA,
                df["date"].max() if "date" in df.columns else pd.NA,
            ],
        }
    )
    overview.to_csv(tables_dir / "01_dataset_overview.csv", index=False)

    miss = df.isna().sum().rename("missing_count").reset_index()
    miss.columns = ["column", "missing_count"]
    miss["missing_pct"] = (miss["missing_count"] / len(df) * 100).round(2)
    miss.to_csv(tables_dir / "02_missing_by_column.csv", index=False)

    num_cols = [c for c in ("score", "nr_nights") if c in df.columns]
    if num_cols:
        desc = df[num_cols].describe().T
        desc.to_csv(tables_dir / "03_numeric_summary.csv")

    if "score" in df.columns:
        for col, fname in (
            ("country", "04_score_by_country.csv"),
            ("traveler_type", "05_score_by_traveler_type.csv"),
            ("room_type", "06_score_by_room_type.csv"),
        ):
            if col not in df.columns:
                continue
            g = (
                df.groupby(col, dropna=False)["score"]
                .agg(["count", "mean", "std", "min", "max"])
                .round(3)
                .sort_values("count", ascending=False)
            )
            g.to_csv(tables_dir / fname)

    if "date" in df.columns:
        m = df.dropna(subset=["date"]).copy()
        m["year_month"] = m["date"].dt.to_period("M").astype(str)
        per_m = (
            m.groupby("year_month", dropna=False)
            .agg(
                n_reviews=("score", "count"),
                mean_score=("score", "mean"),
            )
            .round(3)
        )
        per_m.to_csv(tables_dir / "07_reviews_and_mean_score_by_month.csv")

    df = df.copy()
    df["_wc_pos"] = _word_count(df["pos_review"]) if "pos_review" in df.columns else 0
    df["_wc_neg"] = _word_count(df["neg_review"]) if "neg_review" in df.columns else 0
    tl = pd.DataFrame(
        {
            "field": ["pos_review", "neg_review"],
            "mean_words": [df["_wc_pos"].mean(), df["_wc_neg"].mean()],
            "median_words": [df["_wc_pos"].median(), df["_wc_neg"].median()],
            "max_words": [df["_wc_pos"].max(), df["_wc_neg"].max()],
        }
    )
    tl = tl.round(2)
    tl.to_csv(tables_dir / "08_text_length_words_summary.csv", index=False)


def plot_figures(df: pd.DataFrame, fig_dir: Path) -> None:
    fig_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "figure.figsize": (8, 5),
            "figure.dpi": 120,
            "axes.grid": True,
            "grid.alpha": 0.3,
        }
    )

    # 1) Score distribution
    if "score" in df.columns:
        fig, ax = plt.subplots()
        ax.hist(df["score"].dropna(), bins=20, color="steelblue", edgecolor="white")
        ax.set_xlabel("Review score")
        ax.set_ylabel("Count")
        ax.set_title("Distribution of review scores")
        fig.tight_layout()
        fig.savefig(fig_dir / "01_score_distribution.png", bbox_inches="tight")
        plt.close(fig)

    # 2) Mean score by country (top 15 by volume)
    if "score" in df.columns and "country" in df.columns:
        g = (
            df.groupby("country")["score"]
            .agg(["count", "mean"])
            .sort_values("count", ascending=False)
            .head(15)
        )
        fig, ax = plt.subplots(figsize=(9, 5))
        g["mean"].sort_values().plot(kind="barh", ax=ax, color="teal")
        ax.set_xlabel("Mean score")
        ax.set_title("Mean review score (top 15 countries by review count)")
        fig.tight_layout()
        fig.savefig(fig_dir / "02_mean_score_top_countries.png", bbox_inches="tight")
        plt.close(fig)

    # 3) Mean score by traveler type
    if "score" in df.columns and "traveler_type" in df.columns:
        g = df.groupby("traveler_type")["score"].mean().sort_values()
        fig, ax = plt.subplots(figsize=(8, max(4, len(g) * 0.35)))
        g.plot(kind="barh", ax=ax, color="coral")
        ax.set_xlabel("Mean score")
        ax.set_title("Mean review score by traveler type")
        fig.tight_layout()
        fig.savefig(fig_dir / "03_mean_score_by_traveler_type.png", bbox_inches="tight")
        plt.close(fig)

    # 4) Mean score by room type (top 12 by volume)
    if "score" in df.columns and "room_type" in df.columns:
        g = (
            df.groupby("room_type")["score"]
            .agg(["count", "mean"])
            .sort_values("count", ascending=False)
            .head(12)
        )
        fig, ax = plt.subplots(figsize=(9, 6))
        g["mean"].sort_values().plot(kind="barh", ax=ax, color="slateblue")
        ax.set_xlabel("Mean score")
        ax.set_title("Mean review score (top 12 room types by count)")
        fig.tight_layout()
        fig.savefig(fig_dir / "04_mean_score_top_room_types.png", bbox_inches="tight")
        plt.close(fig)

    # 5–6) Time series
    if "date" in df.columns and "score" in df.columns:
        m = df.dropna(subset=["date"]).copy()
        m["year_month"] = m["date"].dt.to_period("M")
        cnt = m.groupby("year_month").size()
        fig, ax = plt.subplots()
        cnt.plot(kind="bar", ax=ax, color="steelblue", edgecolor="white")
        ax.set_xlabel("Month")
        ax.set_ylabel("Number of reviews")
        ax.set_title("Reviews per month")
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
        fig.tight_layout()
        fig.savefig(fig_dir / "05_reviews_per_month.png", bbox_inches="tight")
        plt.close(fig)

        mean_m = m.groupby("year_month")["score"].mean()
        fig, ax = plt.subplots()
        mean_m.plot(ax=ax, marker="o", color="darkgreen")
        ax.set_xlabel("Month")
        ax.set_ylabel("Mean score")
        ax.set_title("Mean review score by month")
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
        fig.tight_layout()
        fig.savefig(fig_dir / "06_mean_score_by_month.png", bbox_inches="tight")
        plt.close(fig)

    # 7) Text length (words)
    has_pos = "pos_review" in df.columns
    has_neg = "neg_review" in df.columns
    if has_pos or has_neg:
        if has_pos and has_neg:
            fig, axes = plt.subplots(1, 2, figsize=(10, 4))
            ax_list = [axes[0], axes[1]]
        else:
            fig, ax = plt.subplots(figsize=(5.5, 4))
            ax_list = [ax]
        idx = 0
        if has_pos:
            w = _word_count(df["pos_review"])
            hi = w.quantile(0.99) if len(w) else 0
            ax_list[idx].hist(w.clip(upper=hi), bins=30, color="steelblue", edgecolor="white")
            ax_list[idx].set_xlabel("Word count (positive, capped at 99th pct for display)")
            ax_list[idx].set_title("Positive review length")
            idx += 1
        if has_neg:
            w = _word_count(df["neg_review"])
            hi = w.quantile(0.99) if len(w) else 0
            ax_list[idx].hist(w.clip(upper=hi), bins=30, color="coral", edgecolor="white")
            ax_list[idx].set_xlabel("Word count (negative, capped at 99th pct for display)")
            ax_list[idx].set_title("Negative review length")
        fig.suptitle("Review text length (words)")
        fig.tight_layout()
        fig.savefig(fig_dir / "07_text_length_words_histograms.png", bbox_inches="tight")
        plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description="Step 1: EDA tables and figures")
    p.add_argument(
        "--in",
        dest="in_path",
        default="reviews_cleaned.csv",
        help="Cleaned CSV (from clean_reviews.py)",
    )
    p.add_argument(
        "--out-dir",
        default="outputs/eda",
        help="Base folder for tables/ and figures/ subfolders",
    )
    args = p.parse_args()

    in_path = Path(args.in_path)
    if not in_path.is_file():
        raise SystemExit(f"Input not found: {in_path}")

    base = Path(args.out_dir)
    tables_dir = base / "tables"
    fig_dir = base / "figures"

    df = load_reviews(in_path)
    write_tables(df, tables_dir)
    plot_figures(df, fig_dir)

    print(f"Loaded {len(df)} rows from {in_path}")
    print(f"Tables:  {tables_dir}/")
    print(f"Figures: {fig_dir}/")


if __name__ == "__main__":
    main()
