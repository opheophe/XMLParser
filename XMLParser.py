import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import configparser
import os
from pathlib import Path
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
        self.upper_frame = tk.Frame(self, height=160)  # 20% of 800
        self.upper_frame.pack(fill=tk.X)
        self.upper_frame.pack_propagate(False)
        
        self.lower_frame = tk.Frame(self)
        self.lower_frame.pack(fill=tk.BOTH, expand=True)
        
        # Upper frame contents (left-aligned)
        button_frame = tk.Frame(self.upper_frame)
        button_frame.pack(pady=20, padx=20, anchor=tk.W)
        
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
        
        # Lower frame - Treeview with scrollbars
        self.tree_frame = tk.Frame(self.lower_frame)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Treeview
        self.tree = ttk.Treeview(self.tree_frame)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbars
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = ttk.Scrollbar(self.lower_frame, orient="horizontal", command=self.tree.xview)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Store parsed data
        self.parsed_data = []
        self.current_columns = []
    
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
            elif current == "No configs":
                self.config_var.set(config_names[0])
            elif current and current not in config_names:
                # Previously selected config was deleted, select next one
                self.config_var.set(config_names[0] if config_names else "No configs")
    
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
    
    def parse_and_display_xml(self, file_path):
        try:
            # Parse XML and strip namespaces
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Strip all namespaces from the tree
            root = self.strip_namespaces(root)
            
            # Find deepest repeating element tag
            record_tag = self.find_deepest_repeating_tag(root)
            
            if not record_tag:
                messagebox.showwarning("Warning", "No repeating elements found in XML.")
                return
            
            print(f"Found repeating tag: {record_tag}")
            
            # Find all elements with this tag
            records = root.findall(f".//{record_tag}")
            
            if not records:
                messagebox.showwarning("Warning", f"No records found with tag '{record_tag}'.")
                return
            
            # Collect all possible columns by sampling records
            all_columns = set()
            for record in records[:50]:  # Sample first 50
                cols = self.get_element_columns(record)
                all_columns.update(cols)
            
            self.current_columns = sorted(all_columns)
            
            # Convert records to rows
            self.parsed_data = []
            for record in records:
                row = self.element_to_row(record, self.current_columns)
                self.parsed_data.append(row)
            
            # Display in treeview
            self.display_in_treeview()
            self.export_button.config(state="normal")
            
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
    
    def get_element_columns(self, elem, prefix=""):
        """Get all column paths from an element"""
        columns = set()
        
        current_path = f"{prefix}/{elem.tag}" if prefix else elem.tag
        
        # Add text content column (even if has children, element might have text)
        columns.add(current_path)
        
        # Add attributes
        for attr in elem.attrib:
            attr_col = f"{current_path}@{attr}"
            columns.add(attr_col)
        
        # Recurse into children
        for child in elem:
            columns.update(self.get_element_columns(child, current_path))
        
        return columns
    
    def element_to_row(self, elem, columns, prefix=""):
        """Convert element to row dict"""
        row = {col: "" for col in columns}
        
        # Current path
        current_path = f"{prefix}/{elem.tag}" if prefix else elem.tag
        
        # Text content (not just leaf nodes - capture from all elements)
        if elem.text and elem.text.strip():
            if current_path in row:
                row[current_path] = elem.text.strip()
        
        # Attributes
        for attr, value in elem.attrib.items():
            attr_col = f"{current_path}@{attr}"
            if attr_col in row:
                row[attr_col] = value
        
        # Recurse into children
        for child in elem:
            child_row = self.element_to_row(child, columns, current_path)
            for col, val in child_row.items():
                if val:
                    row[col] = val
        
        return row
    
    def find_deepest_repeating_tag(self, root):
        """Find the deepest XPath where elements repeat"""
        all_paths = []
        
        def get_tag(elem):
            """Get tag without namespace"""
            if '}' in elem.tag:
                return elem.tag.split('}')[-1]
            return elem.tag
        
        def traverse(elem, path="", depth=0):
            tag = get_tag(elem)
            
            # Build path
            if path:
                current_path = f"{path}/{tag}"
            else:
                current_path = tag
            
            # Count children of same tag
            child_tags = {}
            children = list(elem)
            for child in children:
                child_tag = get_tag(child)
                child_tags[child_tag] = child_tags.get(child_tag, 0) + 1
            
            # Find repeating children at this level
            for child_tag, count in child_tags.items():
                if count > 1:
                    # Build simple XPath - just the repeating tag name
                    # Pandas works better with simple tag names
                    all_paths.append((depth, child_tag, count))
            
            # Recurse deeper
            for child in children:
                traverse(child, current_path, depth + 1)
        
        traverse(root)
        
        if not all_paths:
            return None
        
        # Sort by depth (shallowest first) - this is the record level
        # Shallowest repeating element = the actual record container
        all_paths.sort(key=lambda x: x[0])  # Shallowest first
        record_tag = all_paths[0][1]
        record_depth = all_paths[0][0]
        print(f"Found {all_paths[0][2]} repeating elements with tag: {record_tag} at depth {record_depth}")
        
        return record_tag
    
    def flatten_dataframe(self, df):
        """Recursively flatten nested columns in DataFrame"""
        max_depth = 10  # Prevent infinite loops
        
        for _ in range(max_depth):
            needs_flattening = False
            new_df = df.copy()
            
            for col in list(new_df.columns):
                # Check if column contains dictionaries or lists
                sample = new_df[col].dropna().iloc[0] if not new_df[col].dropna().empty else None
                
                if isinstance(sample, dict):
                    needs_flattening = True
                    # Flatten dict column
                    flattened = new_df[col].apply(lambda x: x if isinstance(x, dict) else {})
                    for key in flattened.iloc[0].keys() if flattened.iloc[0] else []:
                        new_df[f"{col}/{key}"] = flattened.apply(lambda x: x.get(key, ""))
                    new_df = new_df.drop(columns=[col])
                    
                elif isinstance(sample, list) and len(sample) > 0 and isinstance(sample[0], dict):
                    needs_flattening = True
                    # For now, skip list columns or convert to string
                    new_df[col] = new_df[col].apply(lambda x: str(x) if isinstance(x, list) else x)
            
            df = new_df
            if not needs_flattening:
                break
        
        return df
    
    def display_in_treeview(self):
        """Display parsed data in Treeview"""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Configure columns
        self.tree["columns"] = self.current_columns
        self.tree["show"] = "headings"
        
        # Set column headings
        for col in self.current_columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, minwidth=50)
        
        # Insert data
        for i, row in enumerate(self.parsed_data[:1000]):  # Limit to 1000 rows for performance
            values = [row.get(col, "") for col in self.current_columns]
            self.tree.insert("", tk.END, values=values)
    
    def export_csv(self):
        """Export parsed data to CSV"""
        if not self.parsed_data:
            messagebox.showwarning("Warning", "No data to export.")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Export to CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            defaultextension=".csv"
        )
        
        if not file_path:
            return
        
        try:
            # Create DataFrame from parsed data and export
            df = pd.DataFrame(self.parsed_data, columns=self.current_columns)
            df.to_csv(file_path, index=False, encoding='utf-8')
            
            messagebox.showinfo("Success", f"Exported {len(self.parsed_data)} rows to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {str(e)}")


if __name__ == "__main__":
    app = XMLParserApp()
    app.mainloop()
