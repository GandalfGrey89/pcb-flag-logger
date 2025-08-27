# PCB Beach & NOAA Surf Zone Daily Logger

Automatically records **daily beach flag status** for Panama City Beach, FL and the **NOAA Surf Zone Forecast (FLZ112)** including rip current risk, surf height, wind, and more.

---

## Status

![PCB Flag](https://github.com/GandalfGrey89/pcb-flag-logger/blob/main/pcb_flags.csv)
![NOAA SRF](https://github.com/GandalfGrey89/pcb-flag-logger/blob/main/data/noaa_pcb_srf_log.tsv)

---


## What it does
- **PCB Flag Logger**:  
  Scrapes the official Panama City Beach flag widget once per day, logs the flag status.

- **NOAA SRF Logger**:  
  Fetches the NOAA/NWS *Surf Zone Forecast* for Coastal Bay (FLZ112) once per day, logging:
  - Rip current risk  
  - Surf height  
  - Wind  
  - UV Index  
  - Water temperature  
  - Tides  

---
  
## Quick start

1. **Clone or fork** this repo  
2. Confirm the following files exist:
   - `pcb_flag_logger.py`
   - `noaa_pcb_srf_logger.py`
   - `.github/workflows/pcb_flag_logger.yml`
   - `.github/workflows/noaa_pcb_srf_logger.yml`
3. Enable GitHub Actions under **Settings → Actions → General → Allow all actions**  
4. The workflows will run daily on schedule (UTC times below)  

## Customize schedule
Edit `.github/workflows/scrape.yml` and change the cron line:
- `5 12 * * *` = 12:05 UTC daily.
- Use [crontab.guru](https://crontab.guru) to pick times. Remember: GitHub Actions uses UTC.

## Data notes
- `date_local` is America/New_York local date, so your CSV stays consistent to the beach’s local day.
- The script is idempotent: if it runs twice in a day, it overwrites that day’s row rather than duplicating.

## Data format examples

- PCB Flag Logger (data/pcb_flag_log.tsv):

date_local    flag_text    normalized_flag    source_url    fetched_at_utc
2025-08-08    Yellow Flag   yellow            https://www.visitpanamacitybeach.com/beach-alerts-iframe/    2025-08-08T12:05:12Z


- NOAA SRF Logger (data/noaa_pcb_srf_log.tsv):

fetched_utc    issued_line    rip_current_risk    surf    wind    uv_index    water_temp    tides    source_url
2025-08-08T12:07:45Z   Issued at 6 AM CDT   MODERATE   2-3 ft   S 10-15 kt   9   84F   Low tide 3:05 PM   https://tgftp.nws.noaa.gov/data/...

## Troubleshooting
- **No row added today**: Check the **Actions** tab logs. If the PCB site structure changes, update the regex in `scrape_pcb_flag.py` (`FLAG_PATTERN`) or the URLs at the top.
- **Private repo warnings**: Make sure Actions are allowed for private repos in your org/account settings if you made it private.

## License
MIT
