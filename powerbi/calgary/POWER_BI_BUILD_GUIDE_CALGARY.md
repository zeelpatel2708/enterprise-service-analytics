# Power BI Build Guide – Edition B (Real Calgary 311 Data)

Build this as a **second report**, `powerbi/calgary_311_operations.pbix`. Do Edition A first: the settings, theme and modelling steps are the same, so this one goes much faster.

## 0. Get the data (one time, needs internet)

```bash
python src/calgary/download_calgary_311.py          # Jan 2024 – Sep 2026, resumable
python src/calgary/run_calgary_pipeline.py          # clean → model → SQL → insights → comparison
pytest -v
```

The download is large (likely over a million rows). If your laptop struggles, start with `--start 2025-01-01`, or test the pipeline first with `--sample 20000`.

Read `docs/calgary/data_quality_report_calgary.md` and `docs/calgary/calgary_insights.md` before building. They tell you what the data contains.

## 1. Setup

Same as Edition A §1: auto date/time off, autodetect relationships off, `ProjectFolder` parameter, theme `northline_theme.json`.

## 2. Load and model

- Paste each table from `power_query_calgary.m`. This includes the six `comparison_*` tables.
- Create the relationships listed at the top of `measures_calgary.dax` (the closed-date relationship is **inactive**).
- Mark `DimDate` as the date table. Sort `Month` by `MonthNumber`, `YearMonth` by `YearMonthKey`, `DayOfWeek` by `DayOfWeekNumber`.
- `DimCommunity[Latitude]` and `[Longitude]`: set Data category to Latitude and Longitude.
- Hide keys and flag columns. Add the measures from `measures_calgary.dax`.
- Page filter on every page: `DimDate[IsAfterSnapshot] = 0`.

## 3. Pages

### Page 1 – City Overview
- Cards: `Total Requests` (ref `Requests YoY %`), `Median Resolution Days`, `Within Benchmark %` (ref `Benchmark Change (pts)`), `Backlog (Month-End Snapshot)`, `Digital Share %`.
- Line: `Total Requests` by `YearMonth`, plus `Requests PY` as a dashed line.
- Bar: top 10 `DimServiceType[ServiceName]` by `Total Requests` (Top N filter).
- Donut: `Total Requests` by `DimChannel[Channel]`.

### Page 2 – Service Performance
- Slicer: `ServiceCategory`. Title bound to `Page Title Service`.
- Matrix: rows `ServiceCategory` → `ServiceName`; values `Total Requests`, `Median Resolution Days`, `P90 Resolution Days`, `Within Benchmark %`, `Benchmark Change (pts)`. Conditional-format the change column with `Benchmark Status Color`.
- Line: `Within Benchmark % Rolling 3M` by month, legend `ServiceCategory` (top 5).
- Decomposition tree: analyse `Total Requests` or `Avg Resolution Days` by Category → Service → Community → Channel.

### Page 3 – Communities (Map)
- Map or Azure Map: Latitude/Longitude from `DimCommunity`, bubble size `Total Requests`, colour `Within Benchmark %`.
- Table: `CommunityName`, `Total Requests`, `Community Rank (Volume)`, `Within Benchmark %`, `Community Rank (Benchmark, min 1,000)`.
- Text box: "Ranks only include communities with ≥ 1,000 requests. Volume reflects population and reporting habits, not service quality."

### Page 4 – Seasonality & Backlog
- Matrix heat-map: rows `ServiceCategory`, columns `MonthShort`, values `Seasonality Index` (background colour scale).
- Column: `Total Requests` by `DayOfWeek`, tooltip `Weekend Share %`.
- Line + column: `Backlog (Month-End Snapshot)` (columns) and `Backlog Over 90 Days %` (line) by month.
- Table: `Agency`, `Stale Open Requests (>365d)`.

### Page 5 – Simulated vs Real (the comparison)
Uses the `comparison_*` tables only (no relationships needed).
- Table: `comparison_summary` (Metric, Simulated, Real).
- Line chart: `comparison_seasonality` – X `MonthNumber`, Y `SeasonalityIndex`, legend `Edition`.
- Clustered bar: `comparison_resolution_distribution` – `Bucket` (sort by `BucketOrder`), `ShareOfClosed`, legend `Edition`.
- Clustered column: `comparison_day_of_week` – `DayOfWeek`, `ShareOfRequests`, legend `Edition`.
- Table: `comparison_capabilities` (what each dataset can answer).
- Table: `comparison_data_quality` – designed defects vs real ones.
- Text box with your 2–3 sentence conclusion (start from `docs/simulated_vs_real.md`, then write it in your own words).

## 4. Validate

Your cards should match `data/calgary/sql_output/c01_overview_by_year.csv` (requests and closed requests per year) and `c10_backlog_trend.csv` (backlog at each month end). If they don't, check which date relationship the measure uses.
