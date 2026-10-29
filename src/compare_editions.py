"""
compare_editions.py
===================
Puts the two editions side by side:

    Edition A - simulated enterprise field-service data (known answers)
    Edition B - real City of Calgary 311 service requests

The same metrics are computed the same way on both (resolution measured in
whole calendar days for both, because the real data only has dates), and
written to:

    data/comparison/*.csv           -> the "Simulated vs Real" Power BI page
    docs/simulated_vs_real.md       -> the written comparison

Why compare? It shows (1) the pipeline works on data you did not design,
(2) where the simulation is realistic and where it is not, and (3) what each
dataset can and cannot answer. That is a mature analyst conversation.

Run:  python src/compare_editions.py   (both editions must be built first)
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import config as A
from calgary import config_calgary as B

# overridable so the test-suite never overwrites your real outputs
OUT = Path(os.environ.get("COMPARISON_DIR", A.ROOT / "data" / "comparison"))
DOC = Path(os.environ.get("COMPARISON_DOC", A.DOCS_DIR / "simulated_vs_real.md"))
BUCKETS = [(-1, 0, "Same day"), (0, 2, "1–2 days"), (2, 7, "3–7 days"), (7, 30, "8–30 days"),
           (30, 90, "31–90 days"), (90, 100000, "Over 90 days")]


def load_a() -> pd.DataFrame:
    f = pd.read_csv(A.ROOT / "data" / "model" / "FactServiceRequests.csv",
                    usecols=["CreatedAt", "ClosedAt", "IsClosed", "IsCancelled"], parse_dates=["CreatedAt", "ClosedAt"])
    return pd.DataFrame({
        "Requested": f.CreatedAt.dt.normalize(),
        "Closed": f.ClosedAt.dt.normalize(),
        "IsClosed": f.IsClosed,
        "Excluded": f.IsCancelled,        # cancelled: not a real piece of work
    })


def load_b() -> pd.DataFrame:
    f = pd.read_csv(B.MODEL_DIR / "FactServiceRequests.csv",
                    usecols=["RequestedDateKey", "ClosedDateKey", "IsClosed", "IsDuplicateRequest"])
    to_dt = lambda s: pd.to_datetime(s.astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
    return pd.DataFrame({"Requested": to_dt(f.RequestedDateKey), "Closed": to_dt(f.ClosedDateKey),
                         "IsClosed": f.IsClosed, "Excluded": f.IsDuplicateRequest})


def metrics(df: pd.DataFrame, edition: str):
    full = df[df.Requested.dt.year.isin([2024, 2025])]
    by_m = full.groupby([full.Requested.dt.year, full.Requested.dt.month]).size().groupby(level=1).mean()
    season = pd.DataFrame({"Edition": edition, "MonthNumber": by_m.index, "SeasonalityIndex": (by_m / by_m.mean()).round(3).values})

    dow = df.Requested.dt.dayofweek.value_counts(normalize=True).sort_index()
    dow = pd.DataFrame({"Edition": edition, "DayOfWeekNumber": dow.index + 1,
                        "DayOfWeek": pd.to_datetime(dow.index + 1, unit="D", origin="2024-01-07").day_name(),
                        "ShareOfRequests": dow.round(4).values})

    c = df[(df.IsClosed == 1) & (df.Excluded == 0)]
    days = (c.Closed - c.Requested).dt.days
    dist = []
    for lo, hi, label in BUCKETS:
        dist.append({"Edition": edition, "Bucket": label, "BucketOrder": len(dist) + 1,
                     "ShareOfClosed": round(((days > lo) & (days <= hi)).mean(), 4)})

    # month-end backlog vs monthly intake
    ratios = []
    for me in pd.date_range("2024-01-31", B.SNAPSHOT_DATE, freq="ME"):
        open_n = ((df.Requested <= me) & (df.Closed.isna() | (df.Closed > me)) & (df.Excluded == 0)).sum()
        intake = ((df.Requested.dt.to_period("M") == me.to_period("M"))).sum()
        ratios.append(open_n / intake if intake else np.nan)

    y = df.Requested.dt.year.value_counts()
    summary = {
        "Requests in window": len(df),
        "Average requests per month": round(len(df) / df.Requested.dt.to_period("M").nunique()),
        "YoY volume growth 2025 vs 2024": round(y.get(2025, np.nan) / y.get(2024, np.nan) - 1, 4),
        "Weekend share of requests": round(df.Requested.dt.dayofweek.ge(5).mean(), 4),
        "Peak-month seasonality index": round(season.SeasonalityIndex.max(), 3),
        "Trough-month seasonality index": round(season.SeasonalityIndex.min(), 3),
        "Median resolution (days)": float(days.median()),
        "P90 resolution (days)": float(days.quantile(0.9)),
        "Closed same day": round((days == 0).mean(), 4),
        "Closed within 7 days": round((days <= 7).mean(), 4),
        "Avg month-end backlog ÷ monthly intake": round(float(np.nanmean(ratios)), 3),
        "Share excluded (cancelled / duplicate)": round(df.Excluded.mean(), 4),
    }
    return summary, season, dow, pd.DataFrame(dist)


def dq_rates():
    rows = []
    a_raw = len(pd.read_csv(A.RAW_DIR / "fsm_service_requests.csv", usecols=[0]))
    for r in pd.read_csv(A.PROCESSED_DIR / "data_quality_log.csv").itertuples():
        if r.Source == "fsm_service_requests.csv" and r.RowsAffected > 0:
            rows.append({"Edition": "Simulated", "Check": r.Check, "RowsAffected": r.RowsAffected,
                         "PctOfRaw": round(r.RowsAffected / a_raw, 5), "Origin": "Injected on purpose"})
    b_raw = len(pd.read_csv(B.RAW_FILE, usecols=[0]))
    for r in pd.read_csv(B.PROCESSED_DIR / "data_quality_log.csv").itertuples():
        if r.RowsAffected > 0 and r.Severity != "Info":
            rows.append({"Edition": "Real (Calgary)", "Check": r.Check, "RowsAffected": r.RowsAffected,
                         "PctOfRaw": round(r.RowsAffected / b_raw, 5), "Origin": "Found in the wild"})
    return pd.DataFrame(rows)


CAPABILITIES = [
    ("Request volume, trend, seasonality", "Yes", "Yes"),
    ("Resolution time", "Yes (hours)", "Yes (days only)"),
    ("Backlog / open requests", "Yes", "Yes"),
    ("Contracted SLA compliance", "Yes (SLA by priority)", "No – benchmark derived from 2024"),
    ("Geography", "6 regions", "~300 communities with coordinates"),
    ("Request channel (phone / app / web)", "No", "Yes"),
    ("Revenue, cost, margin", "Yes", "No"),
    ("Technician / workforce productivity", "Yes", "No"),
    ("Customer satisfaction", "Yes (survey)", "No"),
    ("Repeat visits / first-time fix", "Yes (asset-level)", "No (no asset ID)"),
    ("Targets / budget", "Yes", "No"),
    ("Known 'right answers' to test the analysis", "Yes – planted stories", "No – genuine discovery"),
    ("Real-world noise and messiness", "Partial – designed", "Yes"),
]


def main():
    if not (B.MODEL_DIR / "FactServiceRequests.csv").exists():
        print("Edition B (Calgary) not built yet - skipping comparison.")
        return
    if not (A.ROOT / "data" / "model" / "FactServiceRequests.csv").exists():
        print("Edition A not built yet - run `python run_pipeline.py` first. Skipping comparison.")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    sa, sea_a, dow_a, dist_a = metrics(load_a(), "Simulated")
    sb, sea_b, dow_b, dist_b = metrics(load_b(), "Real (Calgary)")
    summary = pd.DataFrame({"Metric": list(sa), "Simulated": list(sa.values()), "Real (Calgary)": list(sb.values())})
    season, dow, dist = pd.concat([sea_a, sea_b]), pd.concat([dow_a, dow_b]), pd.concat([dist_a, dist_b])
    dq = dq_rates()
    caps = pd.DataFrame(CAPABILITIES, columns=["Question", "Simulated", "Real (Calgary)"])

    for name, df in {"comparison_summary": summary, "comparison_seasonality": season, "comparison_day_of_week": dow,
                     "comparison_resolution_distribution": dist, "comparison_data_quality": dq,
                     "comparison_capabilities": caps}.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
    write_doc(summary, season, dow, dist, dq, caps)
    print(summary.to_string(index=False))


def fmt(metric, v):
    if pd.isna(v):
        return "n/a"
    if any(k in metric for k in ("share", "Share", "growth", "Closed ")):
        return f"{v * 100:.1f}%"
    if isinstance(v, (int, np.integer)) or float(v).is_integer():
        return f"{int(v):,}"
    return f"{v:,.2f}"


def write_doc(summary, season, dow, dist, dq, caps):
    s = summary.set_index("Metric")
    a, b = s["Simulated"], s["Real (Calgary)"]
    L = ["# Simulated vs Real – Edition A compared with Edition B", "",
         f"_Generated by `src/compare_editions.py` on {datetime.now():%Y-%m-%d}. Both editions cover "
         f"{A.START_DATE} to {B.SNAPSHOT_DATE}. Resolution is measured in whole calendar days for both, "
         "because the Calgary data has no times._", "",
         "## Why two editions?", "",
         "* **Edition A (simulated):** a full business with revenue, technicians, CSAT and targets. The data problems and business "
         "stories were planted, so I can *prove* the pipeline and dashboard find the right answers.",
         "* **Edition B (real):** City of Calgary 311 service requests. Nobody planted anything – the defects and insights are genuine.",
         "* **Together:** the same pipeline, model and KPI definitions run on both. The comparison shows where the simulation "
         "is realistic, where it isn't, and what each dataset can and cannot answer.", "",
         "## Headline comparison", "", "| Metric | Simulated | Real (Calgary) |", "|---|---:|---:|"]
    L += [f"| {m} | {fmt(m, a[m])} | {fmt(m, b[m])} |" for m in s.index]

    L += ["", "## Resolution-time distribution (share of closed requests)", "", "| Bucket | Simulated | Real (Calgary) |", "|---|---:|---:|"]
    p = dist.pivot(index=["BucketOrder", "Bucket"], columns="Edition", values="ShareOfClosed").reset_index()
    L += [f"| {r.Bucket} | {r.Simulated * 100:.1f}% | {r['Real (Calgary)'] * 100:.1f}% |" for _, r in p.iterrows()]

    L += ["", "## Seasonality index by month (1.00 = average month)", "", "| Month | Simulated | Real (Calgary) |", "|---|---:|---:|"]
    p = season.pivot(index="MonthNumber", columns="Edition", values="SeasonalityIndex")
    L += [f"| {pd.Timestamp(2024, m, 1):%b} | {r.Simulated:.2f} | {r['Real (Calgary)']:.2f} |" for m, r in p.iterrows()]
    corr = p.Simulated.corr(p["Real (Calgary)"])
    L += ["", f"Correlation of the two seasonal patterns: **{corr:.2f}**.", ""]

    L += ["## Day of week (share of requests)", "", "| Day | Simulated | Real (Calgary) |", "|---|---:|---:|"]
    p = dow.pivot(index=["DayOfWeekNumber", "DayOfWeek"], columns="Edition", values="ShareOfRequests").reset_index()
    L += [f"| {r.DayOfWeek} | {r.Simulated * 100:.1f}% | {r['Real (Calgary)'] * 100:.1f}% |" for _, r in p.iterrows()]

    L += ["", "## Data quality: designed vs found in the wild", "", "| Edition | Check | Rows | % of raw |", "|---|---|---:|---:|"]
    L += [f"| {r.Edition} | {r.Check} | {r.RowsAffected:,} | {r.PctOfRaw * 100:.2f}% |" for r in dq.itertuples()]

    L += ["", "## What each dataset can answer", "", "| Question | Simulated | Real (Calgary) |", "|---|---|---|"]
    L += [f"| {r.Question} | {r.Simulated} | {r._3} |" for r in caps.itertuples()]

    # automatic observations
    obs = []
    if b["Closed same day"] - a["Closed same day"] > 0.15:
        obs.append(f"Real requests are far more often closed the same day ({fmt('Closed same day', b['Closed same day'])} vs "
                   f"{fmt('Closed same day', a['Closed same day'])}). Many 311 requests are information requests or "
                   "routed tickets, not field visits – the simulation models only on-site work.")
    if b["P90 resolution (days)"] > 2 * a["P90 resolution (days)"]:
        obs.append(f"The real data has a much longer tail (P90 {b['P90 resolution (days)']:.0f} days vs "
                   f"{a['P90 resolution (days)']:.0f}). Real backlogs contain slow capital or seasonal work that a "
                   "contracted-SLA business would not tolerate.")
    if abs(b["Weekend share of requests"] - a["Weekend share of requests"]) > 0.05:
        obs.append(f"Weekend share differs ({fmt('Weekend share', a['Weekend share of requests'])} simulated vs "
                   f"{fmt('Weekend share', b['Weekend share of requests'])} real) – citizens report on weekends; businesses mostly don't.")
    obs.append(f"Seasonal patterns correlate at {corr:.2f}. Both peak around weather extremes, but the drivers differ "
               "(equipment failures vs snow, waste and parks).")
    obs.append("The real data needed different cleaning rules: repeated ticket IDs were *updates*, not errors, and closed "
               "tickets without a closed date could be rescued from the update date. Designed defects are cleaner than real ones.")
    L += ["", "## Observations", ""] + [f"* {o}" for o in obs]
    L += ["", "## Interview takeaway", "",
          "> \"I built and tested the pipeline on simulated data where I knew the right answers, then ran the same pipeline on "
          "real City of Calgary data. The comparison showed which of my assumptions held – seasonality and backlog behaviour – "
          "and which didn't, like same-day closures and the long tail of resolution times. It also showed which business "
          "questions real public data simply cannot answer, such as revenue or first-time fix.\"", ""]
    DOC.write_text("\n".join(L), encoding="utf-8")
    print(f"   wrote {DOC}")


if __name__ == "__main__":
    main()
