-- =============================================================================
-- transformations.sql
-- Reusable analytical views on top of the star schema. These are the SQL
-- equivalents of the Power BI measures, so numbers can be cross-checked.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Enriched, denormalised request view (handy for ad-hoc analysis / Excel)
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_service_requests_enriched;
CREATE VIEW vw_service_requests_enriched AS
SELECT f.ServiceRequestID,
       f.AssetID,
       d.Date                    AS CreatedDate,
       d.YearMonth               AS CreatedYearMonth,
       d.Year                    AS CreatedYear,
       d.FiscalYear,
       d.DayOfWeek               AS CreatedDayOfWeek,
       f.CreatedHour,
       r.Region,
       c.CustomerName,
       c.CustomerSegment,
       c.Industry,
       t.TechnicianName,
       t.SkillLevel,
       s.ServiceCategory,
       s.ServiceType,
       p.Priority,
       f.Status,
       f.SLAHours,
       f.ResolutionHours,
       f.SLAMet,
       f.SLAStatus,
       f.RepeatVisitFlag,
       f.FirstTimeFixFlag,
       f.BillingType,
       f.ServiceRevenue,
       f.LabourCost,
       f.PartsCost,
       f.ServiceRevenue - f.LabourCost - f.PartsCost AS GrossMargin,
       f.CSATScore
FROM FactServiceRequests f
JOIN DimDate        d ON d.DateKey        = f.CreatedDateKey
JOIN DimRegion      r ON r.RegionKey      = f.RegionKey
JOIN DimCustomer    c ON c.CustomerKey    = f.CustomerKey
JOIN DimTechnician  t ON t.TechnicianKey  = f.TechnicianKey
JOIN DimServiceType s ON s.ServiceTypeKey = f.ServiceTypeKey
JOIN DimPriority    p ON p.PriorityKey    = f.PriorityKey;

-- -----------------------------------------------------------------------------
-- 2. Monthly regional scorecard: actual vs target, with variance
--    Volume/revenue are attributed to the CREATED month; SLA and resolution to
--    the CLOSED month (a request's SLA outcome is only known when it closes).
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_monthly_region_scorecard;
CREATE VIEW vw_monthly_region_scorecard AS
WITH created AS (
    SELECT f.RegionKey,
           f.CreatedDateKey / 100           AS YearMonthKey,
           COUNT(*)                         AS Requests,
           SUM(f.IsCancelled)               AS Cancelled,
           SUM(COALESCE(f.ServiceRevenue,0)) AS Revenue,
           SUM(COALESCE(f.LabourCost,0) + COALESCE(f.PartsCost,0)) AS DirectCost
    FROM FactServiceRequests f
    GROUP BY f.RegionKey, f.CreatedDateKey / 100
),
closed AS (
    SELECT f.RegionKey,
           f.ClosedDateKey / 100            AS YearMonthKey,
           COUNT(*)                         AS ClosedRequests,
           AVG(f.SLAMet * 1.0)              AS SLACompliance,
           AVG(f.ResolutionHours)           AS AvgResolutionHours,
           AVG(f.CSATScore * 1.0)           AS AvgCSAT,
           COUNT(DISTINCT CASE WHEN f.TechnicianKey > 0 THEN f.TechnicianKey END) AS ActiveTechnicians
    FROM FactServiceRequests f
    WHERE f.IsClosed = 1
    GROUP BY f.RegionKey, f.ClosedDateKey / 100
)
SELECT r.Region,
       t.MonthStartDateKey / 100                          AS YearMonthKey,
       cr.Requests,
       cl.ClosedRequests,
       ROUND(cr.Revenue, 2)                               AS Revenue,
       t.RevenueTarget,
       ROUND(cr.Revenue - t.RevenueTarget, 2)             AS RevenueVariance,
       ROUND(cr.Revenue / NULLIF(t.RevenueTarget, 0), 4)  AS RevenueAchievementPct,
       ROUND((cr.Revenue - cr.DirectCost) / NULLIF(cr.Revenue, 0), 4) AS GrossMarginPct,
       ROUND(cl.SLACompliance, 4)                         AS SLACompliance,
       t.SLATarget,
       ROUND(cl.SLACompliance - t.SLATarget, 4)           AS SLAVariancePts,
       ROUND(cl.AvgResolutionHours, 1)                    AS AvgResolutionHours,
       ROUND(cl.AvgCSAT, 2)                               AS AvgCSAT,
       t.CSATTarget,
       cl.ActiveTechnicians,
       ROUND(cl.ClosedRequests * 1.0 / NULLIF(cl.ActiveTechnicians, 0), 1) AS ClosedPerTechnician,
       t.ProductivityTarget,
       b.OpenRequests                                     AS BacklogAtMonthEnd,
       t.BacklogTarget
FROM FactTargets t
JOIN DimRegion r                ON r.RegionKey = t.RegionKey
LEFT JOIN created cr            ON cr.RegionKey = t.RegionKey AND cr.YearMonthKey = t.MonthStartDateKey / 100
LEFT JOIN closed cl             ON cl.RegionKey = t.RegionKey AND cl.YearMonthKey = t.MonthStartDateKey / 100
LEFT JOIN FactBacklogSnapshot b ON b.RegionKey = t.RegionKey AND b.SnapshotDateKey / 100 = t.MonthStartDateKey / 100
WHERE cr.Requests IS NOT NULL;

-- -----------------------------------------------------------------------------
-- 3. Technician scorecard with fair ranking
--    Only technicians with >= 150 closed jobs are ranked (small samples lie),
--    and ranks are computed WITHIN region so techs are compared to peers who
--    face the same demand and travel conditions.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_technician_scorecard;
CREATE VIEW vw_technician_scorecard AS
WITH stats AS (
    SELECT t.TechnicianKey, t.TechnicianName, t.Region, t.SkillLevel, t.TenureBand, t.IsActive,
           COUNT(*)                               AS ClosedJobs,
           SUM(f.ServiceRevenue)                  AS Revenue,
           AVG(f.ResolutionHours)                 AS AvgResolutionHours,
           AVG(f.SLAMet * 1.0)                    AS SLACompliance,
           AVG(f.FirstTimeFixFlag * 1.0)          AS FirstTimeFixRate,
           AVG(f.CSATScore * 1.0)                 AS AvgCSAT,
           SUM(CASE WHEN p.Priority IN ('Critical','High') THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS ShareHighPriority
    FROM FactServiceRequests f
    JOIN DimTechnician t ON t.TechnicianKey = f.TechnicianKey
    JOIN DimPriority   p ON p.PriorityKey   = f.PriorityKey
    WHERE f.IsClosed = 1 AND f.TechnicianKey > 0
    GROUP BY t.TechnicianKey
)
SELECT *,
       CASE WHEN ClosedJobs >= 150 THEN
            RANK() OVER (PARTITION BY Region, ClosedJobs >= 150 ORDER BY FirstTimeFixRate DESC) END AS FTFRankInRegion,
       CASE WHEN ClosedJobs >= 150 THEN
            RANK() OVER (PARTITION BY Region, ClosedJobs >= 150 ORDER BY SLACompliance DESC) END   AS SLARankInRegion,
       ROUND(PERCENT_RANK() OVER (ORDER BY Revenue), 3)                                            AS RevenuePercentile
FROM stats;
