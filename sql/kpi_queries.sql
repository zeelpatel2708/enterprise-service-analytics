-- =============================================================================
-- kpi_queries.sql
-- Business questions answered in SQL. Each one is interview-ready: it shows a
-- specific technique (CTE, window function, ranking, date logic, pivoting).
-- =============================================================================

-- Q1. Which regions are missing SLA targets? (aggregation + CASE)
-- @name: q01_region_sla_summary
SELECT r.Region,
       COUNT(*)                                                         AS closed_requests,
       ROUND(AVG(f.ResolutionHours), 1)                                 AS avg_resolution_hours,
       ROUND(SUM(CASE WHEN f.ResolutionHours <= f.SLAHours THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 4) AS sla_compliance,
       ROUND(AVG(f.CSATScore * 1.0), 2)                                 AS avg_csat
FROM FactServiceRequests f
JOIN DimRegion r ON r.RegionKey = f.RegionKey
WHERE f.IsClosed = 1
GROUP BY r.Region
ORDER BY sla_compliance;

-- Q2. Company monthly trend with month-over-month change (LAG)
-- @name: q02_monthly_trend_mom
WITH m AS (
    SELECT d.YearMonth,
           COUNT(*)                         AS requests,
           SUM(COALESCE(f.ServiceRevenue,0)) AS revenue
    FROM FactServiceRequests f
    JOIN DimDate d ON d.DateKey = f.CreatedDateKey
    GROUP BY d.YearMonth
)
SELECT YearMonth,
       requests,
       ROUND(revenue, 0)                                                         AS revenue,
       ROUND(revenue / LAG(revenue) OVER (ORDER BY YearMonth) - 1, 4)            AS revenue_mom_pct,
       ROUND(requests * 1.0 / LAG(requests) OVER (ORDER BY YearMonth) - 1, 4)    AS requests_mom_pct,
       ROUND(revenue / LAG(revenue, 12) OVER (ORDER BY YearMonth) - 1, 4)        AS revenue_yoy_pct
FROM m
ORDER BY YearMonth;

-- Q3. Rolling 3-month SLA by region. Ratio of sums (not average of ratios!)
-- @name: q03_rolling_3m_sla_by_region
WITH monthly AS (
    SELECT r.Region,
           f.ClosedDateKey / 100   AS ym,
           SUM(f.SLAMet)           AS met,
           COUNT(*)                AS closed
    FROM FactServiceRequests f
    JOIN DimRegion r ON r.RegionKey = f.RegionKey
    WHERE f.IsClosed = 1
    GROUP BY r.Region, f.ClosedDateKey / 100
)
SELECT Region, ym AS YearMonthKey,
       ROUND(met * 1.0 / closed, 4) AS sla_month,
       ROUND(SUM(met)    OVER w * 1.0 /
             SUM(closed) OVER w, 4)  AS sla_rolling_3m
FROM monthly
WINDOW w AS (PARTITION BY Region ORDER BY ym ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
ORDER BY Region, ym;

-- Q4. Year-over-year revenue by region (conditional aggregation pivot)
-- Compares Jan-Sep of each year so 2026 (data to 30 Sep) is like-for-like.
-- @name: q04_ytd_revenue_by_region
SELECT r.Region,
       ROUND(SUM(CASE WHEN d.Year = 2024 THEN f.ServiceRevenue END), 0) AS ytd_2024,
       ROUND(SUM(CASE WHEN d.Year = 2025 THEN f.ServiceRevenue END), 0) AS ytd_2025,
       ROUND(SUM(CASE WHEN d.Year = 2026 THEN f.ServiceRevenue END), 0) AS ytd_2026,
       ROUND(SUM(CASE WHEN d.Year = 2026 THEN f.ServiceRevenue END) /
             SUM(CASE WHEN d.Year = 2025 THEN f.ServiceRevenue END) - 1, 4) AS yoy_2026_vs_2025
FROM FactServiceRequests f
JOIN DimDate   d ON d.DateKey   = f.CreatedDateKey
JOIN DimRegion r ON r.RegionKey = f.RegionKey
WHERE d.MonthNumber <= 9
GROUP BY r.Region
ORDER BY yoy_2026_vs_2025 DESC;

-- Q5. Which customers generate the most revenue? Pareto / cumulative share
-- @name: q05_customer_revenue_pareto
WITH c AS (
    SELECT dc.CustomerName, dc.CustomerSegment, SUM(f.ServiceRevenue) AS revenue
    FROM FactServiceRequests f
    JOIN DimCustomer dc ON dc.CustomerKey = f.CustomerKey
    GROUP BY dc.CustomerKey
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (ORDER BY revenue DESC)                   AS revenue_rank,
           revenue / SUM(revenue) OVER ()                              AS share,
           SUM(revenue) OVER (ORDER BY revenue DESC ROWS UNBOUNDED PRECEDING)
             / SUM(revenue) OVER ()                                    AS cumulative_share,
           COUNT(*) OVER ()                                            AS total_customers
    FROM c
)
SELECT revenue_rank, CustomerName, CustomerSegment, ROUND(revenue, 0) AS revenue,
       ROUND(share, 4) AS share, ROUND(cumulative_share, 4) AS cumulative_share,
       ROUND(revenue_rank * 1.0 / total_customers, 4) AS pct_of_customers
FROM ranked
WHERE revenue_rank <= 25
   OR revenue_rank = (SELECT MIN(revenue_rank) FROM ranked WHERE cumulative_share >= 0.80)
ORDER BY revenue_rank;

-- Q6. Median resolution time by service type (no MEDIAN() in SQLite:
--     classic ROW_NUMBER / COUNT technique; T-SQL has PERCENTILE_CONT)
-- @name: q06_median_resolution_by_service_type
WITH ordered AS (
    SELECT s.ServiceType, f.ResolutionHours,
           ROW_NUMBER() OVER (PARTITION BY s.ServiceType ORDER BY f.ResolutionHours) AS rn,
           COUNT(*)     OVER (PARTITION BY s.ServiceType)                            AS n
    FROM FactServiceRequests f
    JOIN DimServiceType s ON s.ServiceTypeKey = f.ServiceTypeKey
    WHERE f.IsClosed = 1
)
SELECT ServiceType,
       MAX(n)                                 AS closed_requests,
       ROUND(AVG(ResolutionHours), 1)         AS median_resolution_hours
FROM ordered
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY ServiceType
ORDER BY median_resolution_hours DESC;

-- Q7. ROOT CAUSE - Ottawa: what changed? Mar-Sep 2026 vs the SAME months of 2025.
--     Comparing to the same period last year removes seasonality (a naive
--     "last 6 months vs next 6 months" comparison would mix winter and summer).
--     Other regions are shown as a control group.
-- @name: q07_ottawa_yoy_by_service_type
WITH base AS (
    SELECT s.ServiceType,
           CASE WHEN r.Region = 'Ottawa' THEN 'Ottawa' ELSE 'Other regions' END AS grp,
           d.Year, f.SLAMet, f.IsClosed
    FROM FactServiceRequests f
    JOIN DimRegion r      ON r.RegionKey      = f.RegionKey
    JOIN DimServiceType s ON s.ServiceTypeKey = f.ServiceTypeKey
    JOIN DimDate d        ON d.DateKey        = f.CreatedDateKey
    WHERE d.MonthNumber BETWEEN 3 AND 9 AND d.Year IN (2025, 2026)
),
agg AS (
    SELECT ServiceType, grp,
           SUM(CASE WHEN Year = 2025 THEN 1 ELSE 0 END)                         AS vol_2025,
           SUM(CASE WHEN Year = 2026 THEN 1 ELSE 0 END)                         AS vol_2026,
           AVG(CASE WHEN Year = 2025 AND IsClosed = 1 THEN SLAMet * 1.0 END)    AS sla_2025,
           AVG(CASE WHEN Year = 2026 AND IsClosed = 1 THEN SLAMet * 1.0 END)    AS sla_2026
    FROM base GROUP BY ServiceType, grp
)
SELECT o.ServiceType,
       o.vol_2025                                   AS ottawa_vol_2025,
       o.vol_2026                                   AS ottawa_vol_2026,
       ROUND(o.vol_2026 * 1.0 / o.vol_2025 - 1, 3)  AS ottawa_volume_yoy,
       ROUND(x.vol_2026 * 1.0 / x.vol_2025 - 1, 3)  AS other_regions_volume_yoy,
       ROUND(o.sla_2025, 3)                         AS ottawa_sla_2025,
       ROUND(o.sla_2026, 3)                         AS ottawa_sla_2026,
       ROUND(x.sla_2026, 3)                         AS other_regions_sla_2026
FROM agg o
JOIN agg x ON x.ServiceType = o.ServiceType AND x.grp = 'Other regions'
WHERE o.grp = 'Ottawa'
ORDER BY ottawa_volume_yoy DESC;

-- Q8. ROOT CAUSE - capacity: demand per active technician, by region and month
--     (active = employed on the 15th of the month, from HR dates)
-- @name: q08_demand_per_technician
WITH months AS (
    SELECT DISTINCT YearMonthKey, YearMonth, date(MonthStartDate, '+14 days') AS mid_month
    FROM DimDate WHERE IsCompleteMonth = 1 AND Date >= '2025-01-01'
),
headcount AS (
    SELECT m.YearMonthKey, t.Region, COUNT(*) AS active_technicians
    FROM months m
    JOIN DimTechnician t
      ON t.TechnicianKey > 0
     AND t.HireDate <= m.mid_month
     AND (t.TerminationDate IS NULL OR t.TerminationDate > m.mid_month)
    GROUP BY m.YearMonthKey, t.Region
),
demand AS (
    SELECT f.CreatedDateKey / 100 AS YearMonthKey, r.Region, COUNT(*) AS requests,
           AVG(f.SLAMet * 1.0)    AS sla
    FROM FactServiceRequests f JOIN DimRegion r ON r.RegionKey = f.RegionKey
    GROUP BY 1, 2
)
SELECT h.Region, m.YearMonth, h.active_technicians, d.requests,
       ROUND(d.requests * 1.0 / h.active_technicians, 1) AS requests_per_technician,
       ROUND(d.sla, 3) AS sla_compliance
FROM headcount h
JOIN months m ON m.YearMonthKey = h.YearMonthKey
JOIN demand d ON d.YearMonthKey = h.YearMonthKey AND d.Region = h.Region
ORDER BY h.Region, m.YearMonth;

-- Q9. Does the day/time a ticket is raised matter? (Friday-afternoon effect)
-- @name: q09_sla_by_day_and_time
SELECT d.DayOfWeekNumber, d.DayOfWeek,
       CASE WHEN f.CreatedHour < 12 THEN 'Morning' WHEN f.CreatedHour < 14 THEN 'Midday'
            ELSE 'Afternoon/Evening' END                       AS time_band,
       COUNT(*)                                                AS closed_requests,
       ROUND(AVG(f.SLAMet * 1.0), 4)                           AS sla_compliance
FROM FactServiceRequests f
JOIN DimDate d     ON d.DateKey = f.CreatedDateKey
JOIN DimPriority p ON p.PriorityKey = f.PriorityKey
WHERE f.IsClosed = 1 AND p.Priority <> 'Critical'
GROUP BY d.DayOfWeekNumber, d.DayOfWeek, time_band
ORDER BY d.DayOfWeekNumber, time_band;

-- Q10. First-time fix by technician skill and service category
-- @name: q10_first_time_fix_by_skill
SELECT t.SkillLevel, s.ServiceCategory,
       COUNT(f.FirstTimeFixFlag)                     AS measurable_jobs,
       ROUND(AVG(f.FirstTimeFixFlag * 1.0), 4)       AS first_time_fix_rate
FROM FactServiceRequests f
JOIN DimTechnician  t ON t.TechnicianKey  = f.TechnicianKey
JOIN DimServiceType s ON s.ServiceTypeKey = f.ServiceTypeKey
WHERE f.FirstTimeFixFlag IS NOT NULL AND f.TechnicianKey > 0
GROUP BY t.SkillLevel, s.ServiceCategory
ORDER BY s.ServiceCategory,
         CASE t.SkillLevel WHEN 'Junior' THEN 1 WHEN 'Intermediate' THEN 2 WHEN 'Senior' THEN 3 ELSE 4 END;

-- Q11. Cost of poor first-time fix: warranty callbacks generate cost but no revenue
-- @name: q11_cost_of_repeat_visits
SELECT d.Year,
       SUM(f.RepeatVisitFlag)                                                      AS repeat_visits,
       ROUND(SUM(f.RepeatVisitFlag) * 1.0 / COUNT(*), 4)                           AS repeat_visit_rate,
       ROUND(SUM(CASE WHEN f.BillingType = 'Warranty' THEN f.LabourCost + f.PartsCost END), 0) AS warranty_cost,
       ROUND(SUM(CASE WHEN f.BillingType = 'Warranty' THEN f.LabourCost + f.PartsCost END)
             / SUM(f.LabourCost + f.PartsCost), 4)                                 AS warranty_share_of_cost
FROM FactServiceRequests f
JOIN DimDate d ON d.DateKey = f.CreatedDateKey
WHERE f.IsClosed = 1
GROUP BY d.Year;

-- Q12. Gross margin by region and quarter for Installation work
-- @name: q12_installation_margin_by_region_quarter
SELECT r.Region, d.YearQuarter,
       COUNT(*)                                                                     AS jobs,
       ROUND(AVG(f.PartsCost), 0)                                                   AS avg_parts_cost,
       ROUND(SUM(f.ServiceRevenue - f.LabourCost - f.PartsCost) / SUM(f.ServiceRevenue), 4) AS gross_margin_pct
FROM FactServiceRequests f
JOIN DimRegion r      ON r.RegionKey = f.RegionKey
JOIN DimDate d        ON d.DateKey   = f.CreatedDateKey
JOIN DimServiceType s ON s.ServiceTypeKey = f.ServiceTypeKey
WHERE s.ServiceCategory = 'Installation' AND f.IsInvoiced = 1 AND f.BillingType = 'Billable'
GROUP BY r.Region, d.YearQuarter
ORDER BY r.Region, d.YearQuarter;

-- Q13. Customer retention proxy by segment
-- @name: q13_customer_activity_by_segment
SELECT CustomerSegment, ActivityStatus, COUNT(*) AS customers,
       ROUND(COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY CustomerSegment), 4) AS share_of_segment
FROM DimCustomer
GROUP BY CustomerSegment, ActivityStatus
ORDER BY CustomerSegment, ActivityStatus;

-- Q14. Latest complete month exceptions: which region/KPI combinations miss target?
-- @name: q14_latest_month_exceptions
-- Uses the latest month whose billing has fully posted (see DimDate.IsCompleteMonth)
WITH latest AS (SELECT MAX(YearMonthKey) AS ym FROM DimDate WHERE IsCompleteMonth = 1)
SELECT Region, 'SLA Compliance' AS kpi, SLACompliance AS actual, SLATarget AS target,
       ROUND(SLACompliance - SLATarget, 4) AS variance
FROM vw_monthly_region_scorecard, latest WHERE YearMonthKey = latest.ym AND SLACompliance < SLATarget
UNION ALL
SELECT Region, 'Backlog', BacklogAtMonthEnd, BacklogTarget, BacklogAtMonthEnd - BacklogTarget
FROM vw_monthly_region_scorecard, latest WHERE YearMonthKey = latest.ym AND BacklogAtMonthEnd > BacklogTarget
UNION ALL
SELECT Region, 'Revenue Achievement', RevenueAchievementPct, 1.0, ROUND(RevenueAchievementPct - 1, 4)
FROM vw_monthly_region_scorecard, latest WHERE YearMonthKey = latest.ym AND RevenueAchievementPct < 0.95
UNION ALL
SELECT Region, 'CSAT', AvgCSAT, CSATTarget, ROUND(AvgCSAT - CSATTarget, 2)
FROM vw_monthly_region_scorecard, latest WHERE YearMonthKey = latest.ym AND AvgCSAT < CSATTarget
ORDER BY kpi, variance;

-- Q15. Technician leaderboard (from the fair-ranking view)
-- @name: q15_technician_leaderboard
SELECT Region, TechnicianName, SkillLevel, ClosedJobs,
       ROUND(FirstTimeFixRate, 3) AS first_time_fix_rate,
       ROUND(SLACompliance, 3)    AS sla_compliance,
       ROUND(AvgCSAT, 2)          AS avg_csat,
       FTFRankInRegion
FROM vw_technician_scorecard
WHERE FTFRankInRegion <= 3
ORDER BY Region, FTFRankInRegion;

-- Q16. Monthly regional scorecard (full)
-- @name: q16_monthly_region_scorecard
SELECT * FROM vw_monthly_region_scorecard ORDER BY Region, YearMonthKey;
