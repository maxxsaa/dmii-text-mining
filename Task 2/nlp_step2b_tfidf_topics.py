# -*- coding: utf-8 -*-
"""
(b) Topic discovery with TF–IDF + NMF (non-negative matrix factorization).

NMF factorizes the document–term matrix into W (document × topic) and H (topic × term);
each topic is interpreted from the largest entries in a row of H.

Outputs under outputs/nlp_topics/ (tables + figures).

Usage:
  python nlp_step2b_tfidf_topics.py
  python nlp_step2b_tfidf_topics.py --n-topics 10 --in reviews_cleaned.csv --out-dir outputs/nlp_topics
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

from review_io import combined_review_text, load_reviews


def main() -> None:
    p = argparse.ArgumentParser(description="TF-IDF + NMF topic modeling")
    p.add_argument("--in", dest="in_path", default="reviews_cleaned.csv", help="Cleaned CSV")
    p.add_argument("--out-dir", default="outputs/nlp_topics", help="Output base directory")
    p.add_argument("--n-topics", type=int, default=10, help="Number of NMF components")
    p.add_argument("--max-features", type=int, default=8000)
    p.add_argument("--min-df", type=int, default=2)
    p.add_argument("--ngram-max", type=int, default=2)
    p.add_argument("--top-words", type=int, default=15, help="Top terms per topic to save/plot")
    p.add_argument("--random-state", type=int, default=42)
    args = p.parse_args()

    in_path = Path(args.in_path)
    if not in_path.is_file():
        raise SystemExit(f"Input not found: {in_path}")

    base = Path(args.out_dir)
    tables = base / "tables"
    figures = base / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    df = load_reviews(in_path)
    text = combined_review_text(df)
    mask = text.str.len() > 0
    docs = text[mask].reset_index(drop=True)
    if len(docs) < args.n_topics * 5:
        raise SystemExit("Not enough documents for this number of topics.")

    vec = TfidfVectorizer(
        max_features=args.max_features,
        min_df=args.min_df,
        ngram_range=(1, max(1, args.ngram_max)),
        stop_words="english",
        sublinear_tf=True,
    )
    X = vec.fit_transform(docs)
    feat_names = np.array(vec.get_feature_names_out())

    nmf = NMF(
        n_components=args.n_topics,
        init="nndsvd",
        random_state=args.random_state,
        max_iter=600,
    )
    W = nmf.fit_transform(X)
    H = nmf.components_

    rows = []
    for k in range(args.n_topics):
        top_idx = np.argsort(H[k])[-args.top_words :][::-1]
        for rank, j in enumerate(top_idx, start=1):
            rows.append(
                {
                    "topic": k + 1,
                    "rank": rank,
                    "term": feat_names[j],
                    "weight": float(H[k, j]),
                }
            )
    pd.DataFrame(rows).to_csv(tables / "01_topic_top_words.csv", index=False)

    dominant = np.argmax(W, axis=1)
    strength = W.max(axis=1)
    doc_topics = pd.DataFrame(
        {
            "row_index": np.arange(len(docs)),
            "dominant_topic": dominant + 1,
            "topic_weight_max": strength,
        }
    )
    doc_topics.to_csv(tables / "02_document_dominant_topic.csv", index=False)

    vc = pd.Series(dominant + 1).value_counts().sort_index()
    counts = vc.reset_index()
    counts.columns = ["topic", "n_documents"]
    counts.to_csv(tables / "03_topic_size_by_dominant.csv", index=False)

    pd.DataFrame(
        [
            ["n_documents", len(docs)],
            ["n_topics", args.n_topics],
            ["reconstruction_error", float(nmf.reconstruction_err_)],
        ],
        columns=["metric", "value"],
    ).to_csv(tables / "00_run_metadata.csv", index=False)

    # Figure: top words per topic (horizontal bars, grid of subplots)
    n_cols = min(2, args.n_topics)
    n_rows = int(np.ceil(args.n_topics / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(7 * n_cols, 4.2 * n_rows))
    axes = np.atleast_1d(axes).ravel()
    n_show = min(12, args.top_words)
    for k in range(args.n_topics):
        ax = axes[k]
        top_idx = np.argsort(H[k])[-n_show:][::-1]
        words = feat_names[top_idx]
        vals = H[k][top_idx]
        ax.barh(np.arange(len(words)), vals, color="steelblue")
        ax.set_yticks(np.arange(len(words)))
        ax.set_yticklabels(words, fontsize=8)
        ax.invert_yaxis()
        ax.set_title(f"Topic {k + 1}")
        ax.set_xlabel("NMF weight")
    for j in range(args.n_topics, len(axes)):
        axes[j].set_visible(False)
    fig.suptitle("TF-IDF + NMF — top terms per topic", fontsize=12)
    fig.tight_layout()
    fig.savefig(figures / "01_topics_top_words.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # Topic prevalence (dominant assignment)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(counts["topic"], counts["n_documents"], color="teal", edgecolor="white")
    ax.set_xlabel("Topic (dominant)")
    ax.set_ylabel("Number of reviews")
    ax.set_title("Reviews per topic (by dominant topic)")
    fig.tight_layout()
    fig.savefig(figures / "02_topic_prevalence.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    print(f"Wrote tables to {tables}/ and figures to {figures}/")
    print(f"NMF reconstruction error: {nmf.reconstruction_err_:.4f}")


if __name__ == "__main__":
    main()
