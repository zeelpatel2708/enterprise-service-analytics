# Business Requirements

## Company context

**Northline Field Services** (fictional) maintains, repairs, inspects and installs commercial equipment – HVAC, electrical, mechanical and building-control systems – for about 1,400 business and public-sector customers across six Ontario regions: Toronto, Mississauga, Ottawa, Hamilton, Kitchener-Waterloo and London. Roughly 110 field technicians complete about 2,300 service requests a month.

## Problem statement

Operational data lives in five systems that were never designed to work together:

| System | Owner | What it knows |
|---|---|---|
| CRM | Sales | Customers, segments, account start dates |
| HR | People team | Technicians, skill levels, hire and leaving dates |
| Field Service Management (FSM) | Operations | Tickets, priorities, timestamps, assignments |
| Billing / job costing | Finance | Invoices, labour and parts cost |
| Survey tool | Customer Experience | Post-job satisfaction scores |

Each month an analyst spends two to three days copying extracts into spreadsheets to produce a static KPI pack. Numbers differ between departments (Finance revenue ≠ Operations revenue), data quality problems are fixed by hand and never recorded, and by the time leadership sees the pack it is three weeks old. Nobody can answer *why* a number moved.

## Stakeholders and their questions

| Stakeholder | Key questions | Primary page |
|---|---|---|
| CEO / Executive team | Are we on track against budget? Which regions need attention? Is customer satisfaction slipping? | Executive Overview |
| VP Operations | Why is backlog increasing? Which service types take longest? Where are SLAs being missed? | Operations, Root Cause |
| Regional Managers | How does my region compare with target and with peers? What is driving my month-over-month change? | Regional Performance |
| Service Delivery Managers | Which technicians need coaching? Are repeat visits increasing? | Technician Analysis |
| Finance | Which customers generate the most revenue? What is our gross margin by service line? What do callbacks cost us? | Executive, Regional |

## Business questions this project must answer

1. Which regions are missing SLA targets?
2. Why is backlog increasing?
3. Which technicians have the highest productivity – and is that comparison fair?
4. Which service types have the longest resolution times?
5. Which customers generate the most revenue, and how concentrated is revenue?
6. Are repeat service calls increasing, and what do they cost?
7. Which regions are under-performing against targets?
8. Is customer satisfaction decreasing, and what drives low scores?
9. What is driving month-over-month changes?

## Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Integrate the five source extracts into a single dimensional model | Must |
| FR-02 | Detect, fix or quarantine data-quality defects with a reason code; publish a data-quality report | Must |
| FR-03 | Reconcile billing revenue to operational tickets | Must |
| FR-04 | Provide 15–20 KPIs with documented, unambiguous definitions | Must |
| FR-05 | Compare actuals to monthly regional targets (revenue, SLA, CSAT, productivity, backlog) | Must |
| FR-06 | Support time comparison: MoM, YoY, YTD, fiscal YTD, rolling 3 and 12 months | Must |
| FR-07 | Allow drill-down from company → region → service type → technician → individual request | Must |
| FR-08 | Restrict regional managers to their own region (row-level security) | Must |
| FR-09 | Provide a guided root-cause page for SLA exceptions | Should |
| FR-10 | Rank technicians fairly (minimum volume, within peer group) | Should |
| FR-11 | Automated data-quality tests that must pass before publishing | Should |

## Non-functional requirements

- **Reproducible:** the full pipeline rebuilds from raw extracts with one command (`python run_pipeline.py`).
- **Traceable:** every removed row is kept in `data/quarantine/` with its reason.
- **Consistent:** SQL and DAX use the same KPI definitions and produce the same numbers (see `powerbi/POWER_BI_BUILD_GUIDE.md` §10).
- **Performant:** report visuals render in under 0.5 seconds.

## Out of scope

Real-time streaming, predictive models, and write-back. These would be sensible next phases.

## Assumptions

- Data is extracted on **30 September 2026 at 23:59:59** (the "snapshot").
- Fiscal year runs **1 April – 31 March**.
- Volume and revenue are attributed to the month the request was **created**; SLA, resolution time, CSAT and first-time fix to the month it was **closed**.
- A month is reported as complete once billing has posted (15 days after month end); September 2026 is therefore provisional.
