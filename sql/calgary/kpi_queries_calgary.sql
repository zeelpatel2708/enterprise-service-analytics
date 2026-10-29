-- =============================================================================
-- kpi_queries_calgary.sql  -  Edition B: REAL City of Calgary 311 data
-- Same techniques as Edition A (CTEs, window functions, LAG, ranking, pivots),
-- applied to real municipal service requests.
--
-- Service level: the open data has no published SLA, so each service type has a
-- DERIVED benchmark = the 80th percentile of its 2024 resolution days
-- (see src/calgary/clean_calgary.py). 2024 is ~80% by construction; 2025-2026
-- show whether service got faster or slower than the 2024 baseline.
-- =============================================================================

-- @name: c00_validation_fact_grain
SELECT COUNT(*) AS fact_rows, COUNT(DISTINCT ServiceRequestID) AS distinct_ids,
       CASE WHEN COUNT(*) = COUNT(DISTINCT ServiceRequestID) THEN 'PASS' ELSE 'FAIL' END AS result
FROM FactServiceRequests;

-- @name: c00_validation_rules
SELECT 'Closed before requested' AS rule, COUNT(*) AS violations FROM FactServiceRequests
  WHERE ClosedDateKey < RequestedDateKey
UNION ALL SELECT 'Open with ClosedDateKey', COUNT(*) FROM FactServiceRequests WHERE IsOpen = 1 AND ClosedDateKey IS NOT NULL
UNION ALL SELECT 'Orphan ServiceTypeKey', COUNT(*) FROM FactServiceRequests f
  LEFT JOIN DimServiceType s ON s.ServiceTypeKey = f.ServiceTypeKey WHERE s.ServiceTypeKey IS NULL
UNION ALL SELECT 'Orphan CommunityKey', COUNT(*) FROM FactServiceRequests f
  LEFT JOIN DimCommunity c ON c.CommunityKey = f.CommunityKey WHERE c.CommunityKey IS NULL;

-- C1. Year overview
-- @name: c01_overview_by_year
SELECT d.Year,
       COUNT(*)                                                   AS requests,
       SUM(f.IsClosed)                                            AS closed_requests,
       ROUND(AVG(f.SameDayClosure * 1.0), 4)                      AS same_day_closure_rate,
       ROUND(AVG(f.ResolutionDays * 1.0), 1)                      AS avg_resolution_days,
       ROUND(AVG(f.WithinBenchmark * 1.0), 4)                     AS within_benchmark_rate,
       SUM(f.IsDuplicateRequest)                                  AS duplicate_requests
FROM FactServiceRequests f
JOIN DimDate d ON d.DateKey = f.RequestedDateKey
GROUP BY d.Year
ORDER BY d.Year;

-- C2. Monthly trend with MoM and YoY (LAG)
-- @name: c02_monthly_trend
WITH m AS (
    SELECT d.YearMonth, COUNT(*) AS requests
    FROM FactServiceRequests f JOIN DimDate d ON d.DateKey = f.RequestedDateKey
    GROUP BY d.YearMonth
)
SELECT YearMonth, requests,
       ROUND(requests * 1.0 / LAG(requests)     OVER (ORDER BY YearMonth) - 1, 4) AS mom_pct,
       ROUND(requests * 1.0 / LAG(requests, 12) OVER (ORDER BY YearMonth) - 1, 4) AS yoy_pct
FROM m ORDER BY YearMonth;

-- C3. Top 15 services by volume, share of total and Jan-Sep YoY
-- @name: c03_top_services
WITH s AS (
    SELECT st.ServiceName, st.ServiceCategory,
           COUNT(*) AS requests,
           SUM(CASE WHEN d.Year = 2025 AND d.MonthNumber <= 9 THEN 1 ELSE 0 END) AS jan_sep_2025,
           SUM(CASE WHEN d.Year = 2026 AND d.MonthNumber <= 9 THEN 1 ELSE 0 END) AS jan_sep_2026
    FROM FactServiceRequests f
    JOIN DimServiceType st ON st.ServiceTypeKey = f.ServiceTypeKey
    JOIN DimDate d         ON d.DateKey = f.RequestedDateKey
    GROUP BY st.ServiceTypeKey
)
SELECT ROW_NUMBER() OVER (ORDER BY requests DESC) AS rank_no,
       ServiceName, ServiceCategory, requests,
       ROUND(requests * 1.0 / SUM(requests) OVER (), 4)                 AS share_of_total,
       ROUND(SUM(requests) OVER (ORDER BY requests DESC ROWS UNBOUNDED PRECEDING) * 1.0
             / SUM(requests) OVER (), 4)                                AS cumulative_share,
       ROUND(jan_sep_2026 * 1.0 / NULLIF(jan_sep_2025, 0) - 1, 4)      AS yoy_jan_sep
FROM s
ORDER BY requests DESC
LIMIT 15;

-- C4. Slowest services: median and P90 resolution days (ROW_NUMBER technique)
-- @name: c04_slowest_services
WITH c AS (
    SELECT st.ServiceName, f.ResolutionDays,
           ROW_NUMBER() OVER (PARTITION BY st.ServiceName ORDER BY f.ResolutionDays) AS rn,
           COUNT(*)     OVER (PARTITION BY st.ServiceName)                          AS n
    FROM FactServiceRequests f JOIN DimServiceType st ON st.ServiceTypeKey = f.ServiceTypeKey
    WHERE f.IsClosed = 1 AND f.IsDuplicateRequest = 0
)
SELECT ServiceName, MAX(n) AS closed_requests,
       MAX(CASE WHEN rn = (n + 1) / 2          THEN ResolutionDays END) AS median_days,
       MAX(CASE WHEN rn = CAST(n * 0.9 AS INT) THEN ResolutionDays END) AS p90_days
FROM c
GROUP BY ServiceName
HAVING MAX(n) >= 500
ORDER BY median_days DESC, p90_days DESC
LIMIT 20;

-- C5. Benchmark compliance by category and year (are we faster or slower than 2024?)
-- @name: c05_benchmark_by_category_year
SELECT st.ServiceCategory,
       ROUND(AVG(CASE WHEN d.Year = 2024 THEN f.WithinBenchmark * 1.0 END), 4) AS y2024,
       ROUND(AVG(CASE WHEN d.Year = 2025 THEN f.WithinBenchmark * 1.0 END), 4) AS y2025,
       ROUND(AVG(CASE WHEN d.Year = 2026 THEN f.WithinBenchmark * 1.0 END), 4) AS y2026,
       ROUND(AVG(CASE WHEN d.Year = 2026 THEN f.WithinBenchmark * 1.0 END)
           - AVG(CASE WHEN d.Year = 2025 THEN f.WithinBenchmark * 1.0 END), 4) AS change_pts_2026_vs_2025,
       COUNT(*) AS requests
FROM FactServiceRequests f
JOIN DimServiceType st ON st.ServiceTypeKey = f.ServiceTypeKey
JOIN DimDate d ON d.DateKey = f.ClosedDateKey
GROUP BY st.ServiceCategory
HAVING COUNT(*) >= 1000
ORDER BY change_pts_2026_vs_2025;

-- C6. Channel mix by year - is the city shifting to digital?
-- @name: c06_channel_mix
SELECT d.Year, ch.Channel, ch.ChannelGroup, COUNT(*) AS requests,
       ROUND(COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY d.Year), 4) AS share_of_year
FROM FactServiceRequests f
JOIN DimChannel ch ON ch.ChannelKey = f.ChannelKey
JOIN DimDate d     ON d.DateKey = f.RequestedDateKey
GROUP BY d.Year, ch.Channel
ORDER BY d.Year, requests DESC;

-- C7. Communities: volume and service level (minimum volume for fairness)
-- @name: c07_community_ranking
WITH c AS (
    SELECT cm.CommunityName, COUNT(*) AS requests,
           AVG(f.WithinBenchmark * 1.0) AS within_benchmark,
           AVG(f.ResolutionDays * 1.0)  AS avg_days
    FROM FactServiceRequests f JOIN DimCommunity cm ON cm.CommunityKey = f.CommunityKey
    WHERE cm.CommunityKey > 0
    GROUP BY cm.CommunityKey
    HAVING COUNT(*) >= 1000
)
SELECT CommunityName, requests,
       ROUND(within_benchmark, 4) AS within_benchmark_rate,
       ROUND(avg_days, 1)         AS avg_resolution_days,
       DENSE_RANK() OVER (ORDER BY requests DESC)         AS volume_rank,
       DENSE_RANK() OVER (ORDER BY within_benchmark ASC)  AS worst_service_rank
FROM c
ORDER BY volume_rank
LIMIT 30;

-- C8. Day-of-week pattern
-- @name: c08_day_of_week
SELECT d.DayOfWeekNumber, d.DayOfWeek, COUNT(*) AS requests,
       ROUND(COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (), 4) AS share,
       ROUND(AVG(f.SameDayClosure * 1.0), 4)            AS same_day_closure_rate
FROM FactServiceRequests f JOIN DimDate d ON d.DateKey = f.RequestedDateKey
GROUP BY d.DayOfWeekNumber, d.DayOfWeek
ORDER BY d.DayOfWeekNumber;

-- C9. Seasonality: average monthly volume by category (calendar month pivot)
-- @name: c09_seasonality_by_category
WITH m AS (
    SELECT st.ServiceCategory, d.MonthNumber, d.Year, COUNT(*) AS requests
    FROM FactServiceRequests f
    JOIN DimServiceType st ON st.ServiceTypeKey = f.ServiceTypeKey
    JOIN DimDate d ON d.DateKey = f.RequestedDateKey
    WHERE d.Year IN (2024, 2025)
    GROUP BY st.ServiceCategory, d.MonthNumber, d.Year
),
avgm AS (
    SELECT ServiceCategory, MonthNumber, AVG(requests) AS avg_requests FROM m GROUP BY 1, 2
)
SELECT ServiceCategory, MonthNumber, ROUND(avg_requests, 0) AS avg_requests,
       ROUND(avg_requests / AVG(avg_requests) OVER (PARTITION BY ServiceCategory), 3) AS seasonality_index
FROM avgm
WHERE ServiceCategory IN (SELECT ServiceCategory FROM avgm GROUP BY 1 ORDER BY SUM(avg_requests) DESC LIMIT 8)
ORDER BY ServiceCategory, MonthNumber;

-- C10. Backlog trend (semi-additive snapshot: sum across services, never across months)
-- @name: c10_backlog_trend
SELECT b.SnapshotDateKey,
       SUM(b.OpenRequests)       AS open_requests,
       SUM(b.OpenPastBenchmark)  AS open_past_benchmark,
       SUM(b.OpenOver90Days)     AS open_over_90_days,
       ROUND(SUM(b.OpenOver90Days) * 1.0 / SUM(b.OpenRequests), 4) AS share_over_90_days
FROM FactBacklogSnapshot b
GROUP BY b.SnapshotDateKey
ORDER BY b.SnapshotDateKey;

-- C11. Stale backlog: tickets open > 365 days by agency
-- @name: c11_stale_backlog_by_agency
SELECT st.Agency, SUM(f.IsOpen) AS open_requests, SUM(f.IsStaleOpen) AS stale_over_365_days,
       ROUND(SUM(f.IsStaleOpen) * 1.0 / NULLIF(SUM(f.IsOpen), 0), 4) AS stale_share
FROM FactServiceRequests f JOIN DimServiceType st ON st.ServiceTypeKey = f.ServiceTypeKey
GROUP BY st.Agency
HAVING SUM(f.IsOpen) > 0
ORDER BY stale_over_365_days DESC;

-- C12. Fastest-growing services, Jan-Sep 2026 vs Jan-Sep 2025 (min 300 requests in 2025)
-- @name: c12_fastest_growing_services
WITH s AS (
    SELECT st.ServiceName,
           SUM(CASE WHEN d.Year = 2025 AND d.MonthNumber <= 9 THEN 1 ELSE 0 END) AS v2025,
           SUM(CASE WHEN d.Year = 2026 AND d.MonthNumber <= 9 THEN 1 ELSE 0 END) AS v2026
    FROM FactServiceRequests f
    JOIN DimServiceType st ON st.ServiceTypeKey = f.ServiceTypeKey
    JOIN DimDate d ON d.DateKey = f.RequestedDateKey
    GROUP BY st.ServiceName
)
SELECT ServiceName, v2025, v2026, v2026 - v2025 AS change,
       ROUND(v2026 * 1.0 / v2025 - 1, 4) AS growth_pct
FROM s WHERE v2025 >= 300
ORDER BY growth_pct DESC
LIMIT 15;

-- C13. Rolling 3-month benchmark compliance by category (ratio of sums)
-- @name: c13_rolling_3m_benchmark
WITH m AS (
    SELECT st.ServiceCategory, f.ClosedDateKey / 100 AS ym,
           SUM(f.WithinBenchmark) AS met, COUNT(f.WithinBenchmark) AS measured
    FROM FactServiceRequests f JOIN DimServiceType st ON st.ServiceTypeKey = f.ServiceTypeKey
    WHERE f.WithinBenchmark IS NOT NULL
    GROUP BY 1, 2
)
SELECT ServiceCategory, ym AS YearMonthKey,
       ROUND(met * 1.0 / measured, 4) AS month_rate,
       ROUND(SUM(met) OVER w * 1.0 / SUM(measured) OVER w, 4) AS rolling_3m_rate
FROM m
WINDOW w AS (PARTITION BY ServiceCategory ORDER BY ym ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
ORDER BY ServiceCategory, ym;

-- C14. Data-quality flags carried into the model
-- @name: c14_dq_flags
SELECT 'Closure date imputed from updated_date' AS flag, SUM(ClosedDateImputed) AS rows_flagged FROM FactServiceRequests
UNION ALL SELECT 'Re-opened (had closed_date, status open)', SUM(ReopenedFlag) FROM FactServiceRequests
UNION ALL SELECT 'Closed as duplicate', SUM(IsDuplicateRequest) FROM FactServiceRequests
UNION ALL SELECT 'Open > 365 days', SUM(IsStaleOpen) FROM FactServiceRequests
UNION ALL SELECT 'Unknown community', COUNT(*) FROM FactServiceRequests WHERE CommunityKey = -1;
