import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import configparser
import os
import subprocess
import webbrowser
from pathlib import Path
from collections import Counter
from datetime import datetime
import xml.etree.ElementTree as ET
import csv
import pandas as pd

GITHUB_URL = "https://github.com/opheophe/XMLParser"

def _get_version():
    """Return version string.
    - Bundled exe: reads version.txt written by CI at build time.
    - Dev/source: returns the exact git tag on HEAD, or 'N/A' if untagged.
    """
    if getattr(sys, 'frozen', False):
        try:
            version_file = os.path.join(sys._MEIPASS, 'version.txt')
            with open(version_file, 'r') as f:
                return f.read().strip()
        except Exception:
            return "N/A"
    try:
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--exact-match", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        return tag if tag else "N/A"
    except Exception:
        return "N/A"

_VERSION = _get_version()  # resolved once at startup; avoids subprocess delay on each About open

def make_btn(parent, text, command=None, bg="#7F8C8D", fg="white",
             activebackground=None, activeforeground="white", **kwargs):
    if activebackground is None:
        activebackground = bg
    if sys.platform == "darwin":
        return tk.Button(parent, text=text, command=command, **kwargs)
    return tk.Button(parent, text=text, command=command,
                     bg=bg, fg=fg, activebackground=activebackground,
                     activeforeground=activeforeground, **kwargs)

class SettingsManager:
    def __init__(self, settings_file="Settings.ini"):
        # Use user's home directory for settings to avoid read-only app bundle issues
        import tempfile
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller bundle
            if sys.platform == "win32":
                # Windows: use AppData\Roaming
                app_data_dir = os.path.join(os.environ['APPDATA'], 'XMLParser')
            else:
                # macOS/Linux: use hidden folder in home
                app_data_dir = os.path.join(os.path.expanduser('~'), '.XMLParser')
            os.makedirs(app_data_dir, exist_ok=True)
            self.settings_file = os.path.join(app_data_dir, settings_file)
        else:
            # Running as script
            self.settings_file = settings_file
        self.config = configparser.ConfigParser()
        self.configs = {}
        self.merge_columns = {}
        self.output_columns = {}
        self.last_directory = ""
        self.last_selected_config = ""
        self.decimal_separator = "english"
        self.window_x = 100
        self.window_y = 100
        self.window_width = 1000
        self.window_height = 800
        self.load()
    
    def load(self):
        if os.path.exists(self.settings_file):
            self.config.read(self.settings_file)
            
            # Window settings
            if "Window" in self.config:
                window = self.config["Window"]
                self.window_x = window.getint("x", 100)
                self.window_y = window.getint("y", 100)
                self.window_width = window.getint("width", 1000)
                self.window_height = window.getint("height", 800)
            
            # Last directory
            if "General" in self.config:
                self.last_directory = self.config["General"].get("last_directory", "")
                self.last_selected_config = self.config["General"].get("last_selected_config", "")
                self.decimal_separator = self.config["General"].get("decimal_separator", "english")
            
            # Configs
            self.configs = {}
            self.merge_columns = {}
            self.output_columns = {}
            for section in self.config.sections():
                if section.startswith("Config:"):
                    config_name = section[7:]
                    values = self.config[section].get("values", "")
                    self.configs[config_name] = [v for v in values.split("\n") if v] if values else []
                    merge = self.config[section].get("merge", "")
                    self.merge_columns[config_name] = [v for v in merge.split("\n") if v] if merge else []
                    output = self.config[section].get("output", "")
                    self.output_columns[config_name] = [v for v in output.split("\n") if v] if output else []
        else:
            # Create default CAMT config
            self.configs["CAMT"] = [
                "GrpHdr; Yes",
                "Acct; Yes",
                "TxsSummry; Yes",
                "Ntry; No"
            ]
            self.merge_columns["CAMT"] = [
                "New Line; NtryDtls/TxDtls/RmtInf/Strd/RfrdDocAmt/RmtdAmt@Value; AmountCol1; Amount",
                "New Line; Strd/RfrdDocAmt/RmtdAmt@Value; AmountCol1; Amount",
                "New Line; NtryDtls/TxDtls/RmtInf/Strd/RfrdDocAmt/RmtdAmt@Ccy; Currency;",
                "New Line; Strd/RfrdDocAmt/RmtdAmt@Ccy; Currency;",
                "Merge; NtryDtls/TxDtls/RmtInf/Strd/RfrdDocInf/Nb; DocInfo;",
                "Merge; Strd/RfrdDocInf/Nb; DocInfo;",
                "Hide; NtryDtls/TxDtls/RmtInf/Strd/RfrdDocInf/Tp/CdOrPrtry/Cd; Type;",
                "Hide; Strd/RfrdDocInf/Tp/CdOrPrtry/Cd; Type;",
                "Merge; NtryDtls/TxDtls/RmtInf/Strd/AddtlRmtInf; DocInfo;",
                "Merge; NtryDtls/TxDtls/RltdPties/Dbtr/PstlAdr/AdrLine; Address;",
                "Merge; NtryDtls/TxDtls/RltdPties/Dbtr/PstlAdr/Ctry; Address;",
                "Merge; NtryDtls/TxDtls/RltdPties/Dbtr/PstlAdr/PstCd; Address;",
                "Merge; NtryDtls/TxDtls/RltdPties/Dbtr/PstlAdr/StrtNm; Address;",
                "Merge; NtryDtls/TxDtls/RltdPties/Dbtr/PstlAdr/TwnNm; Address;",
                "Hide; Ntry/BkTxCd/Domn/Cd; ;"
            ]
            self.save()
    
    def save(self):
        self.config = configparser.ConfigParser()
        
        # Window settings
        self.config["Window"] = {
            "x": str(self.window_x),
            "y": str(self.window_y),
            "width": str(self.window_width),
            "height": str(self.window_height)
        }
        
        # General settings
        self.config["General"] = {
            "last_directory": self.last_directory,
            "last_selected_config": self.last_selected_config,
            "decimal_separator": self.decimal_separator
        }
        
        # Configs
        for config_name, values in self.configs.items():
            self.config[f"Config:{config_name}"] = {
                "values": "\n".join(values),
                "merge": "\n".join(self.merge_columns.get(config_name, [])),
                "output": "\n".join(self.output_columns.get(config_name, []))
            }
        
        with open(self.settings_file, "w") as f:
            self.config.write(f)
    
    def add_config(self, name, values=None):
        self.configs[name] = values if values else []
        self.merge_columns[name] = []
        self.output_columns[name] = []
        self.save()

    def delete_config(self, name):
        if name in self.configs:
            del self.configs[name]
            self.merge_columns.pop(name, None)
            self.output_columns.pop(name, None)
            self.save()

    def update_config(self, name, values):
        if name in self.configs:
            self.configs[name] = values
            self.save()

    def update_merge_columns(self, name, rules):
        if name in self.configs:
            self.merge_columns[name] = rules
            self.save()

    def get_output_columns(self, name):
        return self.output_columns.get(name, [])

    def update_output_columns(self, name, rules):
        if name in self.configs:
            self.output_columns[name] = rules
            self.save()

    def get_config_names(self):
        return list(self.configs.keys())

    def get_config(self, name):
        return self.configs.get(name, [])

    def get_merge_columns(self, name):
        return self.merge_columns.get(name, [])
    
    def validate_window_position(self):
        # Get screen dimensions
        root = tk.Tk()
        root.withdraw()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        root.destroy()
        
        # Check if window is within screen bounds (with some tolerance)
        tolerance = 50
        if (self.window_x < -tolerance or 
            self.window_y < -tolerance or
            self.window_x + self.window_width > screen_width + tolerance or
            self.window_y + self.window_height > screen_height + tolerance):
            self.window_x = 100
            self.window_y = 100
            self.window_width = 1500
            self.window_height = 1200
            self.save()


class ConfigsDialog(tk.Toplevel):
    def __init__(self, parent, settings_manager, initial_config=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.initial_config = initial_config
        self.title("Configs")
        self.geometry("680x820")
        self.minsize(500, 500)
        self.transient(parent)
        self.grab_set()

        self.pending_tags   = {}   # {config_name: [tag_entry_strings]}
        self.pending_merge  = {}   # {config_name: [rule_strings]}
        self.pending_output = {}   # {config_name: [output_row_strings]}

        self.create_widgets()
        self.refresh_config_list()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    # ── widget construction ───────────────────────────────────────────────────

    def create_widgets(self):
        # ── fixed close buttons at bottom ─────────────────────────────────────
        close_btn_frame = tk.Frame(self)
        close_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        make_btn(close_btn_frame, text="Close and save",
                 command=self.close_and_save,
                 bg="#27AE60", fg="white",
                 activebackground="#1E8449", activeforeground="white").pack(side=tk.LEFT, padx=5)
        make_btn(close_btn_frame, text="Close",
                 command=self.destroy,
                 bg="#7F8C8D", fg="white",
                 activebackground="#616A6B", activeforeground="white").pack(side=tk.LEFT, padx=5)

        # ── scrollable canvas ─────────────────────────────────────────────────
        outer = tk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(outer, highlightthickness=0)
        vscroll = ttk.Scrollbar(outer, orient="vertical", command=self._canvas.yview)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        content = tk.Frame(self._canvas)
        self._canvas_win = self._canvas.create_window((0, 0), window=content, anchor="nw")

        content.bind("<Configure>",
                     lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(self._canvas_win, width=e.width))

        def _mousewheel(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._canvas.bind_all("<MouseWheel>", _mousewheel)

        # ── config list ────────────────────────────────────────────────────────
        list_frame = tk.Frame(content)
        list_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(list_frame, text="Configs:").pack(anchor=tk.W)

        lb_frame = tk.Frame(list_frame)
        lb_frame.pack(fill=tk.X)
        lb_scroll = tk.Scrollbar(lb_frame)
        lb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.config_listbox = tk.Listbox(lb_frame, height=4, yscrollcommand=lb_scroll.set)
        self.config_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.config_listbox.bind("<<ListboxSelect>>", self.on_config_select)
        lb_scroll.config(command=self.config_listbox.yview)

        # ── config buttons ─────────────────────────────────────────────────────
        buttons_frame = tk.Frame(content)
        buttons_frame.pack(fill=tk.X, padx=10, pady=5)
        self.add_button = make_btn(buttons_frame, text="Add config",
                                   command=self.add_config,
                                   bg="#27AE60", fg="white",
                                   activebackground="#1E8449", activeforeground="white")
        self.add_button.pack(side=tk.LEFT, padx=5)
        self.delete_button = make_btn(buttons_frame, text="Delete config",
                                      command=self.delete_config,
                                      bg="#E74C3C", fg="white",
                                      activebackground="#C0392B", activeforeground="white")
        self.delete_button.pack(side=tk.LEFT, padx=5)

        # ── Tags table ─────────────────────────────────────────────────────────
        tags_outer = tk.Frame(content)
        tags_outer.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(tags_outer, text="Tags to extract:").pack(anchor=tk.W)

        tags_table_frame = tk.Frame(tags_outer)
        tags_table_frame.pack(fill=tk.X)
        self.tags_tree = ttk.Treeview(tags_table_frame,
                                      columns=("tag", "split"),
                                      show="headings", height=6)
        self.tags_tree.heading("tag",   text="Tag")
        self.tags_tree.heading("split", text="Split Tabs")
        self.tags_tree.column("tag",   width=300, minwidth=100, stretch=True)
        self.tags_tree.column("split", width=80,  minwidth=70,  stretch=False)
        tags_vsb = ttk.Scrollbar(tags_table_frame, orient="vertical",
                                 command=self.tags_tree.yview)
        self.tags_tree.configure(yscrollcommand=tags_vsb.set)
        self.tags_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tags_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tags_tree.bind("<Double-1>", self.on_tags_cell_edit)

        tags_btn_frame = tk.Frame(tags_outer)
        tags_btn_frame.pack(fill=tk.X, pady=(3, 0))
        make_btn(tags_btn_frame, text="Add Row", command=self.add_tags_row,
                 bg="#27AE60", fg="white",
                 activebackground="#1E8449", activeforeground="white").pack(side=tk.LEFT, padx=(0, 5))
        make_btn(tags_btn_frame, text="Delete Row", command=self.delete_tags_row,
                 bg="#E74C3C", fg="white",
                 activebackground="#C0392B", activeforeground="white").pack(side=tk.LEFT)

        # ── Merge columns table ────────────────────────────────────────────────
        merge_outer = tk.Frame(content)
        merge_outer.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(merge_outer, text="Rename and merge columns:").pack(anchor=tk.W)

        merge_table_frame = tk.Frame(merge_outer)
        merge_table_frame.pack(fill=tk.X)
        self.merge_tree = ttk.Treeview(merge_table_frame,
                                       columns=("action", "source", "target", "format"),
                                       show="headings", height=8)
        self.merge_tree.heading("action", text="Action")
        self.merge_tree.heading("source", text="Source Column")
        self.merge_tree.heading("target", text="Target Name")
        self.merge_tree.heading("format", text="Format")
        self.merge_tree.column("action", width=80,  minwidth=70,  stretch=False)
        self.merge_tree.column("source", width=220, minwidth=100, stretch=True)
        self.merge_tree.column("target", width=100, minwidth=70,  stretch=True)
        self.merge_tree.column("format", width=70,  minwidth=60,  stretch=False)
        merge_vsb = ttk.Scrollbar(merge_table_frame, orient="vertical",
                                  command=self.merge_tree.yview)
        self.merge_tree.configure(yscrollcommand=merge_vsb.set)
        self.merge_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        merge_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.merge_tree.bind("<Double-1>", self.on_merge_cell_edit)

        merge_btn_frame = tk.Frame(merge_outer)
        merge_btn_frame.pack(fill=tk.X, pady=(3, 0))
        make_btn(merge_btn_frame, text="Add Row", command=self.add_merge_row,
                 bg="#27AE60", fg="white",
                 activebackground="#1E8449", activeforeground="white").pack(side=tk.LEFT, padx=(0, 5))
        make_btn(merge_btn_frame, text="Delete Row", command=self.delete_merge_row,
                 bg="#E74C3C", fg="white",
                 activebackground="#C0392B", activeforeground="white").pack(side=tk.LEFT)

        # ── Output section ─────────────────────────────────────────────────────
        output_outer = tk.Frame(content)
        output_outer.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(output_outer, text="Output:").pack(anchor=tk.W)

        output_table_frame = tk.Frame(output_outer)
        output_table_frame.pack(fill=tk.X)
        self.output_tree = ttk.Treeview(output_table_frame,
                                        columns=("tag", "column", "rename", "hide", "order"),
                                        show="headings", height=8)
        self.output_tree.heading("tag",    text="Tag")
        self.output_tree.heading("column", text="Column Name")
        self.output_tree.heading("rename", text="Rename to")
        self.output_tree.heading("hide",   text="Hide")
        self.output_tree.heading("order",  text="Order")
        self.output_tree.column("tag",    width=100, minwidth=60,  stretch=False)
        self.output_tree.column("column", width=190, minwidth=80,  stretch=True)
        self.output_tree.column("rename", width=150, minwidth=80,  stretch=False)
        self.output_tree.column("hide",   width=50,  minwidth=50,  stretch=False)
        self.output_tree.column("order",  width=60,  minwidth=50,  stretch=False)
        output_vsb = ttk.Scrollbar(output_table_frame, orient="vertical",
                                   command=self.output_tree.yview)
        self.output_tree.configure(yscrollcommand=output_vsb.set)
        self.output_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        output_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_tree.bind("<Double-1>",      self.on_output_cell_edit)
        self.output_tree.bind("<ButtonRelease-1>", self.on_output_hide_toggle)

        output_btn_frame = tk.Frame(output_outer)
        output_btn_frame.pack(fill=tk.X, pady=(3, 0))
        make_btn(output_btn_frame, text="Add Row", command=self.add_output_row,
                 bg="#27AE60", fg="white",
                 activebackground="#1E8449", activeforeground="white").pack(side=tk.LEFT, padx=(0, 5))
        make_btn(output_btn_frame, text="Delete Row", command=self.delete_output_row,
                 bg="#E74C3C", fg="white",
                 activebackground="#C0392B", activeforeground="white").pack(side=tk.LEFT)

        self.current_config = None

    # ── config list helpers ───────────────────────────────────────────────────

    def refresh_config_list(self):
        self.config_listbox.delete(0, tk.END)
        for name in sorted(self.settings_manager.get_config_names()):
            self.config_listbox.insert(tk.END, name)
        if self.initial_config and not self.current_config:
            for i in range(self.config_listbox.size()):
                if self.config_listbox.get(i) == self.initial_config:
                    self.config_listbox.selection_set(i)
                    self.config_listbox.see(i)
                    self.on_config_select(None)
                    break
        self.update_parent_dropdown()

    def on_config_select(self, event):
        selection = self.config_listbox.curselection()
        if selection:
            if self.current_config:
                self._buffer_current_edits()
            self.current_config = self.config_listbox.get(selection[0])
            self._load_config(self.current_config)

    def _buffer_current_edits(self):
        tags, merge = self._read_ui()
        output = self._read_output_ui()
        self.pending_tags[self.current_config]   = tags
        self.pending_merge[self.current_config]  = merge
        self.pending_output[self.current_config] = output

    def _read_ui(self):
        tags = []
        for item in self.tags_tree.get_children():
            vals = self.tags_tree.item(item, "values")
            tag   = vals[0].strip() if len(vals) > 0 else ""
            split = vals[1].strip() if len(vals) > 1 else "Yes"
            if tag:
                tags.append(f"{tag}; {split}")
        merge = []
        for item in self.merge_tree.get_children():
            vals   = self.merge_tree.item(item, "values")
            action = vals[0].strip() if len(vals) > 0 else "New Line"
            source = vals[1].strip() if len(vals) > 1 else ""
            target = vals[2].strip() if len(vals) > 2 else ""
            fmt    = vals[3].strip() if len(vals) > 3 else ""
            if source:
                merge.append(f"{action}; {source}; {target}; {fmt}")
        return tags, merge

    def _read_output_ui(self):
        rows = []
        for item in self.output_tree.get_children():
            vals   = self.output_tree.item(item, "values")
            tag    = vals[0].strip() if len(vals) > 0 else ""
            col    = vals[1].strip() if len(vals) > 1 else ""
            rename = vals[2].strip() if len(vals) > 2 else ""
            hide   = vals[3].strip() if len(vals) > 3 else "No"
            order  = vals[4].strip() if len(vals) > 4 else ""
            if not col:
                continue
            # Only persist rows that actually configure something
            if hide == "Yes" or order or rename:
                rows.append(f"{tag}; {col}; {rename}; {hide}; {order}")
        return rows

    def _get_current_columns(self):
        """Return list of (base_tag, column) pairs from the parent app's displayed tabs."""
        tab_data = getattr(self.master, "tab_data", [])
        seen = []
        for tab_name, columns, _, _ in tab_data:
            # Strip trailing number for split tabs: "Ntry 1" → "Ntry"
            parts = tab_name.rsplit(' ', 1)
            base_tag = parts[0] if len(parts) == 2 and parts[1].isdigit() else tab_name
            for col in columns:
                pair = (base_tag, col)
                if pair not in seen:
                    seen.append(pair)
        return seen

    def _load_config(self, config_name):
        # ── tags ──
        tags = self.pending_tags.get(config_name,
               self.settings_manager.get_config(config_name))
        for item in self.tags_tree.get_children():
            self.tags_tree.delete(item)
        for entry in tags:
            parts = [p.strip() for p in entry.split(';')]
            tag   = parts[0] if len(parts) > 0 else ""
            split = parts[1] if len(parts) > 1 else "Yes"
            if split not in ("Yes", "No"):
                split = "Yes"
            self.tags_tree.insert("", tk.END, values=(tag, split))

        # ── merge (Hide rules are filtered out and migrated to output) ──
        merge = self.pending_merge.get(config_name,
                self.settings_manager.get_merge_columns(config_name))
        migrated_hides = {}   # col -> True for any Hide rules found in merge
        for item in self.merge_tree.get_children():
            self.merge_tree.delete(item)
        for rule in merge:
            parts  = [p.strip() for p in rule.split(';')]
            action = parts[0] if len(parts) > 0 else "New Line"
            source = parts[1] if len(parts) > 1 else ""
            target = parts[2] if len(parts) > 2 else ""
            fmt    = parts[3] if len(parts) > 3 else ""
            if action not in ("New Line", "Merge", "Hide"):
                if target in ("New Line", "Merge", "Hide"):
                    action, target = target, action
                else:
                    action = "New Line"
            if action == "Hide":
                # Migrate to output section instead of showing in merge table
                if source:
                    migrated_hides[source] = True
                continue
            if fmt not in ("", "String", "Amount"):
                fmt = ""
            self.merge_tree.insert("", tk.END, values=(action, source, target, fmt))

        # ── output ──
        saved = self.pending_output.get(config_name,
                self.settings_manager.get_output_columns(config_name))
        saved_map = {}   # (tag, col) -> (rename, hide, order)
        for row in saved:
            parts = [p.strip() for p in row.split(';')]
            # Backward compat:
            #   3-part: col; hide; order          (oldest — no tag, no rename)
            #   4-part: tag; col; hide; order     (old — no rename)
            #   5-part: tag; col; rename; hide; order  (current)
            if len(parts) == 3:
                tag_s, col, rename, hide, order = '', parts[0], '', parts[1], parts[2]
            elif len(parts) == 4:
                tag_s, col, rename, hide, order = parts[0], parts[1], '', parts[2], parts[3]
            elif len(parts) >= 5:
                tag_s, col, rename, hide, order = parts[0], parts[1], parts[2], parts[3], parts[4]
            else:
                continue
            if col:
                saved_map[(tag_s, col)] = (rename, hide, order)

        # Migrate any Hide rules from merge (no tag — applies to all)
        for col in migrated_hides:
            key = ('', col)
            if key not in saved_map:
                saved_map[key] = ('', 'Yes', '')

        # Combine current parse columns with saved-only extras
        current_pairs = self._get_current_columns()   # list of (base_tag, col)
        all_pairs = list(current_pairs)
        for key in saved_map:
            if key not in all_pairs:
                all_pairs.append(key)

        # Sort: by tag, then column name
        all_pairs.sort(key=lambda p: (p[0], p[1]))

        for item in self.output_tree.get_children():
            self.output_tree.delete(item)
        for tag_s, col in all_pairs:
            rename_val, hide_val, order_val = saved_map.get((tag_s, col), ('', 'No', ''))
            self.output_tree.insert("", tk.END, values=(tag_s, col, rename_val, hide_val, order_val))

    # ── save / close ─────────────────────────────────────────────────────────

    def close_and_save(self):
        if self.current_config:
            self._buffer_current_edits()
        for config_name, tags in self.pending_tags.items():
            self.settings_manager.update_config(config_name, tags)
        for config_name, merge in self.pending_merge.items():
            self.settings_manager.update_merge_columns(config_name, merge)
        for config_name, output in self.pending_output.items():
            self.settings_manager.update_output_columns(config_name, output)
        self.destroy()

    # ── merge table editing ───────────────────────────────────────────────────

    def on_merge_cell_edit(self, event):
        region = self.merge_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col_id = self.merge_tree.identify_column(event.x)
        item   = self.merge_tree.identify_row(event.y)
        if not item:
            return
        col_idx  = int(col_id[1:]) - 1
        col_names = ("action", "source", "target", "format")
        col_name  = col_names[col_idx]
        bbox = self.merge_tree.bbox(item, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        current = self.merge_tree.set(item, col_name)
        if col_name == "action":
            dropdown_values = ["New Line", "Merge"]   # Hide removed
            editor = ttk.Combobox(self.merge_tree, values=dropdown_values, state="readonly")
            editor.set(current if current in dropdown_values else dropdown_values[0])
            editor.place(x=x, y=y, width=w, height=h)
            editor.focus()
            def commit_combo(event=None, _editor=editor, _item=item, _col=col_name):
                self.merge_tree.set(_item, _col, _editor.get())
                _editor.destroy()
            editor.bind("<<ComboboxSelected>>", commit_combo)
            editor.bind("<FocusOut>", lambda e, _editor=editor: _editor.destroy())
        elif col_name == "format":
            dropdown_values = ["", "String", "Amount"]
            editor = ttk.Combobox(self.merge_tree, values=dropdown_values, state="readonly")
            editor.set(current if current in dropdown_values else "")
            editor.place(x=x, y=y, width=w, height=h)
            editor.focus()
            def commit_fmt(event=None, _editor=editor, _item=item, _col=col_name):
                self.merge_tree.set(_item, _col, _editor.get())
                _editor.destroy()
            editor.bind("<<ComboboxSelected>>", commit_fmt)
            editor.bind("<FocusOut>", lambda e, _editor=editor: _editor.destroy())
        else:
            editor = tk.Entry(self.merge_tree)
            editor.insert(0, current)
            editor.select_range(0, tk.END)
            editor.place(x=x, y=y, width=w, height=h)
            editor.focus()
            def commit_entry(event=None, _editor=editor, _item=item, _col=col_name):
                self.merge_tree.set(_item, _col, _editor.get())
                _editor.destroy()
            def cancel_entry(event=None, _editor=editor):
                _editor.destroy()
            editor.bind("<Return>",   commit_entry)
            editor.bind("<FocusOut>", commit_entry)
            editor.bind("<Escape>",   cancel_entry)

    def add_merge_row(self):
        item = self.merge_tree.insert("", tk.END, values=("New Line", "", "", ""))
        self.merge_tree.selection_set(item)
        self.merge_tree.see(item)

    def delete_merge_row(self):
        for item in self.merge_tree.selection():
            self.merge_tree.delete(item)

    # ── tags table editing ────────────────────────────────────────────────────

    def on_tags_cell_edit(self, event):
        region = self.tags_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col_id = self.tags_tree.identify_column(event.x)
        item   = self.tags_tree.identify_row(event.y)
        if not item:
            return
        col_idx  = int(col_id[1:]) - 1
        col_names = ("tag", "split")
        col_name  = col_names[col_idx]
        bbox = self.tags_tree.bbox(item, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        current = self.tags_tree.set(item, col_name)
        if col_name == "split":
            editor = ttk.Combobox(self.tags_tree, values=["Yes", "No"], state="readonly")
            editor.set(current if current in ("Yes", "No") else "Yes")
            editor.place(x=x, y=y, width=w, height=h)
            editor.focus()
            def commit_tags_combo(event=None, _editor=editor, _item=item, _col=col_name):
                self.tags_tree.set(_item, _col, _editor.get())
                _editor.destroy()
            editor.bind("<<ComboboxSelected>>", commit_tags_combo)
            editor.bind("<FocusOut>", lambda e, _editor=editor: _editor.destroy())
        else:
            editor = tk.Entry(self.tags_tree)
            editor.insert(0, current)
            editor.select_range(0, tk.END)
            editor.place(x=x, y=y, width=w, height=h)
            editor.focus()
            def commit_tags_entry(event=None, _editor=editor, _item=item, _col=col_name):
                self.tags_tree.set(_item, _col, _editor.get())
                _editor.destroy()
            def cancel_tags_entry(event=None, _editor=editor):
                _editor.destroy()
            editor.bind("<Return>",   commit_tags_entry)
            editor.bind("<FocusOut>", commit_tags_entry)
            editor.bind("<Escape>",   cancel_tags_entry)

    def add_tags_row(self):
        item = self.tags_tree.insert("", tk.END, values=("", "Yes"))
        self.tags_tree.selection_set(item)
        self.tags_tree.see(item)

    def delete_tags_row(self):
        for item in self.tags_tree.selection():
            self.tags_tree.delete(item)

    # ── output table editing ──────────────────────────────────────────────────

    def on_output_hide_toggle(self, event):
        """Single-click on the Hide column (#4) toggles Yes/No."""
        col_id = self.output_tree.identify_column(event.x)
        if col_id != "#4":
            return
        item = self.output_tree.identify_row(event.y)
        if not item:
            return
        current = self.output_tree.set(item, "hide")
        self.output_tree.set(item, "hide", "No" if current == "Yes" else "Yes")

    def on_output_cell_edit(self, event):
        """Double-click edits Tag, Column Name, or Order; Hide is handled by single-click."""
        region = self.output_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col_id = self.output_tree.identify_column(event.x)
        item   = self.output_tree.identify_row(event.y)
        if not item:
            return
        col_idx   = int(col_id[1:]) - 1
        col_names = ("tag", "column", "rename", "hide", "order")
        col_name  = col_names[col_idx]
        if col_name == "hide":
            return   # handled by single-click toggle
        bbox = self.output_tree.bbox(item, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        current = self.output_tree.set(item, col_name)
        editor = tk.Entry(self.output_tree)
        editor.insert(0, current)
        editor.select_range(0, tk.END)
        editor.place(x=x, y=y, width=w, height=h)
        editor.focus()
        def commit(event=None, _editor=editor, _item=item, _col=col_name):
            val = _editor.get()
            if _col == "order" and val and not val.isdigit():
                val = ""   # reject non-integer input
            self.output_tree.set(_item, _col, val)
            _editor.destroy()
        def cancel(event=None, _editor=editor):
            _editor.destroy()
        editor.bind("<Return>",   commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>",   cancel)

    def add_output_row(self):
        item = self.output_tree.insert("", tk.END, values=("", "", "", "No", ""))
        self.output_tree.selection_set(item)
        self.output_tree.see(item)

    def delete_output_row(self):
        for item in self.output_tree.selection():
            self.output_tree.delete(item)

    # ── config add / delete ───────────────────────────────────────────────────

    def add_config(self):
        dialog = tk.Toplevel(self)
        dialog.title("Add Config")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("300x100")
        tk.Label(dialog, text="Config name:").pack(pady=5)
        name_entry = tk.Entry(dialog)
        name_entry.pack(fill=tk.X, padx=10)
        name_entry.focus()

        def confirm():
            name = name_entry.get().strip()
            if name:
                if name in self.settings_manager.get_config_names():
                    messagebox.showerror("Error", f"Config '{name}' already exists.")
                else:
                    self.settings_manager.add_config(name)
                    self.refresh_config_list()
                    for i in range(self.config_listbox.size()):
                        if self.config_listbox.get(i) == name:
                            self.config_listbox.selection_clear(0, tk.END)
                            self.config_listbox.selection_set(i)
                            self.config_listbox.see(i)
                            self.on_config_select(None)
                            break
                    dialog.destroy()

        def cancel():
            dialog.destroy()

        btn_f = tk.Frame(dialog)
        btn_f.pack(pady=10)
        make_btn(btn_f, text="OK", command=confirm,
                 bg="#27AE60", fg="white",
                 activebackground="#1E8449", activeforeground="white").pack(side=tk.LEFT, padx=5)
        make_btn(btn_f, text="Cancel", command=cancel,
                 bg="#7F8C8D", fg="white",
                 activebackground="#616A6B", activeforeground="white").pack(side=tk.LEFT, padx=5)
        dialog.bind("<Return>", lambda e: confirm())
        dialog.bind("<Escape>", lambda e: cancel())
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - dialog.winfo_width())  // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

    def delete_config(self):
        selection = self.config_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a config to delete.")
            return
        name = self.config_listbox.get(selection[0])
        if messagebox.askyesno("Confirm", f"Delete config '{name}'?"):
            for tree in (self.tags_tree, self.merge_tree, self.output_tree):
                for item in tree.get_children():
                    tree.delete(item)
            self.pending_tags.pop(name, None)
            self.pending_merge.pop(name, None)
            self.pending_output.pop(name, None)
            self.current_config = None
            self.settings_manager.delete_config(name)
            self.refresh_config_list()

    # ── info dialog ───────────────────────────────────────────────────────────


    def update_parent_dropdown(self):
        self.master.update_config_dropdown()


class XMLParserApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.settings_manager = SettingsManager()
        self.settings_manager.validate_window_position()

        self.title("XML Parser")
        self.geometry(f"{self.settings_manager.window_width}x{self.settings_manager.window_height}+{self.settings_manager.window_x}+{self.settings_manager.window_y}")

        self.decimal_var = tk.StringVar(value=self.settings_manager.decimal_separator)
        self.tab_data = []
        self.create_menu()
        self.create_widgets()
        self.update_config_dropdown()
        
        # Bind window close to save settings
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Configure>", self.on_resize)
        
        # macOS-specific: Ensure window appears when built with --windowed
        if sys.platform == "darwin":
            try:
                self.lift()
                self.after(100, self.force_focus)
            except Exception as e:
                print(f"Window activation error: {e}")
    
    def force_focus(self):
        try:
            self.focus_force()
        except Exception as e:
            print(f"Focus error: {e}")
    
    def create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Configs", command=self.open_configs)
        settings_menu.add_separator()

        decimal_menu = tk.Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="Decimal separator", menu=decimal_menu)
        decimal_menu.add_radiobutton(label="English  (1 234.56)", variable=self.decimal_var,
                                     value="english", command=self.on_decimal_change)
        decimal_menu.add_radiobutton(label="Swedish  (1 234,56)", variable=self.decimal_var,
                                     value="swedish", command=self.on_decimal_change)

        dev_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Dev", menu=dev_menu)
        dev_menu.add_command(label="Open Folder", command=self.open_program_folder)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Config…", command=self.show_config_help)
        help_menu.add_separator()
        help_menu.add_command(label="About XMLParser…", command=self.show_about)
        help_menu.add_command(label="View on GitHub", command=lambda: webbrowser.open(GITHUB_URL))

    def show_config_help(self):
        dlg = tk.Toplevel(self)
        dlg.title("Config Settings Guide")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(True, True)
        dlg.geometry("620x520")

        text_frame = tk.Frame(dlg)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

        vsb = ttk.Scrollbar(text_frame, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        txt = tk.Text(text_frame, wrap=tk.WORD, font=("Courier", 9),
                      yscrollcommand=vsb.set, relief="flat",
                      padx=8, pady=6, state="normal")
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.config(command=txt.yview)

        content = (
            "TAGS TO EXTRACT\n"
            "───────────────\n"
            "Each row specifies one XML tag to search for in the loaded file.\n"
            "\n"
            "  Tag         — The XML element name to look for (e.g. Ntry).\n"
            "  Split Tabs  — What to do when multiple elements with this\n"
            "                tag are found in the file:\n"
            "\n"
            "    Yes  Each instance gets its own tab (Tag 1, Tag 2, …).\n"
            "    No   All instances are combined into a single tab.\n"
            "\n"
            "\n"
            "RENAME AND MERGE COLUMNS\n"
            "────────────────────────\n"
            "Maps raw XML paths to friendlier column names and controls how\n"
            "multiple source fields are combined.\n"
            "\n"
            "  Action        — How to combine values when multiple source\n"
            "                  columns map to the same target:\n"
            "\n"
            "    New Line  Each unique value gets its own row so no data\n"
            "              is lost. If one row has values in two sources,\n"
            "              two output rows are produced.\n"
            "\n"
            "    Merge     All source values are joined into one cell,\n"
            "              separated by a space.\n"
            "              Example: 'Main St' + '12' → 'Main St 12'\n"
            "\n"
            "  Source Column — The raw XML path of the source column\n"
            "                  (e.g. NtryDtls/TxDtls/RmtInf/Strd/Nb).\n"
            "  Target Name   — The display name for the merged output column.\n"
            "  Format        — How the column is typed in Excel export:\n"
            "\n"
            "    (blank)   Default — @Value columns are numeric, others text.\n"
            "    String    Force the column to text even if it looks numeric.\n"
            "    Amount    Force the column to numeric.\n"
            "\n"
            "Notes:\n"
            "• Multiple rows sharing the same Target Name funnel several\n"
            "  source columns into one output column.\n"
            "• Identical values across sources are deduplicated (shown once).\n"
            "• Double-click any cell to edit it.\n"
            "\n"
            "\n"
            "OUTPUT\n"
            "──────\n"
            "Fine-tunes which columns appear in the final output, what they\n"
            "are called, and in what order they appear. The list is\n"
            "pre-populated with all columns from the most recent parse.\n"
            "\n"
            "  Tag         — Limit this rule to a specific tag-tab.\n"
            "                Leave blank to apply to all tabs.\n"
            "  Column Name — The column as it comes out of parsing/merging.\n"
            "  Rename to   — Optional. If filled in, the column header in\n"
            "                the output is replaced with this name.\n"
            "                Leave blank to keep the original name.\n"
            "  Hide        — Single-click to toggle Yes/No.\n"
            "                Yes removes the column from all output.\n"
            "                A warning appears in the toolbar if a value\n"
            "                (Amount) column is hidden.\n"
            "  Order       — Integer. Columns with an order number are\n"
            "                placed first, sorted ascending. Columns without\n"
            "                a number follow in their default order.\n"
            "\n"
            "Only rows where Hide = Yes, Order, or Rename to are set are\n"
            "saved. Display-only rows (nothing configured) are not persisted\n"
            "but reappear automatically the next time a file is parsed.\n"
        )

        txt.insert("1.0", content)
        txt.config(state="disabled")

        make_btn(dlg, text="Close", command=dlg.destroy,
                 bg="#7F8C8D", fg="white",
                 activebackground="#616A6B", activeforeground="white").pack(pady=(0, 10))

        dlg.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - dlg.winfo_width())  // 2
        y = self.winfo_y() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")

    def show_about(self):
        version = _VERSION
        dlg = tk.Toplevel(self)
        dlg.title("About XMLParser")
        dlg.resizable(False, False)
        dlg.grab_set()

        pad = {"padx": 20, "pady": 6}

        tk.Label(dlg, text="XMLParser", font=("TkDefaultFont", 16, "bold")).pack(**pad)
        tk.Label(dlg, text=f"Version: {version}").pack(**pad)

        link = tk.Label(dlg, text=GITHUB_URL, fg="#0078D7", cursor="hand2")
        link.pack(**pad)
        link.bind("<Button-1>", lambda e: webbrowser.open(GITHUB_URL))

        tk.Button(dlg, text="Close", command=dlg.destroy, width=10).pack(pady=(4, 16))

        # Centre over main window
        self.update_idletasks()
        dlg.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dlg.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")

    def on_decimal_change(self):
        self.settings_manager.decimal_separator = self.decimal_var.get()
        self.settings_manager.save()

    def open_program_folder(self):
        # Open the directory where settings are stored
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller bundle
            if sys.platform == "win32":
                folder = os.path.join(os.environ['APPDATA'], 'XMLParser')
            else:
                folder = os.path.join(os.path.expanduser('~'), '.XMLParser')
        else:
            # Running as script - open current directory
            folder = os.getcwd()
        
        if sys.platform == "darwin":  # macOS
            subprocess.Popen(["open", folder])
        elif sys.platform == "win32":  # Windows
            subprocess.Popen(["explorer", folder])
        elif sys.platform.startswith("linux"):  # Linux
            subprocess.Popen(["xdg-open", folder])
        else:
            # Fallback for other platforms
            import webbrowser
            webbrowser.open(f"file://{folder}")
    
    def create_widgets(self):
        # Main container with 20/80 split
        self.upper_frame = tk.Frame(self)
        self.upper_frame.pack(fill=tk.X)

        self.lower_frame = tk.Frame(self)
        self.lower_frame.pack(fill=tk.BOTH, expand=True)

        # Upper frame contents (left-aligned)
        button_frame = tk.Frame(self.upper_frame)
        button_frame.pack(pady=5, padx=10, anchor=tk.W)
        
        self.open_button = make_btn(button_frame, text="Open", command=self.open_file,
                                    bg="#4A90D9", fg="white", activebackground="#357ABD", activeforeground="white")
        self.open_button.pack(side=tk.LEFT, padx=10)

        # Config dropdown
        self.config_var = tk.StringVar(self)
        self.config_dropdown = ttk.Combobox(button_frame, textvariable=self.config_var, state="readonly", width=30)
        self.config_dropdown.pack(side=tk.LEFT, padx=10)
        self.config_dropdown.bind("<<ComboboxSelected>>", self.on_config_selected)

        # Export CSV button
        self.export_button = make_btn(button_frame, text="Export CSV", command=self.export_csv, state="disabled",
                                      bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white",
                                      disabledforeground="black")
        self.export_button.pack(side=tk.LEFT, padx=10)

        # Export Excel button
        self.export_excel_button = make_btn(button_frame, text="Export Excel", command=self.export_excel, state="disabled",
                                            bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white",
                                            disabledforeground="black")
        self.export_excel_button.pack(side=tk.LEFT, padx=10)

        # Status chip — shown after parsing (success or hidden-value warning)
        # Outer frame acts as a 1 px coloured border
        self.status_border = tk.Frame(button_frame, bd=0)
        self.status_inner  = tk.Frame(self.status_border, bd=0)
        self.status_label  = tk.Label(self.status_inner, padx=10, pady=3,
                                      font=("TkDefaultFont", 9, "bold"))
        self.status_label.pack()
        self.status_inner.pack(padx=1, pady=1)
        # Not packed yet — shown on demand
        
        # Notebook
        self.notebook = ttk.Notebook(self.lower_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tab_data = []  # list of (tab_name, columns, rows, col_formats)
    
    def _initial_dir(self):
        """Return the best starting directory for any file dialog.

        Uses the stored last-directory when it still exists on disk;
        falls back to the user's home directory otherwise.
        """
        d = self.settings_manager.last_directory
        if d and os.path.isdir(d):
            return d
        return os.path.expanduser("~")

    def open_file(self):
        file_paths = filedialog.askopenfilenames(
            title="Select XML file(s)",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            initialdir=self._initial_dir()
        )

        if file_paths:
            self.settings_manager.last_directory = os.path.dirname(file_paths[0])
            self.settings_manager.save()
            self.parse_and_display_xml(file_paths)
    
    def update_config_dropdown(self):
        config_names = self.settings_manager.get_config_names()
        
        if not config_names:
            self.config_dropdown["values"] = ["No configs"]
            self.config_var.set("No configs")
            self.config_dropdown.config(state="disabled")
        else:
            self.config_dropdown.config(state="readonly")
            current = self.config_var.get()
            last_selected = self.settings_manager.last_selected_config
            self.config_dropdown["values"] = config_names
            
            if current in config_names:
                self.config_var.set(current)
            elif last_selected in config_names:
                self.config_var.set(last_selected)
            else:
                self.config_var.set(config_names[0])
    
    def on_config_selected(self, event=None):
        selected = self.config_var.get()
        if selected != "No configs":
            self.settings_manager.last_selected_config = selected
            self.settings_manager.save()
        print(f"Selected config: {selected}")
    
    def open_configs(self):
        ConfigsDialog(self, self.settings_manager, self.config_var.get())
    
    def on_resize(self, event):
        if event.widget == self:
            self.settings_manager.window_width = self.winfo_width()
            self.settings_manager.window_height = self.winfo_height()
    
    def on_close(self):
        # Save final window position
        self.settings_manager.window_x = self.winfo_x()
        self.settings_manager.window_y = self.winfo_y()
        self.settings_manager.save()
        self.destroy()
    
    def find_record_info(self, elem):
        """Return (record_tag, record_parent) for the first repeating child tag found, or (None, None)."""
        child_tag_counts = Counter(child.tag for child in elem)
        for tag, count in child_tag_counts.items():
            if count > 1:
                # Leaf-only repetitions are split field values, not record structures — skip them
                if any(len(c) > 0 for c in elem if c.tag == tag):
                    return tag, elem
        for child in elem:
            if child_tag_counts[child.tag] == 1:
                result_tag, result_parent = self.find_record_info(child)
                if result_tag is not None:
                    return result_tag, result_parent
        return None, None

    def get_leaves_excluding_tag(self, elem, exclude_tag, path="", leaves=None):
        """Collect nodes with data from elem, skipping all subtrees rooted at exclude_tag."""
        if leaves is None:
            leaves = []
        current_path = f"{path}/{elem.tag}" if path else elem.tag
        if elem.tag == exclude_tag:
            return leaves
        text = elem.text.strip() if elem.text else ""
        if len(elem) == 0 or text or elem.attrib:
            leaves.append({'path': current_path, 'tag': elem.tag, 'text': text, 'attributes': dict(elem.attrib)})
        for child in elem:
            self.get_leaves_excluding_tag(child, exclude_tag, current_path, leaves)
        return leaves

    def collect_flat_records(self, elem, ancestor_leaves=None):
        """Recursively descend to the deepest repeating level, accumulating ancestor context."""
        if ancestor_leaves is None:
            ancestor_leaves = []

        record_tag, record_parent = self.find_record_info(elem)

        if record_tag is None:
            return [ancestor_leaves + self.get_leaf_nodes(elem)]

        parent_leaves = self.get_leaves_excluding_tag(elem, record_tag)
        combined = ancestor_leaves + parent_leaves

        result = []
        for record_elem in record_parent.findall(record_tag):
            result.extend(self.collect_flat_records(record_elem, combined))
        return result

    def element_to_rows(self, elem):
        all_leaf_lists = self.collect_flat_records(elem)

        if not all_leaf_lists:
            return [], []

        all_paths = sorted(set(leaf['path'] for leaves in all_leaf_lists for leaf in leaves))
        amount_columns = set()
        columns = []
        for col in all_paths:
            if col.endswith('/Amt') or col.endswith('/RmtdAmt'):
                columns.append(f"{col}@Value")
                columns.append(f"{col}@Ccy")
                amount_columns.add(col)
            else:
                columns.append(col)

        rows = []
        for leaves in all_leaf_lists:
            row = {}
            for leaf in leaves:
                path = leaf['path']
                value = leaf['text']
                if path in amount_columns:
                    val_key = f"{path}@Value"
                    ccy_key = f"{path}@Ccy"
                    new_ccy = leaf['attributes'].get('Ccy', '')
                    if value or val_key not in row:
                        row[val_key] = value
                    if new_ccy or ccy_key not in row:
                        row[ccy_key] = new_ccy
                else:
                    if leaf['attributes']:
                        attr_parts = [f"{k}={v}" for k, v in leaf['attributes'].items()]
                        value = f"{value} ({' '.join(attr_parts)})" if value else ' '.join(attr_parts)
                    if value:
                        row[path] = (row[path] + " " + value) if row.get(path) else value
                    elif path not in row:
                        row[path] = ""
            rows.append(row)

        return columns, rows

    def apply_column_merges(self, columns, rows, merge_rules):
        if not merge_rules:
            return columns, rows, {}

        hide_cols = set()
        target_to_sources = {}
        target_action_mode = {}
        target_format = {}
        for rule in merge_rules:
            if ';' not in rule:
                continue
            parts = rule.split(';', 3)
            if len(parts) < 2:
                continue
            action = parts[0].strip()
            source = parts[1].strip()
            target = parts[2].strip() if len(parts) > 2 else ""
            fmt = parts[3].strip() if len(parts) > 3 else ""
            if action not in ("New Line", "Merge", "Hide"):
                # Old format was Target; Source; Conflict — migrate transparently
                if target in ("New Line", "Merge", "Hide"):
                    action, target = target, action
                else:
                    action = "New Line"
            if not source:
                continue
            if action == "Hide":
                hide_cols.add(source)
            else:
                if not target:
                    continue
                if target not in target_to_sources:
                    target_to_sources[target] = []
                    target_action_mode[target] = action
                if source not in target_to_sources[target]:
                    target_to_sources[target].append(source)
                if fmt in ("String", "Amount"):
                    target_format[target] = fmt

        all_source_cols = {src for srcs in target_to_sources.values() for src in srcs}

        # Build new column order: drop hidden cols, replace first source with target name.
        new_columns = []
        added_targets = set()
        for col in columns:
            if col in hide_cols:
                continue
            if col in all_source_cols:
                target = next((t for t, srcs in target_to_sources.items() if col in srcs), None)
                if target and target not in added_targets:
                    added_targets.add(target)
                    new_columns.append(target)
            else:
                new_columns.append(col)

        new_rows = []
        for row in rows:
            target_values = {}
            for target, sources in target_to_sources.items():
                seen = []
                for src in sources:
                    v = row.get(src, "")
                    if v and v not in seen:
                        seen.append(v)
                target_values[target] = seen

            # Only "New Line" targets with multiple values drive row expansion.
            new_line_multi = [t for t, vals in target_values.items()
                              if len(vals) > 1 and target_action_mode.get(t) == "New Line"]
            max_expand = max((len(target_values[t]) for t in new_line_multi), default=1)

            for i in range(max_expand):
                new_row = {}
                for col in new_columns:
                    if col in target_to_sources:
                        vals = target_values[col]
                        if target_action_mode.get(col) == "Merge":
                            new_row[col] = " ".join(v for v in vals if v)
                        else:
                            new_row[col] = vals[i] if i < len(vals) else ""
                    else:
                        new_row[col] = row.get(col, "")
                new_rows.append(new_row)

        return new_columns, new_rows, target_format

    def apply_output_columns(self, columns, rows, output_rules, tag="", col_formats=None):
        """Apply hide, reorder, and rename rules from the Output config section for a given tag-tab.

        Rules with an empty tag apply to all tabs; rules with a specific tag apply
        only when tag matches.
        Formats (backward-compatible):
          3-part: "col; hide; order"               (oldest — no tag, no rename)
          4-part: "tag; col; hide; order"           (old — no rename)
          5-part: "tag; col; rename; hide; order"   (current)
        col_formats is updated so renamed columns keep their format (Amount/String).
        """
        if not output_rules:
            return columns, rows, col_formats or {}
        hide_cols  = set()
        order_map  = {}
        rename_map = {}
        for rule in output_rules:
            parts = [p.strip() for p in rule.split(';')]
            if len(parts) == 3:
                rule_tag, col, rename, hide, order = '', parts[0], '', parts[1], parts[2]
            elif len(parts) == 4:
                rule_tag, col, rename, hide, order = parts[0], parts[1], '', parts[2], parts[3]
            elif len(parts) >= 5:
                rule_tag, col, rename, hide, order = parts[0], parts[1], parts[2], parts[3], parts[4]
            else:
                continue
            if not col:
                continue
            # Apply if rule_tag is empty (global) or matches the current tab's tag
            if rule_tag and rule_tag != tag:
                continue
            if hide == 'Yes':
                hide_cols.add(col)
            if order:
                try:
                    order_map[col] = int(order)
                except ValueError:
                    pass
            if rename:
                rename_map[col] = rename
        # Flag if any hidden column is a value/amount column
        if hide_cols:
            fmts = col_formats or {}
            if any(c.endswith('@Value') or fmts.get(c) == 'Amount' for c in hide_cols):
                self._hidden_value_cols = True

        new_columns = [col for col in columns if col not in hide_cols]
        ordered   = sorted([c for c in new_columns if c in order_map], key=lambda c: order_map[c])
        unordered = [c for c in new_columns if c not in order_map]
        final_orig    = ordered + unordered
        final_columns = [rename_map.get(c, c) for c in final_orig]
        new_rows      = [{rename_map.get(col, col): row.get(col, '') for col in final_orig} for row in rows]
        # Remap col_formats so renamed columns retain their format type
        new_formats = {rename_map.get(c, c): fmt for c, fmt in (col_formats or {}).items()}
        return final_columns, new_rows, new_formats

    def deduplicate_amount_values(self, columns, rows, entry_boundaries=None):
        """Clear repeated @Value entries within each entry.

        entry_boundaries: set of row indices that start a new top-level entry.
        last_values is reset at each boundary so amounts from one entry never
        suppress the same amount in the next entry.
        """
        value_cols = {col for col in columns if col.endswith('@Value')}
        if not rows or not value_cols:
            return rows
        last_values = {col: rows[0].get(col, "") for col in value_cols}
        for i in range(1, len(rows)):
            if entry_boundaries and i in entry_boundaries:
                last_values = {col: rows[i].get(col, "") for col in value_cols}
                continue
            for col in value_cols:
                curr = rows[i].get(col, "")
                if curr == last_values[col]:
                    rows[i][col] = ""
                elif curr != "":
                    last_values[col] = curr
        return rows

    def _entry_row_boundaries(self, root):
        """Return the set of row indices where each top-level repeating element
        starts, so deduplicate_amount_values can reset between entries."""
        record_tag, record_parent = self.find_record_info(root)
        if not record_tag or record_parent is None:
            return None
        boundaries = set()
        idx = 0
        for entry_elem in record_parent.findall(record_tag):
            boundaries.add(idx)
            idx += len(self.collect_flat_records(entry_elem))
        return boundaries

    def parse_with_config(self, root, config_tags, merge_rules=None, output_rules=None):
        # config_tags entries are "TagName; SplitTabs" strings
        tag_entries = []
        for entry in config_tags:
            parts = [p.strip() for p in entry.split(';')]
            tag = parts[0]
            split = parts[1] if len(parts) > 1 else "Yes"
            if split not in ("Yes", "No"):
                split = "Yes"
            if tag:
                tag_entries.append((tag, split))

        tabs = []
        for tag, split in tag_entries:
            elements = root.findall(f".//{tag}")
            if not elements:
                continue

            if split == "No" or len(elements) == 1:
                # Combine all instances into one tab, processing each element
                # independently so deduplication never crosses entry boundaries.
                all_columns, all_rows = [], []
                col_formats = {}
                for elem in elements:
                    columns, rows = self.element_to_rows(elem)
                    columns, rows, elem_formats = self.apply_column_merges(columns, rows, merge_rules or [])
                    rows = self.deduplicate_amount_values(columns, rows)
                    if not all_columns:
                        all_columns = columns
                        col_formats = elem_formats
                    all_rows.extend(rows)
                if output_rules:
                    all_columns, all_rows, col_formats = self.apply_output_columns(all_columns, all_rows, output_rules, tag, col_formats)
                tabs.append((tag, all_columns, all_rows, col_formats))
            else:
                for i, elem in enumerate(elements):
                    columns, rows = self.element_to_rows(elem)
                    columns, rows, col_formats = self.apply_column_merges(columns, rows, merge_rules or [])
                    rows = self.deduplicate_amount_values(columns, rows)
                    if output_rules:
                        columns, rows, col_formats = self.apply_output_columns(columns, rows, output_rules, tag, col_formats)
                    tabs.append((f"{tag} {i + 1}", columns, rows, col_formats))

        return tabs

    def get_leaf_nodes(self, elem, path="", leaves=None):
        if leaves is None:
            leaves = []

        current_path = f"{path}/{elem.tag}" if path else elem.tag
        text = elem.text.strip() if elem.text else ""

        if len(elem) == 0 or text or elem.attrib:
            leaves.append({
                'path': current_path,
                'tag': elem.tag,
                'text': text,
                'attributes': dict(elem.attrib)
            })

        for child in elem:
            self.get_leaf_nodes(child, current_path, leaves)

        return leaves

    def parse_and_display_xml(self, file_paths):
        if isinstance(file_paths, str):
            file_paths = (file_paths,)
        self._hidden_value_cols = False   # reset before each parse
        try:
            selected_config = self.config_var.get()
            has_config = selected_config and selected_config != "No configs"
            config_tags = self.settings_manager.get_config(selected_config) if has_config else []
            merge_rules = self.settings_manager.get_merge_columns(selected_config) if has_config else []
            output_rules = self.settings_manager.get_output_columns(selected_config) if has_config else []

            merged = {}        # tab_name -> (columns, rows, col_formats)
            split_counters = {}  # base_name -> running count across files

            for file_path in file_paths:
                tree = ET.parse(file_path)
                root = tree.getroot()
                root = self.strip_namespaces(root)

                if config_tags:
                    tabs = self.parse_with_config(root, config_tags, merge_rules, output_rules)
                else:
                    columns, rows = self.element_to_rows(root)
                    columns, rows, col_formats = self.apply_column_merges(columns, rows, merge_rules)
                    rows = self.deduplicate_amount_values(
                        columns, rows, self._entry_row_boundaries(root))
                    tabs = [("Sheet1", columns, rows, col_formats)] if rows else []

                for tab_name, columns, rows, col_formats in tabs:
                    parts = tab_name.rsplit(" ", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        # Numbered (split) tab — renumber sequentially across files
                        base = parts[0]
                        split_counters[base] = split_counters.get(base, 0) + 1
                        merged[f"{base} {split_counters[base]}"] = (columns, rows, col_formats)
                    else:
                        # Non-split tab — merge rows under the same tab name
                        if tab_name in merged:
                            merged[tab_name] = (merged[tab_name][0],
                                                merged[tab_name][1] + rows,
                                                merged[tab_name][2])
                        else:
                            merged[tab_name] = (columns, rows, col_formats)

            if not merged:
                messagebox.showwarning("Warning", "No data found in selected file(s).")
                return

            self.display_tabs([(name, cols, rows, fmts)
                               for name, (cols, rows, fmts) in merged.items()])
            self.export_button.config(state="normal")
            self.export_excel_button.config(state="normal")

            # Update and show the status chip
            if getattr(self, '_hidden_value_cols', False):
                self.status_border.config(bg="#E67E22")
                self.status_inner.config(bg="#FEF0E7")
                self.status_label.config(text="⚠ Value columns hidden",
                                         fg="#D35400", bg="#FEF0E7")
            else:
                self.status_border.config(bg="#27AE60")
                self.status_inner.config(bg="#EAF7EE")
                self.status_label.config(text="✓ Parsed successfully",
                                         fg="#1E8449", bg="#EAF7EE")
            self.status_border.pack(side=tk.LEFT, padx=(10, 0))

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to parse XML: {str(e)}")
    
    def strip_namespaces(self, elem):
        """Recursively strip namespaces from XML element and its children"""
        # Fix tag
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}')[-1]
        
        # Fix attributes
        attrs = {}
        for key in list(elem.attrib.keys()):
            if '}' in key:
                new_key = key.split('}')[-1]
                attrs[new_key] = elem.attrib[key]
                del elem.attrib[key]
        elem.attrib.update(attrs)
        
        # Recurse
        for child in elem:
            self.strip_namespaces(child)
        
        return elem
    
    def display_tabs(self, tabs):
        """Replace all notebook tabs with freshly built treeviews."""
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)
        self.tab_data = []

        for tab_name, columns, rows, col_formats in tabs:
            frame = tk.Frame(self.notebook)
            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)

            tree = ttk.Treeview(frame, columns=columns, show="headings")
            tree.grid(row=0, column=0, sticky="nsew")

            vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
            vsb.grid(row=0, column=1, sticky="ns")
            hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
            hsb.grid(row=1, column=0, sticky="ew")

            tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

            for col in columns:
                tree.heading(col, text=col)
                max_chars = len(col)
                for row in rows[:100]:
                    val = str(row.get(col, ""))
                    if len(val) > max_chars:
                        max_chars = len(val)
                width = min(max(max_chars * 8, 50), 300)
                tree.column(col, width=width, minwidth=50, stretch=True)

            for row in rows[:1000]:
                tree.insert("", tk.END, values=[row.get(col, "") for col in columns])

            # Single click on a cell → read-only overlay for text selection / copy
            tree.bind("<ButtonRelease-1>", lambda e, t=tree: self._open_cell_overlay(e, t))

            self.notebook.add(frame, text=tab_name)
            self.tab_data.append((tab_name, columns, rows, col_formats))

    def _dismiss_cell_overlay(self):
        """Destroy any active cell overlay."""
        overlay = getattr(self, '_cell_overlay', None)
        if overlay:
            try:
                overlay.destroy()
            except tk.TclError:
                pass
            self._cell_overlay = None

    def _open_cell_overlay(self, event, tree):
        """Place a read-only Entry over the clicked cell so the user can select and copy text."""
        self._dismiss_cell_overlay()

        if tree.identify("region", event.x, event.y) != "cell":
            return
        col_id = tree.identify_column(event.x)
        item   = tree.identify_row(event.y)
        if not item:
            return
        bbox = tree.bbox(item, col_id)
        if not bbox:
            return
        x, y, w, h = bbox

        col_idx = int(col_id[1:]) - 1
        vals    = tree.item(item, "values")
        value   = str(vals[col_idx]) if col_idx < len(vals) else ""

        overlay = tk.Entry(tree, relief="solid", borderwidth=1)
        overlay.insert(0, value)
        overlay.configure(state="readonly")
        overlay.place(x=x, y=y, width=w, height=h)
        overlay.focus_set()
        # Pre-select all so a single Ctrl+C copies everything immediately
        overlay.after(10, lambda: overlay.select_range(0, tk.END))

        overlay.bind("<Escape>",    lambda e: self._dismiss_cell_overlay())
        overlay.bind("<FocusOut>",  lambda e: self._dismiss_cell_overlay())
        overlay.bind("<Return>",    lambda e: self._dismiss_cell_overlay())
        # Ctrl/Cmd+A selects all within the overlay
        overlay.bind("<Control-a>", lambda e: overlay.select_range(0, tk.END))
        overlay.bind("<Command-a>", lambda e: overlay.select_range(0, tk.END))
        self._cell_overlay = overlay

    def default_filename(self, ext, tab_name=""):
        base = datetime.now().strftime(f"%Y-%m-%d %H%M%S")
        name = f"{base} {tab_name}" if tab_name else base
        return f"{name}{ext}"

    def show_export_dialog(self, file_path):
        dialog = tk.Toplevel(self)
        dialog.title("Export complete")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text=f"Saved to:\n{file_path}", justify=tk.LEFT, wraplength=400).pack(padx=20, pady=(15, 10))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(padx=20, pady=(0, 15))

        def open_location():
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", file_path])
            else:
                subprocess.Popen(f'explorer /select,"{file_path}"')
            dialog.destroy()

        def open_file():
            if sys.platform == "darwin":
                subprocess.Popen(["open", file_path])
            else:
                os.startfile(file_path)
            dialog.destroy()

        make_btn(btn_frame, text="Open location",
                 command=open_location,
                 bg="#4A90D9", fg="white", activebackground="#357ABD", activeforeground="white").pack(side=tk.LEFT, padx=5)
        make_btn(btn_frame, text="Open file",
                 command=open_file,
                 bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white").pack(side=tk.LEFT, padx=5)
        make_btn(btn_frame, text="OK",
                 command=dialog.destroy,
                 bg="#7F8C8D", fg="white", activebackground="#616A6B", activeforeground="white").pack(side=tk.LEFT, padx=5)

        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

    def export_csv(self):
        if not self.tab_data:
            messagebox.showwarning("Warning", "No data to export.")
            return

        current_idx = self.notebook.index(self.notebook.select())
        tab_name, columns, rows, col_formats = self.tab_data[current_idx]

        file_path = filedialog.asksaveasfilename(
            title="Export to CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            defaultextension=".csv",
            initialdir=self._initial_dir(),
            initialfile=self.default_filename(".csv", tab_name)
        )

        if not file_path:
            return

        try:
            swedish = self.settings_manager.decimal_separator == "swedish"
            df = pd.DataFrame(rows, columns=columns)
            if swedish:
                def _to_swedish(v):
                    s = str(v).strip().replace(",", ".")
                    try:
                        return f"{float(s):.2f}".replace(".", ",")
                    except (ValueError, TypeError):
                        return str(v)
                for col in df.columns:
                    fmt = col_formats.get(col, "")
                    if fmt == "Amount" or (not fmt and col.endswith('@Value')):
                        df[col] = df[col].fillna("").apply(_to_swedish)
            df.to_csv(file_path, index=False, encoding='utf-8')
            self.show_export_dialog(file_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {str(e)}")

    def export_excel(self):
        if not self.tab_data:
            messagebox.showwarning("Warning", "No data to export.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Export to Excel",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            defaultextension=".xlsx",
            initialdir=self._initial_dir(),
            initialfile=self.default_filename(".xlsx")
        )

        if not file_path:
            return

        try:
            swedish = self.settings_manager.decimal_separator == "swedish"
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                for tab_name, columns, rows, col_formats in self.tab_data:
                    df = pd.DataFrame(rows, columns=columns)
                    for col in df.columns:
                        fmt = col_formats.get(col, "")
                        if fmt == "Amount" or (not fmt and col.endswith('@Value')):
                            if swedish:
                                def _to_swedish(v):
                                    s = str(v).strip().replace(",", ".")
                                    try:
                                        return f"{float(s):.2f}".replace(".", ",")
                                    except (ValueError, TypeError):
                                        return str(v)   # preserve non-numeric as-is
                                df[col] = df[col].fillna("").apply(_to_swedish)
                            else:
                                # Convert parseable values to float; keep others as-is
                                def _safe_numeric(v):
                                    s = str(v).strip()
                                    if not s:
                                        return v
                                    try:
                                        return float(s.replace(",", "."))
                                    except (ValueError, TypeError):
                                        return v
                                df[col] = df[col].fillna("").apply(_safe_numeric)
                        elif fmt == "String":
                            df[col] = df[col].fillna("").astype(str)
                    df.to_excel(writer, sheet_name=tab_name[:31], index=False)
            self.show_export_dialog(file_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export Excel: {str(e)}")


if __name__ == "__main__":
    try:
        app = XMLParserApp()
        app.mainloop()
    except Exception as e:
        import traceback
        import os
        from datetime import datetime
        
        # Log error to file
        error_log = os.path.join(os.getcwd(), f"xmlparser_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        with open(error_log, 'w') as f:
            f.write(f"XMLParser Error Log - {datetime.now()}\n")
            f.write("=" * 50 + "\n")
            f.write(f"Error: {e}\n\n")
            f.write("Traceback:\n")
            traceback.print_exc(file=f)
        
        # Show error in message box if possible
        try:
            from tkinter import messagebox
            messagebox.showerror("XMLParser Error", 
                f"An error occurred and has been logged to:\n{error_log}\n\nError: {str(e)}")
        except:
            pass
