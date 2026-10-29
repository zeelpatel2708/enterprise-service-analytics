"""
Automated data-quality tests for the cleaned star schema.
Run after the pipeline:   pytest -v

These are the same guarantees a BI team would enforce in CI before a
Power BI dataset refresh is allowed to publish.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config as C  # noqa: E402

MODEL = C.ROOT / "data" / "model"


@pytest.fixture(scope="module")
def fact():
    return pd.read_csv(MODEL / "FactServiceRequests.csv", parse_dates=["CreatedAt", "ClosedAt"])


@pytest.fixture(scope="module")
def dims():
    return {n: pd.read_csv(MODEL / f"{n}.csv") for n in
            ["DimDate", "DimCustomer", "DimTechnician", "DimRegion", "DimServiceType", "DimPriority"]}


# ---------------------------------------------------------------- structure --
def test_fact_grain_is_unique(fact):
    assert fact.ServiceRequestID.is_unique


@pytest.mark.parametrize("dim,key", [("DimDate", "DateKey"), ("DimCustomer", "CustomerKey"),
                                     ("DimTechnician", "TechnicianKey"), ("DimRegion", "RegionKey"),
                                     ("DimServiceType", "ServiceTypeKey"), ("DimPriority", "PriorityKey")])
def test_dimension_keys_unique(dims, dim, key):
    assert dims[dim][key].is_unique


@pytest.mark.parametrize("fk,dim,key", [("CustomerKey", "DimCustomer", "CustomerKey"),
                                        ("TechnicianKey", "DimTechnician", "TechnicianKey"),
                                        ("RegionKey", "DimRegion", "RegionKey"),
                                        ("ServiceTypeKey", "DimServiceType", "ServiceTypeKey"),
                                        ("PriorityKey", "DimPriority", "PriorityKey"),
                                        ("CreatedDateKey", "DimDate", "DateKey")])
def test_no_orphan_foreign_keys(fact, dims, fk, dim, key):
    orphans = ~fact[fk].isin(dims[dim][key])
    assert orphans.sum() == 0, f"{orphans.sum()} orphan {fk} values"


def test_closed_date_keys_resolve(fact, dims):
    closed = fact.ClosedDateKey.dropna()
    assert closed.isin(dims["DimDate"].DateKey).all()


def test_date_table_is_contiguous(dims):
    d = pd.to_datetime(dims["DimDate"].Date)
    assert (d.diff().dropna() == pd.Timedelta(days=1)).all()
    assert d.min() <= fact_min_date() and d.max() >= pd.Timestamp(C.SNAPSHOT_DATE).normalize()


def fact_min_date():
    return pd.read_csv(MODEL / "FactServiceRequests.csv", usecols=["CreatedAt"],
                       parse_dates=["CreatedAt"]).CreatedAt.min().normalize()


# ----------------------------------------------------------- business rules --
def test_no_closed_before_created(fact):
    assert (fact.ClosedAt.dropna() >= fact.loc[fact.ClosedAt.notna(), "CreatedAt"]).all()


def test_csat_in_range(fact):
    assert fact.CSATScore.dropna().between(1, 5).all()


def test_no_negative_money(fact):
    for col in ["LabourCost", "PartsCost", "ServiceRevenue"]:
        assert (fact[col].dropna() >= 0).all(), col


def test_status_flags_mutually_exclusive(fact):
    assert (fact.IsOpen + fact.IsClosed + fact.IsCancelled == 1).all()


def test_sla_result_only_for_closed(fact):
    assert fact.loc[fact.IsClosed == 1, "SLAMet"].notna().all()
    assert fact.loc[fact.IsClosed == 0, "SLAMet"].isna().all()


def test_sla_met_matches_hours(fact):
    c = fact[fact.IsClosed == 1]
    expected = (c.ResolutionHours <= c.SLAHours).astype(int)
    assert (expected == c.SLAMet).mean() > 0.999  # rounding tolerance on the boundary


def test_open_requests_have_no_close_date(fact):
    assert fact.loc[fact.IsOpen == 1, "ClosedDateKey"].isna().all()


def test_repeat_visits_point_to_real_requests(fact):
    parents = fact.RepeatOfRequestID.dropna()
    assert parents.isin(fact.ServiceRequestID).all()


def test_first_time_fix_not_measured_for_recent_closures(fact):
    recent = fact.ClosedAt > pd.Timestamp(C.SNAPSHOT_DATE) - pd.Timedelta(days=30)
    assert fact.loc[recent, "FirstTimeFixFlag"].isna().all()


# ------------------------------------------------------------ reconciliation --
def test_revenue_reconciles_to_clean_billing(fact):
    billing = pd.read_csv(C.PROCESSED_DIR / "clean_billing.csv")
    assert round(fact.ServiceRevenue.sum(), 2) == round(billing.InvoiceAmount.sum(), 2)
    assert fact.InvoiceID.dropna().is_unique


def test_no_rows_silently_lost():
    """raw (deduplicated) = clean + quarantined, for service requests."""
    raw = pd.read_csv(C.RAW_DIR / "fsm_service_requests.csv", dtype=str, keep_default_na=False).drop_duplicates()
    clean = pd.read_csv(C.PROCESSED_DIR / "clean_service_requests.csv")
    q = pd.read_csv(C.QUARANTINE_DIR / "quarantine_records.csv", dtype=str)
    q_fsm = q[q.SourceFile == "fsm_service_requests.csv"]
    assert len(raw) == len(clean) + len(q_fsm)


def test_volume_is_realistic(fact):
    assert 50_000 <= len(fact) <= 100_000
