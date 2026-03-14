# CCIL Zero Rates scraper (2013-01-01 to 2025-12-31)

This repository contains a reproducible scraper for CCIL Zero Rates data from:

- Source page: https://www.ccilindia.com/zero-rates
- Requested range: `2013-01-01` to `2025-12-31`
- Output granularity: **daily (trading days present on CCIL)**

## Why this scraper exists

The Zero Rates page is rendered dynamically and the UI typically shows only a very small window of records at a time.  
This script automates the underlying form submission for every calendar date in the requested range, then compiles unique daily observations into one dataset.

## Repository contents

- `scrape_zero_rates.py` — scraper script.
- `data/zero_rates_2013-01-01_to_2025-12-31_daily.csv` — latest compiled daily dataset.
- `data/zero_rates_2013-01-01_to_2025-12-31_daily.metadata.json` — metadata for the latest run.
- `data/versions/<UTC timestamp>/...` — immutable versioned snapshots of each run.

## How to run

```bash
python3 scrape_zero_rates.py
```

The script uses only Python standard library modules (no pip dependencies required).

## Latest run summary

- Calendar days queried: `4748`
- Trading days captured: `3136`
- Errors: `0`
- Run timestamp (UTC): `20260314T043740Z`

## Notes

- Weekend/holiday dates are expected to return no record.
- The dataset stores all rate-tenor fields returned by the page (`zerorate00` through `zerorate_50_5` style fields).
