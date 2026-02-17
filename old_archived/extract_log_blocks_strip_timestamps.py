#!/usr/bin/env python3
"""
extract_log_blocks_strip_timestamps.py

Usage:
    python extract_log_blocks_strip_timestamps.py path/to/logfile.log
Options:
    --pnp-out     output file for LogTemp: [PnP] lines (default: pnp_lines.txt)
    --debug-out   output file for DebugLogSharedTagPositions blocks (default: debug_blocks.txt)
    --num         number of lines to capture after the DebugLogSharedTagPositions line (default: 100)
    --no-summary  do not print final summary
Behavior:
    - Writes every line containing "LogTemp: [PnP]" to pnp_out with our own line numbers.
    - For each "LogTemp: === DebugLogSharedTagPositions" line, writes that line + the next N lines (default 100) to debug_out.
    - Strips leading bracketed timestamps/IDs at the start of each log line (e.g. "[2026.02.16-09.21.45:449][566]").
"""

import argparse
import re
import sys

# pattern to remove one or more leading bracketed blocks like:
# [2026.02.16-09.21.45:449][566]  (or any sequence of [ ... ] groups) at start of line
_LEADING_BRACKETED_RE = re.compile(r'^(?:\[[^\]]*\]\s*)+')

def clean_line(line: str) -> str:
    """
    Remove any leading bracketed timestamp/ID groups from the start of `line`,
    and strip trailing newline.
    """
    s = line.rstrip("\r\n")
    s = _LEADING_BRACKETED_RE.sub("", s)
    return s.lstrip()  # also remove any space after the bracket groups

def extract(log_path, pnp_out, debug_out, num_lines, show_counts):
    pnp_count = 0
    debug_blocks = 0
    debug_count = 0

    with open(log_path, 'r', encoding='utf-8', errors='ignore') as fin, \
         open(pnp_out, 'w', encoding='utf-8', errors='ignore') as fpnp, \
         open(debug_out, 'w', encoding='utf-8', errors='ignore') as fdebug:

        iterator = iter(fin)
        lineno = 0

        for line in iterator:
            lineno += 1

            if "LogTemp: [PnP]" in line:
                pnp_count += 1
                fpnp.write(f" {clean_line(line)}\n")

            if "LogTemp: === DebugLogSharedTagPositions" in line:
                debug_blocks += 1
                debug_count += 1
                fdebug.write(f"\n=== DEBUG BLOCK {debug_blocks} START (line {lineno}) ===\n")
                fdebug.write(f" {clean_line(line)}\n")

                # capture following num_lines lines
                for i in range(num_lines):
                    try:
                        next_line = next(iterator)
                        lineno += 1
                        debug_count += 1
                        fdebug.write(f" {clean_line(next_line)}\n")
                    except StopIteration:
                        break

    if show_counts:
        print(f"Finished. Found {pnp_count} 'LogTemp: [PnP]' lines.")
        print(f"Captured {debug_blocks} debug block(s), total {debug_count} lines written to '{debug_out}'.")
        print(f"'LogTemp: [PnP]' lines written to '{pnp_out}'.")

def main():
    ap = argparse.ArgumentParser(description="Extract PnP lines and DebugLogSharedTagPositions blocks from a log file (strips leading bracketed timestamps).")
    ap.add_argument("logfile", help="Path to the log file to parse")
    ap.add_argument("--pnp-out", default="pnp_lines.txt", help="Output file for LogTemp: [PnP] lines")
    ap.add_argument("--debug-out", default="debug_blocks.txt", help="Output file for DebugLogSharedTagPositions blocks")
    ap.add_argument("--num", type=int, default=100, help="Number of lines to capture after the DebugLogSharedTagPositions line")
    ap.add_argument("--no-summary", dest="show_counts", action="store_false", help="Do not print summary counts")
    ap.set_defaults(show_counts=True)

    args = ap.parse_args()
    extract(args.logfile, args.pnp_out, args.debug_out, args.num, args.show_counts)

if __name__ == "__main__":
    main()
