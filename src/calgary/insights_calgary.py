"""
insights_calgary.py
===================
Writes docs/calgary/calgary_insights.md: a fact sheet of what the REAL data
says, computed from the SQL outputs. These are starting points for your own
analysis - open the Power BI report, check each one, and write the "why" in
your own words (see the prompts at the end of each section).

Run:  python src/calgary/insights_calgary.py
"""
from datetime import datetime

import pandas as pd

import config_calgary as CC


def read(name):
    p = CC.SQL_OUT_DIR / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def pct(x, digits=1):
    return "n/a" if pd.isna(x) else f"{x * 100:.{digits}f}%"


def table(df, cols, fmt=None):
    fmt = fmt or {}
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df[cols].itertuples(index=False):
        out.append("| " + " | ".join(fmt.get(c, str)(v) for c, v in zip(cols, r)) + " |")
    return out


def main():
    ov, top, slow = read("c01_overview_by_year"), read("c03_top_services"), read("c04_slowest_services")
    bench, chan, dow = read("c05_benchmark_by_category_year"), read("c06_channel_mix"), read("c08_day_of_week")
    seas, back, grow = read("c09_seasonality_by_category"), read("c10_backlog_trend"), read("c12_fastest_growing_services")
    stale, dq = read("c11_stale_backlog_by_agency"), read("c14_dq_flags")

    L = ["# Calgary 311 – Insights Fact Sheet (real data)", "",
         f"_Generated {datetime.now():%Y-%m-%d} from `data/calgary/sql_output/`. Window {CC.START_DATE} – {CC.SNAPSHOT_DATE}._", "",
         "> These numbers are computed automatically. Your job as the analyst: confirm each one in Power BI, "
         "dig into the *why*, and write the final story in your own words.", ""]

    if len(ov):
        tot = ov.requests.sum()
        L += ["## 1. Scale", "", f"**{tot:,}** service requests in the window.", ""]
        L += table(ov, ["Year", "requests", "closed_requests", "same_day_closure_rate", "avg_resolution_days", "within_benchmark_rate"],
                   {"requests": "{:,}".format, "closed_requests": "{:,}".format,
                    "same_day_closure_rate": pct, "within_benchmark_rate": pct})
        L += ["", "_2026 covers January–September only. 2024 is the benchmark year, so its within-benchmark rate is ~80% by definition._", ""]

    if len(top):
        L += ["## 2. What people ask for", ""]
        L += table(top, ["rank_no", "ServiceName", "requests", "share_of_total", "cumulative_share", "yoy_jan_sep"],
                   {"requests": "{:,}".format, "share_of_total": pct, "cumulative_share": pct, "yoy_jan_sep": pct})
        top15 = top.cumulative_share.iloc[-1]
        L += ["", f"The top {len(top)} service types account for **{pct(top15)}** of all requests.",
              "", "_Prompt: which of these are seasonal (waste, snow, parks) and which are steady (bylaw, roads)?_", ""]

    if len(grow):
        L += ["## 3. Fastest-growing services (Jan–Sep 2026 vs Jan–Sep 2025)", ""]
        L += table(grow.head(10), ["ServiceName", "v2025", "v2026", "growth_pct"],
                   {"v2025": "{:,}".format, "v2026": "{:,}".format, "growth_pct": pct})
        L += ["", "_Prompt: is the growth real demand, a new reporting channel, or a re-categorisation of an old service type? "
              "Check the monthly trend for a step change._", ""]

    if len(slow):
        L += ["## 4. Slowest services (median days to close, ≥ 500 closed)", ""]
        L += table(slow.head(10), ["ServiceName", "closed_requests", "median_days", "p90_days"], {"closed_requests": "{:,}".format})
        L += [""]

    if len(bench):
        L += ["## 5. Getting faster or slower? (share closed within the 2024 benchmark)", ""]
        L += table(bench, ["ServiceCategory", "y2024", "y2025", "y2026", "change_pts_2026_vs_2025"],
                   {c: pct for c in ["y2024", "y2025", "y2026", "change_pts_2026_vs_2025"]})
        worst = bench.sort_values("change_pts_2026_vs_2025").iloc[0]
        best = bench.sort_values("change_pts_2026_vs_2025").iloc[-1]
        L += ["", f"Biggest decline: **{worst.ServiceCategory}** ({pct(worst.change_pts_2026_vs_2025)} pts). "
              f"Biggest improvement: **{best.ServiceCategory}** ({pct(best.change_pts_2026_vs_2025)} pts).",
              "", "_Prompt: use the decomposition tree on the decline – is it one service, one agency, or one season?_", ""]

    if len(chan):
        dig = chan[chan.ChannelGroup == "Digital"].groupby("Year").share_of_year.sum()
        L += ["## 6. Channel shift", "", "Digital share (app/web/email) of requests by year: " +
              ", ".join(f"{y}: {pct(v)}" for y, v in dig.items()), ""]

    if len(dow):
        L += ["## 7. Day of week", ""]
        L += table(dow, ["DayOfWeek", "requests", "share", "same_day_closure_rate"],
                   {"requests": "{:,}".format, "share": pct, "same_day_closure_rate": pct})
        L += [""]

    if len(seas):
        peaks = seas.loc[seas.groupby("ServiceCategory").seasonality_index.idxmax(), ["ServiceCategory", "MonthNumber", "seasonality_index"]]
        L += ["## 8. Seasonality – peak month per category (2024–2025 average)", ""]
        L += table(peaks, ["ServiceCategory", "MonthNumber", "seasonality_index"], {"seasonality_index": lambda v: f"{v:.2f}×"})
        L += [""]

    if len(back):
        first, last = back.iloc[0], back.iloc[-1]
        L += ["## 9. Backlog", "",
              f"Open requests at month end: **{int(first.open_requests):,}** ({int(first.SnapshotDateKey)}) → "
              f"**{int(last.open_requests):,}** ({int(last.SnapshotDateKey)}). "
              f"Share older than 90 days at the latest snapshot: **{pct(last.share_over_90_days)}**.", ""]
    if len(stale):
        L += table(stale.head(8), ["Agency", "open_requests", "stale_over_365_days", "stale_share"],
                   {"open_requests": "{:,}".format, "stale_over_365_days": "{:,}".format, "stale_share": pct})
        L += ["", "_Prompt: are year-old open tickets real work, or tickets nobody closed in the system? "
              "That is a data-governance finding, not just an operations one._", ""]

    if len(dq):
        L += ["## 10. Data-quality flags in the model", ""]
        L += table(dq, ["flag", "rows_flagged"], {"rows_flagged": lambda v: f"{int(v):,}" if pd.notna(v) else "0"})
        L += [""]

    (CC.DOCS_DIR / "calgary_insights.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"   wrote {CC.DOCS_DIR / 'calgary_insights.md'}")


if __name__ == "__main__":
    main()
