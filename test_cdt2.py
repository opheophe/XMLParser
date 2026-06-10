"""Trace CdtNoteAmt through element_to_rows for each Ntry."""
import sys, types
for mod in ['tkinter','tkinter.ttk','tkinter.filedialog','tkinter.messagebox']:
    sys.modules[mod] = types.ModuleType(mod)
import tkinter as tk
for name in ['Tk','Toplevel','Frame','Label','Button','Entry','Listbox',
             'Scrollbar','Canvas','Menu','StringVar','BooleanVar','Text',
             'END','BOTH','X','Y','W','LEFT','RIGHT','TOP','BOTTOM','WORD','NORMAL','DISABLED']:
    setattr(tk, name, type(name, (), {'__init__': lambda s,*a,**k:None}))

import XMLParser as xp
import xml.etree.ElementTree as ET, re

with open('Testdata/Testdata4.XML', 'r', encoding='utf-8') as f:
    content = f.read()
content = re.sub(r' xmlns[^"]*"[^"]*"', '', content)
root = ET.fromstring(content)

class FakeApp(xp.XMLParserApp):
    def __init__(self): pass

app = FakeApp()
app.strip_namespaces(root)

ntries = root.findall('.//Ntry')
print(f'Total Ntry elements: {len(ntries)}')

for i, ntry in enumerate(ntries):
    cols, rows = app.element_to_rows(ntry)
    cdt = [c for c in cols if 'CdtNote' in c]
    if cdt:
        print(f'Ntry[{i}]: CdtNoteAmt cols found: {cdt}')
        vals = [r.get(cdt[0],'') for r in rows if r.get(cdt[0],'')]
        print(f'  values: {vals[:5]}')
    else:
        print(f'Ntry[{i}]: no CdtNoteAmt (rows={len(rows)}, total cols={len(cols)})')
        # Check if any leaf has CdtNoteAmt
        all_leaf_lists = app.collect_flat_records(ntry)
        cdt_leaves = [leaf for ll in all_leaf_lists for leaf in ll if 'CdtNote' in leaf['path']]
        if cdt_leaves:
            print(f'  BUT collect_flat_records has {len(cdt_leaves)} CdtNote leaves:')
            print(f'    {cdt_leaves[:3]}')
