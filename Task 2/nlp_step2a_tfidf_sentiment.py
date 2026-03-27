# -*- coding: utf-8 -*-
"""
(a) Sentiment-style classification from review text using TF–IDF + logistic regression.

Labels are derived from the numeric score (weak supervision), not manual sentiment:
  - score <= neg_threshold  -> negative
  - score >= pos_threshold  -> positive
  - between                 -> neutral

Outputs under outputs/nlp_sentiment/ (tables + figures).

Usage:
  python nlp_step2a_tfidf_sentiment.py
  python nlp_step2a_tfidf_sentiment.py --in reviews_cleaned.csv --out-dir outputs/nlp_sentiment
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from review_io import combined_review_text, load_reviews


def score_to_label(
    score: float,
    neg_threshold: float,
    pos_threshold: float,
) -> str | None:
    if pd.isna(score):
        return None
    if score <= neg_threshold:
        return "negative"
    if score >= pos_threshold:
        return "positive"
    return "neutral"


def main() -> None:
    p = argparse.ArgumentParser(description="TF-IDF + logistic sentiment (score-derived labels)")
    p.add_argument("--in", dest="in_path", default="reviews_cleaned.csv", help="Cleaned CSV")
    p.add_argument("--out-dir", default="outputs/nlp_sentiment", help="Output base directory")
    p.add_argument("--pos-threshold", type=float, default=8.0, help="Score >= this -> positive")
    p.add_argument("--neg-threshold", type=float, default=6.0, help="Score <= this -> negative")
    p.add_argument("--test-size", type=float, default=0.2, help="Holdout fraction")
    p.add_argument("--random-state", type=int, default=42)
    p.add_argument("--max-features", type=int, default=8000)
    p.add_argument("--min-df", type=int, default=2)
    p.add_argument("--ngram-max", type=int, default=2, help="Max n-gram (1=unigrams only)")
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
    if "score" not in df.columns:
        raise SystemExit("Column 'score' is required for score-derived labels.")
    text = combined_review_text(df)
    labels = df["score"].apply(
        lambda s: score_to_label(s, args.neg_threshold, args.pos_threshold)
    )
    mask = (text.str.len() > 0) & labels.notna()
    X = text[mask].reset_index(drop=True)
    y = labels[mask].reset_index(drop=True)

    if len(X) < 50:
        raise SystemExit("Not enough rows with text and valid labels after filtering.")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=y,
    )

    pipe = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=args.max_features,
                    min_df=args.min_df,
                    ngram_range=(1, max(1, args.ngram_max)),
                    stop_words="english",
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=args.random_state,
                ),
            ),
        ]
    )
    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)

    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    pd.DataFrame(report).T.to_csv(tables / "01_classification_report.csv")
    with open(tables / "02_classification_report.txt", "w", encoding="utf-8") as f:
        f.write(
            classification_report(y_test, y_pred, zero_division=0),
        )

    cm = confusion_matrix(y_test, y_pred, labels=sorted(y.unique()))
    labels_order = sorted(y.unique())
    pd.DataFrame(cm, index=[f"true_{c}" for c in labels_order], columns=[f"pred_{c}" for c in labels_order]).to_csv(
        tables / "03_confusion_matrix.csv"
    )

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels_order)))
    ax.set_yticks(range(len(labels_order)))
    ax.set_xticklabels(labels_order, rotation=45, ha="right")
    ax.set_yticklabels(labels_order)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True (score-derived)")
    ax.set_title("Confusion matrix — TF-IDF + logistic regression")
    plt.colorbar(im, ax=ax, fraction=0.046)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", color="black", fontsize=9)
    fig.tight_layout()
    fig.savefig(figures / "01_confusion_matrix.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # Top TF-IDF coefficients per class (one-vs-rest for multinomial)
    clf: LogisticRegression = pipe.named_steps["clf"]
    vec: TfidfVectorizer = pipe.named_steps["tfidf"]
    feat_names = np.array(vec.get_feature_names_out())
    for i, cname in enumerate(clf.classes_):
        coef = clf.coef_[i]
        top = np.argsort(coef)[-25:][::-1]
        pd.DataFrame({"term": feat_names[top], "weight": coef[top]}).to_csv(
            tables / f"04_top_terms_{cname}.csv",
            index=False,
        )

    meta = pd.DataFrame(
        [
            ["n_samples_total", len(X)],
            ["n_train", len(X_train)],
            ["n_test", len(X_test)],
            ["pos_threshold", args.pos_threshold],
            ["neg_threshold", args.neg_threshold],
            ["labels", ", ".join(sorted(y.unique()))],
        ],
        columns=["key", "value"],
    )
    meta.to_csv(tables / "00_run_metadata.csv", index=False)

    print(f"Wrote tables to {tables}/ and figures to {figures}/")
    print(classification_report(y_test, y_pred, zero_division=0))


if __name__ == "__main__":
    main()
