# PCB Beach Flag Logger

Automatically records the daily beach flag status for Panama City Beach, FL.

![PCB Flag](https://github.com/GandalfGrey89/pcb-flag-logger/blob/main/pcb_flags.csv)
![NOAA SRF](https://github.com/<you>/<repo>/actions/workflows/noaa_pcb_srf_logger.yml/badge.svg)


## What it does
- Scrapes the PCB official flag widget once per day.
- Logs the result to `pcb_flags.csv` as:
date_local,flag_text,normalized_flag,source_url,fetched_at_utc
2025-08-08,Yellow Flag,yellow,https://www.visitpanamacitybeach.com/beach-alerts-iframe/,2025-08-08T12:05:12Z
  
## Quick start
1. Create a new GitHub repo (e.g., `pcb-flag-logger`) with a README.
2. Upload:
 - `scrape_pcb_flag.py`
 - `.github/workflows/scrape.yml`
3. Go to **Actions** → **Enable workflows**.
4. That’s it. It will run daily at 12:05 UTC (≈ 8:05 AM New York).

## Customize schedule
Edit `.github/workflows/scrape.yml` and change the cron line:
- `5 12 * * *` = 12:05 UTC daily.
- Use [crontab.guru](https://crontab.guru) to pick times. Remember: GitHub Actions uses UTC.

## Data notes
- `date_local` is America/New_York local date, so your CSV stays consistent to the beach’s local day.
- The script is idempotent: if it runs twice in a day, it overwrites that day’s row rather than duplicating.

## Troubleshooting
- **No row added today**: Check the **Actions** tab logs. If the PCB site structure changes, update the regex in `scrape_pcb_flag.py` (`FLAG_PATTERN`) or the URLs at the top.
- **Private repo warnings**: Make sure Actions are allowed for private repos in your org/account settings if you made it private.

## License
MIT
