# Resume Bullets & Interview Prep

Everything below is true of this project – only claim what you have actually built and can explain. Swap the numbers if you regenerate the data with a different seed.

## Resume bullets (pick 3–4)

- Built an end-to-end BI platform for a 6-region field-service business: integrated 5 source systems (CRM, HR, field service, billing, surveys; ~177K raw records) into a Kimball star schema with 3 fact tables and 6 dimensions, served through a Power BI semantic model.
- Developed a Python/pandas validation pipeline with 30+ data-quality and reconciliation checks that standardised, de-duplicated or quarantined ~7,000 defective records (1,650+ quarantined) (duplicates, invalid dates, orphan invoices, out-of-range scores) with full audit trail; enforced with 27 automated pytest checks.
- Authored 80+ DAX measures including time intelligence (YTD, fiscal YTD, YoY, rolling 3/12-month), role-playing date relationships (USERELATIONSHIP), semi-additive backlog snapshots, volume-weighted targets and filtered RANKX rankings; implemented dynamic row-level security for regional managers.
- Wrote interview-grade SQL (CTEs, window functions, LAG, rolling ratios, Pareto analysis, median without built-in functions) to reproduce every dashboard KPI and reconcile Power BI to source data.
- Identified a capacity-driven SLA decline in one region (93% → 81%) masked by 17% revenue growth, a $620K/yr cost of repeat visits concentrated in junior technicians, and a 12-point installation-margin squeeze caused by an un-updated price list.

## 60-second project pitch

> "I built an analytics platform for a fictional field-service company whose data was spread across five systems that didn't agree. I generated realistic source extracts in Python – deliberately including the kinds of defects you see in real data – then built a cleaning pipeline that fixes what's unambiguous, quarantines what isn't, and reconciles billing to operations. I modelled it as a star schema and built a Power BI model with about 80 DAX measures and dynamic row-level security. The part I'm proudest of is the root-cause page: Ottawa looked like our best region on revenue, but SLA compliance had dropped from 93% to 81%. By drilling through service type, technician capacity and HR data, I showed it was a capacity problem – an emergency-repair surge just as two senior technicians left – not a performance problem."

## Questions you should be ready for

**Modelling**

- *Why a star schema rather than one big flat table?* Smaller model (dimensions stored once), simpler and faster DAX, filters flow one way, and it's the shape Power BI's engine (VertiPaq) is optimised for.
- *What is the grain of each fact table?* FactServiceRequests: one row per request. FactTargets: region × month. FactBacklogSnapshot: region × month-end.
- *Why two relationships between the fact and DimDate?* Role-playing dimension. Only one can be active; outcome measures activate the closed-date path with `USERELATIONSHIP`.
- *Why do you have a separate backlog snapshot table?* Backlog is a state at a point in time, not an event. It's semi-additive: you take the last value in a period instead of summing. I also built a DAX version that computes it from timestamps, and the two reconcile (they differ only by tickets that were cancelled while open).
- *Why `TechnicianKey = -1`?* An "Unknown member". Dropping closed jobs with no technician would understate revenue by ~$227K; mapping them to Unknown keeps totals correct and makes the data issue visible.

**DAX**

- *CALCULATE in one sentence?* It evaluates an expression in a modified filter context – it's how every "with this condition" measure works.
- *Why `DIVIDE` instead of `/`?* Handles divide-by-zero by returning blank (or an alternate value) instead of an error.
- *Why is your rolling 3-month SLA not an average of three monthly percentages?* Months have different volumes; averaging percentages weights a 300-job month the same as a 500-job month. The measure computes met ÷ measured over the whole window.
- *How does your technician ranking avoid unfair comparisons?* `RANKX` over `ALLSELECTED` (so it respects the region/skill filter) and only for technicians with ≥ 150 jobs.
- *Difference between ALL, ALLSELECTED and REMOVEFILTERS?* ALL / REMOVEFILTERS remove filters entirely (REMOVEFILTERS only as a CALCULATE modifier); ALLSELECTED removes filters from inside the visual but keeps the outer slicer selection – right for "% of visible total".

**SQL**

- *How do you find duplicates?* `GROUP BY` all columns `HAVING COUNT(*) > 1` for exact duplicates; `GROUP BY` business key for conflicting duplicates.
- *Why was `date(x) IS NOT NULL` not enough to validate dates?* SQLite normalises `2025-02-30` to March 2; you have to re-format and compare to the original string.
- *How would you compute a median without MEDIAN()?* `ROW_NUMBER()` and `COUNT()` over a partition, then average the middle one or two rows.

**Data quality**

- *How do you decide between fixing and quarantining?* Fix only when the correct value is unambiguous (a misspelt region). Quarantine when fixing would mean guessing (a close date before the open date). Never delete silently; log counts and reasons.
- *How do you know you didn't lose rows?* A test asserts raw (deduplicated) = clean + quarantined, and a SQL query reconciles model revenue to billing.

**Analysis / business**

- *How did you find the Ottawa root cause?* (See analysis_findings.md – walk through region → service type → capacity → HR.)
- *What would you do next?* Automate the refresh (Power BI service + gateway or Fabric), add alerting on requests-per-technician, build a demand forecast for staffing, and add a technician utilisation measure from scheduled hours.
- *What are the limitations?* Synthetic data; CSAT has non-response bias (unhappy customers answer more often); the retention metric is a proxy; September 2026 is provisional because billing lags.
