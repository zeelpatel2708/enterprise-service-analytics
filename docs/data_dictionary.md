# Data Dictionary

Star schema produced by `src/build_model.py` (files in `data/model/`).

```
                 DimDate (role-playing: Created / Closed / Month / Snapshot)
                    │
DimCustomer ─┐      │      ┌─ DimServiceType
DimTechnician ┼── FactServiceRequests ──┼─ DimPriority
DimRegion ───┘      │      └─ (DimRegion also filters FactTargets & FactBacklogSnapshot)
```

## DimDate

One row per calendar day, 2024-01-01 to 2026-12-31. Marked as the date table in Power BI. Fiscal year runs April–March.

Rows: 1,096

| Column | Type | Description |
|---|---|---|
| DateKey | integer | Surrogate key, YYYYMMDD integer |
| Date | date | Calendar date |
| Year | integer | Calendar year |
| QuarterNumber | integer | 1–4 |
| Quarter | text | Q1–Q4 |
| YearQuarter | text | e.g. 2026-Q3 |
| MonthNumber | integer | 1–12 |
| Month | text | Full month name (sort by MonthNumber) |
| MonthShort | text | Jan–Dec |
| YearMonth | text | e.g. 2026-09 (sort by YearMonthKey) |
| YearMonthKey | integer | e.g. 202609 |
| MonthStartDate | date | First day of the month |
| MonthEndDate | date | Last day of the month |
| ISOWeek | integer | ISO week number |
| Day | integer | Day of month |
| DayOfWeekNumber | integer | Monday = 1 … Sunday = 7 |
| DayOfWeek | text | Day name |
| IsWeekend | integer | 1 = Saturday/Sunday |
| FiscalYear | text | FY label; FY2026 = Apr 2025–Mar 2026 |
| FiscalQuarter | text | FQ1 = Apr–Jun |
| FiscalMonthNumber | integer | April = 1 |
| IsAfterSnapshot | integer | 1 = date after the 30 Sep 2026 extract (no data yet) |
| IsCompleteMonth | integer | 1 = month whose billing has fully posted (month end + 15 days ≤ snapshot) |

## DimRegion

One row per service region.

Rows: 6

| Column | Type | Description |
|---|---|---|
| RegionKey | integer | Surrogate key |
| Region | text | Region name (master list) |
| Province | text | Province code |
| RegionalManager | text | Accountable manager |
| RegionalManagerEmail | text | Login used by dynamic RLS |

## DimCustomer

One row per customer account (CRM). Duplicates removed, names and province standardised.

Rows: 1,400

| Column | Type | Description |
|---|---|---|
| CustomerKey | integer | Surrogate key |
| CustomerID | text | CRM business key (CUST-xxxxx) |
| CustomerName | text | Company name |
| Industry | text | Industry |
| CustomerSegment | text | Enterprise / Government / Mid-Market / Small Business |
| City | text | Customer city |
| Province | text | Province (standardised to ON) |
| AccountStartDate | date | Date the account was opened |
| FirstRequestDate | date | First service request in the data |
| LastRequestDate | date | Most recent service request |
| ActivityStatus | text | Retention proxy: Active (<90 days since last request), Cooling (90–180), At Risk (180+), No Activity |

## DimTechnician

One row per technician (HR), plus two special members: -1 Unknown (closed work with no technician recorded) and -2 Unassigned (new tickets not yet dispatched).

Rows: 111

| Column | Type | Description |
|---|---|---|
| TechnicianKey | integer | Surrogate key (-1 Unknown, -2 Unassigned) |
| TechnicianID | text | HR business key (TECH-xxxx) |
| TechnicianName | text | Full name |
| SkillLevel | text | Junior / Intermediate / Senior / Expert |
| Specialization | text | Trade specialisation |
| Region | text | Home region |
| HireDate | date | Hire date |
| TerminationDate | date | Leaving date (blank = still employed) |
| IsActive | integer (nullable) | 1 = employed at snapshot |
| TenureYears | decimal | Years of service at snapshot (or at leaving) |
| TenureBand | text | < 1 yr / 1-3 yrs / 3-6 yrs / 6+ yrs |

## DimServiceType

Service catalogue.

Rows: 8

| Column | Type | Description |
|---|---|---|
| ServiceTypeKey | integer | Surrogate key |
| ServiceCategory | text | Repair / Maintenance / Inspection / Installation |
| ServiceType | text | Specific service |
| ListPrice2024 | integer | Base list price in 2024 (rises 3% each January) |

## DimPriority

Contracted SLA policy by priority.

Rows: 4

| Column | Type | Description |
|---|---|---|
| PriorityKey | integer | Surrogate key (= sort order) |
| Priority | text | Critical / High / Medium / Low |
| SLAHours | integer | Hours allowed from creation to closure |
| PriceMultiplier | decimal | Price uplift for urgency |
| SortOrder | integer | Display order |

## FactServiceRequests

Transaction fact. **Grain: one row per service request.** Combines FSM tickets, billing (job costing) and the CSAT survey.

Rows: 75,909

| Column | Type | Description |
|---|---|---|
| ServiceRequestID | text | FSM ticket number (degenerate dimension) |
| AssetID | text | Customer equipment/site serviced – used to detect repeat visits |
| CustomerKey | integer | → DimCustomer |
| TechnicianKey | integer | → DimTechnician |
| RegionKey | integer | → DimRegion |
| ServiceTypeKey | integer | → DimServiceType |
| PriorityKey | integer | → DimPriority |
| CreatedDateKey | integer | → DimDate (active relationship) |
| ClosedDateKey | integer (nullable) | → DimDate (inactive; blank while open) |
| CreatedAt | datetime | Ticket creation timestamp |
| ClosedAt | datetime | Closure timestamp (Closed only) |
| CreatedHour | integer | Hour of day the ticket was raised (0–23) |
| Status | text | Open / In Progress / Closed / Cancelled |
| IsClosed | integer | 1 = Closed |
| IsOpen | integer | 1 = Open or In Progress |
| IsCancelled | integer | 1 = Cancelled |
| SLAHours | decimal | SLA allowed for the ticket's priority |
| ResolutionHours | decimal | Elapsed hours created → closed (Closed only) |
| SLAMet | integer (nullable) | 1 = closed within SLA, 0 = breached, blank = not closed |
| SLAStatus | text | Met / Breached / Open - Within SLA / Open - Breached / Not Applicable |
| OpenAgeHours | decimal | Age at snapshot for open tickets |
| RepeatVisitFlag | integer | 1 = Repair request on the same asset within 30 days of a previous closure |
| RepeatOfRequestID | text | The earlier request this one is a repeat of |
| FirstTimeFixFlag | integer (nullable) | 1 = no repeat visit within 30 days; 0 = caused a repeat; blank = closed < 30 days ago or not closed |
| InvoiceID | text | Billing invoice (blank = not invoiced) |
| IsInvoiced | integer | 1 = has a valid invoice |
| BillingType | text | Billable / Warranty (free callback) / Not Invoiced |
| WorkHours | decimal | On-site labour hours |
| LabourCost | decimal | Loaded labour cost ($) |
| PartsCost | decimal | Parts cost at purchase price ($) |
| ServiceRevenue | decimal | Invoice amount ($); 0 for warranty work |
| CSATScore | integer (nullable) | Survey score 1–5 (blank = no response) |
| DQ_MissingTechnician | integer | 1 = technician was missing in the source (mapped to Unknown) |

## FactTargets

Budget fact. **Grain: one row per region per month** (Jan 2024 – Dec 2026).

Rows: 216

| Column | Type | Description |
|---|---|---|
| RegionKey | integer | → DimRegion |
| MonthStartDateKey | integer | → DimDate (first day of month) |
| RevenueTarget | decimal | Monthly revenue budget ($) |
| SLATarget | decimal | Target SLA compliance (0.90; Toronto 0.92) |
| CSATTarget | decimal | Target average CSAT |
| ProductivityTarget | integer | Closed requests per technician per month |
| BacklogTarget | integer | Maximum open requests at month end |

## FactBacklogSnapshot

Periodic snapshot fact. **Grain: one row per region per month-end.** Semi-additive – never sum across months.

Rows: 198

| Column | Type | Description |
|---|---|---|
| RegionKey | integer | → DimRegion |
| SnapshotDateKey | integer | → DimDate (month-end date) |
| OpenRequests | integer | Requests open at 23:59:59 on the snapshot date |
| OpenBreachedSLA | integer | …of which already past their SLA |
| OpenOver7Days | integer | …of which older than 7 days |

## SecurityUserRegion

Security mapping for dynamic row-level security. Disconnected (no relationship).

Rows: 18

| Column | Type | Description |
|---|---|---|
| UserEmail | text | User principal name |
| RegionKey | integer | Region the user may see |
| Role | text | Executive / Operations Manager / Regional Manager |

## Raw source extracts (`data/raw/`)

| File | Source system | Contents |
|---|---|---|
| crm_customers.csv | CRM | Customer accounts |
| hr_technicians.csv | HR | Workforce, hire and leaving dates |
| fsm_service_requests.csv | Field Service Management | Tickets: customer, asset, technician, region, type, priority, status, timestamps |
| billing_invoices.csv | Finance | One invoice per completed job, with job-costing (labour, parts) |
| csat_survey_responses.csv | Survey tool | Post-job customer satisfaction (1–5) |
| sla_policy.csv | Contracts | SLA hours by priority |
| service_catalogue.csv | Pricing | Service categories, types and list prices |
| regions.csv | Operations | Regions and managers |
| regional_targets.csv | FP&A | Monthly budget per region |
| _injected_defects_log.csv | (generator) | What defects were deliberately injected – the answer key for data quality |
