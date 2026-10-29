// =============================================================================
// power_query_calgary.m - Power Query (M) for Edition B (real Calgary 311 data)
//
// Uses the same ProjectFolder parameter as Edition A. Build Edition B in its own
// .pbix (calgary_311_operations.pbix). For each table: Blank Query > Advanced
// Editor > paste > rename the query to the table name in the header.
// =============================================================================

// ---------------------------------------------------------------- DimDate
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\calgary\model\DimDate.csv"),
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
            {"ISOWeek", Int64.Type},
            {"Day", Int64.Type},
            {"DayOfWeekNumber", Int64.Type},
            {"DayOfWeek", type text},
            {"IsWeekend", Int64.Type},
            {"Season", type text},
            {"IsAfterSnapshot", Int64.Type}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- DimServiceType
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\calgary\model\DimServiceType.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"ServiceTypeKey", Int64.Type},
            {"ServiceName", type text},
            {"ServiceCategory", type text},
            {"Agency", type text},
            {"BenchmarkDays", Int64.Type},
            {"VolumeRank", Int64.Type},
            {"Top20Service", type text}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- DimCommunity
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\calgary\model\DimCommunity.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"CommunityKey", Int64.Type},
            {"CommunityCode", type text},
            {"CommunityName", type text},
            {"Latitude", type number},
            {"Longitude", type number}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- DimChannel
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\calgary\model\DimChannel.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"ChannelKey", Int64.Type},
            {"Channel", type text},
            {"ChannelGroup", type text}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- FactServiceRequests
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\calgary\model\FactServiceRequests.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"ServiceRequestID", type text},
            {"ServiceTypeKey", Int64.Type},
            {"CommunityKey", Int64.Type},
            {"ChannelKey", Int64.Type},
            {"RequestedDateKey", Int64.Type},
            {"ClosedDateKey", Int64.Type},
            {"StatusGroup", type text},
            {"StatusRaw", type text},
            {"IsClosed", Int64.Type},
            {"IsOpen", Int64.Type},
            {"IsDuplicateRequest", Int64.Type},
            {"ResolutionDays", Int64.Type},
            {"SameDayClosure", Int64.Type},
            {"BenchmarkDays", Int64.Type},
            {"WithinBenchmark", Int64.Type},
            {"OpenAgeDays", Int64.Type},
            {"IsStaleOpen", Int64.Type},
            {"ClosedDateImputed", Int64.Type},
            {"ReopenedFlag", Int64.Type}
        },
        "en-CA")
in
    Typed

// ---------------------------------------------------------------- FactBacklogSnapshot
let
    Source   = Csv.Document(
                   File.Contents(ProjectFolder & "\data\calgary\model\FactBacklogSnapshot.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(
        Promoted,
        {
            {"ServiceTypeKey", Int64.Type},
            {"SnapshotDateKey", Int64.Type},
            {"OpenRequests", Int64.Type},
            {"OpenPastBenchmark", Int64.Type},
            {"OpenOver90Days", Int64.Type}
        },
        "en-CA")
in
    Typed

// =============================================================================
// COMPARISON TABLES (Simulated vs Real page) - from data/comparison/
// Load each of these the same way; they have no relationships (standalone visuals).
// =============================================================================

// ---------------------------------------------------------------- comparison_summary
let
    Source   = Csv.Document(File.Contents(ProjectFolder & "\data\comparison\comparison_summary.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
    // then: Transform > Detect data type (these small tables are safe to auto-type)
in
    Promoted

// ---------------------------------------------------------------- comparison_seasonality
let
    Source   = Csv.Document(File.Contents(ProjectFolder & "\data\comparison\comparison_seasonality.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
    // then: Transform > Detect data type (these small tables are safe to auto-type)
in
    Promoted

// ---------------------------------------------------------------- comparison_day_of_week
let
    Source   = Csv.Document(File.Contents(ProjectFolder & "\data\comparison\comparison_day_of_week.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
    // then: Transform > Detect data type (these small tables are safe to auto-type)
in
    Promoted

// ---------------------------------------------------------------- comparison_resolution_distribution
let
    Source   = Csv.Document(File.Contents(ProjectFolder & "\data\comparison\comparison_resolution_distribution.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
    // then: Transform > Detect data type (these small tables are safe to auto-type)
in
    Promoted

// ---------------------------------------------------------------- comparison_data_quality
let
    Source   = Csv.Document(File.Contents(ProjectFolder & "\data\comparison\comparison_data_quality.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
    // then: Transform > Detect data type (these small tables are safe to auto-type)
in
    Promoted

// ---------------------------------------------------------------- comparison_capabilities
let
    Source   = Csv.Document(File.Contents(ProjectFolder & "\data\comparison\comparison_capabilities.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
    // then: Transform > Detect data type (these small tables are safe to auto-type)
in
    Promoted
