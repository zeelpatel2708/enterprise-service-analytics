"""
build_model_calgary.py
======================
Star schema for the real Calgary 311 data (data/calgary/model/*.csv).
Same shape and naming as Edition A wherever the data allows, so the DAX and
SQL patterns transfer directly.

    Dimensions : DimDate, DimServiceType, DimCommunity, DimChannel
    Facts      : FactServiceRequests   (one row per 311 request)
                 FactBacklogSnapshot   (service type x month-end, semi-additive)

Run:  python src/calgary/build_model_calgary.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config_calgary as CC

SNAPSHOT = pd.Timestamp(CC.SNAPSHOT_DATE)


def date_key(s):
    d = pd.to_datetime(s)  # arithmetic instead of strftime: no million temporary strings
    return (d.dt.year * 10000 + d.dt.month * 100 + d.dt.day).astype("Int64")


def key_from(col: pd.Series, mapping: dict) -> np.ndarray:
    """Map a categorical column to surrogate keys via its distinct values (memory-light)."""
    lookup = np.array([mapping.get(c, np.nan) for c in col.cat.categories] + [np.nan], dtype=float)
    return lookup[col.cat.codes.to_numpy()]


def build_dim_date():
    d = pd.Series(pd.date_range(CC.START_DATE, CC.CALENDAR_END, freq="D"))
    return pd.DataFrame({
        "DateKey": date_key(d), "Date": d.dt.date, "Year": d.dt.year,
        "QuarterNumber": d.dt.quarter, "Quarter": "Q" + d.dt.quarter.astype(str),
        "YearQuarter": d.dt.year.astype(str) + "-Q" + d.dt.quarter.astype(str),
        "MonthNumber": d.dt.month, "Month": d.dt.strftime("%B"), "MonthShort": d.dt.strftime("%b"),
        "YearMonth": d.dt.strftime("%Y-%m"), "YearMonthKey": d.dt.year * 100 + d.dt.month,
        "MonthStartDate": d.dt.to_period("M").dt.start_time.dt.date,
        "ISOWeek": d.dt.isocalendar().week.astype(int).values, "Day": d.dt.day,
        "DayOfWeekNumber": d.dt.dayofweek + 1, "DayOfWeek": d.dt.day_name(),
        "IsWeekend": (d.dt.dayofweek >= 5).astype(int),
        "Season": d.dt.month.map({12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
                                  6: "Summer", 7: "Summer", 8: "Summer", 9: "Fall", 10: "Fall", 11: "Fall"}),
        "IsAfterSnapshot": (d > SNAPSHOT).astype(int),
    })


def main():
    CC.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    # keep_default_na=False: real codes such as "NA" (a community code) or "None"
    # must stay text - pandas would otherwise silently turn them into missing values.
    # Text columns are read as categories to keep memory low on 1M+ rows.
    text = ["ServiceName", "ServiceCategory", "Agency", "CommunityCode", "CommunityName", "Channel",
            "StatusGroup", "StatusRaw", "LocationType"]
    sr = pd.read_csv(CC.PROCESSED_DIR / "clean_service_requests.csv",
                     parse_dates=["RequestedDate", "ClosedDate"],
                     usecols=lambda c: c != "UpdatedDate",
                     dtype={**{c: "category" for c in text}, "ServiceRequestID": str},
                     keep_default_na=False, na_values=[""])

    dim_date = build_dim_date()

    svc = (sr.groupby(["ServiceName", "ServiceCategory", "Agency"], observed=True)
             .agg(BenchmarkDays=("BenchmarkDays", "max"), Requests=("ServiceRequestID", "size"))
             .reset_index().sort_values(["ServiceCategory", "ServiceName"]))
    # one row per service name (agency = the most common one)
    svc = svc.sort_values("Requests", ascending=False).drop_duplicates("ServiceName").sort_values("ServiceName")
    svc.insert(0, "ServiceTypeKey", range(1, len(svc) + 1))
    svc["VolumeRank"] = svc.Requests.rank(ascending=False, method="first").astype(int)
    svc["Top20Service"] = np.where(svc.VolumeRank <= 20, svc.ServiceName, "Other services")
    dim_svc = svc.drop(columns="Requests")
    skey = dict(zip(dim_svc.ServiceName, dim_svc.ServiceTypeKey))

    comm = (sr.groupby(["CommunityCode", "CommunityName"], observed=True)
              .agg(Latitude=("Latitude", "mean"), Longitude=("Longitude", "mean"))
              .reset_index())
    comm = comm.sort_values("CommunityName").drop_duplicates("CommunityCode")
    comm.insert(0, "CommunityKey", range(1, len(comm) + 1))
    comm.loc[comm.CommunityCode == "UNK", "CommunityKey"] = -1
    comm["Latitude"] = comm.Latitude.round(5)
    comm["Longitude"] = comm.Longitude.round(5)
    ckey = dict(zip(comm.CommunityCode, comm.CommunityKey))

    ch = pd.DataFrame({"Channel": sorted(sr.Channel.cat.categories.astype(str))})
    ch.insert(0, "ChannelKey", range(1, len(ch) + 1))
    ch["ChannelGroup"] = np.select([ch.Channel.str.contains("App|Web|Online|Email|Social", case=False),
                                    ch.Channel.str.contains("Phone|Call", case=False)],
                                   ["Digital", "Phone"], "Other")
    chkey = dict(zip(ch.Channel, ch.ChannelKey))

    fact = pd.DataFrame({
        "ServiceRequestID": sr.ServiceRequestID,
        "ServiceTypeKey": key_from(sr.ServiceName, skey),
        "CommunityKey": key_from(sr.CommunityCode, ckey),
        "ChannelKey": key_from(sr.Channel, chkey),
        "RequestedDateKey": date_key(sr.RequestedDate),
        "ClosedDateKey": date_key(sr.ClosedDate),
        "StatusGroup": sr.StatusGroup,
        "StatusRaw": sr.StatusRaw,
        "IsClosed": sr.IsClosed, "IsOpen": sr.IsOpen,
        "IsDuplicateRequest": sr.IsDuplicateRequest,
        "ResolutionDays": sr.ResolutionDays.astype("Int64"),
        "SameDayClosure": sr.SameDayClosure.astype("Int64"),
        "BenchmarkDays": sr.BenchmarkDays,
        "WithinBenchmark": sr.WithinBenchmark.astype("Int64"),
        "OpenAgeDays": sr.OpenAgeDays.astype("Int64"),
        "IsStaleOpen": sr.IsStaleOpen,
        "ClosedDateImputed": sr.ClosedDateImputed,
        "ReopenedFlag": sr.ReopenedFlag,
    })
    for key, src in [("ServiceTypeKey", "ServiceName"), ("CommunityKey", "CommunityCode"), ("ChannelKey", "Channel")]:
        missing = fact[key].isna()
        if missing.any():
            examples = sr.loc[missing, src].drop_duplicates().head(5).tolist()
            raise SystemExit(f"{missing.sum():,} rows have no {key}. Unmatched {src} values: {examples}")
        fact[key] = fact[key].astype(int)

    # periodic snapshot: open requests per service type at each month end
    rows = []
    for me in pd.date_range(CC.START_DATE, SNAPSHOT, freq="ME"):
        open_m = (sr.RequestedDate <= me) & (sr.ClosedDate.isna() | (sr.ClosedDate > me))
        if not open_m.any():
            continue
        age = (me - sr.RequestedDate).dt.days
        g = pd.DataFrame({"ServiceName": sr.ServiceName[open_m], "Breached": (age > sr.BenchmarkDays)[open_m],
                          "Aged90": (age > 90)[open_m]})
        g = g.groupby("ServiceName", observed=True).agg(OpenRequests=("Breached", "size"),
                                         OpenPastBenchmark=("Breached", "sum"),
                                         OpenOver90Days=("Aged90", "sum")).reset_index()
        g["SnapshotDateKey"] = int(me.strftime("%Y%m%d"))
        rows.append(g)
    fb = pd.concat(rows, ignore_index=True)
    fb.insert(0, "ServiceTypeKey", fb.pop("ServiceName").astype(str).map(skey))
    fb.insert(1, "SnapshotDateKey", fb.pop("SnapshotDateKey"))

    out = {"DimDate": dim_date, "DimServiceType": dim_svc, "DimCommunity": comm, "DimChannel": ch,
           "FactServiceRequests": fact, "FactBacklogSnapshot": fb}
    for name, df in out.items():
        df.to_csv(CC.MODEL_DIR / f"{name}.csv", index=False)
        print(f"  {name:22s} {len(df):>9,} rows  {df.shape[1]:>3} cols")


if __name__ == "__main__":
    main()
