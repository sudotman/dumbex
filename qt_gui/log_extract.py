#!/usr/bin/env python3
"""
Modern Log Extractor
Requires: pip install customtkinter
"""

import threading
import argparse
import json
import re
import os
import tkinter as tk  # for file dialogs
import customtkinter as ctk
from dataclasses import dataclass
from typing import List, Optional

# -------------------------------------------------------------------------
#  CORE LOGIC (Pure Python, same as before)
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class BlockRule:
    trigger: str
    after: int

@dataclass(frozen=True)
class Rules:
    include: List[str]
    blocks: List[BlockRule]
    regex: bool = False

def _compile(patterns: List[str], regex: bool):
    if not regex:
        return patterns, None
    return None, [re.compile(p) for p in patterns]

def _matches(line: str, lits: Optional[List[str]], regs: Optional[List[re.Pattern]]):
    if lits:
        return any(p in line for p in lits)
    return any(r.search(line) for r in (regs or []))

def extract_process(
    in_path: str,
    out_path: str,
    rules: Rules,
    separators: bool,
    progress_callback=None,
    preview_callback=None
):
    # Compile patterns
    inc_lit, inc_re = _compile(rules.include, rules.regex)
    trig_lit, trig_re = _compile([b.trigger for b in rules.blocks], rules.regex)
    
    # Setup state
    after_map = [b.after for b in rules.blocks]
    active_counters = [0] * len(rules.blocks)
    
    fin = open(in_path, "r", encoding="utf-8", errors="replace")
    fout = open(out_path, "w", encoding="utf-8", errors="replace") if out_path else None
    
    try:
        line_count = 0
        match_count = 0
        
        for line in fin:
            line_count += 1
            keep = False
            
            # 1. Check Includes
            if rules.include and _matches(line, inc_lit, inc_re):
                keep = True
                
            # 2. Check Triggers
            triggered = False
            if rules.blocks:
                # Identify hits
                if trig_lit:
                    hits = [i for i, t in enumerate(trig_lit) if t in line]
                else:
                    hits = [i for i, r in enumerate(trig_re) if r.search(line)]
                
                if hits:
                    triggered = True
                    keep = True
                    for i in hits:
                        active_counters[i] = max(active_counters[i], after_map[i])
                    
                    if separators:
                        sep = f"\n>>> BLOCK TRIGGER @ L{line_count} >>>\n"
                        if fout: fout.write(sep)
                        if preview_callback: preview_callback(sep)

                # Check active windows
                if not triggered and any(c > 0 for c in active_counters):
                    keep = True
                    active_counters = [max(0, c - 1) for c in active_counters]

            if keep:
                match_count += 1
                if fout: fout.write(line)
                if preview_callback: preview_callback(line)
            
            # Update UI every 2000 lines
            if progress_callback and line_count % 2000 == 0:
                progress_callback(line_count, match_count, False)
                
        if progress_callback:
            progress_callback(line_count, match_count, True)
            
    finally:
        fin.close()
        if fout: fout.close()

# -------------------------------------------------------------------------
#  MODERN UI (CustomTkinter)
# -------------------------------------------------------------------------

ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Log Extractor Pro")
        self.geometry("1100x750")
        self.minsize(900, 600)

        # Layout: 2 Columns
        # Col 0: Sidebar (Settings) - Weight 0 (Fixed width)
        # Col 1: Preview (Terminal) - Weight 1 (Expands)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1) # Push content up

        self.logo_label = ctk.CTkLabel(self.sidebar, text="LOG EXTRACTOR", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # 1. Files Section
        self.frame_files = self.create_section_frame("File Operations")
        self.frame_files.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        self.entry_in = self.create_file_picker(self.frame_files, 0, "Input Log", False)
        self.entry_out = self.create_file_picker(self.frame_files, 2, "Output File", True)

        # 2. Rules Section (Tabview for compactness)
        self.frame_rules = ctk.CTkTabview(self.sidebar, width=280, height=250)
        self.frame_rules.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        self.tab_inc = self.frame_rules.add("Includes")
        self.tab_blk = self.frame_rules.add("Blocks")
        
        # Tab 1: Includes
        self.txt_inc = ctk.CTkTextbox(self.tab_inc, height=180, width=250, font=("Consolas", 12))
        self.txt_inc.pack(fill="both", expand=True, padx=5, pady=5)
        self.txt_inc.insert("0.0", "LogTemp: [PnP]\n")
        
        # Tab 2: Blocks
        self.txt_blk = ctk.CTkTextbox(self.tab_blk, height=180, width=250, font=("Consolas", 12))
        self.txt_blk.pack(fill="both", expand=True, padx=5, pady=5)
        self.txt_blk.insert("0.0", "LogTemp: === DebugLogSharedTagPositions::100\n")

        # 3. Settings Section
        self.frame_opts = self.create_section_frame("Configuration")
        self.frame_opts.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        
        self.sw_regex = ctk.CTkSwitch(self.frame_opts, text="Regex Mode")
        self.sw_regex.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.sw_sep = ctk.CTkSwitch(self.frame_opts, text="Add Separators")
        self.sw_sep.select()
        self.sw_sep.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.lbl_def = ctk.CTkLabel(self.frame_opts, text="Default Lines After:")
        self.lbl_def.grid(row=1, column=0, padx=10, pady=(0,10), sticky="w")
        self.ent_def = ctk.CTkEntry(self.frame_opts, width=60)
        self.ent_def.insert(0, "100")
        self.ent_def.grid(row=1, column=1, padx=10, pady=(0,10), sticky="w")

        # 4. Action Area (Bottom of Sidebar)
        self.btn_run = ctk.CTkButton(self.sidebar, text="START EXTRACTION", height=50, 
                                     font=ctk.CTkFont(size=14, weight="bold"), 
                                     fg_color="transparent", border_width=2, 
                                     text_color=("gray10", "#DCE4EE"),
                                     command=self.start_extraction)
        self.btn_run.grid(row=5, column=0, padx=20, pady=20, sticky="ew")

        self.progress = ctk.CTkProgressBar(self.sidebar)
        self.progress.grid(row=6, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.progress.set(0)

        # --- Main Area (Preview) ---
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_area.grid_rowconfigure(1, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        # Header
        self.lbl_status = ctk.CTkLabel(self.main_area, text="Ready", anchor="w", text_color="gray70")
        self.lbl_status.grid(row=0, column=0, sticky="w", padx=5, pady=(5, 5))

        # Terminal
        self.terminal = ctk.CTkTextbox(self.main_area, font=("Consolas", 13), activate_scrollbars=True)
        self.terminal.grid(row=1, column=0, sticky="nsew")
        self.terminal.configure(state="disabled")

        # Tags for coloring terminal output (simulated)
        self.terminal.tag_config("highlight", foreground="#60a5fa") # Blueish

    def create_section_frame(self, title):
        frame = ctk.CTkFrame(self.sidebar)
        frame.grid_columnconfigure(0, weight=1)
        lbl = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray70")
        lbl.grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=5)
        return frame

    def create_file_picker(self, parent, start_row, label_text, is_save):
        lbl = ctk.CTkLabel(parent, text=label_text, anchor="w")
        lbl.grid(row=start_row, column=0, padx=10, sticky="w")
        
        entry = ctk.CTkEntry(parent, placeholder_text="Select file...")
        entry.grid(row=start_row+1, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        def browse():
            file_path = tk.filedialog.asksaveasfilename() if is_save else tk.filedialog.askopenfilename()
            if file_path:
                entry.delete(0, "end")
                entry.insert(0, file_path)
                
        btn = ctk.CTkButton(parent, text="..", width=30, command=browse)
        btn.grid(row=start_row+1, column=1, padx=(0, 10), pady=(0, 10))
        
        parent.grid_columnconfigure(0, weight=1)
        return entry

    def log_to_terminal(self, text):
        self.terminal.configure(state="normal")
        # Keep buffer size manageable
        if float(self.terminal.index("end")) > 5000:
             self.terminal.delete("1.0", "2000.0")
        self.terminal.insert("end", text)
        self.terminal.see("end")
        self.terminal.configure(state="disabled")

    def update_progress(self, scanned, matched, done):
        if done:
            self.progress.set(1)
            self.btn_run.configure(state="normal", text="START EXTRACTION")
            self.lbl_status.configure(text=f"COMPLETED. Scanned: {scanned:,} | Extracted: {matched:,}", text_color="#4ade80") # Green
        else:
            # Indeterminate pulsing or rough percentage if we knew file size (not implemented for speed)
            self.progress.set((scanned % 10000) / 10000) 
            self.lbl_status.configure(text=f"RUNNING... Scanned: {scanned:,} | Found: {matched:,}")

    def start_extraction(self):
        in_path = self.entry_in.get()
        out_path = self.entry_out.get()
        
        if not in_path or not os.path.exists(in_path):
            self.log_to_terminal("ERROR: Input file not found.\n")
            return
            
        # Parse Rules
        includes = [x for x in self.txt_inc.get("1.0", "end").splitlines() if x.strip()]
        block_lines = [x for x in self.txt_blk.get("1.0", "end").splitlines() if x.strip()]
        
        blocks = []
        def_after = int(self.ent_def.get() or 100)
        
        for bl in block_lines:
            if "::" in bl:
                trig, num = bl.rsplit("::", 1)
                blocks.append(BlockRule(trig.strip(), int(num)))
            else:
                blocks.append(BlockRule(bl, def_after))
                
        rules = Rules(includes, blocks, self.sw_regex.get())
        
        # Reset UI
        self.terminal.configure(state="normal")
        self.terminal.delete("1.0", "end")
        self.terminal.configure(state="disabled")
        self.btn_run.configure(state="disabled", text="PROCESSING...")
        self.lbl_status.configure(text="Initializing...", text_color="gray70")
        
        # Run in thread
        t = threading.Thread(target=extract_process, args=(
            in_path, out_path, rules, 
            self.sw_sep.get(), 
            lambda s, m, d: self.after(0, self.update_progress, s, m, d),
            lambda txt: self.after(0, self.log_to_terminal, txt)
        ), daemon=True)
        t.start()

# -------------------------------------------------------------------------
#  CLI HANDLER
# -------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    # Add other CLI args here if needed to bypass GUI
    args, unknown = parser.parse_known_args()

    if args.cli:
        print("Run with --help to see CLI options or without arguments for GUI.")
        # ... logic to call extract_process via CLI ...
    else:
        app = App()
        app.mainloop()