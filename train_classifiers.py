"""
Module 6 classifier training — beat vs not_beat (binary).
'meet' (5.4%) is folded into 'not_beat' since it's too rare to model separately.

Model A (core)  : trailing_4q_beat_rate + pre_earnings_30d_momentum  (full 1330 rows)
Model B (rich)  : + net_analyst_rating_change_90d + sector_momentum   (924 non-NaN rows)

WARNING printed below about random split.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

INPUT_CSV    = "earnings_history.csv"
FEATURES_A   = ["trailing_4q_beat_rate", "pre_earnings_30d_momentum"]
FEATURES_B   = ["trailing_4q_beat_rate", "pre_earnings_30d_momentum",
                 "net_analyst_rating_change_90d", "sector_momentum"]
RANDOM_STATE = 42
TEST_SIZE    = 0.20
N_CAL_BINS   = 4


def prep(df: pd.DataFrame, features: list[str]) -> tuple:
    sub = df.dropna(subset=features).copy()
    y   = (sub["beat_miss_meet"] == "beat").astype(int)
    X   = sub[features]
    return X, y, len(sub)


def evaluate(X, y, n_rows, features, label) -> dict:
    beat_rate     = y.mean()
    baseline_acc  = max(beat_rate, 1 - beat_rate)
    majority_name = "beat" if beat_rate >= 0.5 else "not_beat"

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )

    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)

    model  = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)
    model.fit(X_tr_s, y_tr)

    y_pred = model.predict(X_te_s)
    y_prob = model.predict_proba(X_te_s)[:, 1]

    acc = accuracy_score(y_te, y_pred)
    auc = roc_auc_score(y_te, y_prob)

    frac_pos, mean_pred = calibration_curve(y_te, y_prob, n_bins=N_CAL_BINS, strategy="quantile")

    return {
        "label":        label,
        "n_rows":       n_rows,
        "n_train":      len(X_tr),
        "n_test":       len(X_te),
        "beat_rate":    beat_rate,
        "baseline_acc": baseline_acc,
        "majority":     majority_name,
        "acc":          acc,
        "delta":        acc - baseline_acc,
        "auc":          auc,
        "cal_pred":     mean_pred,
        "cal_actual":   frac_pos,
        "features":     features,
        "coef":         list(zip(features, model.coef_[0])),
    }


def print_model(r: dict):
    w = 62
    print(f"\n{'='*w}")
    print(f"  {r['label']}")
    print(f"  Features : {r['features']}")
    print(f"  Rows     : {r['n_rows']}  (train {r['n_train']} / test {r['n_test']})")
    print(f"  Beat rate: {r['beat_rate']:.1%}  ->  baseline = always predict '{r['majority']}'")
    print(f"{'='*w}")
    print(f"  Naive baseline accuracy : {r['baseline_acc']:.3f}")
    print(f"  Test accuracy           : {r['acc']:.3f}  ({r['delta']:+.3f} vs baseline)")
    print(f"  Test AUC                : {r['auc']:.3f}")
    print(f"\n  Calibration ({N_CAL_BINS} equal-frequency bins on test set):")
    print(f"    {'Bin':>3}  {'Mean predicted prob':>20}  {'Actual beat rate':>17}  {'Diff':>7}")
    for i, (mp, fp) in enumerate(zip(r["cal_pred"], r["cal_actual"]), 1):
        print(f"    {i:>3}  {mp:>20.3f}  {fp:>17.3f}  {fp-mp:>+7.3f}")
    print(f"\n  Coefficients (on standardised features):")
    for feat, coef in r["coef"]:
        print(f"    {feat:<40} {coef:+.4f}")


def print_summary(ra: dict, rb: dict):
    w = 62
    print(f"\n{'='*w}")
    print(f"  SIDE-BY-SIDE SUMMARY")
    print(f"{'='*w}")
    rows = [
        ("Rows used",      f"{ra['n_rows']:>8d}",      f"{rb['n_rows']:>8d}"),
        ("Train / Test",   f"{ra['n_train']:>5d} / {ra['n_test']:<5d}",
                           f"{rb['n_train']:>5d} / {rb['n_test']:<5d}"),
        ("Beat rate",      f"{ra['beat_rate']:>8.1%}",  f"{rb['beat_rate']:>8.1%}"),
        ("Baseline acc",   f"{ra['baseline_acc']:>8.3f}",f"{rb['baseline_acc']:>8.3f}"),
        ("Test accuracy",  f"{ra['acc']:>8.3f}",        f"{rb['acc']:>8.3f}"),
        ("vs baseline",    f"{ra['delta']:>+8.3f}",     f"{rb['delta']:>+8.3f}"),
        ("Test AUC",       f"{ra['auc']:>8.3f}",        f"{rb['auc']:>8.3f}"),
    ]
    print(f"  {'Metric':<18}  {'Model A':>14}  {'Model B':>14}")
    print(f"  {'-'*50}")
    for label, va, vb in rows:
        print(f"  {label:<18}  {va:>14}  {vb:>14}")
    print()


def main():
    print("\n" + "!" * 62)
    print("  *** RANDOM SPLIT WARNING ***")
    print("  Train/test split is random (stratified, 80/20).")
    print("  Quarterly earnings data has a time dimension: rows from")
    print("  the same ticker appear in both train and test, and the")
    print("  model can implicitly learn per-ticker patterns rather")
    print("  than generalisable features. Metrics below will likely")
    print("  be OPTIMISTIC. Replace with a time-based split before")
    print("  drawing conclusions (e.g. train <= 2021, test >= 2022).")
    print("!" * 62)

    df = pd.read_csv(INPUT_CSV)

    Xa, ya, na = prep(df, FEATURES_A)
    Xb, yb, nb = prep(df, FEATURES_B)

    ra = evaluate(Xa, ya, na, FEATURES_A, "MODEL A  —  core (2 features, full dataset)")
    rb = evaluate(Xb, yb, nb, FEATURES_B, "MODEL B  —  rich (4 features, non-NaN subset)")

    print_model(ra)
    print_model(rb)
    print_summary(ra, rb)


if __name__ == "__main__":
    main()
