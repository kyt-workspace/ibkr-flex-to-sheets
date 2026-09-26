# ibkr-flex-to-sheets

Convert an Interactive Brokers **Flex Query** trade export into tab-separated
rows ready to paste into a manual trading journal in Google Sheets.

- **Offline.** Standard library only — no network calls, no Google API, no
  external packages.
- **No matching or aggregation.** Each row is one raw execution (fill), in
  chronological order — you keep full manual control of your journal.
- **Timezone-aware.** Converts each trade's exchange-local time to a fixed
  target timezone (Singapore time by default), correctly handling daylight
  saving because IBKR reports each trade's own zone abbreviation.

## Output format

| Column | Example | Notes |
|---|---|---|
| ID | `1` | Sequential, assigned after sorting — matches chronological order |
| Symbol | `TSM` | |
| Buy/Sell | `Buy` | |
| Date | `17/12/2025` | Converted to the target timezone |
| Time | `1203` | 24-hour, `HHMM`, converted to the target timezone |
| Price | `$287.40` | |
| Quantity | `5.0` | |
| *(blank)* | | Spacer column — e.g. for a Stop Loss you fill in by hand |
| Fee | `$1.09` | `\|commission\| + \|tax\|` |

Columns are separated with real tab characters, so pasting a row into Google
Sheets — or importing the output file — drops each value into its own cell.

## Setup

### 1. Create a Flex Query in IBKR

1. Client Portal → **Reports/Tax Docs → Flex Queries**
2. Create a new **Trade Confirmation** Flex Query
3. Under **Sections → Trade Confirmations**, enable: `Symbol`, `Buy/Sell`,
   `Date/Time`, `Price`, `Quantity`, `Commission`, `Tax`
4. Under **General Configuration**, set **Format: XML**
5. Save, run it, and download the XML export

There's no setting in IBKR to change the reported timezone — it always
reports the *exchange's* local time. This script converts it for you (see
[Configuration](#configuration) below).

### 2. Run the script

Requires Python 3.9+, no other dependencies.

```bash
# Simplest: drop your export as export.xml in this folder, then run:
python3 ibkr_flex_to_sheets.py

# Or specify paths explicitly:
python3 ibkr_flex_to_sheets.py path/to/export.xml --out rows.txt

# Skip auto-opening the output file:
python3 ibkr_flex_to_sheets.py --no-open
```

By default the script writes to `TradeJournal_Export.txt` and opens it in your system's
default text editor. Select all, copy, and paste into your Google Sheet.

> **Copying from a terminal instead?** Many terminal emulators render tabs
> as aligned spaces, so a direct copy from the terminal window often loses
> the real tab characters and everything lands in one cell. Either open the
> written `.txt` file in a text editor and copy from there, or in Sheets use
> **File → Import → Upload**, choosing **Tab** as the separator — that reads
> the file directly and sidesteps clipboard formatting entirely.

## Configuration

All configuration lives at the top of `ibkr_flex_to_sheets.py`:

- `DEFAULT_XML_PATH` / `DEFAULT_OUT_PATH` — default file paths used when run
  with no arguments.
- `TARGET_UTC_OFFSET_HOURS` — the timezone to convert every trade into.
  Defaults to `8` (Singapore, fixed UTC+8, no DST). Change this if you
  journal in a different timezone.
- `SOURCE_TZ_OFFSETS` — maps exchange timezone abbreviations (as IBKR
  reports them, e.g. `EDT`, `GMT`) to UTC offsets. Covers the major US, UK,
  and Asian markets. If you trade an exchange whose abbreviation isn't
  listed, the script will skip that record and tell you which abbreviation
  to add.

## Known limitations

- **Stop Loss** and any subjective fields (setups, mistakes, notes) aren't
  in IBKR's trade data at all — the script leaves a blank column where
  applicable, for manual entry.
- **Round-trip trades aren't matched.** This script outputs raw executions,
  not paired open/close trades. If you need FIFO-matched round trips
  instead, that's a different (more involved) parsing step — open an issue
  or adapt `parse_flex_query_xml()`.
- Assumes the XML `dateTime` format `DD/MM/YYYY;HH:MM:SS ZZZ` (IBKR's
  standard Trade Confirmation format). A different Flex Query report type
  may use different field names or formats.

## License

MIT — see [LICENSE](LICENSE).
