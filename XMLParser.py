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
            for section in self.config.sections():
                if section.startswith("Config:"):
                    config_name = section[7:]  # Remove "Config:" prefix
                    values = self.config[section].get("values", "")
                    self.configs[config_name] = [v for v in values.split("\n") if v] if values else []
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
                "values": "\n".join(values)
            }
        
        with open(self.settings_file, "w") as f:
            self.config.write(f)
    
    def add_config(self, name, values=None):
        self.configs[name] = values if values else []
        self.save()
    
    def delete_config(self, name):
        if name in self.configs:
            del self.configs[name]
            self.save()
    
    def update_config(self, name, values):
        if name in self.configs:
            self.configs[name] = values
            self.save()
    
    def get_config_names(self):
        return list(self.configs.keys())
    
    def get_config(self, name):
        return self.configs.get(name, [])
    
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
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.title("Configs")
        self.geometry("500x600")
        self.transient(parent)
        self.grab_set()
        
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
        
        self.add_button = tk.Button(buttons_frame, text="Add config", command=self.add_config)
        self.add_button.pack(side=tk.LEFT, padx=5)
        
        self.delete_button = tk.Button(buttons_frame, text="Delete config", command=self.delete_config)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        
        # Values editor
        values_frame = tk.Frame(self)
        values_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        tk.Label(values_frame, text="Values (one per line):").pack(anchor=tk.W)
        
        values_scrollbar = tk.Scrollbar(values_frame)
        values_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.values_text = tk.Text(values_frame, height=15, yscrollcommand=values_scrollbar.set)
        self.values_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        values_scrollbar.config(command=self.values_text.yview)
        
        self.values_text.bind("<KeyRelease>", self.on_values_changed)
        self.values_text.bind("<FocusOut>", self.save_current_config)
        
        # Close button
        tk.Button(self, text="Close", command=self.destroy).pack(pady=10)
        
        self.current_config = None
    
    def refresh_config_list(self):
        self.config_listbox.delete(0, tk.END)
        for name in sorted(self.settings_manager.get_config_names()):
            self.config_listbox.insert(tk.END, name)
        self.update_parent_dropdown()
    
    def on_config_select(self, event):
        selection = self.config_listbox.curselection()
        if selection:
            self.save_current_config()
            self.current_config = self.config_listbox.get(selection[0])
            values = self.settings_manager.get_config(self.current_config)
            self.values_text.delete("1.0", tk.END)
            self.values_text.insert("1.0", "\n".join(values))
    
    def on_values_changed(self, event=None):
        self.save_current_config()
    
    def save_current_config(self, event=None):
        if self.current_config:
            values = self.values_text.get("1.0", tk.END).strip().split("\n")
            values = [v for v in values if v]
            self.settings_manager.update_config(self.current_config, values)
    
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
        tk.Button(button_frame, text="OK", command=confirm).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=cancel).pack(side=tk.LEFT, padx=5)
        
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
            self.values_text.delete("1.0", tk.END)
            self.current_config = None
            self.settings_manager.delete_config(name)
            self.refresh_config_list()
    
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
    
    def create_widgets(self):
        # Main container with 20/80 split
        self.upper_frame = tk.Frame(self)
        self.upper_frame.pack(fill=tk.X)

        self.lower_frame = tk.Frame(self)
        self.lower_frame.pack(fill=tk.BOTH, expand=True)

        # Upper frame contents (left-aligned)
        button_frame = tk.Frame(self.upper_frame)
        button_frame.pack(pady=5, padx=10, anchor=tk.W)
        
        self.open_button = tk.Button(button_frame, text="Open", command=self.open_file)
        self.open_button.pack(side=tk.LEFT, padx=10)
        
        # Config dropdown
        self.config_var = tk.StringVar(self)
        self.config_dropdown = ttk.Combobox(button_frame, textvariable=self.config_var, state="readonly", width=30)
        self.config_dropdown.pack(side=tk.LEFT, padx=10)
        self.config_dropdown.bind("<<ComboboxSelected>>", self.on_config_selected)
        
        # Export CSV button
        self.export_button = tk.Button(button_frame, text="Export CSV", command=self.export_csv, state="disabled")
        self.export_button.pack(side=tk.LEFT, padx=10)

        # Export Excel button
        self.export_excel_button = tk.Button(button_frame, text="Export Excel", command=self.export_excel, state="disabled")
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
        ConfigsDialog(self, self.settings_manager)
    
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
        """Collect leaf nodes from elem, skipping all subtrees rooted at exclude_tag."""
        if leaves is None:
            leaves = []
        current_path = f"{path}/{elem.tag}" if path else elem.tag
        if elem.tag == exclude_tag:
            return leaves
        if len(elem) == 0:
            text = elem.text.strip() if elem.text else ""
            leaves.append({'path': current_path, 'tag': elem.tag, 'text': text, 'attributes': dict(elem.attrib)})
        else:
            for child in elem:
                self.get_leaves_excluding_tag(child, exclude_tag, current_path, leaves)
        return leaves

    def element_to_rows(self, elem):
        """Convert an element to (columns, rows), using the first repeating child as the row boundary."""
        record_tag, record_parent = self.find_record_info(elem)

        if record_tag is None:
            return self.leaves_to_table(self.get_leaf_nodes(elem))

        parent_leaves = self.get_leaves_excluding_tag(elem, record_tag)
        all_record_leaves = [
            parent_leaves + self.get_leaf_nodes(record_elem)
            for record_elem in record_parent.findall(record_tag)
        ]

        all_paths = sorted(set(leaf['path'] for leaves in all_record_leaves for leaf in leaves))
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
        for leaves in all_record_leaves:
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

    def leaves_to_table(self, leaves):
        """Convert leaf nodes to (columns, rows) using occurrence-index row assignment."""
        raw_columns = sorted(set(leaf['path'] for leaf in leaves))
        amount_columns = set()
        columns = []
        for col in raw_columns:
            if col.endswith('/Amt') or col.endswith('/RmtdAmt'):
                columns.append(f"{col}@Value")
                columns.append(f"{col}@Ccy")
                amount_columns.add(col)
            else:
                columns.append(col)

        path_counts = Counter(leaf['path'] for leaf in leaves)
        num_rows = max(path_counts.values()) if path_counts else 1

        occurrence_counters = {}
        rows = [{} for _ in range(num_rows)]

        for leaf in leaves:
            path = leaf['path']
            occurrence_counters.setdefault(path, 0)
            row_idx = occurrence_counters[path]
            occurrence_counters[path] += 1

            if row_idx >= num_rows:
                continue

            value = leaf['text']
            if path in amount_columns:
                rows[row_idx][f"{path}@Value"] = value
                rows[row_idx][f"{path}@Ccy"] = leaf['attributes'].get('Ccy', '')
            else:
                if leaf['attributes']:
                    attr_parts = [f"{k}={v}" for k, v in leaf['attributes'].items()]
                    value = f"{value} ({' '.join(attr_parts)})" if value else ' '.join(attr_parts)
                rows[row_idx][path] = value

        return columns, rows

    def parse_with_config(self, root, config_tags):
        """Return list of (tab_name, columns, rows) using config tags to split into tabs."""
        tag_elements = {tag: root.findall(f".//{tag}") for tag in config_tags}

        tabs = []
        for tag in config_tags:
            elements = tag_elements.get(tag, [])
            if not elements:
                continue

            if len(elements) == 1:
                columns, rows = self.element_to_rows(elements[0])
                tabs.append((tag, columns, rows))
            else:
                for i, elem in enumerate(elements):
                    columns, rows = self.element_to_rows(elem)
                    tabs.append((f"{tag} {i + 1}", columns, rows))

        return tabs

    def get_leaf_nodes(self, elem, path="", leaves=None):
        if leaves is None:
            leaves = []

        current_path = f"{path}/{elem.tag}" if path else elem.tag

        if len(elem) == 0:
            text = elem.text.strip() if elem.text else ""
            leaves.append({
                'path': current_path,
                'tag': elem.tag,
                'text': text,
                'attributes': dict(elem.attrib)
            })
        else:
            for child in elem:
                self.get_leaf_nodes(child, current_path, leaves)

        return leaves

    def parse_and_display_xml(self, file_path):
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            root = self.strip_namespaces(root)

            selected_config = self.config_var.get()
            config_tags = self.settings_manager.get_config(selected_config) if selected_config and selected_config != "No configs" else []

            if config_tags:
                tabs = self.parse_with_config(root, config_tags)
            else:
                columns, rows = self.element_to_rows(root)
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
    
    def default_filename(self, ext):
        return datetime.now().strftime(f"Output %Y-%m-%d %H%M{ext}")

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
                  command=lambda: [subprocess.Popen(f'explorer /select,"{file_path}"'), dialog.destroy()]).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Open file",
                  command=lambda: [os.startfile(file_path), dialog.destroy()]).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="OK",
                  command=dialog.destroy).pack(side=tk.LEFT, padx=5)

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
            initialfile=self.default_filename(".csv")
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
