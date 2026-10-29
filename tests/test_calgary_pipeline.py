"""
Tests for Edition B (real Calgary 311 data).

The pipeline is run end-to-end on a small fixture file in the exact Calgary
export format (tests/fixtures/make_calgary_fixture.py), in a temporary folder,
so these tests work offline and never touch your real downloaded data.
If you have downloaded the real data, the model checks also run against it.
"""
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
REAL_MODEL = ROOT / "data" / "calgary" / "model"


@pytest.fixture(scope="module")
def fixture_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("calgary")
    (tmp / "raw").mkdir()
    subprocess.run([sys.executable, str(ROOT / "tests" / "fixtures" / "make_calgary_fixture.py"),
                    str(tmp / "raw" / "calgary_311_service_requests.csv"), "8000"], check=True)
    env = {**os.environ, "CALGARY_DATA_DIR": str(tmp), "CALGARY_DOCS_DIR": str(tmp / "docs"),
           "COMPARISON_DIR": str(tmp / "comparison"), "COMPARISON_DOC": str(tmp / "docs" / "cmp.md")}
    for step in ["clean_calgary.py", "build_model_calgary.py", "load_warehouse_calgary.py", "insights_calgary.py"]:
        r = subprocess.run([sys.executable, str(ROOT / "src" / "calgary" / step)], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        assert r.returncode == 0, r.stderr
    return tmp


def model_dirs(fixture_run):
    dirs = [fixture_run / "model"]
    if (REAL_MODEL / "FactServiceRequests.csv").exists():
        dirs.append(REAL_MODEL)
    return dirs


def test_fact_grain_unique(fixture_run):
    for d in model_dirs(fixture_run):
        f = pd.read_csv(d / "FactServiceRequests.csv", usecols=["ServiceRequestID"])
        assert f.ServiceRequestID.is_unique, d


def test_foreign_keys_resolve(fixture_run):
    for d in model_dirs(fixture_run):
        f = pd.read_csv(d / "FactServiceRequests.csv", low_memory=False)
        for fk, dim in [("ServiceTypeKey", "DimServiceType"), ("CommunityKey", "DimCommunity"), ("ChannelKey", "DimChannel")]:
            keys = pd.read_csv(d / f"{dim}.csv")[fk]
            assert f[fk].isin(keys).all(), (d, fk)
        dates = pd.read_csv(d / "DimDate.csv").DateKey
        assert f.RequestedDateKey.isin(dates).all()
        assert f.ClosedDateKey.dropna().isin(dates).all()


def test_business_rules(fixture_run):
    for d in model_dirs(fixture_run):
        f = pd.read_csv(d / "FactServiceRequests.csv", low_memory=False)
        closed = f[f.IsClosed == 1]
        assert (closed.ClosedDateKey >= closed.RequestedDateKey).all()
        assert (closed.ResolutionDays >= 0).all()
        assert f.loc[f.IsOpen == 1, "ClosedDateKey"].isna().all()
        assert (f.IsOpen + f.IsClosed == 1).all()


def test_defects_were_caught(fixture_run):
    log = pd.read_csv(fixture_run / "processed" / "data_quality_log.csv").set_index("Check").RowsAffected
    assert log["Exact duplicate rows"] > 0
    assert log["closed_date before requested_date"] > 0
    assert log["Closed without closed_date - imputed from updated_date"] > 0
    assert log["Missing community"] > 0


def test_no_rows_silently_lost(fixture_run):
    raw = pd.read_csv(fixture_run / "raw" / "calgary_311_service_requests.csv", dtype=str)
    log = pd.read_csv(fixture_run / "processed" / "data_quality_log.csv").set_index("Check").RowsAffected
    clean = pd.read_csv(fixture_run / "processed" / "clean_service_requests.csv", usecols=[0])
    q = pd.read_csv(fixture_run / "quarantine" / "quarantine_records.csv", usecols=[0])
    removed = (log["Exact duplicate rows"] + log["Same ticket ID more than once (record updated)"]
               + log["Requested outside analysis window (filtered, not an error)"])
    assert len(raw) == len(clean) + len(q) + removed


def test_sql_outputs_and_report(fixture_run):
    out = fixture_run / "sql_output"
    assert (out / "c01_overview_by_year.csv").exists()
    rules = pd.read_csv(out / "c00_validation_rules.csv")
    assert (rules.violations == 0).all()
    assert (fixture_run / "docs" / "calgary_insights.md").exists()
