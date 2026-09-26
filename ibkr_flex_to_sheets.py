"""
IBKR Trade Export -> Sheets (offline, copy-paste version)
============================================================

Fully offline - standard library only, no internet, no Google API, no
external packages. Reads a Flex Query "Trade Confirmation" XML export,
converts each execution to your Google Sheets row format, and prints
tab-separated rows to the terminal (and optionally a .txt file) for you
to copy and paste manually into your journal.

Usage:
    python ibkr_flex_to_sheets.py                     # uses TradeJournal_Export.xml -> TradeJournal_Export.txt, auto-opens it
    python ibkr_flex_to_sheets.py path/to/export.xml
    python ibkr_flex_to_sheets.py path/to/export.xml --out custom.txt
    python ibkr_flex_to_sheets.py --no-open             # write TradeJournal_Export.txt but don't auto-open it

Output row format (per execution), ascending by time:
    ID <TAB> Symbol <TAB> Buy/Sell <TAB> Date <TAB> Time <TAB> Price <TAB> Quantity <TAB> (blank: Stop Loss) <TAB> Fee

Fee = |commission| + |tax|
Time is converted from the exchange's local zone (read from the abbreviation
in dateTime, e.g. "EDT") to Singapore time (UTC+8, no DST).

Expects <TradeConfirm> elements like:
    <TradeConfirm symbol="NVDA" buySell="BUY" dateTime="01/01/2026;13:30:00 EDT"
                   price="188.50" quantity="10" commission="-1.00003"
                   tax="-0.0900027"/>
-----------------------------------------------------------------------------
"""

import argparse
import datetime as dt
import os
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

# Default paths - change these if you'd rather not pass arguments each time.
DEFAULT_XML_PATH = "TradeJournal_Export.xml"
DEFAULT_OUT_PATH = "TradeJournal_Export.txt"

# Exchange timezone abbreviation -> UTC offset in hours.
# Add more here if you trade other markets (check the abbreviation IBKR
# prints in your export and look up its UTC offset for that date).
TZ_OFFSETS = {
    "EST": -5, "EDT": -4,   # US Eastern (NYSE, NASDAQ)
    "CST": -6, "CDT": -5,   # US Central
    "MST": -7, "MDT": -6,   # US Mountain
    "PST": -8, "PDT": -7,   # US Pacific
    "GMT": 0,  "BST": 1,    # UK (LSE)
    "HKT": 8,               # Hong Kong
    "SGT": 8,                # Singapore
    "JST": 9,                # Japan
}

SGT_OFFSET_HOURS = 8  # Singapore is fixed UTC+8, no DST


def to_singapore_time(date_str, time_str, tz_abbr):
    """Converts an exchange-local datetime + zone abbreviation to SGT."""
    naive = dt.datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M:%S")
    offset_hours = TZ_OFFSETS.get(tz_abbr.upper())
    if offset_hours is None:
        return None
    utc_dt = naive - dt.timedelta(hours=offset_hours)
    return utc_dt + dt.timedelta(hours=SGT_OFFSET_HOURS)


def parse_ibkr_xml(path):
    """
    Parses <TradeConfirm> elements from a Flex Query XML export.
    dateTime format: "DD/MM/YYYY;HH:MM:SS ZZZ" e.g. "22/09/2026;09:36:26 EDT"
    Returns (rows, skipped) where skipped is a list of human-readable reasons.
    """
    tree = ET.parse(path)
    rows = []
    skipped = []

    for elem in tree.iter("TradeConfirm"):
        symbol = elem.attrib.get("symbol", "?")
        try:
            side = elem.attrib["buySell"].strip().upper()
            qty = abs(float(elem.attrib["quantity"]))
            price = float(elem.attrib["price"])
            commission = abs(float(elem.attrib.get("commission", "0")))
            tax = abs(float(elem.attrib.get("tax", "0")))

            date_part, rest = elem.attrib["dateTime"].split(";")
            time_part, tz_abbr = rest.strip().rsplit(" ", 1)
        except (KeyError, ValueError) as e:
            skipped.append(f"{symbol}: malformed record ({e})")
            continue

        sgt_dt = to_singapore_time(date_part.strip(), time_part.strip(), tz_abbr)
        if sgt_dt is None:
            skipped.append(f'{symbol}: unknown timezone "{tz_abbr}" — add it to TZ_OFFSETS')
            continue

        fee = commission + tax
        side_str = "Buy" if side == "BUY" else "Sell"
        date_str = sgt_dt.strftime("%d/%m/%Y")
        time_str = sgt_dt.strftime("%H%M")

        rows.append(
            {
                "sort_key": sgt_dt,
                "cells": [symbol, side_str, date_str, time_str, f"${price:,.2f}", qty, "", f"${fee:,.2f}"],
            }
        )

    rows.sort(key=lambda r: r["sort_key"])

    # Assign sequential IDs after sorting, so ID order matches chronological order
    for i, row in enumerate(rows, start=1):
        row["cells"].insert(0, i)

    return rows, skipped


def format_tsv(rows):
    return "\n".join("\t".join(str(c) for c in r["cells"]) for r in rows)


def open_in_default_editor(path):
    """Best-effort: open the output file in whatever the OS treats as default for .txt."""
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(path)  # noqa: this only exists on Windows
        elif system == "Darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Convert IBKR Flex Query XML to tab-separated rows for Sheets.")
    parser.add_argument("xml_path", nargs="?", default=DEFAULT_XML_PATH,
                         help=f"Path to the Flex Query XML export (default: {DEFAULT_XML_PATH})")
    parser.add_argument("--out", default=DEFAULT_OUT_PATH,
                         help=f"Write the output to this .txt file (default: {DEFAULT_OUT_PATH})")
    parser.add_argument("--no-open", action="store_true",
                         help="Don't automatically open the output file after writing")
    args = parser.parse_args()

    try:
        rows, skipped = parse_ibkr_xml(args.xml_path)
    except FileNotFoundError:
        print(f"File not found: {args.xml_path}", file=sys.stderr)
        print(f"(Tip: either place your export at '{DEFAULT_XML_PATH}', or pass a path: "
              f"python3 ibkr_convert.py path/to/export.xml)", file=sys.stderr)
        sys.exit(1)
    except ET.ParseError as e:
        print(f"Could not parse XML: {e}", file=sys.stderr)
        sys.exit(1)

    if not rows:
        print("No valid trade records found.")
    else:
        tsv = format_tsv(rows)
        print(f"\n{len(rows)} trade(s), ascending order:\n")
        print(tsv)
        print()

        with open(args.out, "w", encoding="utf-8") as f:
            f.write(tsv + "\n")
        print(f"Written to {args.out}")

        if not args.no_open:
            opened = open_in_default_editor(args.out)
            if opened:
                print(f"Opened {args.out} — copy from there and paste into Sheets.")
            else:
                print(f"Couldn't auto-open the file — open {args.out} manually and copy from it.")

    if skipped:
        print(f"\nSkipped {len(skipped)} record(s):", file=sys.stderr)
        for s in skipped:
            print(f"  - {s}", file=sys.stderr)


if __name__ == "__main__":
    main()
