import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
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

DEFAULT_VALUE_TAGS = [
    "RmtdAmt; Positive; Amount; NtryDtls",
    "CdtNoteAmt; Negative; Amount; NtryDtls",
    "Sum; Positive; Total; TxsSummry",
]

def _get_version():
    """Return version string."""
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

_VERSION = _get_version()

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
        import tempfile
        if getattr(sys, 'frozen', False):
            if sys.platform == "win32":
                app_data_dir = os.path.join(os.environ['APPDATA'], 'XMLParser')
            else:
                app_data_dir = os.path.join(os.path.expanduser('~'), '.XMLParser')
            os.makedirs(app_data_dir, exist_ok=True)
            self.settings_file = os.path.join(app_data_dir, settings_file)
        else:
            self.settings_file = settings_file
        self.config = configparser.ConfigParser()
        self.configs = {}
        self.merge_columns = {}
        self.output_columns = {}
        self.only_order_columns = {}
        self.last_directory = ""
        self.last_selected_config = ""
        self.decimal_separator = "english"
        self.window_x = 100
        self.window_y = 100
        self.window_width = 1000
        self.window_height = 800
        self.load()

    def _is_old_format(self, entries):
        """Return True if all non-empty entries use the old 'Tag; Yes/No' format."""
        if not entries:
            return False
        for e in entries:
            parts = [p.strip() for p in e.split(';')]
            if len(parts) >= 2 and parts[1] not in ("Yes", "No", "Positive", "Negative"):
                return False
            if len(parts) >= 2 and parts[1] in ("Positive", "Negative"):
                return False
        return True

    def load(self):
        if os.path.exists(self.settings_file):
            self.config.read(self.settings_file)

            if "Window" in self.config:
                window = self.config["Window"]
                self.window_x = window.getint("x", 100)
                self.window_y = window.getint("y", 100)
                self.window_width = window.getint("width", 1000)
                self.window_height = window.getint("height", 800)

            if "General" in self.config:
                self.last_directory = self.config["General"].get("last_directory", "")
                self.last_selected_config = self.config["General"].get("last_selected_config", "")
                self.decimal_separator = self.config["General"].get("decimal_separator", "english")

            self.configs = {}
            self.merge_columns = {}
            self.output_columns = {}
            for section in self.config.sections():
                if section.startswith("Config:"):
                    config_name = section[7:]
                    values = self.config[section].get("values", "")
                    entries = [v for v in values.split("\n") if v] if values else []
                    # Auto-migrate CAMT profile if it has old-format entries
                    if config_name == "CAMT" and self._is_old_format(entries):
                        entries = list(DEFAULT_VALUE_TAGS)
                    self.configs[config_name] = entries
                    merge = self.config[section].get("merge", "")
                    self.merge_columns[config_name] = [v for v in merge.split("\n") if v] if merge else []
                    output = self.config[section].get("output", "")
                    self.output_columns[config_name] = [v for v in output.split("\n") if v] if output else []
                    self.only_order_columns[config_name] = self.config[section].getboolean("only_order_columns", False)
        else:
            self.configs["CAMT"] = list(DEFAULT_VALUE_TAGS)
            self.merge_columns["CAMT"] = []
            self.output_columns["CAMT"] = []
            self.only_order_columns["CAMT"] = False
            self.save()

    def save(self):
        self.config = configparser.ConfigParser()

        self.config["Window"] = {
            "x": str(self.window_x),
            "y": str(self.window_y),
            "width": str(self.window_width),
            "height": str(self.window_height)
        }

        self.config["General"] = {
            "last_directory": self.last_directory,
            "last_selected_config": self.last_selected_config,
            "decimal_separator": self.decimal_separator
        }

        for config_name, values in self.configs.items():
            self.config[f"Config:{config_name}"] = {
                "values": "\n".join(values),
                "merge": "\n".join(self.merge_columns.get(config_name, [])),
                "output": "\n".join(self.output_columns.get(config_name, [])),
                "only_order_columns": str(self.only_order_columns.get(config_name, False))
            }

        with open(self.settings_file, "w") as f:
            self.config.write(f)

    def export_profile(self, name, path):
        """Write a single [Config:name] section to an ini file."""
        cfg = configparser.ConfigParser()
        cfg[f"Config:{name}"] = {
            "values":              "\n".join(self.configs.get(name, [])),
            "merge":               "\n".join(self.merge_columns.get(name, [])),
            "output":              "\n".join(self.output_columns.get(name, [])),
            "only_order_columns":  str(self.only_order_columns.get(name, False)),
        }
        with open(path, "w", encoding="utf-8") as f:
            cfg.write(f)

    def import_profile(self, name, path):
        """Read a profile ini file and store it under the given name."""
        cfg = configparser.ConfigParser()
        cfg.read(path, encoding="utf-8")
        section = None
        for sec in cfg.sections():
            if sec.startswith("Config:"):
                section = sec
                break
        if section is None:
            raise ValueError("No [Config:…] section found in file.")
        values_raw = cfg[section].get("values", "")
        self.configs[name]             = [v for v in values_raw.split("\n") if v]
        merge_raw  = cfg[section].get("merge", "")
        self.merge_columns[name]       = [v for v in merge_raw.split("\n") if v]
        output_raw = cfg[section].get("output", "")
        self.output_columns[name]      = [v for v in output_raw.split("\n") if v]
        self.only_order_columns[name]  = cfg[section].getboolean("only_order_columns", False)
        self.save()

    def add_config(self, name, values=None):
        self.configs[name] = values if values else list(DEFAULT_VALUE_TAGS)
        self.merge_columns[name] = []
        self.output_columns[name] = []
        self.save()

    def delete_config(self, name):
        if name in self.configs:
            del self.configs[name]
            self.merge_columns.pop(name, None)
            self.output_columns.pop(name, None)
            self.only_order_columns.pop(name, None)
            self.save()

    def rename_config(self, old_name, new_name):
        if old_name not in self.configs:
            return
        self.configs[new_name]            = self.configs.pop(old_name)
        self.merge_columns[new_name]      = self.merge_columns.pop(old_name, [])
        self.output_columns[new_name]     = self.output_columns.pop(old_name, [])
        self.only_order_columns[new_name] = self.only_order_columns.pop(old_name, False)
        if self.last_selected_config == old_name:
            self.last_selected_config = new_name
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

    def get_only_order_columns(self, name):
        return self.only_order_columns.get(name, False)

    def update_only_order_columns(self, name, value):
        if name in self.configs:
            self.only_order_columns[name] = value
            self.save()

    def reset_config(self, name):
        if name in self.configs:
            self.configs[name] = list(DEFAULT_VALUE_TAGS)
            self.merge_columns[name] = []
            self.output_columns[name] = []
            self.save()

    def get_config_names(self):
        return list(self.configs.keys())

    def get_config(self, name):
        return self.configs.get(name, [])

    def get_merge_columns(self, name):
        return self.merge_columns.get(name, [])

    def validate_window_position(self, screen_width, screen_height):
        # Allow positions outside the primary screen by up to one full screen
        # dimension in any direction — this lets windows on secondary monitors
        # survive across sessions. Only reset if the title bar is completely
        # unreachable (i.e. more than one screen away from the primary).
        min_x = -screen_width
        min_y = -screen_height
        max_x = screen_width * 2
        max_y = screen_height * 2
        title_bar_visible = (
            self.window_x + self.window_width  > min_x and
            self.window_y + 30                 > min_y and
            self.window_x                      < max_x and
            self.window_y                      < max_y
        )
        if not title_bar_visible:
            self.window_x = 100
            self.window_y = 100
            self.window_width = 1000
            self.window_height = 800
            self.save()


class ConfigsDialog(tk.Toplevel):
    def __init__(self, parent, settings_manager, initial_config=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.initial_config = initial_config
        self.title("Configs")
        self.geometry("680x740")
        self.minsize(500, 500)
        self.transient(parent)
        self.grab_set()

        self.pending_tags         = {}   # {config_name: [tag_entry_strings]}
        self.pending_output       = {}   # {config_name: [output_row_strings]}
        self.pending_only_order   = {}   # {config_name: bool}

        self.create_widgets()
        self.refresh_config_list()

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
        self.reset_button = make_btn(buttons_frame, text="Reset config",
                                     command=self.reset_config,
                                     bg="#E67E22", fg="white",
                                     activebackground="#CA6F1E", activeforeground="white")
        self.reset_button.pack(side=tk.LEFT, padx=5)
        make_btn(buttons_frame, text="Import",
                 command=self.import_profile,
                 bg="#7F8C8D", fg="white",
                 activebackground="#616A6B", activeforeground="white").pack(side=tk.LEFT, padx=5)
        make_btn(buttons_frame, text="Export",
                 command=self.export_profile,
                 bg="#7F8C8D", fg="white",
                 activebackground="#616A6B", activeforeground="white").pack(side=tk.LEFT, padx=5)
        make_btn(buttons_frame, text="Rename",
                 command=self.rename_profile,
                 bg="#7F8C8D", fg="white",
                 activebackground="#616A6B", activeforeground="white").pack(side=tk.LEFT, padx=5)

        # ── Value-tags to extract table ────────────────────────────────────────
        tags_outer = tk.Frame(content)
        tags_outer.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(tags_outer, text="Value-tags to extract:").pack(anchor=tk.W)

        tags_table_frame = tk.Frame(tags_outer)
        tags_table_frame.pack(fill=tk.X)
        self.tags_tree = ttk.Treeview(tags_table_frame,
                                      columns=("path", "sign", "rename", "highest"),
                                      show="headings", height=6)
        self.tags_tree.heading("path",    text="Path")
        self.tags_tree.heading("sign",    text="Sign")
        self.tags_tree.heading("rename",  text="Rename")
        self.tags_tree.heading("highest", text="Highest level")
        self.tags_tree.column("path",    width=190, minwidth=80,  stretch=True)
        self.tags_tree.column("sign",    width=85,  minwidth=70,  stretch=False)
        self.tags_tree.column("rename",  width=100, minwidth=60,  stretch=False)
        self.tags_tree.column("highest", width=95,  minwidth=60,  stretch=False)
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

        # ── Output section ─────────────────────────────────────────────────────
        output_outer = tk.Frame(content)
        output_outer.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(output_outer, text="Output:").pack(anchor=tk.W)

        self.only_order_var = tk.BooleanVar(value=False)
        tk.Checkbutton(output_outer, text="Only display columns with Order",
                       variable=self.only_order_var).pack(anchor=tk.W, pady=(0, 4))

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
        tags = self._read_ui()
        output = self._read_output_ui()
        self.pending_tags[self.current_config]       = tags
        self.pending_output[self.current_config]     = output
        self.pending_only_order[self.current_config] = self.only_order_var.get()

    def _read_ui(self):
        tags = []
        for item in self.tags_tree.get_children():
            vals    = self.tags_tree.item(item, "values")
            path    = vals[0].strip() if len(vals) > 0 else ""
            sign    = vals[1].strip() if len(vals) > 1 else "Positive"
            rename  = vals[2].strip() if len(vals) > 2 else ""
            highest = vals[3].strip() if len(vals) > 3 else ""
            if path:
                tags.append(f"{path}; {sign}; {rename}; {highest}")
        return tags

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
            if hide == "Yes" or order or rename:
                rows.append(f"{tag}; {col}; {rename}; {hide}; {order}")
        return rows

    def _get_current_columns(self):
        """Return list of (base_tag, column) pairs from the parent app's displayed tabs."""
        tab_data = getattr(self.master, "tab_data", [])
        seen = []
        for tab_name, columns, _, _ in tab_data:
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
            parts   = [p.strip() for p in entry.split(';')]
            path    = parts[0] if len(parts) > 0 else ""
            sign    = parts[1] if len(parts) > 1 else "Positive"
            rename  = parts[2] if len(parts) > 2 else ""
            highest = parts[3] if len(parts) > 3 else ""
            # Migrate old Yes/No format
            if sign in ("Yes", "No"):
                sign = "Positive"
                rename = ""
                highest = ""
            if sign not in ("Positive", "Negative"):
                sign = "Positive"
            self.tags_tree.insert("", tk.END, values=(path, sign, rename, highest))

        # ── output ──
        # Migrate any old Hide rules from legacy merge_columns to output
        merge_rules = self.settings_manager.get_merge_columns(config_name)
        migrated_hides = {}
        for rule in merge_rules:
            parts = [p.strip() for p in rule.split(';')]
            action = parts[0] if parts else ""
            source = parts[1] if len(parts) > 1 else ""
            if action == "Hide" and source:
                migrated_hides[source] = True

        saved = self.pending_output.get(config_name,
                self.settings_manager.get_output_columns(config_name))
        saved_map = {}
        for row in saved:
            parts = [p.strip() for p in row.split(';')]
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

        for col in migrated_hides:
            key = ('', col)
            if key not in saved_map:
                saved_map[key] = ('', 'Yes', '')

        current_pairs = self._get_current_columns()
        all_pairs = list(current_pairs)
        for key in saved_map:
            if key not in all_pairs:
                all_pairs.append(key)
        all_pairs.sort(key=lambda p: (p[0], p[1]))

        for item in self.output_tree.get_children():
            self.output_tree.delete(item)
        for tag_s, col in all_pairs:
            rename_val, hide_val, order_val = saved_map.get((tag_s, col), ('', 'No', ''))
            self.output_tree.insert("", tk.END, values=(tag_s, col, rename_val, hide_val, order_val))

        only_order = self.pending_only_order.get(
            config_name,
            self.settings_manager.get_only_order_columns(config_name)
        )
        self.only_order_var.set(only_order)

    # ── profile import / export / rename ─────────────────────────────────────

    def _selected_config_name(self):
        sel = self.config_listbox.curselection()
        if not sel:
            return None
        return self.config_listbox.get(sel[0])

    def import_profile(self):
        self.master.import_profile()
        self.refresh_config_list()

    def export_profile(self):
        name = self._selected_config_name()
        if not name:
            messagebox.showwarning("Export Profile", "Select a config first.", parent=self)
            return
        self.master.config_var.set(name)
        self.master.export_profile()

    def rename_profile(self):
        name = self._selected_config_name()
        if not name:
            messagebox.showwarning("Rename Profile", "Select a config first.", parent=self)
            return
        self._buffer_current_edits()
        self.master.config_var.set(name)
        self.master.rename_profile()
        self.refresh_config_list()

    # ── save / close ─────────────────────────────────────────────────────────

    def close_and_save(self):
        if self.current_config:
            self._buffer_current_edits()
        for config_name, tags in self.pending_tags.items():
            self.settings_manager.update_config(config_name, tags)
            # Clear legacy merge data so it doesn't resurface
            self.settings_manager.update_merge_columns(config_name, [])
        for config_name, output in self.pending_output.items():
            self.settings_manager.update_output_columns(config_name, output)
        for config_name, only_order in self.pending_only_order.items():
            self.settings_manager.update_only_order_columns(config_name, only_order)
        self.destroy()

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
        col_names = ("path", "sign", "rename", "highest")
        col_name  = col_names[col_idx]
        bbox = self.tags_tree.bbox(item, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        current = self.tags_tree.set(item, col_name)
        if col_name == "sign":
            editor = ttk.Combobox(self.tags_tree, values=["Positive", "Negative"], state="readonly")
            editor.set(current if current in ("Positive", "Negative") else "Positive")
            editor.place(x=x, y=y, width=w, height=h)
            editor.focus()
            def commit_combo(event=None, _editor=editor, _item=item, _col=col_name):
                self.tags_tree.set(_item, _col, _editor.get())
                _editor.destroy()
            editor.bind("<<ComboboxSelected>>", commit_combo)
            editor.bind("<FocusOut>", lambda e, _editor=editor: _editor.destroy())
        else:
            editor = tk.Entry(self.tags_tree)
            editor.insert(0, current)
            editor.select_range(0, tk.END)
            editor.place(x=x, y=y, width=w, height=h)
            editor.focus()
            def commit_entry(event=None, _editor=editor, _item=item, _col=col_name):
                self.tags_tree.set(_item, _col, _editor.get())
                _editor.destroy()
            def cancel_entry(event=None, _editor=editor):
                _editor.destroy()
            editor.bind("<Return>",   commit_entry)
            editor.bind("<FocusOut>", commit_entry)
            editor.bind("<Escape>",   cancel_entry)

    def add_tags_row(self):
        item = self.tags_tree.insert("", tk.END, values=("", "Positive", "", "", ""))
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
            return
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
                val = ""
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

    # ── config add / delete / reset ───────────────────────────────────────────

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
            for tree in (self.tags_tree, self.output_tree):
                for item in tree.get_children():
                    tree.delete(item)
            self.pending_tags.pop(name, None)
            self.pending_output.pop(name, None)
            self.current_config = None
            self.settings_manager.delete_config(name)
            self.refresh_config_list()

    def reset_config(self):
        if not self.current_config:
            messagebox.showwarning("Warning", "Please select a config to reset.")
            return
        if messagebox.askyesno("Confirm",
                f"Reset '{self.current_config}' to default tags?\n\n"
                "This will replace all value-tag entries with the defaults."):
            self.settings_manager.reset_config(self.current_config)
            self.pending_tags.pop(self.current_config, None)
            self.pending_output.pop(self.current_config, None)
            self._load_config(self.current_config)

    # ── info dialog ───────────────────────────────────────────────────────────

    def update_parent_dropdown(self):
        self.master.update_config_dropdown()


class ProgressDialog(tk.Toplevel):
    """Modal-ish progress popup shown while parsing."""
    def __init__(self, parent, n_files):
        super().__init__(parent)
        self.title("Parsing…")
        self.resizable(False, False)
        self.transient(parent)
        # No grab_set — causes hangs on macOS when used with threads

        self._lbl = tk.Label(self, text=f"Parsing {n_files} file(s)…",
                             padx=24, pady=12, font=("TkDefaultFont", 10))
        self._lbl.pack()

        self._bar = ttk.Progressbar(self, mode='determinate', length=240, maximum=100)
        self._bar.pack(padx=24, pady=(0, 18))

        # Centre on parent
        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

        if sys.platform == "darwin":
            self.lift()
            self.attributes("-topmost", True)
        self.update()

    def set_message(self, msg):
        """Update label text — must be called from the main thread."""
        self._lbl.config(text=msg)

    def set_progress(self, pct):
        """Set bar fill 0–100 — must be called from the main thread."""
        self._bar['value'] = pct

    def close(self):
        self.destroy()


class XMLParserApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.settings_manager = SettingsManager()
        self.update_idletasks()
        self.settings_manager.validate_window_position(
            self.winfo_screenwidth(), self.winfo_screenheight()
        )

        self.title("XML Parser")
        self.geometry(f"{self.settings_manager.window_width}x{self.settings_manager.window_height}+{self.settings_manager.window_x}+{self.settings_manager.window_y}")

        self.decimal_var = tk.StringVar(value=self.settings_manager.decimal_separator)
        self.tab_data = []
        self.create_menu()
        self.create_widgets()
        self.update_config_dropdown()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._initialized = False
        self.after_idle(lambda: setattr(self, '_initialized', True))
        self.bind("<Configure>", self.on_resize)

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
        dlg.geometry("660x680")

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
            "VALUE-TAGS TO EXTRACT\n"
            "─────────────────────\n"
            "Each row specifies one XML amount field to extract.\n"
            "The parser finds every occurrence of that field in the\n"
            "document and produces one output row per occurrence.\n"
            "\n"
            "  Path          — XML path to the amount element.\n"
            "                  Simple tag:    RmtdAmt\n"
            "                  Nested path:   Strd/RfrdDocAmt/RmtdAmt\n"
            "\n"
            "  Sign          — Positive: value kept as-is.\n"
            "                  Negative: value multiplied by -1.\n"
            "\n"
            "  Rename        — Display name for the amount column and the\n"
            "                  output tab. Entries that share the same Rename\n"
            "                  are merged onto the same tab.\n"
            "                  Leave blank to use the Path as the name.\n"
            "\n"
            "  Highest level — Ancestor tag at which the upward walk stops.\n"
            "                  Context from tags above this level is ignored.\n"
            "                  Leave blank to walk all the way to the root.\n"
            "\n"
            "\n"
            "HOW PARSING WORKS\n"
            "─────────────────\n"
            "For each occurrence of a configured Path:\n"
            "\n"
            "  1. The parser starts at the matched element (the amount).\n"
            "\n"
            "  2. It walks UP through parent elements, stopping at the\n"
            "     Highest level tag (or root if not set).\n"
            "\n"
            "  3. At each level, sibling elements that are not in the\n"
            "     ancestor chain are collected as context columns.\n"
            "     Siblings are descended recursively to gather leaf values.\n"
            "\n"
            "  4. Column order follows XML document order:\n"
            "     — Siblings appearing before the ancestor chain in the XML\n"
            "       become columns to the LEFT of the amount column.\n"
            "     — Siblings appearing after become columns to the RIGHT.\n"
            "     — Context from outer levels appears before inner levels.\n"
            "\n"
            "  5. If two context siblings share the same column name, their\n"
            "     values are space-joined (trimmed) into one column.\n"
            "\n"
            "  6. The amount column itself is split into two columns:\n"
            "       <Rename>        — numeric value\n"
            "       <Rename>@Ccy    — currency code (if present)\n"
            "\n"
            "  7. Entries with the same Rename are merged onto one tab.\n"
            "     Sign (Positive/Negative) is applied before merging.\n"
            "\n"
            "\n"
            "CONTROL SUMS\n"
            "────────────\n"
            "After parsing, a 'Control sums: OK / MISMATCH' button appears\n"
            "in the toolbar. Click it to open the control sums popup.\n"
            "\n"
            "  In XML   — Signed sum of that amount field taken directly\n"
            "             from the XML, with Positive/Negative applied.\n"
            "             This is the ground truth from the source file.\n"
            "\n"
            "  Parsed   — Signed sum of the parsed output rows.\n"
            "             When two entries share a tab the net signed total\n"
            "             is shown (e.g. debits + credits).\n"
            "\n"
            "  OK / MISMATCH — In XML total is compared to Parsed total.\n"
            "             A MISMATCH means values were lost or duplicated\n"
            "             during parsing.\n"
            "\n"
            "\n"
            "OUTPUT\n"
            "──────\n"
            "Fine-tunes which context columns appear, what they are called,\n"
            "and in what order. Double-click a cell to edit.\n"
            "\n"
            "  Tag         — Limit this rule to a specific tab name.\n"
            "                Leave blank to apply to all tabs.\n"
            "  Column Name — The column name as it comes out of parsing.\n"
            "  Rename to   — Optional. Replaces the column header.\n"
            "                Two columns renamed to the same name are merged:\n"
            "                their values are space-joined (trimmed).\n"
            "  Hide        — Single-click to toggle Yes/No.\n"
            "                Yes removes the column from the output.\n"
            "  Order       — Integer. Context columns with an Order number\n"
            "                come first, sorted ascending. Ties keep their\n"
            "                natural parse order. Amount columns are not\n"
            "                affected by Order — they always reflect the\n"
            "                XML document position.\n"
            "\n"
            "  Only display columns with order\n"
            "              — Checkbox above the table. When checked, any\n"
            "                column without an Order value is treated as\n"
            "                hidden. Only columns that have an Order number\n"
            "                appear in the output. The setting is saved per\n"
            "                profile.\n"
            "\n"
            "Only rows where Hide = Yes, Order, or Rename to are set\n"
            "are saved. All other columns reappear automatically on\n"
            "the next parse.\n"
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

        self.update_idletasks()
        dlg.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dlg.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")

    def on_decimal_change(self):
        self.settings_manager.decimal_separator = self.decimal_var.get()
        self.settings_manager.save()

    def open_program_folder(self):
        if getattr(sys, 'frozen', False):
            if sys.platform == "win32":
                folder = os.path.join(os.environ['APPDATA'], 'XMLParser')
            else:
                folder = os.path.join(os.path.expanduser('~'), '.XMLParser')
        else:
            folder = os.getcwd()

        if sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", folder])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", folder])
        else:
            import webbrowser
            webbrowser.open(f"file://{folder}")

    def create_widgets(self):
        self.upper_frame = tk.Frame(self)
        self.upper_frame.pack(fill=tk.X)

        self.lower_frame = tk.Frame(self)
        self.lower_frame.pack(fill=tk.BOTH, expand=True)

        button_frame = tk.Frame(self.upper_frame)
        button_frame.pack(pady=5, padx=10, anchor=tk.W)

        self.open_button = make_btn(button_frame, text="Open", command=self.open_file,
                                    bg="#4A90D9", fg="white", activebackground="#357ABD", activeforeground="white")
        self.open_button.pack(side=tk.LEFT, padx=10)

        self.config_var = tk.StringVar(self)
        self.config_dropdown = ttk.Combobox(button_frame, textvariable=self.config_var, state="readonly", width=30)
        self.config_dropdown.pack(side=tk.LEFT, padx=10)
        self.config_dropdown.bind("<<ComboboxSelected>>", self.on_config_selected)

        self.export_button = make_btn(button_frame, text="Export CSV", command=self.export_csv, state="disabled",
                                      bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white",
                                      disabledforeground="black")
        self.export_button.pack(side=tk.LEFT, padx=10)

        self.export_excel_button = make_btn(button_frame, text="Export Excel", command=self.export_excel, state="disabled",
                                            bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white",
                                            disabledforeground="black")
        self.export_excel_button.pack(side=tk.LEFT, padx=10)

        self._status_info = None  # message to show in popup
        self.status_border = tk.Frame(button_frame, bd=0)
        self.status_inner  = tk.Frame(self.status_border, bd=0)
        self.status_label  = tk.Label(self.status_inner, padx=10, pady=3,
                                      font=("TkDefaultFont", 9, "bold"),
                                      cursor="hand2")
        self.status_label.pack()
        self.status_inner.pack(padx=1, pady=1)
        self.status_label.bind("<Button-1>", lambda e: self._show_status_popup())

        self._ctrl_sum_data = None  # (parsed_sums, signed_raw_sums, mismatch)
        self.ctrl_sum_border = tk.Frame(button_frame, bd=0)
        self.ctrl_sum_inner  = tk.Frame(self.ctrl_sum_border, bd=0)
        self.ctrl_sum_btn    = tk.Label(self.ctrl_sum_inner, padx=10, pady=3,
                                        font=("TkDefaultFont", 9, "bold"),
                                        cursor="hand2")
        self.ctrl_sum_btn.pack()
        self.ctrl_sum_inner.pack(padx=1, pady=1)
        self.ctrl_sum_btn.bind("<Button-1>", lambda e: self._show_ctrl_sum_popup())

        # Notebook — LEFT, fills remaining space
        self.notebook = ttk.Notebook(self.lower_frame)
        self.notebook.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tab_data = []

    def _initial_dir(self):
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

    def export_profile(self):
        selected = self.config_var.get()
        if not selected or selected == "No configs":
            messagebox.showwarning("Export Profile", "No profile selected.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export Profile",
            initialdir=self.settings_manager.last_directory or os.path.expanduser("~"),
            initialfile=f"{selected}.ini",
            defaultextension=".ini",
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.settings_manager.export_profile(selected, path)
        except Exception as e:
            messagebox.showerror("Export Profile", f"Failed to export: {e}", parent=self)

    def import_profile(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Import Profile",
            initialdir=self.settings_manager.last_directory or os.path.expanduser("~"),
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
        )
        if not path:
            return

        self._do_import_profile(path)

    def _do_import_profile(self, path, prefill_name=""):
        name = simpledialog.askstring(
            "Import Profile",
            "Enter a name for this profile:",
            initialvalue=prefill_name,
            parent=self,
        )
        if not name:
            return
        name = name.strip()
        if not name:
            return

        if name in self.settings_manager.configs:
            choice = messagebox.askquestion(
                "Profile Exists",
                f'A profile named "{name}" already exists.\n\nOverwrite it?',
                icon="warning",
                type=messagebox.YESNOCANCEL,
                parent=self,
            )
            if choice == "cancel":
                return
            if choice == "no":
                self._do_import_profile(path, prefill_name=name)
                return

        try:
            self.settings_manager.import_profile(name, path)
        except Exception as e:
            messagebox.showerror("Import Profile", f"Failed to import: {e}", parent=self)
            return

        self.update_config_dropdown()
        self.config_var.set(name)
        messagebox.showinfo("Import Profile", f'Profile "{name}" imported successfully.', parent=self)

    def rename_profile(self):
        selected = self.config_var.get()
        if not selected or selected == "No configs":
            messagebox.showwarning("Rename Profile", "No profile selected.", parent=self)
            return
        self._do_rename_profile(selected)

    def _do_rename_profile(self, old_name, prefill_name=None):
        new_name = simpledialog.askstring(
            "Rename Profile",
            f'Rename "{old_name}" to:',
            initialvalue=prefill_name if prefill_name is not None else old_name,
            parent=self,
        )
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            return

        if new_name in self.settings_manager.configs:
            choice = messagebox.askquestion(
                "Profile Exists",
                f'A profile named "{new_name}" already exists.\n\nOverwrite it?',
                icon="warning",
                type=messagebox.YESNOCANCEL,
                parent=self,
            )
            if choice == "cancel":
                return
            if choice == "no":
                self._do_rename_profile(old_name, prefill_name=new_name)
                return
            self.settings_manager.delete_config(new_name)

        self.settings_manager.rename_config(old_name, new_name)
        self.update_config_dropdown()
        self.config_var.set(new_name)

    def on_resize(self, event):
        if event.widget == self and self._initialized:
            self.settings_manager.window_x      = self.winfo_x()
            self.settings_manager.window_y      = self.winfo_y()
            self.settings_manager.window_width  = self.winfo_width()
            self.settings_manager.window_height = self.winfo_height()

    def on_close(self):
        self.settings_manager.window_x      = self.winfo_x()
        self.settings_manager.window_y      = self.winfo_y()
        self.settings_manager.window_width  = self.winfo_width()
        self.settings_manager.window_height = self.winfo_height()
        self.settings_manager.save()
        self.destroy()

    # ── XML helpers ───────────────────────────────────────────────────────────

    def strip_namespaces(self, elem):
        """Recursively strip namespaces from XML element and its children."""
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}')[-1]
        attrs = {}
        for key in list(elem.attrib.keys()):
            if '}' in key:
                new_key = key.split('}')[-1]
                attrs[new_key] = elem.attrib[key]
                del elem.attrib[key]
        elem.attrib.update(attrs)
        for child in elem:
            self.strip_namespaces(child)
        return elem

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

    # ── new value-driven parser ───────────────────────────────────────────────

    def _collect_sibling_leaves(self, elem, rel_path, row):
        """Recursively collect leaf data from elem into row using rel_path as key."""
        if len(elem) == 0:
            text = elem.text.strip() if elem.text else ""
            ccy = elem.attrib.get('Ccy', '')
            if ccy and text:
                text = f"{text} {ccy}"
            elif ccy:
                text = ccy
            if text:
                row[rel_path] = (row[rel_path] + " " + text) if row.get(rel_path) else text
        else:
            for child in elem:
                self._collect_sibling_leaves(child, rel_path + "/" + child.tag, row)

    def collect_value_rows(self, root, value_path_str, rename, parent_map,
                           highest_level="", on_progress=None):
        """Find all occurrences of value_path_str and build one row per occurrence.

        Each row contains the amount value plus all sibling context collected
        by walking up the ancestor chain.
        Returns (columns, rows, col_formats).
        """
        col_name = rename if rename else value_path_str

        found = [e for e in root.findall('.//' + value_path_str)
                 if e.text and e.text.strip()]
        if not found:
            return [], [], {}

        total = len(found)
        rows = []
        all_keys = set()
        # Track column key order respecting XML document order:
        # siblings that precede the ancestor chain go before Amount;
        # siblings that follow go after Amount.
        before_key_order = {}  # key -> None (insertion-ordered set)
        after_key_order  = {}

        for idx, val_elem in enumerate(found):
            if on_progress:
                on_progress(idx + 1, total)
            row = {
                col_name: val_elem.text.strip(),
                col_name + "@Ccy": val_elem.attrib.get('Ccy', ''),
            }

            before_levels = []  # one dict per walk step, innermost first
            after_levels  = []

            current = val_elem
            while current in parent_map:
                parent = parent_map[current]
                before_this = {}
                after_this  = {}
                passed = False
                for child in parent:
                    if child is current:
                        passed = True
                    elif not passed:
                        self._collect_sibling_leaves(child, child.tag, before_this)
                    else:
                        self._collect_sibling_leaves(child, child.tag, after_this)
                before_levels.append(before_this)
                after_levels.append(after_this)
                row.update(before_this)
                row.update(after_this)
                if highest_level and parent.tag == highest_level:
                    break
                current = parent

            rows.append(row)
            all_keys.update(row.keys())

            # Outermost before-siblings first, innermost last (just before Amount)
            for d in reversed(before_levels):
                for k in d:
                    if k not in before_key_order and k not in after_key_order:
                        before_key_order[k] = None
            # Innermost after-siblings first, outermost last (just after Amount)
            for d in after_levels:
                for k in d:
                    if k not in before_key_order and k not in after_key_order:
                        after_key_order[k] = None

        columns = (list(before_key_order.keys()) +
                   [col_name, col_name + "@Ccy"] +
                   list(after_key_order.keys()))
        covered = set(columns)
        for k in sorted(all_keys):
            if k not in covered:
                columns.append(k)

        col_formats = {col_name: "Amount"}
        return columns, rows, col_formats

    def parse_with_value_tags(self, root, value_tag_entries, output_rules=None, progress_cb=None, only_order=False):
        """Parse XML using value-tag entries of the form 'path; sign; rename'.

        Returns list of (tab_name, columns, rows, col_formats).
        progress_cb(path, done, total) is called during each collect_value_rows call.
        """
        entries = []
        for entry in value_tag_entries:
            parts   = [p.strip() for p in entry.split(';')]
            path    = parts[0] if len(parts) > 0 else ""
            sign    = parts[1] if len(parts) > 1 else "Positive"
            rename  = parts[2] if len(parts) > 2 else ""
            highest = parts[3] if len(parts) > 3 else ""
            # Migrate old format
            if sign in ("Yes", "No"):
                sign = "Positive"
                rename = ""
                highest = ""
            if sign not in ("Positive", "Negative"):
                sign = "Positive"
            tab = rename if rename else path
            if path:
                entries.append({'path': path, 'sign': sign, 'rename': rename,
                                'tab': tab, 'highest': highest})

        if not entries:
            return []

        parent_map = {child: parent for parent in root.iter() for child in parent}

        # Group by tab name (preserving insertion order)
        groups = {}
        for e in entries:
            groups.setdefault(e['tab'], []).append(e)

        tabs = []
        for tab_name, group_entries in groups.items():
            all_columns = []
            all_rows = []
            seen_cols = set()
            col_formats = {}

            for e in group_entries:
                _path = e['path']
                def _make_prog(_p=_path):
                    def _cb(done, total):
                        if progress_cb:
                            progress_cb(_p, done, total)
                    return _cb
                cols, rows, fmts = self.collect_value_rows(
                    root, e['path'], e['rename'] if e['rename'] else e['path'], parent_map,
                    highest_level=e.get('highest', ''),
                    on_progress=_make_prog() if progress_cb else None)
                if not rows:
                    continue

                col_name = e['rename'] if e['rename'] else e['path']

                if e['sign'] == 'Negative':
                    for row in rows:
                        raw = row.get(col_name, '')
                        if raw:
                            try:
                                row[col_name] = str(-abs(float(raw.replace(',', '.'))))
                            except (ValueError, TypeError):
                                pass

                for col in cols:
                    if col not in seen_cols:
                        all_columns.append(col)
                        seen_cols.add(col)
                col_formats.update(fmts)
                all_rows.extend(rows)

            if not all_rows:
                continue

            if output_rules or only_order:
                all_columns, all_rows, col_formats = self.apply_output_columns(
                    all_columns, all_rows, output_rules, tab_name, col_formats, only_order)

            tabs.append((tab_name, all_columns, all_rows, col_formats))

        return tabs

    def apply_output_columns(self, columns, rows, output_rules, tag="", col_formats=None, only_order=False):
        """Apply hide, reorder, and rename rules from the Output config section."""
        if not output_rules and not only_order:
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
        if only_order:
            for col in columns:
                if col not in order_map and col not in hide_cols:
                    hide_cols.add(col)

        if hide_cols:
            fmts = col_formats or {}
            if any(c.endswith('@Value') or fmts.get(c) == 'Amount' for c in hide_cols):
                self._hidden_value_cols = True

        new_columns = [col for col in columns if col not in hide_cols]
        ordered   = sorted([c for c in new_columns if c in order_map], key=lambda c: order_map[c])
        unordered = [c for c in new_columns if c not in order_map]
        final_orig = ordered + unordered

        # Group original columns by their final (possibly renamed) name so that
        # columns sharing a name have their content merged rather than overwritten.
        merge_groups = {}   # final_name -> [orig_col, ...]
        seen_final   = []
        for orig_col in final_orig:
            final_name = rename_map.get(orig_col, orig_col)
            if final_name not in merge_groups:
                merge_groups[final_name] = []
                seen_final.append(final_name)
            merge_groups[final_name].append(orig_col)

        final_columns = seen_final
        new_rows = []
        for row in rows:
            new_row = {}
            for final_name, orig_cols in merge_groups.items():
                parts  = [str(row.get(c, '')).strip() for c in orig_cols]
                new_row[final_name] = ' '.join(p for p in parts if p)
            new_rows.append(new_row)

        fmts = col_formats or {}
        new_formats = {}
        for final_name, orig_cols in merge_groups.items():
            if all(fmts.get(c) == 'Amount' for c in orig_cols):
                new_formats[final_name] = 'Amount'

        return final_columns, new_rows, new_formats

    # ── no-config fallback: element-based parsing ─────────────────────────────

    def _find_record_info(self, elem):
        child_tag_counts = Counter(child.tag for child in elem)
        for tag, count in child_tag_counts.items():
            if count > 1:
                if any(len(c) > 0 for c in elem if c.tag == tag):
                    return tag, elem
        for child in elem:
            if child_tag_counts[child.tag] == 1:
                result_tag, result_parent = self._find_record_info(child)
                if result_tag is not None:
                    return result_tag, result_parent
        return None, None

    def _get_leaves_excluding_tag(self, elem, exclude_tag, path="", leaves=None):
        if leaves is None:
            leaves = []
        current_path = f"{path}/{elem.tag}" if path else elem.tag
        if elem.tag == exclude_tag:
            return leaves
        text = elem.text.strip() if elem.text else ""
        if len(elem) == 0 or text or elem.attrib:
            leaves.append({'path': current_path, 'tag': elem.tag, 'text': text, 'attributes': dict(elem.attrib)})
        for child in elem:
            self._get_leaves_excluding_tag(child, exclude_tag, current_path, leaves)
        return leaves

    def _collect_flat_records(self, elem, ancestor_leaves=None):
        if ancestor_leaves is None:
            ancestor_leaves = []
        record_tag, record_parent = self._find_record_info(elem)
        if record_tag is None:
            return [ancestor_leaves + self.get_leaf_nodes(elem)]
        parent_leaves = self._get_leaves_excluding_tag(elem, record_tag)
        combined = ancestor_leaves + parent_leaves
        result = []
        for record_elem in record_parent.findall(record_tag):
            result.extend(self._collect_flat_records(record_elem, combined))
        return result

    def element_to_rows(self, elem):
        all_leaf_lists = self._collect_flat_records(elem)
        if not all_leaf_lists:
            return [], []
        all_paths = sorted(set(leaf['path'] for leaves in all_leaf_lists for leaf in leaves))
        amount_columns = set()
        for leaves in all_leaf_lists:
            for leaf in leaves:
                if leaf['attributes'].get('Ccy'):
                    amount_columns.add(leaf['path'])
        columns = []
        for col in all_paths:
            if col in amount_columns:
                columns.append(f"{col}@Value")
                columns.append(f"{col}@Ccy")
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

    # ── control sum helpers ───────────────────────────────────────────────────

    def _calc_parsed_sums(self):
        sums = {}
        for tab_name, columns, rows, col_formats in self.tab_data:
            total = 0.0
            for col in columns:
                if col_formats.get(col) == "Amount" or col.endswith('@Value'):
                    for row in rows:
                        v = row.get(col, '')
                        if v:
                            try:
                                total += float(str(v).replace(',', '.'))
                            except (ValueError, TypeError):
                                pass
            sums[tab_name] = total
        return sums

    def _calc_raw_xml_sums(self, roots, value_tag_entries):
        """Sum element values per tab before sign application.

        Returns (unsigned, signed):
          unsigned — always positive, used for the 'In XML' display
          signed   — sign applied per entry, used for the mismatch check
        """
        unsigned = {}
        signed   = {}
        for entry_str in value_tag_entries:
            parts  = [p.strip() for p in entry_str.split(';')]
            path   = parts[0] if parts else ""
            sign   = parts[1] if len(parts) > 1 else "Positive"
            rename = parts[2] if len(parts) > 2 else ""
            if sign in ("Yes", "No"):
                sign = "Positive"
            if sign not in ("Positive", "Negative"):
                sign = "Positive"
            tab = rename if rename else path
            if not path:
                continue
            mult = -1.0 if sign == "Negative" else 1.0
            for root in roots:
                for elem in root.findall('.//' + path):
                    if elem.text:
                        try:
                            val = abs(float(elem.text.strip().replace(',', '.')))
                            unsigned[tab] = unsigned.get(tab, 0.0) + val
                            signed[tab]   = signed.get(tab, 0.0) + mult * val
                        except (ValueError, TypeError):
                            pass
        return unsigned, signed

    def _extract_document_sums(self, roots):
        results = []
        for root in roots:
            for elem in root.iter('Sum'):
                text = elem.text.strip() if elem.text else ""
                if not text:
                    continue
                try:
                    val = float(text.replace(',', '.'))
                except (ValueError, TypeError):
                    continue
                # Build a readable label from the two nearest ancestors
                parts = []
                parent_map_local = {child: parent for parent in root.iter() for child in parent}
                cur = elem
                for _ in range(2):
                    if cur in parent_map_local:
                        cur = parent_map_local[cur]
                        parts.insert(0, cur.tag)
                label = "/".join(parts) + "/Sum" if parts else "Sum"
                results.append((label, val))
        return results

    def _update_control_panel(self, parsed_sums, raw_sums, signed_raw_sums=None):
        ref_sums   = signed_raw_sums if signed_raw_sums is not None else raw_sums
        raw_abs    = sum(ref_sums.values())
        parsed_abs = sum(parsed_sums.values())
        mismatch   = abs(raw_abs - parsed_abs) > 0.005

        self._ctrl_sum_data = (parsed_sums, ref_sums, mismatch)

        btn_bg  = "#E74C3C" if mismatch else "#27AE60"
        btn_fg  = "#FEE" if mismatch else "#EAF7EE"
        btn_txt = "Control sums: MISMATCH" if mismatch else "Control sums: OK"
        self.ctrl_sum_border.config(bg=btn_bg)
        self.ctrl_sum_inner.config(bg=btn_fg)
        self.ctrl_sum_btn.config(text=btn_txt, fg="#1E8449" if not mismatch else "#C0392B",
                                 bg=btn_fg)
        self.ctrl_sum_border.pack(side=tk.LEFT, padx=(6, 0))

    def _show_status_popup(self):
        if not self._status_info:
            return
        title, message, color = self._status_info
        win = tk.Toplevel(self)
        win.title("Parse Status")
        win.transient(self)
        win.resizable(False, False)
        win.minsize(300, 0)

        header = tk.Label(win, text=title, font=("TkDefaultFont", 10, "bold"),
                          fg=color, padx=16, pady=8, anchor="w")
        header.pack(fill=tk.X)

        ttk.Separator(win, orient="horizontal").pack(fill=tk.X, padx=12, pady=4)

        tk.Label(win, text=message, wraplength=320, justify="left",
                 padx=16, pady=8, anchor="w").pack(fill=tk.X)

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(4, 12))

        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - win.winfo_width())  // 2
        y = self.winfo_y() + (self.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")

    def _show_ctrl_sum_popup(self):
        if not self._ctrl_sum_data:
            return
        parsed_sums, ref_sums, mismatch = self._ctrl_sum_data

        win = tk.Toplevel(self)
        win.title("Control Sums")
        win.transient(self)
        win.resizable(True, False)
        win.minsize(280, 0)

        lbl_pad = {"padx": 12, "pady": (8, 2), "anchor": "w"}
        sub_pad = {"padx": 24, "pady": 1}

        for tab_name in parsed_sums:
            tk.Label(win, text=tab_name,
                     font=("TkDefaultFont", 9, "bold")).pack(**lbl_pad)

            raw_val    = ref_sums.get(tab_name, 0.0)
            parsed_val = parsed_sums[tab_name]

            for label, value in (("In XML:", raw_val), ("Parsed:", parsed_val)):
                row_f = tk.Frame(win)
                row_f.pack(fill=tk.X, **sub_pad)
                tk.Label(row_f, text=label, anchor="w", width=9,
                         font=("TkDefaultFont", 9)).pack(side=tk.LEFT)
                color = "#E74C3C" if value < 0 else "#1A5276"
                tk.Label(row_f, text=f"{value:,.2f}", anchor="e",
                         font=("TkDefaultFont", 9), fg=color).pack(side=tk.RIGHT)

        ttk.Separator(win, orient="horizontal").pack(fill=tk.X, padx=12, pady=8)

        chip_bg  = "#E74C3C" if mismatch else "#27AE60"
        chip_txt = "MISMATCH" if mismatch else "Sums match — no values lost or duplicated during parsing"
        chip_f = tk.Frame(win, bg=chip_bg)
        chip_f.pack(padx=12, pady=(0, 10), anchor="w")
        tk.Label(chip_f, text=chip_txt, bg=chip_bg, fg="white",
                 font=("TkDefaultFont", 9, "bold"), padx=8, pady=3).pack()

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))

        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - win.winfo_width())  // 2
        y = self.winfo_y() + (self.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")

    # ── main parse/display ────────────────────────────────────────────────────

    def parse_and_display_xml(self, file_paths):
        if isinstance(file_paths, str):
            file_paths = (file_paths,)

        selected_config = self.config_var.get()
        has_config      = selected_config and selected_config != "No configs"
        config_tags     = self.settings_manager.get_config(selected_config) if has_config else []
        output_rules    = self.settings_manager.get_output_columns(selected_config) if has_config else []
        only_order      = self.settings_manager.get_only_order_columns(selected_config) if has_config else False

        prog = ProgressDialog(self, len(file_paths))
        result_box = [None]   # filled by worker thread

        def worker():
            try:
                hidden = False
                merged    = {}
                all_roots = []

                for i, file_path in enumerate(file_paths):
                    self.after(0, lambda m=f"Parsing file {i+1} of {len(file_paths)}…":
                               prog.set_message(m))
                    tree = ET.parse(file_path)
                    root = tree.getroot()
                    root = self.strip_namespaces(root)
                    all_roots.append(root)

                    if config_tags:
                        self._hidden_value_cols = False
                        n_files = len(file_paths)
                        def _make_prog_cb(_i=i):
                            last_pct = [-1]
                            def _cb(path, done, total):
                                pct = int(done / total * 100) if total else 0
                                if done == 1:
                                    last_pct[0] = -1   # force refresh at start of each path
                                if pct == last_pct[0]:
                                    return
                                last_pct[0] = pct
                                msg = f"File {_i+1}/{n_files}: {path} ({done}/{total})"
                                def _update(m=msg, p=pct):
                                    prog.set_message(m)
                                    prog.set_progress(p)
                                self.after(0, _update)
                            return _cb
                        tabs = self.parse_with_value_tags(root, config_tags, output_rules,
                                                          progress_cb=_make_prog_cb(),
                                                          only_order=only_order)
                        if self._hidden_value_cols:
                            hidden = True
                    else:
                        columns, rows = self.element_to_rows(root)
                        if output_rules or only_order:
                            self._hidden_value_cols = False
                            columns, rows, col_formats = self.apply_output_columns(
                                columns, rows, output_rules, "Sheet1", {}, only_order)
                            if self._hidden_value_cols:
                                hidden = True
                        else:
                            col_formats = {}
                        tabs = [("Sheet1", columns, rows, col_formats)] if rows else []

                    for tab_name, columns, rows, col_formats in tabs:
                        parts = tab_name.rsplit(" ", 1)
                        if len(parts) == 2 and parts[1].isdigit():
                            base     = parts[0]
                            existing = sum(1 for k in merged
                                          if k.startswith(base + " ") and k[len(base)+1:].isdigit())
                            merged[f"{base} {existing + 1}"] = (columns, rows, col_formats)
                        else:
                            if tab_name in merged:
                                prev_cols, prev_rows, prev_fmts = merged[tab_name]
                                seen = set(prev_cols)
                                merged_cols = list(prev_cols)
                                for col in columns:
                                    if col not in seen:
                                        merged_cols.append(col)
                                        seen.add(col)
                                merged_fmts = dict(prev_fmts)
                                merged_fmts.update(col_formats)
                                merged[tab_name] = (merged_cols, prev_rows + rows, merged_fmts)
                            else:
                                merged[tab_name] = (columns, rows, col_formats)

                result_box[0] = ('ok', merged, all_roots, hidden)
            except Exception as exc:
                import traceback as _tb
                result_box[0] = ('error', exc, _tb.format_exc())
            self.after(0, on_done)

        def on_done():
            prog.close()
            kind = result_box[0][0]
            if kind == 'error':
                _, exc, tb = result_box[0]
                print(tb)
                messagebox.showerror("Error", f"Failed to parse XML: {exc}")
                return

            _, merged, all_roots, hidden = result_box[0]
            self._hidden_value_cols = hidden

            if not merged:
                messagebox.showwarning("Warning", "No data found in selected file(s).")
                return

            self.display_tabs([(name, cols, rows, fmts)
                               for name, (cols, rows, fmts) in merged.items()])
            self.export_button.config(state="normal")
            self.export_excel_button.config(state="normal")

            if hidden:
                self.status_border.config(bg="#E67E22")
                self.status_inner.config(bg="#FEF0E7")
                self.status_label.config(text="⚠ Value columns hidden",
                                         fg="#D35400", bg="#FEF0E7")
                self._status_info = (
                    "⚠ Value columns hidden",
                    "One or more amount columns were detected but hidden because "
                    "they could not be unambiguously matched to a configured value tag.\n\n"
                    "Check your config's Value Tags and make sure each tag path is "
                    "unique enough to match exactly the columns you expect.",
                    "#E67E22"
                )
            else:
                self.status_border.config(bg="#27AE60")
                self.status_inner.config(bg="#EAF7EE")
                self.status_label.config(text="✓ Parsed successfully",
                                         fg="#1E8449", bg="#EAF7EE")
                self._status_info = (
                    "✓ Parsed successfully",
                    "All files were read and parsed without errors.\n\n"
                    "Rows and columns have been populated in the tabs below. "
                    "Check the Control Sums button to verify that no values were "
                    "lost or duplicated during parsing.",
                    "#27AE60"
                )
            self.status_border.pack(side=tk.LEFT, padx=(10, 0))
            self.bell()

            parsed_sums              = self._calc_parsed_sums()
            raw_sums, signed_raw_sums = self._calc_raw_xml_sums(all_roots, config_tags)
            self._update_control_panel(parsed_sums, raw_sums, signed_raw_sums)

        threading.Thread(target=worker, daemon=True).start()

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

            tree.bind("<ButtonRelease-1>", lambda e, t=tree: self._open_cell_overlay(e, t))

            self.notebook.add(frame, text=tab_name)
            self.tab_data.append((tab_name, columns, rows, col_formats))

    def _dismiss_cell_overlay(self):
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
        overlay.after(10, lambda: overlay.select_range(0, tk.END))

        overlay.bind("<Escape>",    lambda e: self._dismiss_cell_overlay())
        overlay.bind("<FocusOut>",  lambda e: self._dismiss_cell_overlay())
        overlay.bind("<Return>",    lambda e: self._dismiss_cell_overlay())
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
                subprocess.Popen(['explorer', '/select,', file_path.replace('/', '\\')])
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
                                        return str(v)
                                df[col] = df[col].fillna("").apply(_to_swedish)
                            else:
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

        error_log = os.path.join(os.getcwd(), f"xmlparser_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        with open(error_log, 'w') as f:
            f.write(f"XMLParser Error Log - {datetime.now()}\n")
            f.write("=" * 50 + "\n")
            f.write(f"Error: {e}\n\n")
            f.write("Traceback:\n")
            traceback.print_exc(file=f)

        try:
            from tkinter import messagebox
            messagebox.showerror("XMLParser Error",
                f"An error occurred and has been logged to:\n{error_log}\n\nError: {str(e)}")
        except:
            pass
