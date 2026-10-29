-- =============================================================================
-- create_tables.sql
-- Enterprise Field Service Analytics - warehouse DDL
--
-- Layer 1  stg_*   : raw source extracts, loaded as TEXT exactly as received
--                    (never trust source types - validate first)
-- Layer 2  Dim/Fact: cleaned star schema consumed by Power BI
--
-- Dialect: SQLite. For SQL Server swap TEXT -> NVARCHAR(n), REAL -> DECIMAL(12,2),
--          and add IDENTITY / proper DATE / DATETIME2 types.
-- =============================================================================

-- ---------------------------------------------------------------- staging ----
CREATE TABLE stg_crm_customers (
    CustomerID        TEXT,
    CustomerName      TEXT,
    Industry          TEXT,
    CustomerSegment   TEXT,
    City              TEXT,
    Province          TEXT,
    AccountStartDate  TEXT
);

CREATE TABLE stg_hr_technicians (
    TechnicianID      TEXT,
    TechnicianName    TEXT,
    SkillLevel        TEXT,
    Specialization    TEXT,
    Region            TEXT,
    HireDate          TEXT,
    TerminationDate   TEXT
);

CREATE TABLE stg_fsm_service_requests (
    ServiceRequestID  TEXT,
    CustomerID        TEXT,
    AssetID           TEXT,
    TechnicianID      TEXT,
    Region            TEXT,
    ServiceType       TEXT,
    Priority          TEXT,
    Status            TEXT,
    CreatedAt         TEXT,
    ClosedAt          TEXT
);

CREATE TABLE stg_billing_invoices (
    InvoiceID         TEXT,
    ServiceRequestID  TEXT,
    InvoiceDate       TEXT,
    BillingType       TEXT,
    WorkHours         TEXT,
    LabourCost        TEXT,
    PartsCost         TEXT,
    InvoiceAmount     TEXT
);

CREATE TABLE stg_csat_survey_responses (
    SurveyResponseID  TEXT,
    ServiceRequestID  TEXT,
    ResponseDate      TEXT,
    CSATScore         TEXT,
    Comment           TEXT
);

CREATE TABLE stg_sla_policy (
    Priority          TEXT,
    SLAHours          TEXT,
    EffectiveFrom     TEXT
);

CREATE TABLE stg_regional_targets (
    Month              TEXT,
    Region             TEXT,
    RevenueTarget      TEXT,
    SLATarget          TEXT,
    CSATTarget         TEXT,
    ProductivityTarget TEXT,
    BacklogTarget      TEXT
);

-- ------------------------------------------------------------- dimensions ----
CREATE TABLE DimDate (
    DateKey            INTEGER PRIMARY KEY,      -- YYYYMMDD
    Date               TEXT NOT NULL,
    Year               INTEGER,
    QuarterNumber      INTEGER,
    Quarter            TEXT,
    YearQuarter        TEXT,
    MonthNumber        INTEGER,
    Month              TEXT,
    MonthShort         TEXT,
    YearMonth          TEXT,
    YearMonthKey       INTEGER,
    MonthStartDate     TEXT,
    MonthEndDate       TEXT,
    ISOWeek            INTEGER,
    Day                INTEGER,
    DayOfWeekNumber    INTEGER,                  -- Monday = 1
    DayOfWeek          TEXT,
    IsWeekend          INTEGER,
    FiscalYear         TEXT,                     -- FY starts 1 April
    FiscalQuarter      TEXT,
    FiscalMonthNumber  INTEGER,
    IsAfterSnapshot    INTEGER,
    IsCompleteMonth    INTEGER
);

CREATE TABLE DimRegion (
    RegionKey             INTEGER PRIMARY KEY,
    Region                TEXT NOT NULL UNIQUE,
    Province              TEXT,
    RegionalManager       TEXT,
    RegionalManagerEmail  TEXT
);

CREATE TABLE DimCustomer (
    CustomerKey        INTEGER PRIMARY KEY,
    CustomerID         TEXT NOT NULL UNIQUE,
    CustomerName       TEXT,
    Industry           TEXT,
    CustomerSegment    TEXT,
    City               TEXT,
    Province           TEXT,
    AccountStartDate   TEXT,
    FirstRequestDate   TEXT,
    LastRequestDate    TEXT,
    ActivityStatus     TEXT
);

CREATE TABLE DimTechnician (
    TechnicianKey      INTEGER PRIMARY KEY,      -- -1 Unknown, -2 Unassigned
    TechnicianID       TEXT NOT NULL UNIQUE,
    TechnicianName     TEXT,
    SkillLevel         TEXT,
    Specialization     TEXT,
    Region             TEXT,
    HireDate           TEXT,
    TerminationDate    TEXT,
    IsActive           INTEGER,
    TenureYears        REAL,
    TenureBand         TEXT
);

CREATE TABLE DimServiceType (
    ServiceTypeKey     INTEGER PRIMARY KEY,
    ServiceCategory    TEXT,
    ServiceType        TEXT NOT NULL UNIQUE,
    ListPrice2024      REAL
);

CREATE TABLE DimPriority (
    PriorityKey        INTEGER PRIMARY KEY,
    Priority           TEXT NOT NULL UNIQUE,
    SLAHours           REAL,
    PriceMultiplier    REAL,
    SortOrder          INTEGER
);

-- ------------------------------------------------------------------ facts ----
-- Grain: one row per service request
CREATE TABLE FactServiceRequests (
    ServiceRequestID     TEXT PRIMARY KEY,
    AssetID              TEXT,
    CustomerKey          INTEGER NOT NULL REFERENCES DimCustomer(CustomerKey),
    TechnicianKey        INTEGER NOT NULL REFERENCES DimTechnician(TechnicianKey),
    RegionKey            INTEGER NOT NULL REFERENCES DimRegion(RegionKey),
    ServiceTypeKey       INTEGER NOT NULL REFERENCES DimServiceType(ServiceTypeKey),
    PriorityKey          INTEGER NOT NULL REFERENCES DimPriority(PriorityKey),
    CreatedDateKey       INTEGER NOT NULL REFERENCES DimDate(DateKey),
    ClosedDateKey        INTEGER REFERENCES DimDate(DateKey),   -- NULL while open
    CreatedAt            TEXT NOT NULL,
    ClosedAt             TEXT,
    CreatedHour          INTEGER,
    Status               TEXT,
    IsClosed             INTEGER,
    IsOpen               INTEGER,
    IsCancelled          INTEGER,
    SLAHours             REAL,
    ResolutionHours      REAL,
    SLAMet               INTEGER,               -- NULL unless Closed
    SLAStatus            TEXT,
    OpenAgeHours         REAL,
    RepeatVisitFlag      INTEGER,
    RepeatOfRequestID    TEXT,
    FirstTimeFixFlag     INTEGER,               -- NULL until 30 days after closure
    InvoiceID            TEXT,
    IsInvoiced           INTEGER,
    BillingType          TEXT,
    WorkHours            REAL,
    LabourCost           REAL,
    PartsCost            REAL,
    ServiceRevenue       REAL,
    CSATScore            INTEGER,
    DQ_MissingTechnician INTEGER
);

-- Grain: one row per region per month (budget)
CREATE TABLE FactTargets (
    RegionKey           INTEGER NOT NULL REFERENCES DimRegion(RegionKey),
    MonthStartDateKey   INTEGER NOT NULL REFERENCES DimDate(DateKey),
    RevenueTarget       REAL,
    SLATarget           REAL,
    CSATTarget          REAL,
    ProductivityTarget  REAL,
    BacklogTarget       INTEGER,
    PRIMARY KEY (RegionKey, MonthStartDateKey)
);

-- Grain: one row per region per month-end (periodic snapshot)
CREATE TABLE FactBacklogSnapshot (
    RegionKey           INTEGER NOT NULL REFERENCES DimRegion(RegionKey),
    SnapshotDateKey     INTEGER NOT NULL REFERENCES DimDate(DateKey),
    OpenRequests        INTEGER,
    OpenBreachedSLA     INTEGER,
    OpenOver7Days       INTEGER,
    PRIMARY KEY (RegionKey, SnapshotDateKey)
);

CREATE TABLE SecurityUserRegion (
    UserEmail   TEXT NOT NULL,
    RegionKey   INTEGER NOT NULL REFERENCES DimRegion(RegionKey),
    Role        TEXT,
    PRIMARY KEY (UserEmail, RegionKey)
);

CREATE INDEX ix_fsr_created  ON FactServiceRequests (CreatedDateKey);
CREATE INDEX ix_fsr_region   ON FactServiceRequests (RegionKey, CreatedDateKey);
CREATE INDEX ix_fsr_tech     ON FactServiceRequests (TechnicianKey);
CREATE INDEX ix_fsr_asset    ON FactServiceRequests (AssetID, CreatedAt);
