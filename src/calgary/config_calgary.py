"""
Configuration for Edition B: real City of Calgary 311 Service Requests.

Source: Open Calgary - "311 Service Requests"
        https://data.calgary.ca/Services-and-Amenities/311-Service-Requests/iahh-g8bj
Licence: Open Government Licence - City of Calgary

Notes on the source (checked October 2026):
* Dates are published at DAY precision (time part is always 00:00:00), so
  resolution time is measured in whole days, not hours.
* Fields used: service_request_id, requested_date, updated_date, closed_date,
  status_description, source, service_name, agency_responsible, comm_code,
  comm_name, location_type, longitude, latitude.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as BASE  # noqa: E402

ROOT = BASE.ROOT
# CALGARY_DATA_DIR lets the test-suite run the pipeline on a small fixture
# without touching your real downloaded data.
DATA = Path(os.environ.get("CALGARY_DATA_DIR", ROOT / "data" / "calgary"))
RAW_DIR = DATA / "raw"
PROCESSED_DIR = DATA / "processed"
QUARANTINE_DIR = DATA / "quarantine"
MODEL_DIR = DATA / "model"
SQL_OUT_DIR = DATA / "sql_output"
SQL_DIR = ROOT / "sql" / "calgary"
DOCS_DIR = Path(os.environ.get("CALGARY_DOCS_DIR", ROOT / "docs" / "calgary"))
WAREHOUSE_DB = DATA / "warehouse_calgary.db"
RAW_FILE = RAW_DIR / "calgary_311_service_requests.csv"

# Socrata (SODA) API
DATASET_ID = "iahh-g8bj"
API_URL = f"https://data.calgary.ca/resource/{DATASET_ID}.csv"
COLUMNS = ["service_request_id", "requested_date", "updated_date", "closed_date",
           "status_description", "source", "service_name", "agency_responsible",
           "comm_code", "comm_name", "location_type", "longitude", "latitude"]
PAGE_SIZE = 50_000

# Same analysis window and snapshot as Edition A so the two are comparable
START_DATE = BASE.START_DATE                     # 2024-01-01
SNAPSHOT_DATE = "2026-09-30"                     # requests after this are excluded;
                                                 # closures after this count as still open
CALENDAR_END = BASE.CALENDAR_END
FISCAL_YEAR_START_MONTH = 1                      # City of Calgary budgets on the calendar year

# Service-level benchmark. The open data has no published SLA per service, so we
# DERIVE one: for each service type, the 80th-percentile resolution time (days) in a
# baseline year. Later periods are measured against that benchmark.
BENCHMARK_YEAR = 2024
BENCHMARK_PERCENTILE = 0.80
MIN_BENCHMARK_VOLUME = 50   # service types with fewer closed requests use their category benchmark

# Calgary bounding box (generous) for coordinate validation
LAT_RANGE = (50.80, 51.25)
LON_RANGE = (-114.35, -113.80)

LONG_OPEN_DAYS = 365        # open longer than this at snapshot = "stale" ticket
