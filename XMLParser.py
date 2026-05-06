import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import configparser
import os
import subprocess
from pathlib import Path
from collections import Counter
from datetime import datetime
import xml.etree.ElementTree as ET
import csv
import pandas as pd


class SettingsManager:
    def __init__(self, settings_file="Settings.ini"):
        self.settings_file = settings_file
        self.config = configparser.ConfigParser()
        self.configs = {}
        self.merge_columns = {}
        self.last_directory = ""
        self.last_selected_config = ""
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
            
            # Configs
            self.configs = {}
            self.merge_columns = {}
            for section in self.config.sections():
                if section.startswith("Config:"):
                    config_name = section[7:]
                    values = self.config[section].get("values", "")
                    self.configs[config_name] = [v for v in values.split("\n") if v] if values else []
                    merge = self.config[section].get("merge", "")
                    self.merge_columns[config_name] = [v for v in merge.split("\n") if v] if merge else []
        else:
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
            "last_selected_config": self.last_selected_config
        }
        
        # Configs
        for config_name, values in self.configs.items():
            self.config[f"Config:{config_name}"] = {
                "values": "\n".join(values),
                "merge": "\n".join(self.merge_columns.get(config_name, []))
            }
        
        with open(self.settings_file, "w") as f:
            self.config.write(f)
    
    def add_config(self, name, values=None):
        self.configs[name] = values if values else []
        self.merge_columns[name] = []
        self.save()

    def delete_config(self, name):
        if name in self.configs:
            del self.configs[name]
            self.merge_columns.pop(name, None)
            self.save()

    def update_config(self, name, values):
        if name in self.configs:
            self.configs[name] = values
            self.save()

    def update_merge_columns(self, name, rules):
        if name in self.configs:
            self.merge_columns[name] = rules
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
        self.geometry("560x800")
        self.transient(parent)
        self.grab_set()

        self.pending_tags = {}   # {config_name: [tag_entry_strings]}
        self.pending_merge = {}  # {config_name: [rule_strings]}

        self.create_widgets()
        self.refresh_config_list()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        # Config list
        list_frame = tk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        tk.Label(list_frame, text="Configs:").pack(anchor=tk.W)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.config_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.config_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.config_listbox.bind("<<ListboxSelect>>", self.on_config_select)
        scrollbar.config(command=self.config_listbox.yview)
        
        # Buttons frame
        buttons_frame = tk.Frame(self)
        buttons_frame.pack(fill=tk.X, padx=10, pady=5)

        self.add_button = tk.Button(buttons_frame, text="Add config", command=self.add_config,
                                    bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white")
        self.add_button.pack(side=tk.LEFT, padx=5)

        self.delete_button = tk.Button(buttons_frame, text="Delete config", command=self.delete_config,
                                       bg="#E74C3C", fg="white", activebackground="#C0392B", activeforeground="white")
        self.delete_button.pack(side=tk.LEFT, padx=5)

        self.info_button = tk.Button(buttons_frame, text="Info", command=self.show_info,
                                     bg="#3498DB", fg="white", activebackground="#2980B9", activeforeground="white")
        self.info_button.pack(side=tk.LEFT, padx=5)
        
        # Tags table
        tags_outer = tk.Frame(self)
        tags_outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tk.Label(tags_outer, text="Tags to extract:").pack(anchor=tk.W)

        tags_table_frame = tk.Frame(tags_outer)
        tags_table_frame.pack(fill=tk.BOTH, expand=True)

        self.tags_tree = ttk.Treeview(
            tags_table_frame,
            columns=("tag", "split"),
            show="headings",
            height=6
        )
        self.tags_tree.heading("tag", text="Tag")
        self.tags_tree.heading("split", text="Split Tabs")
        self.tags_tree.column("tag", width=300, minwidth=100, stretch=True)
        self.tags_tree.column("split", width=80, minwidth=70, stretch=False)

        tags_vsb = ttk.Scrollbar(tags_table_frame, orient="vertical", command=self.tags_tree.yview)
        self.tags_tree.configure(yscrollcommand=tags_vsb.set)
        self.tags_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tags_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tags_tree.bind("<Double-1>", self.on_tags_cell_edit)

        tags_btn_frame = tk.Frame(tags_outer)
        tags_btn_frame.pack(fill=tk.X, pady=(3, 0))
        tk.Button(tags_btn_frame, text="Add Row", command=self.add_tags_row,
                  bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white").pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(tags_btn_frame, text="Delete Row", command=self.delete_tags_row,
                  bg="#E74C3C", fg="white", activebackground="#C0392B", activeforeground="white").pack(side=tk.LEFT)


        # Merge columns table
        merge_outer = tk.Frame(self)
        merge_outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tk.Label(merge_outer, text="Rename and merge columns:").pack(anchor=tk.W)

        table_frame = tk.Frame(merge_outer)
        table_frame.pack(fill=tk.BOTH, expand=True)

        self.merge_tree = ttk.Treeview(
            table_frame,
            columns=("action", "source", "target"),
            show="headings",
            height=8
        )
        self.merge_tree.heading("action", text="Action")
        self.merge_tree.heading("source", text="Source Column")
        self.merge_tree.heading("target", text="Target Name")
        self.merge_tree.column("action", width=80, minwidth=70, stretch=False)
        self.merge_tree.column("source", width=250, minwidth=100, stretch=True)
        self.merge_tree.column("target", width=110, minwidth=70, stretch=True)

        merge_vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.merge_tree.yview)
        self.merge_tree.configure(yscrollcommand=merge_vsb.set)
        self.merge_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        merge_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.merge_tree.bind("<Double-1>", self.on_merge_cell_edit)

        merge_btn_frame = tk.Frame(merge_outer)
        merge_btn_frame.pack(fill=tk.X, pady=(3, 0))
        tk.Button(merge_btn_frame, text="Add Row", command=self.add_merge_row,
                  bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white").pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(merge_btn_frame, text="Delete Row", command=self.delete_merge_row,
                  bg="#E74C3C", fg="white", activebackground="#C0392B", activeforeground="white").pack(side=tk.LEFT)

        # Close buttons
        close_btn_frame = tk.Frame(self)
        close_btn_frame.pack(pady=10)
        tk.Button(close_btn_frame, text="Close and save",
                  command=self.close_and_save,
                  bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white").pack(side=tk.LEFT, padx=5)
        tk.Button(close_btn_frame, text="Close",
                  command=self.destroy,
                  bg="#7F8C8D", fg="white", activebackground="#616A6B", activeforeground="white").pack(side=tk.LEFT, padx=5)

        self.current_config = None
    
    def refresh_config_list(self):
        self.config_listbox.delete(0, tk.END)
        for name in sorted(self.settings_manager.get_config_names()):
            self.config_listbox.insert(tk.END, name)
        # Pre-select initial config
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
        self.pending_tags[self.current_config] = tags
        self.pending_merge[self.current_config] = merge

    def _read_ui(self):
        tags = []
        for item in self.tags_tree.get_children():
            vals = self.tags_tree.item(item, "values")
            tag = vals[0].strip() if len(vals) > 0 else ""
            split = vals[1].strip() if len(vals) > 1 else "Yes"
            if tag:
                tags.append(f"{tag}; {split}")
        merge = []
        for item in self.merge_tree.get_children():
            vals = self.merge_tree.item(item, "values")
            action = vals[0].strip() if len(vals) > 0 else "New Line"
            source = vals[1].strip() if len(vals) > 1 else ""
            target = vals[2].strip() if len(vals) > 2 else ""
            if source:
                merge.append(f"{action}; {source}; {target}")
        return tags, merge

    def _load_config(self, config_name):
        tags = self.pending_tags.get(config_name,
               self.settings_manager.get_config(config_name))
        merge = self.pending_merge.get(config_name,
                self.settings_manager.get_merge_columns(config_name))

        for item in self.tags_tree.get_children():
            self.tags_tree.delete(item)
        for entry in tags:
            parts = [p.strip() for p in entry.split(';')]
            tag = parts[0] if len(parts) > 0 else ""
            split = parts[1] if len(parts) > 1 else "Yes"
            if split not in ("Yes", "No"):
                split = "Yes"
            self.tags_tree.insert("", tk.END, values=(tag, split))

        for item in self.merge_tree.get_children():
            self.merge_tree.delete(item)
        for rule in merge:
            parts = [p.strip() for p in rule.split(';')]
            action = parts[0] if len(parts) > 0 else "New Line"
            source = parts[1] if len(parts) > 1 else ""
            target = parts[2] if len(parts) > 2 else ""
            if action not in ("New Line", "Merge", "Hide"):
                # Old format was Target; Source; Conflict — migrate on load
                if target in ("New Line", "Merge", "Hide"):
                    action, target = target, action
                else:
                    action = "New Line"
            self.merge_tree.insert("", tk.END, values=(action, source, target))

    def close_and_save(self):
        if self.current_config:
            self._buffer_current_edits()
        for config_name, tags in self.pending_tags.items():
            self.settings_manager.update_config(config_name, tags)
        for config_name, merge in self.pending_merge.items():
            self.settings_manager.update_merge_columns(config_name, merge)
        self.destroy()

    def on_merge_cell_edit(self, event):
        region = self.merge_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col_id = self.merge_tree.identify_column(event.x)
        item = self.merge_tree.identify_row(event.y)
        if not item:
            return
        col_idx = int(col_id[1:]) - 1
        col_names = ("action", "source", "target")
        col_name = col_names[col_idx]
        bbox = self.merge_tree.bbox(item, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        current = self.merge_tree.set(item, col_name)
        if col_name == "action":
            editor = ttk.Combobox(self.merge_tree, values=["New Line", "Merge", "Hide"], state="readonly")
            editor.set(current if current in ("New Line", "Merge", "Hide") else "New Line")
            editor.place(x=x, y=y, width=w, height=h)
            editor.focus()
            def commit_combo(event=None, _editor=editor, _item=item, _col=col_name):
                self.merge_tree.set(_item, _col, _editor.get())
                _editor.destroy()
            editor.bind("<<ComboboxSelected>>", commit_combo)
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
            editor.bind("<Return>", commit_entry)
            editor.bind("<FocusOut>", commit_entry)
            editor.bind("<Escape>", cancel_entry)

    def add_merge_row(self):
        item = self.merge_tree.insert("", tk.END, values=("New Line", "", ""))
        self.merge_tree.selection_set(item)
        self.merge_tree.see(item)

    def delete_merge_row(self):
        selected = self.merge_tree.selection()
        if selected:
            for item in selected:
                self.merge_tree.delete(item)

    def on_tags_cell_edit(self, event):
        region = self.tags_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col_id = self.tags_tree.identify_column(event.x)
        item = self.tags_tree.identify_row(event.y)
        if not item:
            return
        col_idx = int(col_id[1:]) - 1
        col_names = ("tag", "split")
        col_name = col_names[col_idx]
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
            editor.bind("<Return>", commit_tags_entry)
            editor.bind("<FocusOut>", commit_tags_entry)
            editor.bind("<Escape>", cancel_tags_entry)

    def add_tags_row(self):
        item = self.tags_tree.insert("", tk.END, values=("", "Yes"))
        self.tags_tree.selection_set(item)
        self.tags_tree.see(item)

    def delete_tags_row(self):
        selected = self.tags_tree.selection()
        if selected:
            for item in selected:
                self.tags_tree.delete(item)

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
                    # Select the new config
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
        
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="OK", command=confirm,
                  bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=cancel,
                  bg="#7F8C8D", fg="white", activebackground="#616A6B", activeforeground="white").pack(side=tk.LEFT, padx=5)
        
        dialog.bind("<Return>", lambda e: confirm())
        dialog.bind("<Escape>", lambda e: cancel())
        
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
    
    def delete_config(self):
        selection = self.config_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a config to delete.")
            return
        
        name = self.config_listbox.get(selection[0])
        if messagebox.askyesno("Confirm", f"Delete config '{name}'?"):
            for item in self.tags_tree.get_children():
                self.tags_tree.delete(item)
            for item in self.merge_tree.get_children():
                self.merge_tree.delete(item)
            self.pending_tags.pop(name, None)
            self.pending_merge.pop(name, None)
            self.current_config = None
            self.settings_manager.delete_config(name)
            self.refresh_config_list()
    
    def show_info(self):
        info = tk.Toplevel(self)
        info.title("Config Settings Guide")
        info.transient(self)
        info.grab_set()
        info.resizable(False, False)

        text = (
            "TAGS TO EXTRACT\n"
            "───────────────\n"
            "Each row specifies one XML tag to search for in the loaded file.\n"
            "\n"
            "  Tag         — The XML tag name to look for.\n"
            "  Split Tabs  — What to do when multiple elements with this\n"
            "                tag are found:\n"
            "\n"
            "    Yes  Each instance gets its own tab (Tag 1, Tag 2, …).\n"
            "    No   All instances are combined into a single tab.\n"
            "\n"
            "RENAME AND MERGE COLUMNS\n"
            "────────────────────────\n"
            "The table has three columns:\n"
            "\n"
            "  Action        — What to do with the source column:\n"
            "\n"
            "    New Line  When a single row has values in more than one\n"
            "              source mapped to the same target, each unique\n"
            "              value gets its own row so no data is lost.\n"
            "\n"
            "    Merge     Multiple source values are joined into one cell\n"
            "              separated by a space.\n"
            "              Example: 'Main St' + '12' → 'Main St 12'\n"
            "\n"
            "    Hide      The source column is removed from the output.\n"
            "              Target Name is ignored for hidden columns.\n"
            "\n"
            "  Source Column — The XML path of the source column.\n"
            "  Target Name   — The display name for the output column\n"
            "                  (ignored when Action is Hide).\n"
            "\n"
            "• Multiple rows with the same Target Name map several source\n"
            "  columns into one output column.\n"
            "• Duplicate values across sources are never repeated.\n"
            "• Double-click any cell to edit it. The Action cell opens\n"
            "  a dropdown; other cells accept free text.\n"
        )

        tk.Label(info, text=text, justify=tk.LEFT, font=("Courier", 9), padx=15, pady=10).pack()
        tk.Button(info, text="Close", command=info.destroy,
                  bg="#7F8C8D", fg="white", activebackground="#616A6B", activeforeground="white").pack(pady=(0, 10))

        info.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - info.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - info.winfo_height()) // 2
        info.geometry(f"+{x}+{y}")

    def update_parent_dropdown(self):
        self.master.update_config_dropdown()


class XMLParserApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.settings_manager = SettingsManager()
        self.settings_manager.validate_window_position()
        
        self.title("XML Parser")
        self.geometry(f"{self.settings_manager.window_width}x{self.settings_manager.window_height}+{self.settings_manager.window_x}+{self.settings_manager.window_y}")
        
        self.create_menu()
        self.create_widgets()
        self.update_config_dropdown()
        
        # Bind window close to save settings
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Configure>", self.on_resize)
    
    def create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Configs", command=self.open_configs)

        dev_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Dev", menu=dev_menu)
        dev_menu.add_command(label="Open Folder", command=self.open_program_folder)

    def open_program_folder(self):
        folder = os.path.dirname(os.path.abspath(__file__))
        subprocess.Popen(f'explorer "{folder}"')
    
    def create_widgets(self):
        # Main container with 20/80 split
        self.upper_frame = tk.Frame(self)
        self.upper_frame.pack(fill=tk.X)

        self.lower_frame = tk.Frame(self)
        self.lower_frame.pack(fill=tk.BOTH, expand=True)

        # Upper frame contents (left-aligned)
        button_frame = tk.Frame(self.upper_frame)
        button_frame.pack(pady=5, padx=10, anchor=tk.W)
        
        self.open_button = tk.Button(button_frame, text="Open", command=self.open_file,
                                     bg="#4A90D9", fg="white", activebackground="#357ABD", activeforeground="white")
        self.open_button.pack(side=tk.LEFT, padx=10)

        # Config dropdown
        self.config_var = tk.StringVar(self)
        self.config_dropdown = ttk.Combobox(button_frame, textvariable=self.config_var, state="readonly", width=30)
        self.config_dropdown.pack(side=tk.LEFT, padx=10)
        self.config_dropdown.bind("<<ComboboxSelected>>", self.on_config_selected)

        # Export CSV button
        self.export_button = tk.Button(button_frame, text="Export CSV", command=self.export_csv, state="disabled",
                                       bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white",
                                       disabledforeground="black")
        self.export_button.pack(side=tk.LEFT, padx=10)

        # Export Excel button
        self.export_excel_button = tk.Button(button_frame, text="Export Excel", command=self.export_excel, state="disabled",
                                             bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white",
                                             disabledforeground="black")
        self.export_excel_button.pack(side=tk.LEFT, padx=10)
        
        # Notebook
        self.notebook = ttk.Notebook(self.lower_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tab_data = []  # list of (tab_name, columns, rows)
    
    def open_file(self):
        initial_dir = self.settings_manager.last_directory if self.settings_manager.last_directory else "."
        file_path = filedialog.askopenfilename(
            title="Select XML file",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            initialdir=initial_dir
        )
        
        if file_path:
            self.settings_manager.last_directory = os.path.dirname(file_path)
            self.settings_manager.save()
            self.parse_and_display_xml(file_path)
    
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
                    row[f"{path}@Value"] = value
                    row[f"{path}@Ccy"] = leaf['attributes'].get('Ccy', '')
                else:
                    if leaf['attributes']:
                        attr_parts = [f"{k}={v}" for k, v in leaf['attributes'].items()]
                        value = f"{value} ({' '.join(attr_parts)})" if value else ' '.join(attr_parts)
                    row[path] = value
            rows.append(row)

        return columns, rows

    def apply_column_merges(self, columns, rows, merge_rules):
        if not merge_rules:
            return columns, rows

        hide_cols = set()
        target_to_sources = {}
        target_action_mode = {}
        for rule in merge_rules:
            if ';' not in rule:
                continue
            parts = rule.split(';', 2)
            if len(parts) < 2:
                continue
            action = parts[0].strip()
            source = parts[1].strip()
            target = parts[2].strip() if len(parts) > 2 else ""
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

        return new_columns, new_rows

    def deduplicate_amount_values(self, columns, rows):
        value_cols = {col for col in columns if col.endswith('@Value')}
        if not rows or not value_cols:
            return rows
        last_values = {col: rows[0].get(col, "") for col in value_cols}
        for i in range(1, len(rows)):
            for col in value_cols:
                curr = rows[i].get(col, "")
                if curr == last_values[col]:
                    rows[i][col] = ""
                elif curr != "":
                    last_values[col] = curr
        return rows

    def parse_with_config(self, root, config_tags, merge_rules=None):
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
                # Combine all instances into one tab
                all_columns, all_rows = [], []
                for elem in elements:
                    columns, rows = self.element_to_rows(elem)
                    if not all_columns:
                        all_columns = columns
                    all_rows.extend(rows)
                all_columns, all_rows = self.apply_column_merges(all_columns, all_rows, merge_rules or [])
                all_rows = self.deduplicate_amount_values(all_columns, all_rows)
                tabs.append((tag, all_columns, all_rows))
            else:
                for i, elem in enumerate(elements):
                    columns, rows = self.element_to_rows(elem)
                    columns, rows = self.apply_column_merges(columns, rows, merge_rules or [])
                    rows = self.deduplicate_amount_values(columns, rows)
                    tabs.append((f"{tag} {i + 1}", columns, rows))

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

    def parse_and_display_xml(self, file_path):
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            root = self.strip_namespaces(root)

            selected_config = self.config_var.get()
            has_config = selected_config and selected_config != "No configs"
            config_tags = self.settings_manager.get_config(selected_config) if has_config else []
            merge_rules = self.settings_manager.get_merge_columns(selected_config) if has_config else []

            if config_tags:
                tabs = self.parse_with_config(root, config_tags, merge_rules)
            else:
                columns, rows = self.element_to_rows(root)
                columns, rows = self.apply_column_merges(columns, rows, merge_rules)
                rows = self.deduplicate_amount_values(columns, rows)
                if not rows:
                    messagebox.showwarning("Warning", "No data found in XML.")
                    return
                tabs = [("Sheet1", columns, rows)]

            if not tabs:
                messagebox.showwarning("Warning", "No data found for the selected config tags.")
                return

            self.display_tabs(tabs)
            self.export_button.config(state="normal")
            self.export_excel_button.config(state="normal")

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

        for tab_name, columns, rows in tabs:
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

            self.notebook.add(frame, text=tab_name)
            self.tab_data.append((tab_name, columns, rows))
    
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

        tk.Button(btn_frame, text="Open location",
                  command=lambda: [subprocess.Popen(f'explorer /select,"{file_path}"'), dialog.destroy()],
                  bg="#4A90D9", fg="white", activebackground="#357ABD", activeforeground="white").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Open file",
                  command=lambda: [os.startfile(file_path), dialog.destroy()],
                  bg="#27AE60", fg="white", activebackground="#1E8449", activeforeground="white").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="OK",
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
        tab_name, columns, rows = self.tab_data[current_idx]

        file_path = filedialog.asksaveasfilename(
            title="Export to CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            defaultextension=".csv",
            initialfile=self.default_filename(".csv", tab_name)
        )

        if not file_path:
            return

        try:
            df = pd.DataFrame(rows, columns=columns)
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
            initialfile=self.default_filename(".xlsx")
        )

        if not file_path:
            return

        try:
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                for tab_name, columns, rows in self.tab_data:
                    df = pd.DataFrame(rows, columns=columns)
                    for col in df.columns:
                        if col.endswith('@Value'):
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    df.to_excel(writer, sheet_name=tab_name[:31], index=False)
            self.show_export_dialog(file_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export Excel: {str(e)}")


if __name__ == "__main__":
    app = XMLParserApp()
    app.mainloop()
