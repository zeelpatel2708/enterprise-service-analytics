"""
build_model.py
==============
Turns the cleaned operational tables into a Kimball-style star schema that
Power BI imports directly (data/model/*.csv).

    Dimensions : DimDate, DimCustomer, DimTechnician, DimRegion,
                 DimServiceType, DimPriority
    Facts      : FactServiceRequests   (transaction grain: one row per request)
                 FactTargets           (region x month budget)
                 FactBacklogSnapshot   (periodic snapshot: region x month-end)
    Security   : SecurityUserRegion    (dynamic row-level security mapping)

Surrogate keys are integers. Special members:
    TechnicianKey -1 = "Unknown"     (closed work with no technician recorded)
    TechnicianKey -2 = "Unassigned"  (new tickets not yet dispatched)

Run:  python src/build_model.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C

MODEL_DIR = C.ROOT / "data" / "model"
SNAPSHOT = pd.Timestamp(C.SNAPSHOT_DATE)


def date_key(s: pd.Series) -> pd.Series:
    return pd.to_numeric(pd.to_datetime(s).dt.strftime("%Y%m%d"), errors="coerce").astype("Int64")


def build_dim_date() -> pd.DataFrame:
    d = pd.DataFrame({"Date": pd.date_range(C.START_DATE, C.CALENDAR_END, freq="D")})
    fy_shift = d.Date.dt.month >= C.FISCAL_YEAR_START_MONTH
    fiscal_month = (d.Date.dt.month - C.FISCAL_YEAR_START_MONTH) % 12 + 1
    iso = d.Date.dt.isocalendar()
    out = pd.DataFrame({
        "DateKey": date_key(d.Date),
        "Date": d.Date.dt.date,
        "Year": d.Date.dt.year,
        "QuarterNumber": d.Date.dt.quarter,
        "Quarter": "Q" + d.Date.dt.quarter.astype(str),
        "YearQuarter": d.Date.dt.year.astype(str) + "-Q" + d.Date.dt.quarter.astype(str),
        "MonthNumber": d.Date.dt.month,
        "Month": d.Date.dt.strftime("%B"),
        "MonthShort": d.Date.dt.strftime("%b"),
        "YearMonth": d.Date.dt.strftime("%Y-%m"),
        "YearMonthKey": d.Date.dt.year * 100 + d.Date.dt.month,
        "MonthStartDate": d.Date.dt.to_period("M").dt.start_time.dt.date,
        "MonthEndDate": d.Date.dt.to_period("M").dt.end_time.dt.date,
        "ISOWeek": iso.week.astype(int),
        "Day": d.Date.dt.day,
        "DayOfWeekNumber": d.Date.dt.dayofweek + 1,  # Monday = 1
        "DayOfWeek": d.Date.dt.day_name(),
        "IsWeekend": (d.Date.dt.dayofweek >= 5).astype(int),
        "FiscalYear": "FY" + (d.Date.dt.year + fy_shift.astype(int)).astype(str),
        "FiscalQuarter": "FQ" + ((fiscal_month - 1) // 3 + 1).astype(str),
        "FiscalMonthNumber": fiscal_month,
        "IsAfterSnapshot": (d.Date > SNAPSHOT).astype(int),
        # A month is "complete" for reporting once billing for it has posted
        # (invoices lag closure by up to ~10 days, so allow 15 days after month end).
        "IsCompleteMonth": ((d.Date.dt.to_period("M").dt.end_time + pd.Timedelta(days=15)) <= SNAPSHOT).astype(int),
    })
    return out


def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    P = C.PROCESSED_DIR
    cust = pd.read_csv(P / "clean_customers.csv")
    tech = pd.read_csv(P / "clean_technicians.csv")
    sr = pd.read_csv(P / "clean_service_requests.csv", parse_dates=["CreatedAt", "ClosedAt"])
    bill = pd.read_csv(P / "clean_billing.csv")
    csat = pd.read_csv(P / "clean_csat.csv")
    regions = pd.read_csv(C.RAW_DIR / "regions.csv")
    svc = pd.read_csv(C.RAW_DIR / "service_catalogue.csv")
    targets = pd.read_csv(C.RAW_DIR / "regional_targets.csv", parse_dates=["Month"])

    # ---------------- dimensions ----------------
    dim_date = build_dim_date()

    dim_region = regions.copy()
    dim_region.insert(0, "RegionKey", range(1, len(dim_region) + 1))
    dim_region["RegionalManagerEmail"] = (dim_region.RegionalManager.str.lower()
                                          .str.replace(" ", ".") + "@northline.example")
    rkey = dict(zip(dim_region.Region, dim_region.RegionKey))

    dim_customer = cust.sort_values("CustomerID").reset_index(drop=True)
    dim_customer.insert(0, "CustomerKey", range(1, len(dim_customer) + 1))
    first_req = sr.groupby("CustomerID").CreatedAt.min()
    last_req = sr.groupby("CustomerID").CreatedAt.max()
    dim_customer["FirstRequestDate"] = dim_customer.CustomerID.map(first_req).dt.date
    dim_customer["LastRequestDate"] = dim_customer.CustomerID.map(last_req).dt.date
    days_since = (SNAPSHOT - dim_customer.CustomerID.map(last_req)).dt.days
    # Retention proxy: an account with no request in 180 days is "At Risk"
    dim_customer["ActivityStatus"] = np.select([days_since.isna(), days_since > 180, days_since > 90],
                                               ["No Activity", "At Risk (180d+)", "Cooling (90-180d)"], "Active")
    ckey = dict(zip(dim_customer.CustomerID, dim_customer.CustomerKey))

    dim_tech = tech.sort_values("TechnicianID").reset_index(drop=True)
    dim_tech.insert(0, "TechnicianKey", range(1, len(dim_tech) + 1))
    term = pd.to_datetime(dim_tech.TerminationDate)
    dim_tech["IsActive"] = (term.isna() | (term > SNAPSHOT)).astype(int)
    end = term.fillna(SNAPSHOT).where(term.fillna(SNAPSHOT) < SNAPSHOT, SNAPSHOT)
    dim_tech["TenureYears"] = ((end - pd.to_datetime(dim_tech.HireDate)).dt.days / 365.25).round(1)
    dim_tech["TenureBand"] = pd.cut(dim_tech.TenureYears, [-1, 1, 3, 6, 50],
                                    labels=["< 1 yr", "1-3 yrs", "3-6 yrs", "6+ yrs"]).astype(str)
    special = pd.DataFrame([
        {"TechnicianKey": -1, "TechnicianID": "UNKNOWN", "TechnicianName": "Unknown (not recorded)"},
        {"TechnicianKey": -2, "TechnicianID": "UNASSIGNED", "TechnicianName": "Unassigned"}])
    for col in ["SkillLevel", "Specialization", "Region", "TenureBand"]:
        special[col] = "N/A"
    dim_tech = pd.concat([special, dim_tech], ignore_index=True)[
        ["TechnicianKey", "TechnicianID", "TechnicianName", "SkillLevel", "Specialization", "Region",
         "HireDate", "TerminationDate", "IsActive", "TenureYears", "TenureBand"]]
    dim_tech["IsActive"] = dim_tech.IsActive.astype("Int64")
    tkey = dict(zip(dim_tech.TechnicianID, dim_tech.TechnicianKey))

    dim_svc = svc.copy()
    dim_svc.insert(0, "ServiceTypeKey", range(1, len(dim_svc) + 1))
    skey = dict(zip(dim_svc.ServiceType, dim_svc.ServiceTypeKey))

    dim_pri = pd.DataFrame(C.PRIORITIES, columns=["Priority", "SLAHours", "PriceMultiplier", "SortOrder"])
    dim_pri.insert(0, "PriorityKey", dim_pri.SortOrder)
    pkey = dict(zip(dim_pri.Priority, dim_pri.PriorityKey))

    # ---------------- FactServiceRequests ----------------
    f = sr.merge(bill[["ServiceRequestID", "InvoiceID", "BillingType", "WorkHours", "LabourCost",
                       "PartsCost", "InvoiceAmount"]], on="ServiceRequestID", how="left")
    f = f.merge(csat[["ServiceRequestID", "CSATScore"]], on="ServiceRequestID", how="left")
    fact = pd.DataFrame({
        "ServiceRequestID": f.ServiceRequestID,
        "AssetID": f.AssetID,
        "CustomerKey": f.CustomerID.map(ckey),
        "TechnicianKey": f.TechnicianID.map(tkey),
        "RegionKey": f.Region.map(rkey),
        "ServiceTypeKey": f.ServiceType.map(skey),
        "PriorityKey": f.Priority.map(pkey),
        "CreatedDateKey": date_key(f.CreatedAt),
        "ClosedDateKey": date_key(f.ClosedAt.where(f.Status.eq("Closed"))),
        "CreatedAt": f.CreatedAt,
        "ClosedAt": f.ClosedAt.where(f.Status.eq("Closed")),
        "CreatedHour": f.CreatedAt.dt.hour,
        "Status": f.Status,
        "IsClosed": f.Status.eq("Closed").astype(int),
        "IsOpen": f.Status.isin(["Open", "In Progress"]).astype(int),
        "IsCancelled": f.Status.eq("Cancelled").astype(int),
        "SLAHours": f.SLAHours,
        "ResolutionHours": f.ResolutionHours,
        "SLAMet": f.SLAMet.astype("Int64"),
        "SLAStatus": f.SLAStatus,
        "OpenAgeHours": f.OpenAgeHours,
        "RepeatVisitFlag": f.RepeatVisitFlag,
        "RepeatOfRequestID": f.RepeatOfRequestID,
        "FirstTimeFixFlag": f.FirstTimeFixFlag.astype("Int64"),
        "InvoiceID": f.InvoiceID,
        "IsInvoiced": f.InvoiceID.notna().astype(int),
        "BillingType": f.BillingType.fillna("Not Invoiced"),
        "WorkHours": f.WorkHours,
        "LabourCost": f.LabourCost,
        "PartsCost": f.PartsCost,
        "ServiceRevenue": f.InvoiceAmount,
        "CSATScore": f.CSATScore.astype("Int64"),
        "DQ_MissingTechnician": f.DQ_MissingTechnician,
    })
    assert fact[["CustomerKey", "TechnicianKey", "RegionKey", "ServiceTypeKey", "PriorityKey"]].notna().all().all()

    # ---------------- FactTargets ----------------
    ft = pd.DataFrame({
        "RegionKey": targets.Region.map(rkey),
        "MonthStartDateKey": date_key(targets.Month),
        "RevenueTarget": targets.RevenueTarget,
        "SLATarget": targets.SLATarget,
        "CSATTarget": targets.CSATTarget,
        "ProductivityTarget": targets.ProductivityTarget,
        "BacklogTarget": targets.BacklogTarget,
    })

    # ---------------- FactBacklogSnapshot (periodic snapshot) ----------------
    rows = []
    month_ends = pd.date_range(C.START_DATE, SNAPSHOT, freq="ME")
    open_end = f.ClosedAt.where(f.Status.isin(["Closed", "Cancelled"]))  # NaT = still open
    for me in month_ends:
        eom = me + pd.Timedelta(hours=23, minutes=59, seconds=59)
        is_open = (f.CreatedAt <= eom) & (open_end.isna() | (open_end > eom))
        age_h = (eom - f.CreatedAt).dt.total_seconds() / 3600
        snap = pd.DataFrame({"Region": f.Region[is_open], "Breached": (age_h > f.SLAHours)[is_open],
                             "Aged7d": (age_h > 168)[is_open]})
        g = snap.groupby("Region").agg(OpenRequests=("Breached", "size"),
                                       OpenBreachedSLA=("Breached", "sum"),
                                       OpenOver7Days=("Aged7d", "sum"))
        g = g.reindex(dim_region.Region, fill_value=0).reset_index()
        g["SnapshotDateKey"] = int(me.strftime("%Y%m%d"))
        rows.append(g)
    fb = pd.concat(rows, ignore_index=True)
    fb.insert(0, "RegionKey", fb.pop("Region").map(rkey))
    fb.insert(1, "SnapshotDateKey", fb.pop("SnapshotDateKey"))

    # ---------------- Security mapping for dynamic RLS ----------------
    sec = [{"UserEmail": e, "RegionKey": k, "Role": "Regional Manager"}
           for e, k in zip(dim_region.RegionalManagerEmail, dim_region.RegionKey)]
    for email, role in (("ceo@northline.example", "Executive"), ("vp.operations@northline.example", "Operations Manager")):
        sec += [{"UserEmail": email, "RegionKey": k, "Role": role} for k in dim_region.RegionKey]
    security = pd.DataFrame(sec)

    out = {"DimDate": dim_date, "DimCustomer": dim_customer, "DimTechnician": dim_tech,
           "DimRegion": dim_region, "DimServiceType": dim_svc, "DimPriority": dim_pri,
           "FactServiceRequests": fact, "FactTargets": ft, "FactBacklogSnapshot": fb,
           "SecurityUserRegion": security}
    for name, df in out.items():
        df.to_csv(MODEL_DIR / f"{name}.csv", index=False)
        print(f"  {name:22s} {len(df):>7,} rows  {df.shape[1]:>3} cols")


if __name__ == "__main__":
    main()
