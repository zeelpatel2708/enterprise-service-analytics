# KPI Definitions

Each KPI has one definition, used identically in SQL (`sql/`) and DAX (`powerbi/measures.dax`).

**Date attribution.** Volume and financial KPIs use the request's **created** date. Outcome KPIs (SLA, resolution time, CSAT, first-time fix) use the **closed** date, because the outcome does not exist until the job is finished. In Power BI this is the inactive `ClosedDateKey` relationship activated with `USERELATIONSHIP`.

## Operational

| KPI | Definition | Formula | Notes |
|---|---|---|---|
| Total Service Requests | Requests created in the period | `COUNT(requests)` | Includes cancelled |
| Completed Requests | Requests closed in the period | `COUNT(Status = Closed)` by closed date | |
| Open Requests | Requests currently Open or In Progress | `COUNT(IsOpen = 1)` at snapshot | Live backlog |
| Backlog | Requests open at the end of the period | created ≤ period end AND (not closed OR closed after period end), excl. cancelled | Semi-additive: take the last value, never sum months |
| Avg Resolution Time | Mean elapsed hours from creation to closure | `AVG(ClosedAt − CreatedAt)` | Skewed by long "waiting for parts" jobs |
| Median Resolution Time | 50th percentile of elapsed hours | `MEDIAN(...)` | Preferred for operations reviews |
| SLA Compliance % | Share of closed requests closed within the contracted SLA for their priority | `SUM(SLAMet) / COUNT(closed)` | SLA: Critical 8h, High 24h, Medium 72h, Low 120h |
| Repeat Visit Rate | Share of non-cancelled requests that are repeat visits | `SUM(RepeatVisitFlag) / (requests − cancelled)` | Repeat visit = **Repair** request on the **same asset** within **30 days** after a previous closure on that asset |
| First-Time Fix Rate | Share of closed jobs that did **not** lead to a repeat visit within 30 days | `SUM(FTF) / COUNT(FTF measurable)` | Only measurable 30 days after closure; recent jobs are excluded rather than assumed fixed |

## Financial

| KPI | Definition | Formula |
|---|---|---|
| Service Revenue | Invoiced amount | `SUM(InvoiceAmount)` |
| Revenue per Service Request | Average value of billable work | `Revenue / COUNT(BillingType = Billable)` |
| Labour Cost | Loaded labour cost (wage × hours × 1.30 burden) | `SUM(LabourCost)` |
| Parts Cost | Parts at purchase cost | `SUM(PartsCost)` |
| Gross Service Margin | Revenue minus direct cost | `Revenue − Labour − Parts`; % = ÷ Revenue |
| Warranty Cost | Direct cost of free callbacks | `SUM(cost) WHERE BillingType = Warranty` |

## Customer

| KPI | Definition | Formula | Notes |
|---|---|---|---|
| Average CSAT | Mean post-job survey score (1–5) | `AVG(CSATScore)` | ~30% response rate; unhappy customers respond more often (non-response bias – mention it) |
| Low-CSAT Requests | Responses scoring 1 or 2 | `COUNT(CSAT ≤ 2)` | |
| Customer Retention Proxy | Share of customers with a request in the last 90 days | `COUNT(Active) / COUNT(customers)` | A proxy – there is no contract-end date in the data |
| Repeat Service Calls | Count of repeat visits | `SUM(RepeatVisitFlag)` | |

## Workforce

| KPI | Definition | Formula | Notes |
|---|---|---|---|
| Active Technicians | Technicians who closed ≥ 1 job in the period | `DISTINCTCOUNT(TechnicianKey > 0)` | Excludes Unknown/Unassigned |
| Requests per Technician | Closed jobs per active technician per month | average over months of `Completed / Active Technicians` | Target 26 |
| Revenue per Technician | Revenue of jobs closed ÷ active technicians | | |
| Resolution Time per Technician | Avg Resolution Time sliced by technician | | Compare within priority mix |
| SLA Compliance per Technician | SLA Compliance % sliced by technician | | Ranked only with ≥ 150 jobs |

## Targets & variance

| KPI | Definition |
|---|---|
| Target Achievement % | Actual ÷ Target (revenue) |
| Variance | Actual − Target |
| SLA Variance (pts) | SLA Compliance % − SLA Target, in percentage points. Company-level SLA target is weighted by each region's closed volume. |
| Backlog vs Target | Month-end backlog − backlog target (positive is bad) |
| Regional Performance Score | Average of four capped ratios × 100: revenue achievement, SLA ÷ target, CSAT ÷ target, backlog target ÷ backlog. Each capped at 110% so one strong KPI cannot hide a weak one. |

## Time intelligence

| KPI | Definition |
|---|---|
| Revenue YTD | Calendar year to date |
| Revenue FYTD | Fiscal year to date (April start) |
| Revenue Previous Year | Same period last year (`SAMEPERIODLASTYEAR`) |
| YoY Revenue % | (Revenue − PY) ÷ PY |
| MoM Revenue % | (Revenue − previous month) ÷ previous month |
| Rolling 3 / 12-Month Revenue | Sum over the trailing 3 / 12 months ending at the last visible date |
| Backlog Growth % | (Backlog − previous month backlog) ÷ previous month backlog |

## Ranking

| KPI | Definition |
|---|---|
| Region Rank | Dense rank of regions on the selected KPI within the current selection |
| Technician Rank | Dense rank on first-time fix rate among technicians with ≥ 150 completed jobs, within the current filter (e.g. region) |
| Revenue Contribution % | Share of the visible total |
