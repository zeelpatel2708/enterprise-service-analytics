"""
download_calgary_311.py
=======================
Downloads the City of Calgary 311 Service Requests open dataset through the
Socrata (SODA) API and saves it as one raw CSV:

    data/calgary/raw/calgary_311_service_requests.csv

The download is split by month and saved in parts, so if your connection drops
you can simply re-run the script and it resumes where it stopped.

Usage (from the project folder):
    python src/calgary/download_calgary_311.py                 # Jan 2024 -> 30 Sep 2026
    python src/calgary/download_calgary_311.py --start 2025-01-01
    python src/calgary/download_calgary_311.py --sample 20000  # quick test, first 20k rows

Optional: set an app token to avoid throttling (free at data.calgary.ca > Developer settings)
    Windows:  set SOCRATA_APP_TOKEN=your_token
    macOS:    export SOCRATA_APP_TOKEN=your_token

Certificates: on Windows, Python often cannot find the certificate authorities
your computer trusts (error: CERTIFICATE_VERIFY_FAILED), especially when antivirus
software inspects HTTPS traffic. The script therefore verifies connections with
your operating system's certificate store (the `truststore` package), falling back
to the `certifi` bundle. Verification is never switched off.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

import config_calgary as CC


def make_ssl_context() -> ssl.SSLContext:
    """Verify HTTPS using the OS certificate store (Windows/macOS), else certifi."""
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        pass
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


SSL_CONTEXT = make_ssl_context()


def month_ranges(start: date, end: date):
    cur = date(start.year, start.month, 1)
    while cur <= end:
        nxt = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        yield max(cur, start), min(nxt, date.fromordinal(end.toordinal() + 1))
        cur = nxt


def fetch_page(where: str, offset: int, limit: int, token: str | None) -> list[dict]:
    params = {
        "$select": ",".join(CC.COLUMNS),
        "$where": where,
        "$order": "service_request_id",
        "$limit": str(limit),
        "$offset": str(offset),
    }
    url = CC.API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "portfolio-analytics-project"})
    if token:
        req.add_header("X-App-Token", token)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120, context=SSL_CONTEXT) as resp:
                text = resp.read().decode("utf-8")
            return list(csv.DictReader(io.StringIO(text)))
        except (urllib.error.URLError, TimeoutError) as exc:
            if "CERTIFICATE_VERIFY_FAILED" in str(exc):
                raise SystemExit(
                    "\nCertificate check failed. Run:  pip install truststore certifi\n"
                    "then run this script again. (Your antivirus or network inspects HTTPS;\n"
                    "truststore lets Python use the certificates Windows already trusts.)") from exc
            wait = 5 * (attempt + 1)
            print(f"      network error ({exc}); retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError("Download failed after 5 attempts - check your internet connection and re-run.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=CC.START_DATE)
    ap.add_argument("--end", default=CC.SNAPSHOT_DATE)
    ap.add_argument("--sample", type=int, default=0, help="download only this many rows (testing)")
    args = ap.parse_args()

    token = os.environ.get("SOCRATA_APP_TOKEN")
    parts_dir = CC.RAW_DIR / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    print(f"Downloading Calgary 311 requests {start} -> {end}")

    total = 0
    part_files = []
    for lo, hi in month_ranges(start, end):
        part = parts_dir / f"part_{lo:%Y_%m}.csv"
        part_files.append(part)
        if part.exists() and not args.sample:
            n = sum(1 for _ in open(part, encoding="utf-8")) - 1
            print(f"   {lo:%Y-%m}: already downloaded ({n:,} rows)")
            total += n
            continue
        where = f"requested_date >= '{lo}T00:00:00' AND requested_date < '{hi}T00:00:00'"
        rows, offset = [], 0
        while True:
            limit = CC.PAGE_SIZE if not args.sample else min(CC.PAGE_SIZE, args.sample - total - len(rows))
            if limit <= 0:
                break
            page = fetch_page(where, offset, limit, token)
            rows += page
            offset += len(page)
            if len(page) < limit:
                break
        tmp = part.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CC.COLUMNS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        tmp.replace(part)  # only a complete month becomes a "part"
        total += len(rows)
        print(f"   {lo:%Y-%m}: {len(rows):>8,} rows   (total {total:,})")
        if args.sample and total >= args.sample:
            part_files = [p for p in part_files if p.exists()]
            break

    # combine parts into one raw extract
    with open(CC.RAW_FILE, "w", newline="", encoding="utf-8") as out:
        w = None
        for p in part_files:
            if not p.exists():
                continue
            with open(p, encoding="utf-8") as f:
                r = csv.DictReader(f)
                if w is None:
                    w = csv.DictWriter(out, fieldnames=r.fieldnames)
                    w.writeheader()
                w.writerows(r)
    if args.sample:  # a sample must not be mistaken for the full extract next time
        for p in part_files:
            p.unlink(missing_ok=True)
    print(f"\nSaved {total:,} rows to {CC.RAW_FILE}")
    print("Next: python src/calgary/run_calgary_pipeline.py")


if __name__ == "__main__":
    main()
