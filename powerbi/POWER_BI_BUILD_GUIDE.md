# Power BI Build Guide

Step-by-step instructions to build `enterprise_service_analytics.pbix` from the star schema in `data/model/`. Budget about two working days for steps 1–9.

> **Rule of thumb for the whole build:** every number on a dashboard should be explainable and reproducible. Section 10 lists the exact values your visuals should show, so you can prove your DAX is correct.

---

## 1. Desktop settings (do this first)

*File → Options and settings → Options*

| Setting | Value | Why |
|---|---|---|
| Current file → Data Load → **Auto date/time** | **Off** | We have a proper `DimDate`. Auto date/time creates a hidden date table per date column and bloats the model. |
| Current file → Data Load → **Autodetect relationships** | **Off** | We define relationships deliberately. |
| Current file → Regional settings → Locale | English (Canada) | Currency and date formats. |

---

## 2. Load the data (Power Query)

1. **Home → Transform data → Manage Parameters → New**: `ProjectFolder` (Text) = full path to your repo folder.
2. For each of the 10 tables, **New Source → Blank Query → Advanced Editor**, paste the matching block from `power_query.m`, and rename the query to the table name.
3. Optional (good for interviews): add the `stg_FSM_Cleaned` query from the bottom of `power_query.m`. It re-implements the cleaning rules in M (dedupe, region mapping table + merge, safe date parsing with `try … otherwise`, a `DQ_Issue` flag column). Right-click it → **uncheck Enable load** so it doesn't bloat the model, and screenshot its Applied Steps for your README.
4. **Close & Apply**.

---

## 3. Model view – relationships

Lay tables out as a star: facts in the middle, dimensions around them.

| From (many) | To (one) | Active | Cross-filter |
|---|---|---|---|
| FactServiceRequests[CustomerKey] | DimCustomer[CustomerKey] | ✅ | Single |
| FactServiceRequests[TechnicianKey] | DimTechnician[TechnicianKey] | ✅ | Single |
| FactServiceRequests[RegionKey] | DimRegion[RegionKey] | ✅ | Single |
| FactServiceRequests[ServiceTypeKey] | DimServiceType[ServiceTypeKey] | ✅ | Single |
| FactServiceRequests[PriorityKey] | DimPriority[PriorityKey] | ✅ | Single |
| FactServiceRequests[CreatedDateKey] | DimDate[DateKey] | ✅ | Single |
| FactServiceRequests[ClosedDateKey] | DimDate[DateKey] | ❌ **inactive** (dotted) | Single |
| FactTargets[RegionKey] | DimRegion[RegionKey] | ✅ | Single |
| FactTargets[MonthStartDateKey] | DimDate[DateKey] | ✅ | Single |
| FactBacklogSnapshot[RegionKey] | DimRegion[RegionKey] | ✅ | Single |
| FactBacklogSnapshot[SnapshotDateKey] | DimDate[DateKey] | ✅ | Single |

`SecurityUserRegion` stays **disconnected** (used only by the RLS rule).

**Why the inactive relationship?** A fact can only have one active path to `DimDate`. Volume and revenue use the created date; SLA, CSAT and resolution use the closed date by activating the second relationship inside the measure with `USERELATIONSHIP`. This is the "role-playing dimension" pattern — expect to be asked about it.

### Model hygiene

- **Mark as date table:** select `DimDate` → Table tools → Mark as date table → `Date`.
- **Sort by column:** `DimDate[Month]` by `MonthNumber`, `MonthShort` by `MonthNumber`, `DayOfWeek` by `DayOfWeekNumber`, `YearMonth` by `YearMonthKey`, `DimPriority[Priority]` by `SortOrder`.
- **Hide** every key column and every fact column that is only used inside measures (all `*Key` columns, flags, raw cost columns). Report authors should only see dimensions and measures.
- **Default summarization:** set to *Don't summarize* for numeric attributes like `Year`, `SLAHours`, `TenureYears`.
- **Hierarchy:** in `DimDate` create *Calendar*: Year → Quarter → Month → Date, and *Fiscal*: FiscalYear → FiscalQuarter → YearMonth.
- **Data categories:** `DimCustomer[City]` = City, `DimRegion[Province]` = State or Province (enables the map visual).

---

## 4. Measures

1. Home → Enter data → create an empty table named `_Measures`, load it.
2. Add the measures from `measures.dax` (or paste them in bulk with Tabular Editor).
3. Put them in display folders: `01 Volume`, `02 Service Level`, `03 Customer`, `04 Financial`, `05 Time Intelligence`, `06 Targets & Performance`, `07 Ranking`, `08 Root Cause`, `09 Dynamic / UX`.
4. Create the `KPI Selector` calculated table (code is in the comments of section 09).
5. Delete the dummy column in `_Measures` – the table icon turns into a calculator.

---

## 5. Theme and canvas

- View → Themes → Browse for themes → `northline_theme.json`.
- Canvas 1280 × 720. Put a 56 px header band on each page: title (left), `Data As Of` card (right), slicers for **Year / Month** and **Region** in a consistent position on every page.
- Add a page-level filter `DimDate[IsAfterSnapshot] = 0` on every page so the empty Oct–Dec 2026 dates never show.

---

## 6. Report pages

### Page 1 – Executive Overview
*Question it answers: "Are we on track, and where should I look?"*

| Visual | Fields |
|---|---|
| 6 KPI cards (new card visual) | `Service Revenue` (reference: `Revenue YoY %`), `SLA Compliance %` (ref: `SLA Variance (pts)`), `Avg CSAT` (ref: `CSAT Variance`), `Backlog (Month-End Snapshot)` (ref: `Backlog vs Target`), `Avg Resolution Hours`, `Completed Requests` |
| Line + clustered column | X: `DimDate[YearMonth]`; columns `Service Revenue`; line `Revenue Target` |
| Line chart | X: `YearMonth`; `SLA Compliance %`, `SLA Target` (dashed) |
| Table "Regional scorecard" | `Region`, `Service Revenue`, `Revenue Achievement %`, `SLA Compliance %`, `SLA Status Icon`, `Avg CSAT`, `Backlog (Month-End Snapshot)`, `Regional Performance Score`. Conditional format the SLA column background with *Field value* = `SLA Status Color`. |
| Donut or bar | `Service Revenue` by `DimServiceType[ServiceCategory]` |
| Card "Exceptions" | `Regions Below SLA Target` |

### Page 2 – Operations Performance
*"How is the work flowing?"*

- Column chart: `Total Requests` by `YearMonth`, legend `ServiceCategory` (seasonality is very visible: emergency repairs spike in winter, maintenance in spring and autumn).
- Line: `Backlog (Month-End Snapshot)` and `Backlog Target` by month.
- Matrix: rows `Priority`, columns `ServiceCategory`, values `SLA Compliance %` with background color scale.
- Bar: `Median Resolution Hours` and `P90 Resolution Hours` by `ServiceType`.
- Small table: `SLAStatus` with `Total Requests` (shows open-breached tickets that need attention now).
- **KPI selector:** slicer on `KPI Selector[KPI]` + line chart of `Selected KPI Value` by month, title from `Selected KPI Title` (Format → Title → fx).

### Page 3 – Regional Performance
*"Which regions are under-performing against target?"*

- Slicer: single-select `Region` (tiles).
- Title text box bound to `Report Title Region`.
- Bullet-style bar charts (bar = actual, error-bar/target line = target) for Revenue, SLA, CSAT, Backlog.
- Line: `SLA Compliance % Rolling 3M` by month with `SLA Compliance % (All Regions)` as a benchmark line.
- Table: Region, `Revenue YTD`, `Revenue YTD YoY %`, `Region Rank (Revenue)`, `Region Rank (SLA)`, `Completed per Technician per Month` vs `Productivity Target`.
- Map (optional): `DimCustomer[City]` bubbles sized by `Service Revenue`.

### Page 4 – Technician Analysis
*"Who needs support, and why rankings can mislead."*

- Scatter: X `Completed Requests`, Y `First-Time Fix Rate`, size `Revenue per Technician`, legend `SkillLevel`, details `TechnicianName`. Add an average line on both axes.
- Table: TechnicianName, Region, SkillLevel, TenureBand, `Completed Requests`, `First-Time Fix Rate`, `SLA Compliance %`, `Avg CSAT`, `Technician Rank (FTF)`.
- Column: `First-Time Fix Rate` by `SkillLevel` × `ServiceCategory`.
- Text box with the caveat (this is the point the plan asked you to make):
  > Rankings only include technicians with 150+ completed jobs. Technicians who take more Critical/Emergency work and newer hires on harder installations will look worse on raw averages — compare within region and skill level, not across the whole company.

### Page 5 – Root Cause & Exceptions
*"SLA compliance fell in Ottawa — why?"*

Build it as a guided investigation, top to bottom:

1. Line: `SLA Compliance %` by month for Ottawa vs `SLA Compliance % (All Regions)`.
2. **Decomposition tree:** Analyze `SLA Breaches`, explain by `ServiceType`, `Priority`, `SkillLevel`, `CustomerSegment`, `DayOfWeek`. Use the *High value* AI split.
3. Column: `Emergency Repair Requests` by month, with `Emergency Repair YoY %` in the tooltip.
4. Line + column: `Requests per Active Technician` (line) and `Active Technicians` (columns) by month – capacity falls in Feb 2026 just as demand rises.
5. **Key influencers** visual: analyze `SLAStatus` = Breached, explain by `ServiceType`, `Priority`, `DayOfWeek`, `CreatedHour`, `SkillLevel`. It surfaces the Friday-afternoon/Saturday effect.
6. A text box (or Smart narrative) stating the conclusion in one sentence (see `docs/analysis_findings.md` once you've found it yourself).

---

## 7. Interactivity

- **Drill-through:** create a hidden page *Request Detail* with a table of individual requests (ServiceRequestID, dates, customer, technician, SLAStatus, revenue, CSAT). Add `DimRegion[Region]`, `DimTechnician[TechnicianName]` and `DimServiceType[ServiceType]` as drill-through fields. Right-click any bar → Drill through.
- **Report-page tooltip:** a small 320 × 240 page (Page information → Allow use as tooltip) showing `SLA Compliance %`, `Avg CSAT`, `Backlog`, and a sparkline of revenue. Assign it to the regional table on page 1.
- **Bookmarks:** on page 5, a "Show/Hide analyst notes" toggle using a bookmark + button.
- **Sync slicers:** View → Sync slicers so Year and Region carry across pages.

---

## 8. Row-Level Security

*Modeling → Manage roles*

**Option A – Dynamic RLS (recommended; one role for every manager)**

Role `Regional Manager`, table `DimRegion`, DAX filter:

```DAX
DimRegion[RegionKey]
    IN CALCULATETABLE (
        VALUES ( SecurityUserRegion[RegionKey] ),
        SecurityUserRegion[UserEmail] = USERPRINCIPALNAME ()
    )
```

`SecurityUserRegion.csv` maps each user email to the regions they may see. Executives and the VP Operations are mapped to all six regions; each regional manager to one. Adding a new manager is a data change, not a model change.

**Option B – Static roles (simpler to explain)**

| Role | Table | Filter |
|---|---|---|
| Executive | — | no filter |
| Toronto Manager | DimRegion | `[Region] = "Toronto"` |
| Ottawa Manager | DimRegion | `[Region] = "Ottawa"` |

Also add `DimTechnician[Region] = …` if managers should not even see other regions' technician names.

**Test it:** Modeling → View as → *Other user* = `sophie.tremblay@northline.example` + role `Regional Manager`. You should only see Ottawa. Screenshot this for the README.

> Note: `FactTargets` and `FactBacklogSnapshot` are filtered too, because they relate to `DimRegion`.

---

## 9. Performance checks

- **Performance analyzer** (Optimize → Performance analyzer): record each page; every visual should render in < 500 ms on this data volume.
- Use `DIVIDE` instead of `/`, variables (`VAR`) for repeated expressions, and avoid iterating the fact table (`FILTER(FactServiceRequests, …)`) when a column predicate works.
- Remove unused columns in Power Query (e.g. `AssetID`, `RepeatOfRequestID` if you don't use them) – column count matters more than row count in VertiPaq.
- Optional: run **DAX Studio → View Metrics** (VertiPaq Analyzer) and screenshot model size.

---

## 10. Validate your numbers

With **no slicers applied** (all regions, all dates up to 30 Sep 2026) your measures should return:

| Measure | Expected |
|---|---|
| Total Requests | 75,909 |
| Cancelled Requests | 1,317 |
| Service Revenue | $52,658,152 |
| Direct Cost | $24,200,518 |
| Gross Margin % | 54.0% |
| SLA Compliance % | 91.5% |
| Avg CSAT | 4.06 |
| CSAT Responses | 22,884 |
| First-Time Fix Rate | 89.1% |
| Repeat Visit Rate | 10.7% |
| Open Requests (Current) | 197 |
| Backlog (Month-End Snapshot) at Sep 2026 | 197 |
| Service Revenue, calendar 2025 | $19,246,594 |
| Revenue Target, calendar 2025 | $19,462,700 |
| Revenue YTD, Sep 2026 | $15,701,343 |
| Revenue YTD PY (Jan–Sep 2025) | $14,628,906 |
| Revenue, fiscal FY2026 (Apr 2025–Mar 2026) | $19,747,706 |
| Ottawa, Aug 2026: SLA Compliance % | 74.9% |
| Ottawa, Aug 2026: Avg CSAT | 3.46 |

The same figures come out of `sql/` (`data/sql_output/`). If Power BI and SQL disagree, one of them has a filter-context or attribution bug – finding it is excellent interview material.

> If you regenerate the data with a different `SEED` in `src/config.py`, these values change; re-run `python run_pipeline.py` and use the SQL outputs as your reference.
