"""
Builds a small FAKE file in the exact Calgary 311 export format, used only by
the automated tests (tests/test_calgary_pipeline.py) so the Edition B code can
be tested without internet access. It is never used for analysis.

    python tests/fixtures/make_calgary_fixture.py <output_csv> [rows]
"""
import sys

import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
SERVICES = [("WRS - Cart Management", "OS - Waste and Recycling Services"),
            ("WRS - Compost - Green Cart", "OS - Waste and Recycling Services"),
            ("Roads - Pothole Repair", "TRAN - Roads"),
            ("Roads - Snow and Ice Control", "TRAN - Roads"),
            ("Roads - Traffic Signal Timing Inquiry", "TRAN - Roads"),
            ("Bylaw - Noise Concerns", "CS - Calgary Community Standards"),
            ("Bylaw - Snow and Ice on Sidewalk", "CS - Calgary Community Standards"),
            ("Parks - Tree Concern - GIS", "OS - Parks and Open Spaces"),
            ("Parks - Infrastructure - GIS", "OS - Parks and Open Spaces"),
            ("Animal Services - Dog Bite", "CS - Calgary Community Standards"),
            ("Water - Water Main Break", "UEP - Water Services")]
COMMS = [("BLN", "BELTLINE"), ("SHN", "SHAWNESSY"), ("DAL", "DALHOUSIE"), ("TUS", "TUSCANY"),
         ("MCK", "MCKENZIE LAKE"), ("SHW", "SHERWOOD"), ("MAH", "MAHOGANY"), ("LEG", "LEGACY")]


def main(out, n=30000):
    req = pd.Timestamp("2024-01-01") + pd.to_timedelta(rng.integers(0, 1035, n), "D")
    svc = rng.integers(0, len(SERVICES), n)
    comm = rng.integers(0, len(COMMS), n)
    days = rng.geometric(0.15, n) - 1
    closed = req + pd.to_timedelta(days, "D")
    is_open = closed > pd.Timestamp("2026-10-20")
    fmt = lambda s: s.strftime("%Y-%m-%dT00:00:00.000")
    df = pd.DataFrame({
        "service_request_id": [f"{d.year % 100}-{i:08d}" for i, d in enumerate(req)],
        "requested_date": fmt(req),
        "updated_date": fmt(closed.where(~is_open, pd.Timestamp("2026-10-20"))),
        "closed_date": np.where(is_open, "", fmt(closed)),
        "status_description": np.where(is_open, "Open", "Closed"),
        "source": rng.choice(["Phone", "App", "Other", "Web", "Email"], n, p=[0.45, 0.25, 0.15, 0.1, 0.05]),
        "service_name": [SERVICES[i][0] for i in svc],
        "agency_responsible": [SERVICES[i][1] for i in svc],
        "comm_code": [COMMS[i][0] for i in comm],
        "comm_name": [COMMS[i][1] for i in comm],
        "location_type": "Community Centrepoint",
        "longitude": rng.uniform(-114.2, -113.95, n).round(6),
        "latitude": rng.uniform(50.9, 51.15, n).round(6),
    })
    # realistic defects
    df.loc[df.sample(40, random_state=1).index, "closed_date"] = ""                 # closed, no date
    i = df[df.status_description == "Closed"].sample(25, random_state=2).index
    df.loc[i, "closed_date"] = fmt(req[i] - pd.Timedelta(days=3))                  # closed before requested
    df.loc[df.sample(30, random_state=3).index, ["comm_code", "comm_name"]] = ""   # missing community
    df.loc[df.sample(15, random_state=4).index, "latitude"] = 0                     # bad coordinates
    upd = df.sample(50, random_state=5).copy()                                      # updated duplicates
    upd["updated_date"] = "2026-10-21T00:00:00.000"
    df = pd.concat([df, upd, df.head(20)], ignore_index=True)                       # + exact duplicates
    df.loc[df.sample(60, random_state=6).index, "status_description"] = "Duplicate (Closed)"
    # real-world gotcha: text values that pandas reads as missing by default
    df.loc[df.sample(40, random_state=8).index, ["comm_code", "comm_name"]] = ["NA", "NORTH AIRWAYS"]
    df.loc[df.sample(40, random_state=9).index, "source"] = "None"
    df.to_csv(out, index=False)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 30000)
