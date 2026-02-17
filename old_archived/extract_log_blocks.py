#!/usr/bin/env python3
"""
extract_log_blocks.py

Usage:
    python extract_log_blocks.py path/to/logfile.log
    Optional args:
      --pnp-out     output file for LogTemp: [PnP] lines (default: pnp_lines.txt)
      --debug-out   output file for DebugLogSharedTagPositions blocks (default: debug_blocks.txt)
      --num         number of lines to capture after the DebugLogSharedTagPositions line (default: 100)
      --show-counts print a short summary of counts at the end
"""

import argparse
import io
import sys

def extract(log_path, pnp_out, debug_out, num_lines, show_counts):
    pnp_count = 0
    debug_count = 0
    debug_blocks = 0

    # Open output files (text mode)
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as fin, \
         open(pnp_out, 'w', encoding='utf-8', errors='ignore') as fpnp, \
         open(debug_out, 'w', encoding='utf-8', errors='ignore') as fdebug:

        iterator = iter(fin)
        lineno = 0

        for line in iterator:
            lineno += 1
            # Check for PnP lines
            if "LogTemp: [PnP]" in line:
                pnp_count += 1
                fpnp.write(f"{lineno}: {line.rstrip()}\n")

            # Check for DebugLogSharedTagPositions and capture block
            if "LogTemp: === DebugLogSharedTagPositions" in line:
                debug_blocks += 1
                debug_count += 1  # counting the header line itself
                fdebug.write(f"\n=== DEBUG BLOCK {debug_blocks} START (line {lineno}) ===\n")
                fdebug.write(f"{lineno}: {line.rstrip()}\n")

                # write the following `num_lines` lines (or until EOF)
                for i in range(num_lines):
                    try:
                        next_line = next(iterator)
                        lineno += 1
                        debug_count += 1
                        fdebug.write(f"{lineno}: {next_line.rstrip()}\n")
                    except StopIteration:
                        break

        if show_counts:
            print(f"Finished. Found {pnp_count} 'LogTemp: [PnP]' lines.")
            print(f"Captured {debug_blocks} debug block(s), total {debug_count} lines written to '{debug_out}'.")
            print(f"'LogTemp: [PnP]' lines written to '{pnp_out}'.")

def main():
    ap = argparse.ArgumentParser(description="Extract PnP lines and DebugLogSharedTagPositions blocks from a log file.")
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
