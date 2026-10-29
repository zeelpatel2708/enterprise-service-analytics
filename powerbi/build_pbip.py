"""
build_pbip.py
=============
Generates ready-to-open Power BI Project (.pbip) folders for both editions:

    powerbi/pbip/enterprise_service_analytics.pbip   (Edition A, simulated)
    powerbi/pbip/calgary_311_operations.pbip         (Edition B, real Calgary)

Each project contains a TMDL semantic model with every table (Power Query M),
column type, hidden key, sort order, relationship, the full DAX measure library
(from measures.dax / measures_calgary.dax), the marked date table, row-level
security (Edition A) and empty, named report pages ready for visuals.

Run (from the project folder):
    python powerbi/build_pbip.py --project-folder "C:\\path\\to\\enterprise-service-analytics"

--project-folder is the path Power BI will read the CSV files from (the
ProjectFolder parameter). You can change it later in Power BI:
Transform data > Manage Parameters.

The same TMDL is also written as tmdl_scripts/*.tmdl so it can be pasted into
Power BI Desktop's TMDL view as a fallback.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "powerbi" / "pbip"
NS = uuid.UUID("6f1c2a52-6f43-4b8f-9d1c-1a2b3c4d5e6f")  # deterministic GUIDs -> clean git diffs


def gid(*parts) -> str:
    return str(uuid.uuid5(NS, "|".join(map(str, parts))))


def q(name: str) -> str:
    """Quote a TMDL object name when needed."""
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "'" + name.replace("'", "''") + "'"


# ---------------------------------------------------------------- columns ----
DATE_COLS = {"Date", "MonthStartDate", "MonthEndDate", "AccountStartDate", "FirstRequestDate",
             "LastRequestDate", "HireDate", "TerminationDate"}
DATETIME_COLS = {"CreatedAt", "ClosedAt"}
MONEY_COLS = {"LabourCost", "PartsCost", "ServiceRevenue", "RevenueTarget", "ListPrice2024"}


def infer_columns(csv: Path) -> list[tuple[str, str]]:
    """(column, tmdl dataType) using the data itself plus naming conventions."""
    df = pd.read_csv(csv, nrows=200_000, keep_default_na=False, na_values=[""], low_memory=False)
    cols = []
    for c in df.columns:
        s = df[c]
        if c in DATETIME_COLS:
            t = "dateTimeFull"
        elif c in DATE_COLS:
            t = "date"
        elif c in MONEY_COLS:
            t = "decimal"
        elif pd.api.types.is_integer_dtype(s):
            t = "int64"
        elif pd.api.types.is_float_dtype(s):
            t = "int64" if s.dropna().size and (s.dropna() % 1 == 0).all() and not c.endswith(("Hours", "Target", "Years", "Multiplier", "Index", "Share", "Pct", "Raw", "Closed", "Latitude", "Longitude")) else "double"
        else:
            t = "string"
        cols.append((c, t))
    return cols


M_TYPE = {"int64": "Int64.Type", "string": "type text", "date": "type date",
          "dateTimeFull": "type datetime", "double": "type number", "decimal": "Currency.Type"}
TMDL_TYPE = {"int64": "int64", "string": "string", "date": "dateTime", "dateTimeFull": "dateTime",
             "double": "double", "decimal": "decimal"}
FORMAT = {"date": "yyyy-mm-dd", "dateTimeFull": "yyyy-mm-dd hh:nn", "decimal": "\\$#,0.00;(\\$#,0.00);\\$#,0.00",
          "int64": "0", "double": "#,0.00"}


def m_expression(rel_path: str, cols) -> list[str]:
    types = ",\n".join(f'        {{"{c}", {M_TYPE[t]}}}' for c, t in cols)
    win_path = rel_path.replace("/", "\\")
    return (f'''let
    Source = Csv.Document(
        File.Contents(ProjectFolder & "\\{win_path}"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(
        Promoted,
        {{
{types}
        }},
        "en-CA")
in
    Typed''').split("\n")


def table_tmdl(name, rel_path, cols, *, hidden=(), sort_by=None, no_summarize=(), date_table=False,
               data_category=None, is_hidden_table=False) -> str:
    sort_by = sort_by or {}
    data_category = data_category or {}
    L = [f"table {q(name)}", f"\tlineageTag: {gid('t', name)}"]
    if date_table:
        L.append("\tdataCategory: Time")
    if is_hidden_table:
        L.append("\tisHidden")
    L.append("")
    for c, t in cols:
        L.append(f"\tcolumn {q(c)}")
        L.append(f"\t\tdataType: {TMDL_TYPE[t]}")
        if date_table and c == "Date":
            L.append("\t\tisKey")
        if c in hidden or c.endswith("Key") or c.startswith(("Is", "DQ_")):
            L.append("\t\tisHidden")
        if t in FORMAT:
            L.append(f"\t\tformatString: {FORMAT[t]}")
        L.append(f"\t\tlineageTag: {gid('c', name, c)}")
        if t in ("string", "date", "dateTimeFull") or c in no_summarize or c.endswith("Key") or t == "int64" and c in no_summarize:
            L.append("\t\tsummarizeBy: none")
        elif t in ("int64", "double", "decimal"):
            L.append("\t\tsummarizeBy: none" if c in no_summarize else "\t\tsummarizeBy: sum")
        if c in data_category:
            L.append(f"\t\tdataCategory: {data_category[c]}")
        L.append(f"\t\tsourceColumn: {c}")
        if c in sort_by:
            L.append(f"\t\tsortByColumn: {q(sort_by[c])}")
        L.append("")
        L.append("\t\tannotation SummarizationSetBy = Automatic")
        L.append("")
    L.append(f"\tpartition {q(name)} = m")
    L.append("\t\tmode: import")
    L.append("\t\tsource =")
    L += ["\t\t\t\t" + line for line in m_expression(rel_path, cols)]
    L += ["", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- measures ---
def parse_measures(dax_file: Path) -> list[dict]:
    lines = dax_file.read_text(encoding="utf-8").splitlines()
    measures, folder, cur = [], "Measures", None
    head = re.compile(r"^// [=\-]+ (\d\d [^=\-]+?) [=\-]+\s*$")
    start = re.compile(r"^(?!VAR |RETURN)([A-Za-z][^=\[\]{}\"]*?) =\s*$")
    fmt = re.compile(r"\[Format: (.+?)\]")
    for line in lines:
        h = head.match(line)
        if h:
            folder = h.group(1).strip()
            cur = None
            continue
        s = start.match(line)
        if s:
            cur = {"name": s.group(1).strip(), "folder": folder, "expr": [], "format": None}
            measures.append(cur)
            continue
        if cur is None:
            continue
        f = fmt.search(line)
        if f and line.lstrip().startswith("//"):
            cur["format"] = f.group(1).strip()
            cur = None  # a [Format] comment closes the measure
            continue
        cur["expr"].append(line)
    for m in measures:
        e = m["expr"]
        while e and (not e[-1].strip() or e[-1].lstrip().startswith("//")):
            e.pop()  # drop trailing comments / blank lines
        while e and not e[0].strip():
            e.pop(0)
        assert e, f"empty measure {m['name']}"
    return measures


def measures_table_tmdl(measures) -> str:
    L = ["table _Measures", f"\tlineageTag: {gid('t', '_Measures')}", ""]
    for m in measures:
        expr = [x.rstrip() for x in m["expr"] if x.strip()]  # no blank lines inside TMDL expressions
        notes = []
        while expr and expr[0].lstrip().startswith("//"):  # leading comments become the measure description
            notes.append(expr.pop(0).lstrip()[2:].strip())
        L += [f"\t/// {n}" for n in notes if n]
        L.append(f"\tmeasure {q(m['name'])} =")
        L += ["\t\t\t" + x for x in expr]
        if m["format"]:
            L.append(f"\t\tformatString: {m['format']}")
        L.append(f"\t\tdisplayFolder: {m['folder']}")
        L.append(f"\t\tlineageTag: {gid('m', m['name'])}")
        L.append("")
    L += ["\tcolumn Value", "\t\tdataType: int64", "\t\tisHidden", "\t\tformatString: 0",
          f"\t\tlineageTag: {gid('c', '_Measures', 'Value')}", "\t\tsummarizeBy: none",
          "\t\tisNameInferred", "\t\tsourceColumn: [Value]", "",
          "\t\tannotation SummarizationSetBy = Automatic", "",
          "\tpartition _Measures = calculated", "\t\tmode: import",
          '\t\tsource = ROW ( "Value", 0 )', "", "\tannotation PBI_Id = measures", ""]
    return "\n".join(L)


KPI_SELECTOR = """table 'KPI Selector'
\tlineageTag: {tag}

\tcolumn KPI
\t\tdataType: string
\t\tlineageTag: {tag1}
\t\tsummarizeBy: none
\t\tisNameInferred
\t\tsourceColumn: [KPI]
\t\tsortByColumn: Order

\t\tannotation SummarizationSetBy = Automatic

\tcolumn Order
\t\tdataType: int64
\t\tisHidden
\t\tformatString: 0
\t\tlineageTag: {tag2}
\t\tsummarizeBy: none
\t\tisNameInferred
\t\tsourceColumn: [Order]

\t\tannotation SummarizationSetBy = Automatic

\tpartition 'KPI Selector' = calculated
\t\tmode: import
\t\tsource =
\t\t\t\tDATATABLE (
\t\t\t\t    "KPI", STRING, "Order", INTEGER,
\t\t\t\t    {{
\t\t\t\t        {{ "Service Revenue", 1 }},
\t\t\t\t        {{ "SLA Compliance %", 2 }},
\t\t\t\t        {{ "Avg CSAT", 3 }},
\t\t\t\t        {{ "Backlog", 4 }},
\t\t\t\t        {{ "First-Time Fix Rate", 5 }}
\t\t\t\t    }}
\t\t\t\t)

\tannotation PBI_Id = kpi_selector
""".format(tag=gid("t", "KPI Selector"), tag1=gid("c", "KPI Selector", "KPI"), tag2=gid("c", "KPI Selector", "Order"))


# ---------------------------------------------------------------- writers ----
def write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_project(name, display, tables, relationships, measures, project_folder, pages,
                  roles="", extra_tables=()):
    sm = OUT / f"{name}.SemanticModel"
    rp = OUT / f"{name}.Report"
    for d in (sm, rp):
        if d.exists():
            shutil.rmtree(d)
    d = sm / "definition"

    write(OUT / f"{name}.pbip", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{name}.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2))
    write(sm / "definition.pbism", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "settings": {}}, indent=2))
    for folder, kind in ((sm, "SemanticModel"), (rp, "Report")):
        write(folder / ".platform", json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": kind, "displayName": display},
            "config": {"version": "2.0", "logicalId": gid(name, kind)}}, indent=2))

    write(d / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n\n")
    table_names = [t[0] for t in tables] + list(extra_tables) + ["_Measures"]
    write(d / "model.tmdl", "\n".join([
        "model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-CA", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
        "annotation __PBI_TimeIntelligenceEnabled = 0", "",
        "annotation PBI_QueryOrder = " + json.dumps(["ProjectFolder"] + [t[0] for t in tables]), "",
        "annotation PBI_ProTooling = [\"DevMode\"]", ""] + [f"ref table {q(t)}" for t in table_names] + [""]))
    write(d / "expressions.tmdl", "\n".join([
        f'expression ProjectFolder = "{project_folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
        f"\tlineageTag: {gid('e', name, 'ProjectFolder')}", "", "\tannotation PBI_ResultType = Text", ""]))
    for tname, tmdl in tables:
        write(d / "tables" / f"{tname}.tmdl", tmdl)
    for tname, tmdl in extra_tables.items() if isinstance(extra_tables, dict) else []:
        write(d / "tables" / f"{tname}.tmdl", tmdl)
    write(d / "tables" / "_Measures.tmdl", measures_table_tmdl(measures))

    rel = []
    for frm, to, active in relationships:
        rel.append(f"relationship {gid('r', name, frm, to)}")
        if not active:
            rel.append("\tisActive: false")
        ft, fc = frm.split(".")
        tt, tc = to.split(".")
        rel.append(f"\tfromColumn: {q(ft)}.{q(fc)}")
        rel.append(f"\ttoColumn: {q(tt)}.{q(tc)}")
        rel.append("")
    write(d / "relationships.tmdl", "\n".join(rel))
    if roles:
        write(d / "roles" / "Regional Manager.tmdl", roles)

    # ---------------- report: empty named pages, ready for visuals ----------
    write(rp / "definition.pbir", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{name}.SemanticModel"}}}, indent=2))
    sections = [{"config": "{}", "displayName": p, "displayOption": 1, "filters": "[]",
                 "height": 720.0, "name": f"ReportSection{i:02d}", "ordinal": i,
                 "visualContainers": [], "width": 1280.0} for i, p in enumerate(pages)]
    report_config = {"version": "5.59", "themeCollection": {}, "activeSectionIndex": 0,
                     "defaultDrillFilterOtherVisuals": True, "linguisticSchemaSyncVersion": 0,
                     "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True,
                                  "useStylableVisualContainerHeader": True, "exportDataMode": 1,
                                  "useDefaultAggregateDisplayName": True},
                     "objects": {}}
    write(rp / "report.json", json.dumps({"config": json.dumps(report_config), "layoutOptimization": 0,
                                          "sections": sections}, indent=2))

    # ---------------- fallback: one TMDL script for Desktop's TMDL view -----
    script = ["createOrReplace", ""]
    for f in [d / "expressions.tmdl"] + sorted((d / "tables").glob("*.tmdl")) + [d / "relationships.tmdl"] + sorted((d / "roles").glob("*.tmdl")):
        script += ["\t" + x if x else "" for x in f.read_text(encoding="utf-8").splitlines()] + [""]
    write(OUT / "tmdl_scripts" / f"{name}.tmdl", "\n".join(script))
    print(f"  {name}.pbip  ({len(tables)} tables, {len(relationships)} relationships, {len(measures)} measures)")


def edition_a(project_folder):
    mdir = ROOT / "data" / "model"
    rel = "data/model/{}.csv"
    spec = {
        "DimDate": dict(date_table=True, sort_by={"Month": "MonthNumber", "MonthShort": "MonthNumber",
                                                  "DayOfWeek": "DayOfWeekNumber", "YearMonth": "YearMonthKey",
                                                  "Quarter": "QuarterNumber"},
                        no_summarize={"Year", "QuarterNumber", "MonthNumber", "ISOWeek", "Day", "DayOfWeekNumber",
                                      "FiscalMonthNumber", "YearMonthKey"}),
        "DimRegion": {}, "DimCustomer": {},
        "DimTechnician": dict(no_summarize={"TenureYears"}),
        "DimServiceType": dict(no_summarize={"ListPrice2024"}),
        "DimPriority": dict(sort_by={"Priority": "SortOrder"}, no_summarize={"SLAHours", "PriceMultiplier", "SortOrder"}),
        "FactServiceRequests": dict(hidden={"AssetID", "RepeatOfRequestID", "InvoiceID", "SLAMet", "RepeatVisitFlag",
                                            "FirstTimeFixFlag", "CSATScore", "SLAHours", "ResolutionHours",
                                            "OpenAgeHours", "WorkHours", "LabourCost", "PartsCost", "ServiceRevenue",
                                            "CreatedHour"},
                                    no_summarize={"CreatedHour", "SLAHours"}),
        "FactTargets": dict(hidden={"RevenueTarget", "SLATarget", "CSATTarget", "ProductivityTarget", "BacklogTarget"}),
        "FactBacklogSnapshot": dict(hidden={"OpenRequests", "OpenBreachedSLA", "OpenOver7Days"}),
        "SecurityUserRegion": dict(is_hidden_table=True),
    }
    tables = [(t, table_tmdl(t, rel.format(t), infer_columns(mdir / f"{t}.csv"), **kw)) for t, kw in spec.items()]
    rels = [("FactServiceRequests.CustomerKey", "DimCustomer.CustomerKey", True),
            ("FactServiceRequests.TechnicianKey", "DimTechnician.TechnicianKey", True),
            ("FactServiceRequests.RegionKey", "DimRegion.RegionKey", True),
            ("FactServiceRequests.ServiceTypeKey", "DimServiceType.ServiceTypeKey", True),
            ("FactServiceRequests.PriorityKey", "DimPriority.PriorityKey", True),
            ("FactServiceRequests.CreatedDateKey", "DimDate.DateKey", True),
            ("FactServiceRequests.ClosedDateKey", "DimDate.DateKey", False),
            ("FactTargets.RegionKey", "DimRegion.RegionKey", True),
            ("FactTargets.MonthStartDateKey", "DimDate.DateKey", True),
            ("FactBacklogSnapshot.RegionKey", "DimRegion.RegionKey", True),
            ("FactBacklogSnapshot.SnapshotDateKey", "DimDate.DateKey", True)]
    roles = "\n".join([
        "role 'Regional Manager'", "\tmodelPermission: read", "",
        "\ttablePermission DimRegion =",
        "\t\t\tDimRegion[RegionKey]",
        "\t\t\t    IN CALCULATETABLE (",
        "\t\t\t        VALUES ( SecurityUserRegion[RegionKey] ),",
        "\t\t\t        SecurityUserRegion[UserEmail] = USERPRINCIPALNAME ()",
        "\t\t\t    )", "",
        f"\tannotation PBI_Id = {gid('role', 'rm')}", ""])
    build_project("enterprise_service_analytics", "Enterprise Service Analytics (Edition A)", tables, rels,
                  parse_measures(ROOT / "powerbi" / "measures.dax"), project_folder,
                  ["Executive Overview", "Operations Performance", "Regional Performance",
                   "Technician Analysis", "Root Cause & Exceptions"],
                  roles=roles, extra_tables={"KPI Selector": KPI_SELECTOR})


def edition_b(project_folder, model_dir: Path, comparison_dir: Path):
    spec = {
        "DimDate": dict(date_table=True, sort_by={"Month": "MonthNumber", "MonthShort": "MonthNumber",
                                                  "DayOfWeek": "DayOfWeekNumber", "YearMonth": "YearMonthKey",
                                                  "Quarter": "QuarterNumber"},
                        no_summarize={"Year", "QuarterNumber", "MonthNumber", "ISOWeek", "Day", "DayOfWeekNumber",
                                      "YearMonthKey"}),
        "DimServiceType": dict(no_summarize={"BenchmarkDays", "VolumeRank"}),
        "DimCommunity": dict(data_category={"Latitude": "Latitude", "Longitude": "Longitude"},
                             no_summarize={"Latitude", "Longitude"}),
        "DimChannel": {},
        "FactServiceRequests": dict(hidden={"ResolutionDays", "SameDayClosure", "BenchmarkDays", "WithinBenchmark",
                                            "OpenAgeDays", "ClosedDateImputed", "ReopenedFlag", "StatusRaw"}),
        "FactBacklogSnapshot": dict(hidden={"OpenRequests", "OpenPastBenchmark", "OpenOver90Days"}),
    }
    tables = [(t, table_tmdl(t, f"data/calgary/model/{t}.csv", infer_columns(model_dir / f"{t}.csv"), **kw))
              for t, kw in spec.items()]
    for c in ["comparison_summary", "comparison_seasonality", "comparison_day_of_week",
              "comparison_resolution_distribution", "comparison_data_quality", "comparison_capabilities"]:
        kw = {"sort_by": {"Bucket": "BucketOrder"}} if c == "comparison_resolution_distribution" else {}
        if c == "comparison_day_of_week":
            kw = {"sort_by": {"DayOfWeek": "DayOfWeekNumber"}}
        tables.append((c, table_tmdl(c, f"data/comparison/{c}.csv", infer_columns(comparison_dir / f"{c}.csv"),
                                     no_summarize={"MonthNumber", "DayOfWeekNumber", "BucketOrder"}, **kw)))
    rels = [("FactServiceRequests.ServiceTypeKey", "DimServiceType.ServiceTypeKey", True),
            ("FactServiceRequests.CommunityKey", "DimCommunity.CommunityKey", True),
            ("FactServiceRequests.ChannelKey", "DimChannel.ChannelKey", True),
            ("FactServiceRequests.RequestedDateKey", "DimDate.DateKey", True),
            ("FactServiceRequests.ClosedDateKey", "DimDate.DateKey", False),
            ("FactBacklogSnapshot.ServiceTypeKey", "DimServiceType.ServiceTypeKey", True),
            ("FactBacklogSnapshot.SnapshotDateKey", "DimDate.DateKey", True)]
    build_project("calgary_311_operations", "Calgary 311 Operations (Edition B)", tables, rels,
                  parse_measures(ROOT / "powerbi" / "calgary" / "measures_calgary.dax"), project_folder,
                  ["City Overview", "Service Performance", "Communities", "Seasonality & Backlog", "Simulated vs Real"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-folder", default=str(ROOT))
    ap.add_argument("--calgary-model-dir", default=str(ROOT / "data" / "calgary" / "model"))
    ap.add_argument("--comparison-dir", default=str(ROOT / "data" / "comparison"))
    a = ap.parse_args()
    folder = a.project_folder.rstrip("\\/")
    print("Building Power BI projects ->", OUT)
    edition_a(folder)
    if (Path(a.calgary_model_dir) / "FactServiceRequests.csv").exists():
        edition_b(folder, Path(a.calgary_model_dir), Path(a.comparison_dir))
    else:
        print("  (Edition B skipped: run the Calgary pipeline first)")


if __name__ == "__main__":
    main()
