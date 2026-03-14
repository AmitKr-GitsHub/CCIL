#!/usr/bin/env python3
"""Scrape CCIL zero rates into a daily dataset."""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_URL = "https://www.ccilindia.com/zero-rates"
SKIP_FIELDS = {
    "id",
    "date",
    "stringdate",
    "created_by",
    "created_date",
    "modified_by",
    "modified_timestamp",
}


@dataclass
class SessionConfig:
    action_url: str
    from_field: str
    to_field: str


_thread_local = threading.local()


def build_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def get_session_config(opener: urllib.request.OpenerDirector) -> SessionConfig:
    html = opener.open(BASE_URL, timeout=30).read().decode("utf-8", "ignore")
    form = re.search(r'<form[^>]*id="daterange"[^>]*>', html, re.S)
    if not form:
        raise RuntimeError("Unable to locate daterange form")

    action_url = re.search(r'action="([^"]+)"', form.group(0)).group(1).replace("&amp;", "&")
    form_body = re.search(r'id="daterange">(.*?)</form>', html, re.S)
    names = re.findall(r'name="([^"]+)"', form_body.group(1))
    from_field = next(n for n in names if n.endswith("fromDate"))
    to_field = next(n for n in names if n.endswith("toDate"))

    return SessionConfig(action_url=action_url, from_field=from_field, to_field=to_field)


def get_thread_session() -> Tuple[urllib.request.OpenerDirector, SessionConfig]:
    if not hasattr(_thread_local, "opener"):
        opener = build_opener()
        config = get_session_config(opener)
        _thread_local.opener = opener
        _thread_local.config = config
    return _thread_local.opener, _thread_local.config


def fetch_records_for_day(day: dt.date, max_retries: int = 4) -> Tuple[str, Optional[List[Dict]], Optional[str]]:
    for attempt in range(max_retries):
        try:
            opener, config = get_thread_session()
            params = {config.from_field: day.isoformat(), config.to_field: day.isoformat()}
            payload = urllib.parse.urlencode(params).encode()
            html = opener.open(config.action_url, data=payload, timeout=30).read().decode("utf-8", "ignore")
            rec_match = re.search(r"var records = (\[.*?\]);\s*var dsize", html, re.S)
            if not rec_match:
                raise RuntimeError("No records block")
            return day.isoformat(), json.loads(rec_match.group(1)), None
        except Exception as exc:
            _thread_local.opener = build_opener()
            _thread_local.config = get_session_config(_thread_local.opener)
            if attempt == max_retries - 1:
                return day.isoformat(), None, str(exc)
            time.sleep(0.4 * (attempt + 1))
    return day.isoformat(), None, "unexpected"


def daterange(start: dt.date, end: dt.date):
    current = start
    while current <= end:
        yield current
        current += dt.timedelta(days=1)


def normalize_records(records: Dict[str, Dict]) -> List[Dict[str, str]]:
    ordered_dates = sorted(records.keys())
    rows = []
    for day in ordered_dates:
        rec = records[day]
        row = {"date": day}
        for key, value in rec.items():
            if key in SKIP_FIELDS:
                continue
            row[key] = value
        rows.append(row)
    return rows


def write_csv(rows: List[Dict[str, str]], path: Path) -> None:
    all_columns = sorted({k for row in rows for k in row.keys() if k != "date"})
    columns = ["date", *all_columns]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    start = dt.date(2013, 1, 1)
    end = dt.date(2025, 12, 31)
    all_days = list(daterange(start, end))

    by_date: Dict[str, Dict] = {}
    errors: Dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(fetch_records_for_day, day) for day in all_days]
        for idx, fut in enumerate(as_completed(futures), start=1):
            req_day, records, err = fut.result()
            if err:
                errors[req_day] = err
            elif records:
                for rec in records:
                    rec_date = rec["date"].split()[0]
                    if start.isoformat() <= rec_date <= end.isoformat():
                        by_date[rec_date] = rec
            if idx % 250 == 0 or idx == len(all_days):
                print(
                    f"Processed {idx}/{len(all_days)} requests; captured {len(by_date)} trading days; errors {len(errors)}",
                    flush=True,
                )

    rows = normalize_records(by_date)

    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    csv_path = output_dir / "zero_rates_2013-01-01_to_2025-12-31_daily.csv"
    write_csv(rows, csv_path)

    run_ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    version_dir = output_dir / "versions" / run_ts
    version_dir.mkdir(parents=True, exist_ok=True)
    version_csv = version_dir / csv_path.name
    version_csv.write_bytes(csv_path.read_bytes())

    metadata = {
        "source": BASE_URL,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "calendar_days_processed": len(all_days),
        "trading_days_captured": len(rows),
        "errors": errors,
        "generated_at_utc": run_ts,
        "latest_file": str(csv_path),
        "version_file": str(version_csv),
    }

    meta_path = output_dir / "zero_rates_2013-01-01_to_2025-12-31_daily.metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (version_dir / meta_path.name).write_bytes(meta_path.read_bytes())

    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
