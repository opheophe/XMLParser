"""Verify CdtNoteAmt appears after the fix."""
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

config_tags = ['GrpHdr; Yes', 'Acct; Yes', 'TxsSummry; Yes', 'Ntry; No']
merge_rules = [
    'New Line; Strd/RfrdDocAmt/RmtdAmt@Value; AmountCol1; Amount',
    'New Line; Strd/RfrdDocAmt/RmtdAmt@Ccy; Currency;',
]

tabs = app.parse_with_config(root, config_tags, merge_rules)
for tab_name, cols, rows, _ in tabs:
    cdt = [c for c in cols if 'CdtNote' in c]
    print(f'Tab: {tab_name}  rows={len(rows)}  CdtNoteAmt cols: {cdt}')
    if cdt:
        vals = [r.get(cdt[0], '') for r in rows if r.get(cdt[0], '')]
        print(f'  values: {vals[:5]}')
    if tab_name == 'Ntry' and not cdt:
        print('  FAIL: CdtNoteAmt missing from Ntry tab')
