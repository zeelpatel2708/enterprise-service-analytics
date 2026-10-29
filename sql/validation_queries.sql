-- =============================================================================
-- validation_queries.sql
-- Data-quality checks. Part A profiles the RAW staging tables (what is wrong),
-- Part B proves the cleaned star schema is sound (what we fixed).
-- Every query is tagged with "-- @name:" and saved to data/sql_output/.
-- =============================================================================

-- ============================ PART A : RAW STAGING ===========================

-- @name: v01_raw_row_counts
SELECT 'crm_customers'         AS source, COUNT(*) AS row_count FROM stg_crm_customers
UNION ALL SELECT 'hr_technicians',        COUNT(*) FROM stg_hr_technicians
UNION ALL SELECT 'fsm_service_requests',  COUNT(*) FROM stg_fsm_service_requests
UNION ALL SELECT 'billing_invoices',      COUNT(*) FROM stg_billing_invoices
UNION ALL SELECT 'csat_survey_responses', COUNT(*) FROM stg_csat_survey_responses;

-- Exact duplicate rows: same values in every column
-- @name: v02_fsm_exact_duplicates
SELECT ServiceRequestID, COUNT(*) AS copies
FROM stg_fsm_service_requests
GROUP BY ServiceRequestID, CustomerID, AssetID, TechnicianID, Region, ServiceType,
         Priority, Status, CreatedAt, ClosedAt
HAVING COUNT(*) > 1
ORDER BY copies DESC, ServiceRequestID;

-- @name: v03_fsm_null_customer
SELECT ServiceRequestID, Region, ServiceType, CreatedAt
FROM stg_fsm_service_requests
WHERE CustomerID IS NULL OR TRIM(CustomerID) = '';

-- A date is valid only if re-formatting it returns the same string.
-- SQLite silently rolls '2025-02-30' forward to March 2, so a simple
-- "date() IS NOT NULL" check is NOT enough. (SQL Server: TRY_CONVERT(datetime2, x) IS NULL)
-- @name: v04_fsm_invalid_created_dates
SELECT CreatedAt AS raw_value, COUNT(*) AS rows_affected
FROM stg_fsm_service_requests
WHERE strftime('%Y-%m-%d %H:%M:%S', CreatedAt) IS NULL
   OR strftime('%Y-%m-%d %H:%M:%S', CreatedAt) <> CreatedAt
GROUP BY CreatedAt
ORDER BY rows_affected DESC;

-- @name: v05_fsm_closed_before_created
SELECT ServiceRequestID, CreatedAt, ClosedAt,
       ROUND((julianday(ClosedAt) - julianday(CreatedAt)) * 24, 1) AS hours_difference
FROM stg_fsm_service_requests
WHERE strftime('%Y-%m-%d %H:%M:%S', CreatedAt) = CreatedAt
  AND ClosedAt <> ''
  AND julianday(ClosedAt) < julianday(CreatedAt)
ORDER BY hours_difference;

-- Region spellings that do not match the master list
-- @name: v06_fsm_region_spellings
SELECT s.Region AS raw_region,
       '[' || s.Region || ']' AS raw_region_bracketed,   -- exposes trailing spaces
       COUNT(*) AS rows_affected,
       CASE WHEN r.Region IS NULL THEN 'Needs mapping' ELSE 'Valid' END AS status
FROM stg_fsm_service_requests s
LEFT JOIN DimRegion r ON r.Region = s.Region
GROUP BY s.Region
ORDER BY status, rows_affected DESC;

-- Unassigned is fine for brand-new tickets, but closed work must have a technician
-- @name: v07_fsm_closed_missing_technician
SELECT Status, COUNT(*) AS rows_missing_technician
FROM stg_fsm_service_requests
WHERE TechnicianID IS NULL OR TRIM(TechnicianID) = ''
GROUP BY Status;

-- @name: v08_billing_negative_costs
SELECT InvoiceID, ServiceRequestID, LabourCost, PartsCost, InvoiceAmount
FROM stg_billing_invoices
WHERE CAST(LabourCost AS REAL) < 0
   OR CAST(PartsCost AS REAL) < 0
   OR CAST(InvoiceAmount AS REAL) < 0;

-- Invoices that point to a ticket the FSM system has never heard of
-- @name: v09_billing_orphan_invoices
SELECT b.InvoiceID, b.ServiceRequestID, b.InvoiceAmount
FROM stg_billing_invoices b
LEFT JOIN (SELECT DISTINCT ServiceRequestID FROM stg_fsm_service_requests) f
       ON f.ServiceRequestID = b.ServiceRequestID
WHERE f.ServiceRequestID IS NULL;

-- @name: v10_csat_out_of_range
SELECT CSATScore AS raw_score, COUNT(*) AS responses
FROM stg_csat_survey_responses
WHERE CAST(CSATScore AS INTEGER) NOT BETWEEN 1 AND 5
GROUP BY CSATScore;

-- @name: v11_csat_multiple_responses
SELECT ServiceRequestID, COUNT(*) AS responses,
       MIN(ResponseDate) AS first_response, MAX(ResponseDate) AS last_response
FROM stg_csat_survey_responses
GROUP BY ServiceRequestID
HAVING COUNT(*) > 1;

-- @name: v12_raw_dq_summary
SELECT 'FSM exact duplicate rows' AS check_name,
       (SELECT COUNT(*) - COUNT(DISTINCT ServiceRequestID) FROM stg_fsm_service_requests) AS rows_flagged
UNION ALL SELECT 'FSM null CustomerID',
       (SELECT COUNT(*) FROM stg_fsm_service_requests WHERE CustomerID = '')
UNION ALL SELECT 'FSM invalid CreatedAt',
       (SELECT COUNT(*) FROM stg_fsm_service_requests
         WHERE strftime('%Y-%m-%d %H:%M:%S', CreatedAt) IS NULL
            OR strftime('%Y-%m-%d %H:%M:%S', CreatedAt) <> CreatedAt)
UNION ALL SELECT 'FSM non-standard region name',
       (SELECT COUNT(*) FROM stg_fsm_service_requests s
         WHERE NOT EXISTS (SELECT 1 FROM DimRegion r WHERE r.Region = s.Region))
UNION ALL SELECT 'FSM closed without technician',
       (SELECT COUNT(*) FROM stg_fsm_service_requests WHERE TechnicianID = '' AND Status = 'Closed')
UNION ALL SELECT 'Billing negative amounts',
       (SELECT COUNT(*) FROM stg_billing_invoices
         WHERE CAST(LabourCost AS REAL) < 0 OR CAST(PartsCost AS REAL) < 0)
UNION ALL SELECT 'CSAT outside 1-5',
       (SELECT COUNT(*) FROM stg_csat_survey_responses
         WHERE CAST(CSATScore AS INTEGER) NOT BETWEEN 1 AND 5);

-- ========================= PART B : CLEAN STAR SCHEMA ========================

-- Fact grain must be unique
-- @name: v20_fact_grain_check
SELECT COUNT(*) AS fact_rows,
       COUNT(DISTINCT ServiceRequestID) AS distinct_requests,
       CASE WHEN COUNT(*) = COUNT(DISTINCT ServiceRequestID) THEN 'PASS' ELSE 'FAIL' END AS result
FROM FactServiceRequests;

-- Every foreign key must resolve to a dimension row
-- @name: v21_orphan_foreign_keys
SELECT 'CustomerKey' AS fk, COUNT(*) AS orphans FROM FactServiceRequests f
  LEFT JOIN DimCustomer d ON d.CustomerKey = f.CustomerKey WHERE d.CustomerKey IS NULL
UNION ALL SELECT 'TechnicianKey', COUNT(*) FROM FactServiceRequests f
  LEFT JOIN DimTechnician d ON d.TechnicianKey = f.TechnicianKey WHERE d.TechnicianKey IS NULL
UNION ALL SELECT 'RegionKey', COUNT(*) FROM FactServiceRequests f
  LEFT JOIN DimRegion d ON d.RegionKey = f.RegionKey WHERE d.RegionKey IS NULL
UNION ALL SELECT 'ServiceTypeKey', COUNT(*) FROM FactServiceRequests f
  LEFT JOIN DimServiceType d ON d.ServiceTypeKey = f.ServiceTypeKey WHERE d.ServiceTypeKey IS NULL
UNION ALL SELECT 'CreatedDateKey', COUNT(*) FROM FactServiceRequests f
  LEFT JOIN DimDate d ON d.DateKey = f.CreatedDateKey WHERE d.DateKey IS NULL
UNION ALL SELECT 'ClosedDateKey', COUNT(*) FROM FactServiceRequests f
  LEFT JOIN DimDate d ON d.DateKey = f.ClosedDateKey
  WHERE f.ClosedDateKey IS NOT NULL AND d.DateKey IS NULL;

-- Business-rule assertions on the clean fact table: every row should be 0
-- @name: v22_business_rule_assertions
SELECT 'Closed before created'           AS rule, COUNT(*) AS violations FROM FactServiceRequests
  WHERE ClosedAt IS NOT NULL AND ClosedAt < CreatedAt
UNION ALL SELECT 'CSAT outside 1-5',               COUNT(*) FROM FactServiceRequests
  WHERE CSATScore IS NOT NULL AND CSATScore NOT BETWEEN 1 AND 5
UNION ALL SELECT 'Negative cost or revenue',       COUNT(*) FROM FactServiceRequests
  WHERE LabourCost < 0 OR PartsCost < 0 OR ServiceRevenue < 0
UNION ALL SELECT 'Closed with no SLA result',      COUNT(*) FROM FactServiceRequests
  WHERE Status = 'Closed' AND SLAMet IS NULL
UNION ALL SELECT 'Open with a ClosedDateKey',      COUNT(*) FROM FactServiceRequests
  WHERE IsOpen = 1 AND ClosedDateKey IS NOT NULL
UNION ALL SELECT 'Status flags not mutually exclusive', COUNT(*) FROM FactServiceRequests
  WHERE IsOpen + IsClosed + IsCancelled <> 1;

-- Reconciliation: does clean revenue in the model equal clean billing?
-- Difference should equal the invoices that were quarantined (they never reach the model).
-- @name: v23_revenue_reconciliation
WITH raw_billing AS (
    SELECT COUNT(DISTINCT InvoiceID)                    AS raw_invoices,
           SUM(CAST(InvoiceAmount AS REAL))              AS raw_amount_incl_duplicates
    FROM stg_billing_invoices
),
model AS (
    SELECT COUNT(InvoiceID)      AS model_invoices,
           SUM(ServiceRevenue)   AS model_revenue
    FROM FactServiceRequests
)
SELECT r.raw_invoices,
       m.model_invoices,
       r.raw_invoices - m.model_invoices                     AS invoices_excluded,
       ROUND(r.raw_amount_incl_duplicates, 2)                AS raw_amount_incl_duplicates,
       ROUND(m.model_revenue, 2)                             AS model_revenue,
       ROUND(r.raw_amount_incl_duplicates - m.model_revenue, 2) AS amount_excluded
FROM raw_billing r CROSS JOIN model m;
