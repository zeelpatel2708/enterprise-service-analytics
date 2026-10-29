// =============================================================================
// power_query.m - Power Query (M) for every table in the model
//
// SETUP
//   1. Home > Transform data > Manage Parameters > New Parameter
//        Name: ProjectFolder   Type: Text
//        Current value: the full path of your repo, e.g.
//        C:\Users\you\Documents\enterprise-service-analytics
//   2. For each table below: New Source > Blank Query > Advanced Editor >
//      paste the code > rename the query to the table name in the header.
//
// WHY A PARAMETER? Anyone who clones the repo changes ONE value instead of
// editing ten file paths. Explicit column types (not "auto-detect") make the
// model stable when a CSV changes - a common interview question.
// =============================================================================

// ---------------------------------------------------------------- DimDate
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\model\DimDate.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"DateKey", Int64.Type},
            {"Date", type date},
            {"Year", Int64.Type},
            {"QuarterNumber", Int64.Type},
            {"Quarter", type text},
            {"YearQuarter", type text},
            {"MonthNumber", Int64.Type},
            {"Month", type text},
            {"MonthShort", type text},
            {"YearMonth", type text},
            {"YearMonthKey", Int64.Type},
            {"MonthStartDate", type date},
            {"MonthEndDate", type date},
            {"ISOWeek", Int64.Type},
            {"Day", Int64.Type},
            {"DayOfWeekNumber", Int64.Type},
            {"DayOfWeek", type text},
            {"IsWeekend", Int64.Type},
            {"FiscalYear", type text},
            {"FiscalQuarter", type text},
            {"FiscalMonthNumber", Int64.Type},
            {"IsAfterSnapshot", Int64.Type},
            {"IsCompleteMonth", Int64.Type}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- DimRegion
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\model\DimRegion.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"RegionKey", Int64.Type},
            {"Region", type text},
            {"Province", type text},
            {"RegionalManager", type text},
            {"RegionalManagerEmail", type text}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- DimCustomer
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\model\DimCustomer.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"CustomerKey", Int64.Type},
            {"CustomerID", type text},
            {"CustomerName", type text},
            {"Industry", type text},
            {"CustomerSegment", type text},
            {"City", type text},
            {"Province", type text},
            {"AccountStartDate", type date},
            {"FirstRequestDate", type date},
            {"LastRequestDate", type date},
            {"ActivityStatus", type text}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- DimTechnician
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\model\DimTechnician.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"TechnicianKey", Int64.Type},
            {"TechnicianID", type text},
            {"TechnicianName", type text},
            {"SkillLevel", type text},
            {"Specialization", type text},
            {"Region", type text},
            {"HireDate", type date},
            {"TerminationDate", type date},
            {"IsActive", Int64.Type},
            {"TenureYears", type number},
            {"TenureBand", type text}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- DimServiceType
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\model\DimServiceType.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"ServiceTypeKey", Int64.Type},
            {"ServiceCategory", type text},
            {"ServiceType", type text},
            {"ListPrice2024", Currency.Type}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- DimPriority
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\model\DimPriority.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"PriorityKey", Int64.Type},
            {"Priority", type text},
            {"SLAHours", type number},
            {"PriceMultiplier", type number},
            {"SortOrder", Int64.Type}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- FactServiceRequests
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\model\FactServiceRequests.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"ServiceRequestID", type text},
            {"AssetID", type text},
            {"CustomerKey", Int64.Type},
            {"TechnicianKey", Int64.Type},
            {"RegionKey", Int64.Type},
            {"ServiceTypeKey", Int64.Type},
            {"PriorityKey", Int64.Type},
            {"CreatedDateKey", Int64.Type},
            {"ClosedDateKey", Int64.Type},
            {"CreatedAt", type datetime},
            {"ClosedAt", type datetime},
            {"CreatedHour", Int64.Type},
            {"Status", type text},
            {"IsClosed", Int64.Type},
            {"IsOpen", Int64.Type},
            {"IsCancelled", Int64.Type},
            {"SLAHours", type number},
            {"ResolutionHours", type number},
            {"SLAMet", Int64.Type},
            {"SLAStatus", type text},
            {"OpenAgeHours", type number},
            {"RepeatVisitFlag", Int64.Type},
            {"RepeatOfRequestID", type text},
            {"FirstTimeFixFlag", Int64.Type},
            {"InvoiceID", type text},
            {"IsInvoiced", Int64.Type},
            {"BillingType", type text},
            {"WorkHours", type number},
            {"LabourCost", Currency.Type},
            {"PartsCost", Currency.Type},
            {"ServiceRevenue", Currency.Type},
            {"CSATScore", Int64.Type},
            {"DQ_MissingTechnician", Int64.Type}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- FactTargets
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\model\FactTargets.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"RegionKey", Int64.Type},
            {"MonthStartDateKey", Int64.Type},
            {"RevenueTarget", Currency.Type},
            {"SLATarget", type number},
            {"CSATTarget", type number},
            {"ProductivityTarget", Int64.Type},
            {"BacklogTarget", Int64.Type}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- FactBacklogSnapshot
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\model\FactBacklogSnapshot.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"RegionKey", Int64.Type},
            {"SnapshotDateKey", Int64.Type},
            {"OpenRequests", Int64.Type},
            {"OpenBreachedSLA", Int64.Type},
            {"OpenOver7Days", Int64.Type}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- SecurityUserRegion
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\model\SecurityUserRegion.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"UserEmail", type text},
            {"RegionKey", Int64.Type},
            {"Role", type text}
        },
        "en-CA")
in
    Typed

// =============================================================================
// OPTIONAL SKILLS DEMO: cleaning the RAW extract directly in Power Query
// (the Python pipeline already does this - this query shows you can do it in
//  Power Query too, which many BI roles expect). Name it: stg_FSM_Cleaned
// =============================================================================
let
    Source    = Csv.Document(
                    File.Contents(ProjectFolder & "\data\raw\fsm_service_requests.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted  = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),

    // 1. Remove exact duplicate rows
    Deduped   = Table.Distinct(Promoted),

    // 2. Standardise region names with a mapping table
    RegionMap = #table(
        {"RawKey", "Region"},
        {
            {"toronto", "Toronto"}, {"tor.", "Toronto"}, {"to", "Toronto"},
            {"mississauga", "Mississauga"}, {"missisauga", "Mississauga"},
            {"ottawa", "Ottawa"}, {"ott.", "Ottawa"},
            {"hamilton", "Hamilton"}, {"ham.", "Hamilton"},
            {"kitchener-waterloo", "Kitchener-Waterloo"}, {"kitchener waterloo", "Kitchener-Waterloo"},
            {"k-w", "Kitchener-Waterloo"}, {"kw", "Kitchener-Waterloo"}, {"kitchener", "Kitchener-Waterloo"},
            {"london", "London"}, {"london on", "London"}
        }),
    WithKey   = Table.AddColumn(Deduped, "RawKey", each Text.Lower(Text.Trim([Region])), type text),
    Merged    = Table.NestedJoin(WithKey, {"RawKey"}, RegionMap, {"RawKey"}, "Map", JoinKind.LeftOuter),
    Expanded  = Table.ExpandTableColumn(Merged, "Map", {"Region"}, {"RegionClean"}),

    // 3. Parse dates safely: invalid values become null instead of breaking refresh
    Created   = Table.AddColumn(Expanded, "CreatedAtParsed",
                    each try DateTime.FromText([CreatedAt], [Format = "yyyy-MM-dd HH:mm:ss", Culture = "en-CA"]) otherwise null,
                    type nullable datetime),
    Closed    = Table.AddColumn(Created, "ClosedAtParsed",
                    each if [ClosedAt] = "" then null
                         else try DateTime.FromText([ClosedAt], [Format = "yyyy-MM-dd HH:mm:ss", Culture = "en-CA"]) otherwise null,
                    type nullable datetime),

    // 4. Flag (don't silently drop) rule violations
    Flagged   = Table.AddColumn(Closed, "DQ_Issue", each
                    if [CreatedAtParsed] = null then "Invalid CreatedAt"
                    else if [CustomerID] = "" then "Missing CustomerID"
                    else if [ClosedAtParsed] <> null and [ClosedAtParsed] < [CreatedAtParsed] then "Closed before created"
                    else if [RegionClean] = null then "Unknown region"
                    else "OK", type text),
    Final     = Table.RemoveColumns(Flagged, {"RawKey"})
in
    Final
