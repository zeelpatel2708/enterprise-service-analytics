"""
clean_calgary.py
================
Profiles, validates and cleans the REAL City of Calgary 311 extract, using the
same principles as Edition A (fix the unambiguous, quarantine the rest, log
everything) - but on data whose defects nobody planted.

Real-data judgement calls documented here (good interview material):

* A ticket ID that appears more than once is usually an UPDATED record, not an
  error: keep the most recently updated version.
* "Closed" with no closed_date: use updated_date as the closure date (the last
  time the ticket changed) and flag it as imputed - rather than losing the row.
* closed_date present but status still open: treated as RE-OPENED (open), flagged.
* Closures after the snapshot date count as still open at the snapshot, so the
  analysis window matches Edition A exactly.
* Missing community: kept, mapped to "Unknown" so citywide totals stay complete.

Run:  python src/calgary/clean_calgary.py
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

import config_calgary as CC

SNAPSHOT = pd.Timestamp(CC.SNAPSHOT_DATE)
START = pd.Timestamp(CC.START_DATE)

dq_log: list[dict] = []
quarantine: list[pd.DataFrame] = []


def log(check, rows, action, severity="Error"):
    dq_log.append({"Check": check, "RowsAffected": int(rows), "Action": action, "Severity": severity})


def to_quarantine(df, mask, reason):
    bad = df[mask].copy()
    log(reason, len(bad), "Quarantined")
    if len(bad):
        bad.insert(0, "QuarantineReason", reason)
        quarantine.append(bad.astype(str))
    return df[~mask].copy()


# ---------------------------------------------------------------------------
# Memory: 1.4 million rows of text would need several GB as plain Python strings.
# Text columns are therefore read as CATEGORIES (each distinct value stored once,
# rows hold a small integer code), and every text operation below is applied to
# the few hundred distinct values instead of to 1.4 million rows. Same result,
# a fraction of the memory - an important habit for real-world data volumes.
# ---------------------------------------------------------------------------
def cat_apply(s: pd.Series, func, na_value=None) -> np.ndarray:
    """Apply func to each distinct value of a categorical; return per-row results."""
    mapped = np.array([func(c) for c in s.cat.categories] + [na_value], dtype=object)
    codes = s.cat.codes.to_numpy()          # -1 = missing -> picks the na_value slot
    return mapped[codes]


def cat_map(s: pd.Series, func, na_value=None) -> pd.Series:
    return pd.Series(pd.Categorical(cat_apply(s, func, na_value)), index=s.index)


def parse_ts(s: pd.Series) -> pd.Series:
    """Socrata floating timestamps look like 2026-10-20T00:00:00.000 (parsed once per distinct value)."""
    cats = pd.Series(s.cat.categories.astype(str))
    parsed = pd.to_datetime(cats.str.slice(0, 19), format="%Y-%m-%dT%H:%M:%S", errors="coerce")
    values = np.append(parsed.to_numpy(dtype="datetime64[ns]"), np.datetime64("NaT", "ns"))
    return pd.Series(values[s.cat.codes.to_numpy()], index=s.index)


def classify_status(v: str) -> str:
    v = v.lower()
    if "clos" in v or "complet" in v or "resolved" in v:
        return "Closed"
    return "Open"


def main():
    CC.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    CC.QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    CC.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    if not CC.RAW_FILE.exists():
        raise SystemExit(f"{CC.RAW_FILE} not found. Run: python src/calgary/download_calgary_311.py")

    text_cols = [c for c in CC.COLUMNS if c not in ("service_request_id", "latitude", "longitude")]
    dtypes = {c: "category" for c in text_cols}
    dtypes.update({"service_request_id": str, "latitude": str, "longitude": str})
    df = pd.read_csv(CC.RAW_FILE, dtype=dtypes, keep_default_na=False, na_values=[""])
    raw_rows = len(df)
    # numbers: convert once and drop the text copies straight away (saves memory)
    lat_raw, lon_raw = df.pop("latitude"), df.pop("longitude")
    df["Latitude"] = pd.to_numeric(lat_raw, errors="coerce")
    df["Longitude"] = pd.to_numeric(lon_raw, errors="coerce")
    bad_number = (lat_raw.notna() & df.Latitude.isna()) | (lon_raw.notna() & df.Longitude.isna())
    del lat_raw, lon_raw
    for c in text_cols:  # trim whitespace; blank -> missing
        df[c] = cat_map(df[c], lambda v: v.strip() or None)

    # ---- profile (before any change) -------------------------------------------
    profile = pd.DataFrame({
        "Column": df.columns,
        "NonNull": df.notna().sum().values,
        "NullPct": (df.isna().mean() * 100).round(2).values,
        "Distinct": df.nunique().values,
        "Example": [df[c].dropna().iloc[0] if df[c].notna().any() else "" for c in df.columns],
    })
    profile.to_csv(CC.PROCESSED_DIR / "raw_profile.csv", index=False)

    # ---- duplicates ---------------------------------------------------------------
    n = len(df)
    df = df.drop_duplicates()
    log("Exact duplicate rows", n - len(df), "Removed (kept first)", "Warning")
    df = to_quarantine(df, df.service_request_id.isna(), "Missing service_request_id")
    df["_upd"] = parse_ts(df.updated_date)
    df = df.sort_values(["service_request_id", "_upd"])
    dup = df.service_request_id.duplicated(keep="last")
    log("Same ticket ID more than once (record updated)", dup.sum(), "Kept most recently updated version", "Warning")
    df = df[~dup]

    # ---- dates ----------------------------------------------------------------------
    df["RequestedDate"] = parse_ts(df.requested_date).dt.normalize()
    df["UpdatedDate"] = df._upd.dt.normalize()
    df["ClosedDate"] = parse_ts(df.closed_date).dt.normalize()
    bad_closed_text = df.closed_date.notna() & df.ClosedDate.isna()
    df = to_quarantine(df, df.RequestedDate.isna(), "Invalid or missing requested_date")
    df = to_quarantine(df, bad_closed_text.reindex(df.index, fill_value=False), "Unparseable closed_date")

    out_window = (df.RequestedDate < START) | (df.RequestedDate > SNAPSHOT)
    log("Requested outside analysis window (filtered, not an error)", out_window.sum(), "Excluded", "Info")
    df = df[~out_window]

    df = to_quarantine(df, df.ClosedDate.notna() & (df.ClosedDate < df.RequestedDate), "closed_date before requested_date")

    # ---- status -----------------------------------------------------------------------
    df["StatusGroup"] = cat_map(df.status_description, classify_status, na_value="Unknown").astype(str)
    df["IsDuplicateRequest"] = cat_apply(df.status_description, lambda v: "duplicate" in v.lower(), False).astype(int)
    log("Requests closed as duplicates of another ticket", df.IsDuplicateRequest.sum(),
        "Kept, flagged (excluded from service-level KPIs)", "Info")

    closed_no_date = (df.StatusGroup == "Closed") & df.ClosedDate.isna()
    can_impute = closed_no_date & df.UpdatedDate.notna() & (df.UpdatedDate >= df.RequestedDate)
    df["ClosedDateImputed"] = can_impute.astype(int)
    df.loc[can_impute, "ClosedDate"] = df.loc[can_impute, "UpdatedDate"]
    log("Closed without closed_date - imputed from updated_date", can_impute.sum(), "Fixed (flagged as imputed)", "Warning")
    df = to_quarantine(df, closed_no_date & ~can_impute, "Closed without any usable closure date")

    reopened = (df.StatusGroup == "Open") & df.ClosedDate.notna()
    df["ReopenedFlag"] = reopened.astype(int)
    df.loc[reopened, "ClosedDate"] = pd.NaT
    log("closed_date present but status open (re-opened)", reopened.sum(), "Treated as open, flagged", "Warning")

    unknown_status = df.StatusGroup == "Unknown"
    df.loc[unknown_status & df.ClosedDate.notna(), "StatusGroup"] = "Closed"
    df.loc[unknown_status & df.ClosedDate.isna(), "StatusGroup"] = "Open"
    log("Missing status - derived from closed_date", unknown_status.sum(), "Fixed", "Warning")

    # As-of snapshot: closures after the snapshot are open at the snapshot
    after = df.ClosedDate > SNAPSHOT
    log("Closed after snapshot date - counted as open at snapshot", after.sum(), "Adjusted to snapshot", "Info")
    df.loc[after, "ClosedDate"] = pd.NaT
    df["IsClosed"] = df.ClosedDate.notna().astype(int)
    df["IsOpen"] = 1 - df.IsClosed

    # ---- reference attributes ---------------------------------------------------------
    df = to_quarantine(df, df.service_name.isna(), "Missing service_name")
    df["ServiceCategory"] = cat_map(df.service_name, lambda v: v.split(" - ")[0].strip())
    df["agency_responsible"] = cat_map(df.agency_responsible, lambda v: v, na_value="Unknown")
    df["source"] = cat_map(df.source, lambda v: v.title(), na_value="Unknown")

    miss_comm = df.comm_code.isna() & df.comm_name.isna()
    log("Missing community", miss_comm.sum(), "Kept, mapped to 'Unknown'", "Warning")
    df["comm_code"] = cat_map(df.comm_code, lambda v: v, na_value="UNK")
    df["comm_name"] = cat_map(df.comm_name, lambda v: v.upper(), na_value="UNKNOWN")

    lat, lon = df.Latitude, df.Longitude
    bad_xy = lat.notna() & ~(lat.between(*CC.LAT_RANGE) & lon.between(*CC.LON_RANGE))
    log("Coordinates outside Calgary or not numeric", int(bad_xy.sum()) + int(bad_number.reindex(df.index).sum()),
        "Coordinates set to null", "Warning")
    df["Latitude"] = lat.where(~bad_xy)
    df["Longitude"] = lon.where(~bad_xy)
    df = df.drop(columns=["requested_date", "updated_date", "closed_date", "_upd"])

    # ---- derived measures ---------------------------------------------------------------
    df["ResolutionDays"] = (df.ClosedDate - df.RequestedDate).dt.days
    df["SameDayClosure"] = np.where(df.IsClosed == 1, (df.ResolutionDays == 0).astype(int), np.nan)
    df["OpenAgeDays"] = np.where(df.IsOpen == 1, (SNAPSHOT - df.RequestedDate).dt.days, np.nan)
    df["IsStaleOpen"] = (df.OpenAgeDays > CC.LONG_OPEN_DAYS).astype(int)
    log(f"Open longer than {CC.LONG_OPEN_DAYS} days at snapshot", df.IsStaleOpen.sum(),
        "Kept, flagged as stale backlog", "Info")

    df = add_benchmarks(df)

    keep = ["service_request_id", "RequestedDate", "UpdatedDate", "ClosedDate", "status_description",
            "StatusGroup", "IsClosed", "IsOpen", "IsDuplicateRequest", "ClosedDateImputed", "ReopenedFlag",
            "source", "ServiceCategory", "service_name", "agency_responsible", "comm_code", "comm_name",
            "location_type", "Latitude", "Longitude", "ResolutionDays", "SameDayClosure", "OpenAgeDays",
            "IsStaleOpen", "BenchmarkDays", "WithinBenchmark"]
    clean = df[keep].rename(columns={"service_request_id": "ServiceRequestID", "status_description": "StatusRaw",
                                     "source": "Channel", "service_name": "ServiceName",
                                     "agency_responsible": "Agency", "comm_code": "CommunityCode",
                                     "comm_name": "CommunityName", "location_type": "LocationType"})
    clean.sort_values("RequestedDate").to_csv(CC.PROCESSED_DIR / "clean_service_requests.csv", index=False)

    q = pd.concat(quarantine, ignore_index=True) if quarantine else pd.DataFrame(columns=["QuarantineReason"])
    q.to_csv(CC.QUARANTINE_DIR / "quarantine_records.csv", index=False)
    pd.DataFrame(dq_log).to_csv(CC.PROCESSED_DIR / "data_quality_log.csv", index=False)
    write_report(raw_rows, len(clean), len(q), profile)
    print(pd.DataFrame(dq_log).to_string(index=False))
    print(f"\nRaw {raw_rows:,} -> clean {len(clean):,} (quarantined {len(q):,})")


def add_benchmarks(df: pd.DataFrame) -> pd.DataFrame:
    """Derived service-level benchmark: P80 resolution days per service in the baseline year."""
    base = df[(df.IsClosed == 1) & (df.IsDuplicateRequest == 0) & (df.RequestedDate.dt.year == CC.BENCHMARK_YEAR)]
    g = base.groupby("service_name", observed=True).ResolutionDays
    by_svc = pd.DataFrame({"n": g.size(), "p": g.quantile(CC.BENCHMARK_PERCENTILE)})
    by_cat = base.groupby("ServiceCategory", observed=True).ResolutionDays.quantile(CC.BENCHMARK_PERCENTILE)
    overall = base.ResolutionDays.quantile(CC.BENCHMARK_PERCENTILE) if len(base) else 7
    svc_ok = by_svc[by_svc.n >= CC.MIN_BENCHMARK_VOLUME].p
    bench = pd.Series(cat_apply(df.service_name, lambda v: svc_ok.get(v, np.nan), np.nan), index=df.index, dtype=float)
    cat_bench = pd.Series(cat_apply(df.ServiceCategory, lambda v: by_cat.get(v, np.nan), np.nan), index=df.index, dtype=float)
    bench = bench.fillna(cat_bench).fillna(overall)
    df["BenchmarkDays"] = np.ceil(bench).astype(int)
    measurable = (df.IsClosed == 1) & (df.IsDuplicateRequest == 0)
    df["WithinBenchmark"] = np.where(measurable, (df.ResolutionDays <= df.BenchmarkDays).astype(int), np.nan)
    pd.DataFrame({"ServiceName": svc_ok.index, "BenchmarkDays": np.ceil(svc_ok.values)}).to_csv(
        CC.PROCESSED_DIR / "service_benchmarks.csv", index=False)
    return df


def write_report(raw_rows, clean_rows, q_rows, profile):
    lines = ["# Calgary 311 – Data Quality Report", "",
             f"_Generated by `src/calgary/clean_calgary.py` on {datetime.now():%Y-%m-%d %H:%M}. "
             f"Window: {CC.START_DATE} to {CC.SNAPSHOT_DATE}._", "",
             "These are **real** defects found in the City of Calgary open data – nothing was injected.", "",
             f"* Raw rows downloaded: **{raw_rows:,}**",
             f"* Clean rows in model: **{clean_rows:,}**",
             f"* Quarantined: **{q_rows:,}** (see `data/calgary/quarantine/quarantine_records.csv`)", "",
             "## Checks", "", "| Check | Rows | Severity | Action |", "|---|---:|---|---|"]
    lines += [f"| {r['Check']} | {r['RowsAffected']:,} | {r['Severity']} | {r['Action']} |" for r in dq_log]
    lines += ["", "## Raw column profile", "", "| Column | Non-null | Null % | Distinct | Example |", "|---|---:|---:|---:|---|"]
    lines += [f"| {r.Column} | {r.NonNull:,} | {r.NullPct} | {r.Distinct:,} | {str(r.Example)[:40]} |"
              for r in profile.itertuples()]
    (CC.DOCS_DIR / "data_quality_report_calgary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
