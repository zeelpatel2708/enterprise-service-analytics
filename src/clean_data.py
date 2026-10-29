"""
clean_data.py
=============
Profiles, validates and cleans the raw source extracts.

Design principles (worth explaining in an interview):

* **Fix what is unambiguous, quarantine what is not.** A region spelled
  "Tor." is clearly Toronto, so it is standardised. A ticket closed *before*
  it was opened cannot be repaired without guessing, so it is quarantined.
* **Never silently drop rows.** Every removed row lands in data/quarantine/
  with a reason code, and the counts are written to docs/data_quality_report.md.
* **Keep financial totals whole.** A closed ticket with no technician still
  happened and still earned revenue, so it is kept and mapped to an
  "Unknown" technician instead of being dropped.
* **Reconcile across systems.** Billing and FSM are compared both ways
  (invoices without tickets, closed tickets without invoices).

Run:  python src/clean_data.py
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

import config as C

SNAPSHOT = pd.Timestamp(C.SNAPSHOT_DATE)
TS_FORMAT = "%Y-%m-%d %H:%M:%S"
REPEAT_WINDOW_DAYS = 30

quarantine: list[pd.DataFrame] = []
dq_log: list[dict] = []


def log(source: str, check: str, rows: int, action: str, severity: str = "Error"):
    dq_log.append({"Source": source, "Check": check, "RowsAffected": int(rows),
                   "Action": action, "Severity": severity})


def send_to_quarantine(df: pd.DataFrame, mask: pd.Series, source: str, reason: str, action="Quarantined"):
    bad = df[mask].copy()
    log(source, reason, len(bad), action)
    if len(bad):
        bad.insert(0, "QuarantineReason", reason)
        bad.insert(0, "SourceFile", source)
        quarantine.append(bad.astype(str))
    return df[~mask].copy()


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(C.RAW_DIR / name, dtype=str, keep_default_na=False, na_values=[""])


# ============================================================================
# Customers (CRM)
# ============================================================================
def clean_customers() -> pd.DataFrame:
    src = "crm_customers.csv"
    df = read(src)
    n0 = len(df)

    df["CustomerName"] = df.CustomerName.str.strip()
    upper = df.CustomerName.str.isupper()
    df.loc[upper, "CustomerName"] = df.loc[upper, "CustomerName"].str.title()
    log(src, "Customer name casing / whitespace standardised", upper.sum(), "Fixed", "Warning")

    prov = df.Province.str.strip().str.upper().replace({"ONTARIO": "ON", "ONT.": "ON"})
    log(src, "Province values standardised to 'ON'", (prov != df.Province).sum(), "Fixed", "Warning")
    df["Province"] = prov

    df = df.drop_duplicates()
    log(src, "Exact duplicate customer rows", n0 - len(df), "Removed (kept first)", "Warning")
    df = send_to_quarantine(df, df.CustomerID.duplicated(keep=False), src,
                            "Conflicting rows for the same CustomerID")
    df["AccountStartDate"] = pd.to_datetime(df.AccountStartDate).dt.date
    return df


# ============================================================================
# Technicians (HR)
# ============================================================================
def clean_technicians() -> pd.DataFrame:
    src = "hr_technicians.csv"
    df = read(src).drop_duplicates()
    df = send_to_quarantine(df, df.TechnicianID.duplicated(keep=False), src,
                            "Conflicting rows for the same TechnicianID")
    df["HireDate"] = pd.to_datetime(df.HireDate).dt.date
    df["TerminationDate"] = pd.to_datetime(df.TerminationDate).dt.date
    return df


# ============================================================================
# Service requests (FSM)
# ============================================================================
def clean_service_requests(customers: pd.DataFrame, techs: pd.DataFrame) -> pd.DataFrame:
    src = "fsm_service_requests.csv"
    df = read(src)
    n0 = len(df)

    # 1. exact duplicates (same extract row exported twice)
    df = df.drop_duplicates()
    log(src, "Exact duplicate rows", n0 - len(df), "Removed (kept first)")

    # 2. same ID but different content -> cannot decide which is right
    df = send_to_quarantine(df, df.ServiceRequestID.duplicated(keep=False), src,
                            "Conflicting rows for the same ServiceRequestID")

    # 3. region names
    alias = {a.strip().lower(): k for k, v in C.REGION_ALIASES.items() for a in v}
    alias.update({k.lower(): k for k in C.REGION_ALIASES})
    std = df.Region.str.strip().str.lower().map(alias)
    log(src, "Inconsistent region spelling standardised", (std != df.Region).sum() - std.isna().sum(), "Fixed", "Warning")
    df["Region"] = std
    df = send_to_quarantine(df, df.Region.isna(), src, "Unrecognised region")

    # 4. dates
    df["CreatedAt"] = pd.to_datetime(df.CreatedAt, format=TS_FORMAT, errors="coerce")
    df = send_to_quarantine(df, df.CreatedAt.isna(), src, "Invalid or missing CreatedAt")
    df["ClosedAt"] = pd.to_datetime(df.ClosedAt, format=TS_FORMAT, errors="coerce")
    closed_like = df.Status.isin(["Closed", "Cancelled"])
    df = send_to_quarantine(df, closed_like & df.ClosedAt.isna(), src, "Closed/cancelled without ClosedAt")
    df = send_to_quarantine(df, df.ClosedAt < df.CreatedAt, src, "ClosedAt before CreatedAt")
    df = send_to_quarantine(df, df.CreatedAt > SNAPSHOT, src, "CreatedAt after extract snapshot")

    # 5. referential integrity
    df = send_to_quarantine(df, df.CustomerID.isna(), src, "Missing CustomerID")
    df = send_to_quarantine(df, ~df.CustomerID.isin(customers.CustomerID), src, "CustomerID not found in CRM")
    df = send_to_quarantine(df, ~df.Status.isin(["Open", "In Progress", "Closed", "Cancelled"]), src, "Invalid Status")
    df = send_to_quarantine(df, ~df.Priority.isin([p[0] for p in C.PRIORITIES]), src, "Invalid Priority")
    df = send_to_quarantine(df, ~df.ServiceType.isin([s[1] for s in C.SERVICE_TYPES]), src, "Invalid ServiceType")

    # 6. technician: unassigned is legitimate for new 'Open' tickets, not for closed work
    missing_tech = df.TechnicianID.isna() & df.Status.isin(["Closed", "In Progress"])
    df["DQ_MissingTechnician"] = missing_tech.astype(int)
    log(src, "Closed/in-progress request missing TechnicianID", missing_tech.sum(),
        "Kept, mapped to 'Unknown' technician (revenue preserved)", "Warning")
    df.loc[missing_tech, "TechnicianID"] = "UNKNOWN"
    df.loc[df.TechnicianID.isna(), "TechnicianID"] = "UNASSIGNED"
    unknown_tech = ~df.TechnicianID.isin(set(techs.TechnicianID) | {"UNKNOWN", "UNASSIGNED"})
    df = send_to_quarantine(df, unknown_tech, src, "TechnicianID not found in HR")

    # 7. derived operational fields
    sla = pd.read_csv(C.RAW_DIR / "sla_policy.csv").set_index("Priority").SLAHours
    df["SLAHours"] = df.Priority.map(sla).astype(float)
    is_closed = df.Status.eq("Closed")
    hours = (df.ClosedAt - df.CreatedAt).dt.total_seconds() / 3600
    df["ResolutionHours"] = hours.where(is_closed).round(2)
    df["SLAMet"] = np.where(is_closed, (hours <= df.SLAHours).astype(int), np.nan)
    is_open = df.Status.isin(["Open", "In Progress"])
    age = (SNAPSHOT - df.CreatedAt).dt.total_seconds() / 3600
    df["OpenAgeHours"] = age.where(is_open).round(2)
    df["SLABreachedOpen"] = np.where(is_open, (age > df.SLAHours).astype(int), np.nan)
    df["SLAStatus"] = np.select(
        [df.Status.eq("Cancelled"), is_closed & (df.SLAMet == 1), is_closed,
         is_open & (df.SLABreachedOpen == 1)],
        ["Not Applicable", "Met", "Breached", "Open - Breached"], "Open - Within SLA")

    df = derive_repeat_visits(df)
    return df.sort_values("CreatedAt").reset_index(drop=True)


def derive_repeat_visits(df: pd.DataFrame) -> pd.DataFrame:
    """
    Business rule (docs/kpi_definitions.md):
      A *repeat visit* is a Repair-category request raised on the same asset
      within 30 days after a previous request on that asset was closed.
      The previous request is then NOT a first-time fix.
      First-time fix is only measurable once 30 days have passed since closure.
    """
    svc = pd.read_csv(C.RAW_DIR / "service_catalogue.csv").set_index("ServiceType").ServiceCategory
    work = df[df.Status != "Cancelled"].sort_values(["AssetID", "CreatedAt"]).copy()
    work["PrevClosedAt"] = work.groupby("AssetID").ClosedAt.shift(1)
    work["PrevRequestID"] = work.groupby("AssetID").ServiceRequestID.shift(1)
    gap = (work.CreatedAt - work.PrevClosedAt).dt.total_seconds() / 86400
    is_repair = work.ServiceType.map(svc).eq("Repair")
    work["RepeatVisitFlag"] = (is_repair & gap.between(0, REPEAT_WINDOW_DAYS)).astype(int)
    work["RepeatOfRequestID"] = work.PrevRequestID.where(work.RepeatVisitFlag == 1)

    caused = set(work.loc[work.RepeatVisitFlag == 1, "PrevRequestID"])
    closed = work.Status.eq("Closed")
    observable = work.ClosedAt + pd.Timedelta(days=REPEAT_WINDOW_DAYS) <= SNAPSHOT
    work["FirstTimeFixFlag"] = np.where(closed & observable,
                                        (~work.ServiceRequestID.isin(caused)).astype(int), np.nan)

    df = df.merge(work[["ServiceRequestID", "RepeatVisitFlag", "RepeatOfRequestID", "FirstTimeFixFlag"]],
                  on="ServiceRequestID", how="left")
    df["RepeatVisitFlag"] = df.RepeatVisitFlag.fillna(0).astype(int)
    return df


# ============================================================================
# Billing
# ============================================================================
def clean_billing(sr: pd.DataFrame) -> pd.DataFrame:
    src = "billing_invoices.csv"
    df = read(src)
    n0 = len(df)
    df = df.drop_duplicates()
    log(src, "Exact duplicate invoice rows", n0 - len(df), "Removed (kept first)")
    df = send_to_quarantine(df, df.InvoiceID.duplicated(keep=False), src, "Conflicting rows for the same InvoiceID")

    for col in ["WorkHours", "LabourCost", "PartsCost", "InvoiceAmount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = send_to_quarantine(df, df[["LabourCost", "PartsCost", "InvoiceAmount"]].isna().any(axis=1),
                            src, "Non-numeric amount")
    df = send_to_quarantine(df, (df.LabourCost < 0) | (df.PartsCost < 0) | (df.InvoiceAmount < 0),
                            src, "Negative cost or amount")

    all_ids = set(read("fsm_service_requests.csv").ServiceRequestID)
    df = send_to_quarantine(df, ~df.ServiceRequestID.isin(all_ids), src,
                            "Orphan invoice: ServiceRequestID not in FSM")
    # Invoice belongs to a ticket that was itself quarantined -> park it too
    df = send_to_quarantine(df, ~df.ServiceRequestID.isin(sr.ServiceRequestID), src,
                            "Invoice for a quarantined service request")
    df = send_to_quarantine(df, df.ServiceRequestID.duplicated(keep=False), src,
                            "More than one invoice for a service request")
    df["InvoiceDate"] = pd.to_datetime(df.InvoiceDate).dt.date
    return df


# ============================================================================
# CSAT
# ============================================================================
def clean_csat(sr: pd.DataFrame) -> pd.DataFrame:
    src = "csat_survey_responses.csv"
    df = read(src)
    df["CSATScore"] = pd.to_numeric(df.CSATScore, errors="coerce")
    df = send_to_quarantine(df, ~df.CSATScore.between(1, 5), src, "CSAT score outside 1-5 scale")
    df = send_to_quarantine(df, ~df.ServiceRequestID.isin(sr.ServiceRequestID), src,
                            "Survey for unknown or quarantined service request")
    # Customer answered twice: keep the most recent answer
    df["ResponseDate"] = pd.to_datetime(df.ResponseDate)
    df = df.sort_values(["ServiceRequestID", "ResponseDate"])
    dup = df.ServiceRequestID.duplicated(keep="last")
    log(src, "Multiple responses for one request", dup.sum(), "Kept latest response", "Warning")
    df = df[~dup].copy()
    df["ResponseDate"] = df.ResponseDate.dt.date
    df["CSATScore"] = df.CSATScore.astype(int)
    return df


# ============================================================================
# Reconciliation
# ============================================================================
def reconcile(sr: pd.DataFrame, billing: pd.DataFrame) -> dict:
    closed = sr[sr.Status == "Closed"]
    unbilled = closed[~closed.ServiceRequestID.isin(billing.ServiceRequestID)]
    recent = unbilled.ClosedAt > SNAPSHOT - pd.Timedelta(days=10)
    billed_non_closed = billing[~billing.ServiceRequestID.isin(closed.ServiceRequestID)]
    log("FSM vs Billing", "Closed requests not yet invoiced (closed in last 10 days)", recent.sum(),
        "Expected timing gap - reported as unbilled WIP", "Info")
    log("FSM vs Billing", "Closed requests not invoiced (older than 10 days)", (~recent).sum(),
        "Flagged for finance follow-up", "Warning")
    log("FSM vs Billing", "Invoices for requests that are not Closed", len(billed_non_closed),
        "Flagged", "Warning")
    return {"closed_requests": len(closed), "invoiced": closed.ServiceRequestID.isin(billing.ServiceRequestID).sum(),
            "unbilled_recent": int(recent.sum()), "unbilled_old": int((~recent).sum()),
            "invoice_total": billing.InvoiceAmount.sum()}


def write_report(raw_counts: dict, clean_counts: dict, recon: dict):
    log_df = pd.DataFrame(dq_log)
    log_df.to_csv(C.PROCESSED_DIR / "data_quality_log.csv", index=False)
    lines = [
        "# Data Quality Report",
        "",
        f"_Generated by `src/clean_data.py` on {datetime.now():%Y-%m-%d %H:%M}. Extract snapshot: {C.SNAPSHOT_DATE}._",
        "",
        "## Row counts",
        "",
        "| Source | Raw rows | Clean rows | Removed / quarantined |",
        "|---|---:|---:|---:|",
    ]
    for k in raw_counts:
        lines.append(f"| {k} | {raw_counts[k]:,} | {clean_counts[k]:,} | {raw_counts[k] - clean_counts[k]:,} |")
    lines += ["", "## Checks performed", "",
              "| Source | Check | Rows | Severity | Action |", "|---|---|---:|---|---|"]
    for r in dq_log:
        lines.append(f"| {r['Source']} | {r['Check']} | {r['RowsAffected']:,} | {r['Severity']} | {r['Action']} |")
    pct_inv = recon["invoiced"] / recon["closed_requests"]
    lines += ["", "## FSM ↔ Billing reconciliation", "",
              f"* Closed service requests: **{recon['closed_requests']:,}**",
              f"* Of which invoiced: **{recon['invoiced']:,}** ({pct_inv:.2%})",
              f"* Not yet invoiced, closed in last 10 days (normal billing lag): **{recon['unbilled_recent']:,}**",
              f"* Not invoiced and older than 10 days (needs follow-up): **{recon['unbilled_old']:,}**",
              f"* Clean invoice total: **${recon['invoice_total']:,.2f}**",
              "",
              "Quarantined rows are in `data/quarantine/quarantine_records.csv` with a `QuarantineReason` column.",
              ""]
    (C.DOCS_DIR / "data_quality_report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    C.QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    raw_counts = {f: len(read(f)) for f in ["crm_customers.csv", "hr_technicians.csv", "fsm_service_requests.csv",
                                             "billing_invoices.csv", "csat_survey_responses.csv"]}
    customers = clean_customers()
    techs = clean_technicians()
    sr = clean_service_requests(customers, techs)
    billing = clean_billing(sr)
    csat = clean_csat(sr)
    recon = reconcile(sr, billing)

    outputs = {"clean_customers.csv": customers, "clean_technicians.csv": techs,
               "clean_service_requests.csv": sr, "clean_billing.csv": billing, "clean_csat.csv": csat}
    for name, df in outputs.items():
        df.to_csv(C.PROCESSED_DIR / name, index=False)
    clean_counts = dict(zip(raw_counts, [len(d) for d in outputs.values()]))

    q = pd.concat(quarantine, ignore_index=True) if quarantine else pd.DataFrame()
    q.to_csv(C.QUARANTINE_DIR / "quarantine_records.csv", index=False)
    write_report(raw_counts, clean_counts, recon)

    print(pd.DataFrame(dq_log).to_string(index=False))
    print(f"\nQuarantined rows: {len(q):,}")
    for k in raw_counts:
        print(f"  {k:28s} raw {raw_counts[k]:>7,}  clean {clean_counts[k]:>7,}")


if __name__ == "__main__":
    main()
