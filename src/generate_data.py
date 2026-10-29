"""
generate_data.py
================
Generates the raw source-system extracts for "Northline Field Services", a
fictional multi-region Ontario field-service company.

The data deliberately mimics how a real company's data is spread across
systems that do not agree with each other:

    crm_customers.csv           CRM export (customers)
    hr_technicians.csv          HR system export (workforce)
    fsm_service_requests.csv    Field Service Management system (tickets)
    billing_invoices.csv        Finance / billing system (invoices + job costs)
    csat_survey_responses.csv   Survey tool (customer feedback)
    sla_policy.csv              Contracted SLA hours by priority
    regional_targets.csv        Monthly budget/targets by region (FP&A)

It also embeds realistic *business stories* (things an analyst should be able
to find with the dashboard) and *data-quality defects* (things the pipeline
must detect and handle). Both are documented in docs/ — but try to find the
stories yourself in Power BI before reading the answer key.

Run:  python src/generate_data.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from faker import Faker

import config as C

rng = np.random.default_rng(C.SEED)
fake = Faker("en_CA")
Faker.seed(C.SEED)

START = pd.Timestamp(C.START_DATE)
SNAPSHOT = pd.Timestamp(C.SNAPSHOT_DATE)
MONTHS = pd.date_range(START, SNAPSHOT, freq="MS")

REGION_NAMES = [r[0] for r in C.REGIONS]
REGION_SHARE = {r[0]: r[3] for r in C.REGIONS}
SVC = pd.DataFrame(C.SERVICE_TYPES, columns=["ServiceCategory", "ServiceType", "Share",
                                             "BasePrice", "WorkHours", "PartsMean"])
PRI = pd.DataFrame(C.PRIORITIES, columns=["Priority", "SLAHours", "PriceMult", "SortOrder"])
SLA_HOURS = dict(zip(PRI.Priority, PRI.SLAHours))
PRICE_MULT = dict(zip(PRI.Priority, PRI.PriceMult))

# Story switches ---------------------------------------------------------------
OTTAWA_SURGE_START = pd.Timestamp("2026-03-01")      # Story 1
OTTAWA_TECH_EXIT = pd.Timestamp("2026-02-13")         # Story 1
HAMILTON_SUPPLIER_CHANGE = pd.Timestamp("2025-10-01")  # Story 3

PRIORITY_MIX = {  # service type -> probabilities for Critical, High, Medium, Low
    "Standard Repair":        [0.05, 0.35, 0.50, 0.10],
    "Emergency Repair":       [0.70, 0.30, 0.00, 0.00],
    "Preventive Maintenance": [0.00, 0.05, 0.40, 0.55],
    "Scheduled Maintenance":  [0.00, 0.00, 0.35, 0.65],
    "Safety Inspection":      [0.02, 0.10, 0.50, 0.38],
    "Compliance Inspection":  [0.00, 0.08, 0.52, 0.40],
    "New Installation":       [0.00, 0.15, 0.60, 0.25],
    "Equipment Upgrade":      [0.00, 0.12, 0.58, 0.30],
}


# ============================================================================
# 1. Customers (CRM)
# ============================================================================
CITY_BY_REGION = {
    "Toronto": ["Toronto", "North York", "Scarborough", "Etobicoke"],
    "Mississauga": ["Mississauga", "Brampton", "Oakville"],
    "Ottawa": ["Ottawa", "Kanata", "Nepean", "Orleans"],
    "Hamilton": ["Hamilton", "Burlington", "Stoney Creek", "Ancaster"],
    "Kitchener-Waterloo": ["Kitchener", "Waterloo", "Cambridge"],
    "London": ["London", "St. Thomas", "Strathroy"],
}


def make_customers() -> pd.DataFrame:
    segs = list(C.SEGMENTS)
    seg_p = [C.SEGMENTS[s][0] for s in segs]
    regions = rng.choice(REGION_NAMES, size=C.N_CUSTOMERS, p=[REGION_SHARE[r] for r in REGION_NAMES])
    seg = rng.choice(segs, size=C.N_CUSTOMERS, p=seg_p)

    names, seen = [], set()
    for i in range(C.N_CUSTOMERS):
        n = fake.company()
        while n in seen:
            n = fake.company()
        seen.add(n)
        names.append(n)

    # 85% of accounts existed before the analysis window; 15% are won during it
    pre = rng.random(C.N_CUSTOMERS) < 0.85
    start_pre = pd.to_datetime("2012-01-01") + pd.to_timedelta(rng.integers(0, 4380, C.N_CUSTOMERS), "D")
    start_new = START + pd.to_timedelta(rng.integers(0, (SNAPSHOT - START).days - 60, C.N_CUSTOMERS), "D")
    start = np.where(pre, start_pre, start_new)

    industry = np.where(seg == "Government", "Public Sector",
                        rng.choice([i for i in C.INDUSTRIES if i != "Public Sector"], C.N_CUSTOMERS))
    df = pd.DataFrame({
        "CustomerID": [f"CUST-{i:05d}" for i in range(1, C.N_CUSTOMERS + 1)],
        "CustomerName": names,
        "Industry": industry,
        "CustomerSegment": seg,
        "City": [rng.choice(CITY_BY_REGION[r]) for r in regions],
        "Province": "ON",
        "HomeRegion": regions,
        "AccountStartDate": pd.to_datetime(start).date,
    })
    # Each customer owns serviced equipment/sites (assets). Repeat visits are tracked per asset.
    base_assets = df.CustomerSegment.map({"Enterprise": 90, "Government": 50, "Mid-Market": 16, "Small Business": 6})
    df["NumAssets"] = np.maximum(1, rng.poisson(base_assets))
    return df


# ============================================================================
# 2. Technicians (HR)
# ============================================================================
def make_technicians() -> pd.DataFrame:
    rows, n = [], 1
    skills = list(C.SKILL_LEVELS)
    skill_p = [C.SKILL_LEVELS[s][0] for s in skills]
    for region, prov, _mgr, _share, count in C.REGIONS:
        for _ in range(count):
            hire = pd.Timestamp("2014-01-01") + pd.Timedelta(days=int(rng.integers(0, 3600)))
            rows.append([f"TECH-{n:04d}", f"{fake.first_name()} {fake.last_name()}", rng.choice(skills, p=skill_p),
                         rng.choice(C.SPECIALIZATIONS), region, hire.date(), None])
            n += 1
        # Planned growth hires (capacity keeps pace with ~7%/yr demand growth).
        # Ottawa's Jan-2026 hiring wave was frozen -> part of Story 1.
        for wave_start, pct in (("2025-01-06", 0.08), ("2025-07-07", 0.05), ("2026-01-05", 0.08)):
            if region == "Ottawa" and wave_start.startswith("2026"):
                continue
            for _ in range(max(1, round(count * pct))):
                hire = pd.Timestamp(wave_start) + pd.Timedelta(days=int(rng.integers(0, 45)))
                rows.append([f"TECH-{n:04d}", f"{fake.first_name()} {fake.last_name()}", rng.choice(["Junior", "Intermediate"], p=[0.7, 0.3]),
                             rng.choice(C.SPECIALIZATIONS), region, hire.date(), None])
                n += 1
    df = pd.DataFrame(rows, columns=["TechnicianID", "TechnicianName", "SkillLevel",
                                     "Specialization", "Region", "HireDate", "TerminationDate"])

    # Story 1: two experienced Ottawa technicians leave in Feb 2026 and are NOT backfilled.
    ott = df[(df.Region == "Ottawa") & (df.SkillLevel.isin(["Senior", "Expert"]))].index[:2]
    df.loc[ott, "TerminationDate"] = [OTTAWA_TECH_EXIT.date(), (OTTAWA_TECH_EXIT + pd.Timedelta(days=9)).date()]
    # Normal turnover elsewhere: a couple of leavers who are replaced (handled by the 2025 hires)
    for region, when in (("Toronto", "2024-11-29"), ("Mississauga", "2025-04-30"), ("London", "2025-09-12")):
        i = df[(df.Region == region) & (df.HireDate < pd.Timestamp("2020-01-01").date())].index[0]
        df.loc[i, "TerminationDate"] = pd.Timestamp(when).date()
    return df


def active_techs(techs: pd.DataFrame, region: str, when: pd.Timestamp) -> pd.DataFrame:
    hire = pd.to_datetime(techs.HireDate)
    term = pd.to_datetime(techs.TerminationDate)
    mask = (techs.Region == region) & (hire <= when) & (term.isna() | (term > when))
    return techs[mask]


# ============================================================================
# 3. Demand model
# ============================================================================
def seasonality(category: str, service_type: str, month: int) -> float:
    if service_type == "Emergency Repair":
        return {1: 1.45, 2: 1.35, 3: 1.05, 7: 1.30, 8: 1.20, 12: 1.30}.get(month, 0.90)
    if category == "Repair":
        return {1: 1.20, 2: 1.15, 7: 1.12, 8: 1.08, 12: 1.10}.get(month, 0.96)
    if category == "Maintenance":
        return {4: 1.20, 5: 1.25, 9: 1.20, 10: 1.25, 12: 0.75, 1: 0.85}.get(month, 1.0)
    if category == "Installation":
        return {5: 1.15, 6: 1.20, 8: 1.10, 12: 0.70, 1: 0.75}.get(month, 1.0)
    return 1.0


def expected_volume(story: bool = True) -> pd.DataFrame:
    """Expected number of *original* requests per month x region x service type."""
    rows = []
    for i, m in enumerate(MONTHS):
        growth = 1.0055 ** i  # ~6.8% annual organic growth
        for region in REGION_NAMES:
            for _, s in SVC.iterrows():
                mult = 1.0
                if story and region == "Ottawa" and m >= OTTAWA_SURGE_START:
                    # Story 1: a large Ottawa government/healthcare contract brings an
                    # emergency-repair surge (+~35%) and more standard repairs (+~12%).
                    mult = {"Emergency Repair": 1.32, "Standard Repair": 1.10}.get(s.ServiceType, 1.0)
                lam = REGION_SHARE[region] * s.Share * growth * seasonality(s.ServiceCategory, s.ServiceType, m.month) * mult
                rows.append((m, region, s.ServiceType, lam))
    df = pd.DataFrame(rows, columns=["Month", "Region", "ServiceType", "Lambda"])
    return df


# ============================================================================
# 4. Service requests (FSM) + costs/billing + CSAT
# ============================================================================
def random_created_times(month: pd.Timestamp, n: int, emergency: bool) -> pd.DatetimeIndex:
    days = pd.date_range(month, month + pd.offsets.MonthEnd(0), freq="D")
    dow_w = np.array([1.25, 1.05, 1.0, 1.0, 1.0, 0.35, 0.2]) if not emergency else np.array([1.1, 1, 1, 1, 1.05, 0.9, 0.85])
    w = dow_w[days.dayofweek]
    d = rng.choice(days, size=n, p=w / w.sum())
    if emergency:
        hours = rng.choice(24, size=n, p=np.r_[np.full(6, 0.02), np.full(12, 0.06), np.full(6, 0.026)] /
                           np.r_[np.full(6, 0.02), np.full(12, 0.06), np.full(6, 0.026)].sum())
    else:
        hp = np.array([0.03, 0.08, 0.12, 0.13, 0.12, 0.10, 0.11, 0.11, 0.09, 0.06, 0.05])
        hours = rng.choice(np.arange(7, 18), size=n, p=hp / hp.sum())
    minutes = rng.integers(0, 60, size=n)
    seconds = rng.integers(0, 60, size=n)
    return pd.DatetimeIndex(d) + pd.to_timedelta(hours, "h") + pd.to_timedelta(minutes, "m") + pd.to_timedelta(seconds, "s")


def make_requests(customers: pd.DataFrame, techs: pd.DataFrame):
    exp = expected_volume(story=True)
    # scale to ~93% of the target; repeat visits make up the rest
    scale = C.TARGET_REQUESTS * 0.93 / exp.Lambda.sum()
    exp["N"] = rng.poisson(exp.Lambda * scale)

    seg_w = {s: C.SEGMENTS[s][2] for s in C.SEGMENTS}
    cust_start = pd.to_datetime(customers.AccountStartDate)

    # --- capacity / congestion per region-month --------------------------------
    demand = exp.groupby(["Month", "Region"]).N.sum()
    congestion = {}
    for (m, region), n in demand.items():
        cap = len(active_techs(techs, region, m + pd.Timedelta(days=14))) * C.MONTHLY_CAPACITY_PER_TECH
        util = n * 1.07 / cap  # include expected repeat visits
        congestion[(m, region)] = max(0.92, util / 0.86) ** 1.15

    parts = []
    for (m, region, stype), grp in exp.groupby(["Month", "Region", "ServiceType"]):
        n = int(grp.N.iloc[0])
        if n == 0:
            continue
        created = random_created_times(m, n, emergency=(stype == "Emergency Repair"))
        # customers: active accounts in that region, weighted by segment size
        eligible = customers[(customers.HomeRegion == region) & (cust_start <= m + pd.offsets.MonthEnd(0))]
        w = eligible.CustomerSegment.map(seg_w).to_numpy()
        pick = rng.choice(len(eligible), size=n, p=w / w.sum())
        cust = eligible.CustomerID.to_numpy()[pick]
        asset_no = rng.integers(1, eligible.NumAssets.to_numpy()[pick] + 1)
        asset = [f"AST-{c[5:]}-{a:02d}" for c, a in zip(cust, asset_no)]
        pri = rng.choice(PRI.Priority.to_numpy(), size=n, p=PRIORITY_MIX[stype])
        parts.append(pd.DataFrame({"CreatedAt": created, "CustomerID": cust, "AssetID": asset,
                                   "Region": region, "ServiceType": stype, "Priority": pri, "IsRepeat": False,
                                   "Congestion": congestion[(m, region)]}))
    req = pd.concat(parts, ignore_index=True)
    req = simulate_work(req, customers, techs)

    # --- repeat visits (callbacks) driven by technician skill -----------------
    skill_of = techs.set_index("TechnicianID").SkillLevel
    p_repeat = req.TechnicianID.map(skill_of).map({k: v[2] for k, v in C.SKILL_LEVELS.items()}).fillna(0.06)
    p_repeat += np.where(req.ServiceType.isin(["New Installation", "Equipment Upgrade"]), 0.05, 0)
    p_repeat += np.where(req.ServiceType == "Emergency Repair", 0.02, 0)
    eligible = req.Status.eq("Closed")
    is_parent = eligible & (rng.random(len(req)) < p_repeat)
    parents = req[is_parent]
    rep = pd.DataFrame({
        "CreatedAt": parents.ClosedAt.to_numpy() + pd.to_timedelta(rng.uniform(1, 24, len(parents)), "D"),
        "CustomerID": parents.CustomerID.to_numpy(),
        "AssetID": parents.AssetID.to_numpy(),
        "Region": parents.Region.to_numpy(),
        # a callback is logged as a repair on the same asset
        "ServiceType": np.where((parents.Priority == "Critical").to_numpy() | (rng.random(len(parents)) < 0.15),
                                "Emergency Repair", "Standard Repair"),
        "Priority": rng.choice(["Critical", "High", "Medium"], size=len(parents), p=[0.15, 0.6, 0.25]),
        "IsRepeat": True,
        "Congestion": parents.Congestion.to_numpy(),
        "PreferredTech": np.where(rng.random(len(parents)) < 0.6, parents.TechnicianID.to_numpy(), None),
    })
    rep = rep[rep.CreatedAt <= SNAPSHOT]
    rep = simulate_work(rep, customers, techs)
    req = pd.concat([req, rep], ignore_index=True).sort_values("CreatedAt").reset_index(drop=True)
    req["ServiceRequestID"] = [f"SR-{i:07d}" for i in range(1, len(req) + 1)]
    return req


def simulate_work(req: pd.DataFrame, customers: pd.DataFrame, techs: pd.DataFrame) -> pd.DataFrame:
    req = req.copy()
    n = len(req)
    svc = SVC.set_index("ServiceType")

    # --- technician assignment ----------------------------------------------
    tech_ids = np.empty(n, dtype=object)
    req["_m"] = req.CreatedAt.dt.to_period("M").dt.to_timestamp()
    pref = req["PreferredTech"] if "PreferredTech" in req else pd.Series([None] * n, index=req.index)
    for (m, region), idx in req.groupby(["_m", "Region"]).groups.items():
        pool = active_techs(techs, region, m + pd.Timedelta(days=14)).TechnicianID.to_numpy()
        pos = req.index.get_indexer(idx)
        tech_ids[pos] = rng.choice(pool, size=len(idx))
    pref_arr = pref.to_numpy()
    # keep preferred tech for callbacks if still employed at that date
    term = pd.to_datetime(techs.set_index("TechnicianID").TerminationDate)
    for i in np.where(pd.notna(pref_arr))[0]:
        t = pref_arr[i]
        tt = term.get(t)
        if pd.isna(tt) or tt > req.CreatedAt.iloc[i]:
            tech_ids[i] = t
    req["TechnicianID"] = tech_ids

    # --- elapsed resolution time ---------------------------------------------
    sla = req.Priority.map(SLA_HOURS).to_numpy(float)
    ratio = rng.lognormal(mean=np.log(0.55), sigma=0.42, size=n) * req.Congestion.to_numpy()
    # Friday-afternoon / Saturday tickets wait for Monday unless Critical
    late_week = ((req.CreatedAt.dt.dayofweek == 4) & (req.CreatedAt.dt.hour >= 14)) | (req.CreatedAt.dt.dayofweek == 5)
    ratio *= np.where(late_week & (req.Priority != "Critical"), 1.22, 1.0)
    ratio *= np.where(req.ServiceType.isin(["New Installation", "Equipment Upgrade"]), 1.08, 1.0)
    # Critical work is dispatched to the most senior available tech: tighter spread
    ratio = np.where(req.Priority == "Critical", ratio ** 0.9, ratio)
    stuck = rng.random(n) < 0.004  # waiting on parts / customer access
    ratio = np.where(stuck, ratio * rng.uniform(4, 15, n), ratio)
    res_hours = sla * ratio
    req["ClosedAt"] = req.CreatedAt + pd.to_timedelta(res_hours, "h")
    req["ClosedAt"] = req.ClosedAt.dt.floor("s")

    # --- status ---------------------------------------------------------------
    cancelled = rng.random(n) < 0.018
    status = np.where(cancelled, "Cancelled", np.where(req.ClosedAt > SNAPSHOT, "In Progress", "Closed"))
    recent = (SNAPSHOT - req.CreatedAt) < pd.Timedelta(days=2)
    unassigned = (status == "In Progress") & recent.to_numpy() & (rng.random(n) < 0.35)
    status = np.where(unassigned, "Open", status)
    req["Status"] = status
    req.loc[unassigned, "TechnicianID"] = None
    req.loc[req.Status.isin(["In Progress", "Open"]), "ClosedAt"] = pd.NaT
    # cancellations happen quickly
    cmask = req.Status == "Cancelled"
    req.loc[cmask, "ClosedAt"] = req.loc[cmask, "CreatedAt"] + pd.to_timedelta(rng.uniform(0.5, 30, cmask.sum()), "h")
    req.loc[cmask & (req.ClosedAt > SNAPSHOT), "ClosedAt"] = SNAPSHOT

    # --- costs & revenue ------------------------------------------------------
    skill_of = techs.set_index("TechnicianID").SkillLevel
    wage = req.TechnicianID.map(skill_of).map({k: v[1] for k, v in C.SKILL_LEVELS.items()}).fillna(40).to_numpy()
    work_mean = req.ServiceType.map(svc.WorkHours).to_numpy()
    work = rng.gamma(shape=6, scale=work_mean / 6)
    # juniors take ~15% longer on site
    work *= np.where(req.TechnicianID.map(skill_of) == "Junior", 1.15, 1.0)
    labour_cost = work * wage * 1.30  # 30% burden: travel, benefits, vehicle

    parts_mean = req.ServiceType.map(svc.PartsMean).to_numpy()
    parts_cost = rng.lognormal(np.log(parts_mean), 0.5) * np.where(rng.random(n) < 0.12, 0, 1)
    # Parts are re-billed from the regional parts PRICE LIST (catalogue cost x markup).
    parts_billed = parts_cost * C.PARTS_MARKUP
    # Story 3: Hamilton switches parts supplier for installations -> actual parts cost +40%,
    # but nobody updated the Hamilton price list, so customers are still billed the old price.
    ham = (req.Region == "Hamilton") & req.ServiceType.isin(["New Installation", "Equipment Upgrade"]) & (req.CreatedAt >= HAMILTON_SUPPLIER_CHANGE)
    parts_cost = np.where(ham, parts_cost * 1.40, parts_cost)

    seg = req.CustomerID.map(customers.set_index("CustomerID").CustomerSegment)
    seg_mult = seg.map({s: C.SEGMENTS[s][1] for s in C.SEGMENTS}).to_numpy()
    base = req.ServiceType.map(svc.BasePrice).to_numpy() * req.Priority.map(PRICE_MULT).to_numpy()
    # Price list increases 3% each January
    base *= 1.03 ** (req.CreatedAt.dt.year - 2024).to_numpy()
    labour_billed = base * seg_mult * rng.normal(1, 0.05, n)
    warranty = req.IsRepeat.to_numpy() & (rng.random(n) < 0.8)  # callbacks are usually free
    revenue = np.where(warranty, 0.0, labour_billed + parts_billed)

    req["WorkHours"] = work.round(2)
    req["LabourCost"] = labour_cost.round(2)
    req["PartsCost"] = parts_cost.round(2)
    req["InvoiceAmount"] = revenue.round(2)
    req["BillingType"] = np.where(warranty, "Warranty", "Billable")
    req.loc[req.Status == "Cancelled", ["WorkHours", "LabourCost", "PartsCost", "InvoiceAmount"]] = 0.0
    return req.drop(columns=["_m"] + (["PreferredTech"] if "PreferredTech" in req else []))


def make_billing(req: pd.DataFrame) -> pd.DataFrame:
    b = req[req.Status == "Closed"].copy()
    b["InvoiceDate"] = (b.ClosedAt + pd.to_timedelta(rng.integers(0, 11, len(b)), "D")).dt.date
    b = b[pd.to_datetime(b.InvoiceDate) <= SNAPSHOT]  # late invoices not yet issued
    b = b.sort_values("InvoiceDate").reset_index(drop=True)
    b["InvoiceID"] = [f"INV-{i:07d}" for i in range(1, len(b) + 1)]
    return b[["InvoiceID", "ServiceRequestID", "InvoiceDate", "BillingType", "WorkHours",
              "LabourCost", "PartsCost", "InvoiceAmount"]]


def make_csat(req: pd.DataFrame) -> pd.DataFrame:
    c = req[req.Status == "Closed"].copy()
    sla = c.Priority.map(SLA_HOURS)
    hours = (c.ClosedAt - c.CreatedAt).dt.total_seconds() / 3600
    missed = hours > sla
    # Was the job followed by a callback? (true experience, not visible to the cleaner)
    allreq = req.sort_values("CreatedAt")
    nxt_all = allreq.groupby("AssetID").IsRepeat.shift(-1)
    nxt = nxt_all.reindex(c.index).astype("boolean").fillna(False).astype(bool)
    p_resp = 0.28 + 0.14 * missed + 0.10 * (c.IsRepeat | nxt)
    c = c[rng.random(len(c)) < p_resp]
    missed = missed.loc[c.index]
    nxt = nxt.loc[c.index]
    score = (4.45 - 1.25 * missed - 0.85 * c.IsRepeat - 0.55 * nxt
             - 0.35 * ((hours.loc[c.index] / sla.loc[c.index]) > 0.8)
             + rng.normal(0, 0.55, len(c)))
    c["CSATScore"] = np.clip(np.round(score), 1, 5).astype(int)
    c["ResponseDate"] = (c.ClosedAt + pd.to_timedelta(rng.integers(1, 8, len(c)), "D")).dt.date
    c = c[pd.to_datetime(c.ResponseDate) <= SNAPSHOT].reset_index(drop=True)
    c["SurveyResponseID"] = [f"SRV-{i:06d}" for i in range(1, len(c) + 1)]
    comments = {1: "Very unhappy with response time", 2: "Issue came back", 3: "OK",
                4: "Good service", 5: "Excellent technician"}
    c["Comment"] = c.CSATScore.map(comments).where(rng.random(len(c)) < 0.4, "")
    return c[["SurveyResponseID", "ServiceRequestID", "ResponseDate", "CSATScore", "Comment"]]


def make_targets(req: pd.DataFrame) -> pd.DataFrame:
    """FP&A budget, set from the *no-surprise* demand forecast (stories excluded)."""
    exp = expected_volume(story=False)
    vol = exp.groupby(["Month", "Region"]).Lambda.sum()
    # forecast extends to Dec 2026
    scale = C.TARGET_REQUESTS * 0.93 / exp.Lambda.sum()
    base_rev = req[(req.Status == "Closed") & (req.CreatedAt < "2025-01-01")]
    rev_per_req = (base_rev.groupby("Region").InvoiceAmount.sum() / base_rev.groupby("Region").size())
    rows = []
    months = pd.date_range(START, "2026-12-01", freq="MS")
    for i, m in enumerate(months):
        for region in REGION_NAMES:
            if m in vol.index.get_level_values(0):
                v = vol.loc[(m, region)] * scale
            else:  # extrapolate forecast for Oct-Dec 2026
                lam = sum(REGION_SHARE[region] * s.Share * 1.0055 ** i *
                          seasonality(s.ServiceCategory, s.ServiceType, m.month) for _, s in SVC.iterrows())
                v = lam * scale
            price_uplift = 1.03 ** (m.year - 2024)
            rows.append({
                "Month": m.date(), "Region": region,
                "RevenueTarget": round(v * 1.07 * rev_per_req[region] * price_uplift * 0.99, -2),
                "SLATarget": 0.92 if region == "Toronto" else 0.90,
                "CSATTarget": 4.0,
                "ProductivityTarget": 26,     # closed requests per technician per month
                "BacklogTarget": int(round(v * 0.07)),  # open requests at month end
            })
    return pd.DataFrame(rows)


# ============================================================================
# 5. Inject data-quality defects into the extracts
# ============================================================================
def inject_defects(fsm, billing, csat, customers, techs):
    log = []

    def pick(df, k, mask=None):
        pool = df.index if mask is None else df.index[mask]
        return rng.choice(pool, size=min(k, len(pool)), replace=False)

    # FSM ---------------------------------------------------------------------
    fsm = fsm.copy()
    fsm["CreatedAt"] = fsm.CreatedAt.dt.strftime("%Y-%m-%d %H:%M:%S")
    fsm["ClosedAt"] = fsm.ClosedAt.dt.strftime("%Y-%m-%d %H:%M:%S")

    idx = pick(fsm, int(len(fsm) * 0.05))
    fsm.loc[idx, "Region"] = [rng.choice(C.REGION_ALIASES[r]) for r in fsm.loc[idx, "Region"]]
    log.append(("fsm_service_requests", "Inconsistent region spelling", len(idx)))

    idx = pick(fsm, 210)
    fsm.loc[idx, "CustomerID"] = None
    log.append(("fsm_service_requests", "Null CustomerID", len(idx)))

    idx = pick(fsm, 130)
    fsm.loc[idx, "CreatedAt"] = rng.choice(["2025-02-30 10:15:00", "N/A", "", "00/00/0000", "2024-13-07 08:00:00"], len(idx))
    log.append(("fsm_service_requests", "Invalid CreatedAt date", len(idx)))

    closed = fsm.Status.eq("Closed") & pd.to_datetime(fsm.CreatedAt, errors="coerce", format="%Y-%m-%d %H:%M:%S").notna()
    idx = pick(fsm, 180, closed)
    c = pd.to_datetime(fsm.loc[idx, "CreatedAt"])
    fsm.loc[idx, "ClosedAt"] = (c - pd.to_timedelta(rng.uniform(2, 72, len(idx)), "h")).dt.strftime("%Y-%m-%d %H:%M:%S")
    log.append(("fsm_service_requests", "ClosedAt before CreatedAt", len(idx)))

    idx = pick(fsm, 320, fsm.Status.eq("Closed"))
    fsm.loc[idx, "TechnicianID"] = None
    log.append(("fsm_service_requests", "Closed request missing TechnicianID", len(idx)))

    dup = fsm.loc[pick(fsm, 640)]
    fsm = pd.concat([fsm, dup]).sort_index(kind="stable").reset_index(drop=True)
    log.append(("fsm_service_requests", "Exact duplicate rows", len(dup)))

    # Billing -----------------------------------------------------------------
    billing = billing.copy()
    idx = pick(billing, 90)
    billing.loc[idx, "LabourCost"] = -billing.loc[idx, "LabourCost"]
    idx2 = pick(billing, 70, billing.PartsCost > 0)
    billing.loc[idx2, "PartsCost"] = -billing.loc[idx2, "PartsCost"]
    log.append(("billing_invoices", "Negative cost values", len(idx) + len(idx2)))

    dup = billing.loc[pick(billing, 110)]
    billing = pd.concat([billing, dup]).reset_index(drop=True)
    log.append(("billing_invoices", "Duplicate invoice rows", len(dup)))

    orphans = billing.sample(45, random_state=C.SEED).copy()
    orphans["ServiceRequestID"] = [f"SR-9{rng.integers(100000, 999999)}" for _ in range(len(orphans))]
    orphans["InvoiceID"] = [f"INV-9{i:06d}" for i in range(len(orphans))]
    billing = pd.concat([billing, orphans]).reset_index(drop=True)
    log.append(("billing_invoices", "Orphan invoices (no matching service request)", len(orphans)))

    # CSAT --------------------------------------------------------------------
    csat = csat.copy()
    idx = pick(csat, 260)
    csat.loc[idx, "CSATScore"] = rng.choice([0, 6, 10, -1, 55], len(idx))
    log.append(("csat_survey_responses", "CSAT score outside 1-5", len(idx)))

    dup = csat.loc[pick(csat, 160)].copy()
    dup["ResponseDate"] = (pd.to_datetime(dup.ResponseDate) + pd.Timedelta(days=1)).dt.date
    dup["SurveyResponseID"] = [f"SRV-9{i:05d}" for i in range(len(dup))]
    csat = pd.concat([csat, dup]).reset_index(drop=True)
    log.append(("csat_survey_responses", "Customer answered the same survey twice", len(dup)))

    # CRM ---------------------------------------------------------------------
    customers = customers.drop(columns=["HomeRegion", "NumAssets"]).copy()
    idx = pick(customers, 220)
    customers.loc[idx, "Province"] = rng.choice(["Ontario", "on", "Ont.", "ON "], len(idx))
    log.append(("crm_customers", "Inconsistent province values", len(idx)))
    idx = pick(customers, 60)
    customers.loc[idx, "CustomerName"] = customers.loc[idx, "CustomerName"].str.upper() + "  "
    log.append(("crm_customers", "Customer name casing / whitespace", len(idx)))
    dup = customers.loc[pick(customers, 12)]
    customers = pd.concat([customers, dup]).reset_index(drop=True)
    log.append(("crm_customers", "Duplicate customer rows", len(dup)))

    return fsm, billing, csat, customers, techs, pd.DataFrame(log, columns=["SourceFile", "DefectType", "RowsAffected"])


# ============================================================================
def main():
    C.RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("Generating customers and technicians...")
    customers = make_customers()
    techs = make_technicians()

    print("Simulating service requests...")
    req = make_requests(customers, techs)
    billing = make_billing(req)
    csat = make_csat(req)
    targets = make_targets(req)

    fsm = req[["ServiceRequestID", "CustomerID", "AssetID", "TechnicianID", "Region", "ServiceType",
               "Priority", "Status", "CreatedAt", "ClosedAt"]]
    fsm, billing, csat, customers_raw, techs_raw, defects = inject_defects(fsm, billing, csat, customers, techs)

    sla = PRI[["Priority", "SLAHours"]].assign(EffectiveFrom="2020-01-01")
    svc_catalogue = SVC[["ServiceCategory", "ServiceType", "BasePrice"]].rename(columns={"BasePrice": "ListPrice2024"})
    regions = pd.DataFrame([(r[0], r[1], r[2]) for r in C.REGIONS], columns=["Region", "Province", "RegionalManager"])

    out = {
        "crm_customers.csv": customers_raw,
        "hr_technicians.csv": techs_raw,
        "fsm_service_requests.csv": fsm,
        "billing_invoices.csv": billing,
        "csat_survey_responses.csv": csat,
        "sla_policy.csv": sla,
        "service_catalogue.csv": svc_catalogue,
        "regions.csv": regions,
        "regional_targets.csv": targets,
    }
    for name, df in out.items():
        df.to_csv(C.RAW_DIR / name, index=False)
        print(f"  wrote {name:30s} {len(df):>7,} rows")
    defects.to_csv(C.RAW_DIR / "_injected_defects_log.csv", index=False)
    print("\nInjected defects:\n" + defects.to_string(index=False))


if __name__ == "__main__":
    main()
