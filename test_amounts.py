"""Row-by-row check: is every Strd's RmtdAmt correctly represented in the output?"""
import sys, os, types, xml.etree.ElementTree as ET
from collections import defaultdict

# ── tkinter stub ──────────────────────────────────────────────────────────────
_B = type('_B', (), {'__init__': lambda self, *a, **kw: None,
                     '__getattr__': lambda self, n: (lambda *a, **kw: None)})
class _Var:
    def __init__(self, *a, **kw): self._v = kw.get('value', '')
    def get(self): return self._v
    def set(self, v): self._v = v
    def trace_add(self, *a, **kw): pass
    def __getattr__(self, n): return lambda *a, **kw: None
_TkBase = type('Tk', (_B,), {
    'winfo_screenwidth': lambda self: 1920, 'winfo_screenheight': lambda self: 1080,
    'winfo_x': lambda self: 0, 'winfo_y': lambda self: 0,
    'winfo_width': lambda self: 1000, 'winfo_height': lambda self: 700,
    'update_idletasks': lambda self: None, 'geometry': lambda self, *a: None,
})
tk = types.ModuleType('tkinter'); tk.Tk = _TkBase
for _n in 'Widget Frame LabelFrame Label Button Entry Text Scrollbar Canvas Menu Toplevel OptionMenu Listbox'.split():
    setattr(tk, _n, _B)
tk.StringVar = tk.IntVar = tk.BooleanVar = _Var
for _c in 'END BOTH LEFT RIGHT TOP BOTTOM X Y W E N S NW NE SW SE NSEW WORD NORMAL DISABLED ACTIVE HORIZONTAL VERTICAL FLAT RAISED SUNKEN GROOVE RIDGE SOLID CURRENT ANCHOR'.split():
    setattr(tk, _c, _c.lower())
tk.YES = True; tk.NO = False
ttk = types.ModuleType('tkinter.ttk')
for _n in 'Frame Label Button Entry Combobox Treeview Scrollbar Notebook Style Separator Progressbar'.split():
    setattr(ttk, _n, _B)
fd = types.ModuleType('tkinter.filedialog'); fd.askopenfilenames = fd.asksaveasfilename = lambda **kw: ''
mb = types.ModuleType('tkinter.messagebox')
for _n in 'showerror showwarning showinfo'.split(): setattr(mb, _n, lambda *a, **kw: None)
mb.askyesno = lambda *a, **kw: True
sys.modules.update({'tkinter': tk, 'tkinter.ttk': ttk, 'tkinter.filedialog': fd, 'tkinter.messagebox': mb})

PROJ     = r'C:\Users\opheo\eclipse-workspace\XMLParser\.claude\worktrees\flamboyant-northcutt-6cce8f'
SETTINGS = r'C:\Users\opheo\eclipse-workspace\XMLParser\Settings.ini'
XML_FILE = r'C:\Users\opheo\eclipse-workspace\XMLParser\Testdata\Testdata3.XML'

sys.path.insert(0, PROJ); os.chdir(PROJ)
import XMLParser as xp

sm     = xp.SettingsManager(settings_file=SETTINGS)
parser = object.__new__(xp.XMLParserApp)
tree   = ET.parse(XML_FILE)
root   = parser.strip_namespaces(tree.getroot())

config_tags = sm.configs.get('CAMT', [])
merge_rules  = sm.merge_columns.get('CAMT', [])

# ── source: one entry per Strd, in document order ────────────────────────────
source = []   # (ntry_idx, strd_idx, nb, rmtd_amt)
for ntry_i, ntry in enumerate(root.iter('Ntry')):
    for strd_i, strd in enumerate(ntry.iter('Strd')):
        nb   = strd.find('.//Nb')
        rmtd = strd.find('.//RmtdAmt')
        source.append((
            ntry_i,
            strd_i,
            nb.text.strip()   if nb   is not None and nb.text   else '',
            rmtd.text.strip() if rmtd is not None and rmtd.text else '',
        ))

# ── output ────────────────────────────────────────────────────────────────────
tabs = parser.parse_with_config(root, config_tags, merge_rules)
_, columns, out_rows, _ = next(t for t in tabs if t[0] == 'Ntry')
amt_col = next((c for c in columns if 'AmountCol1' in c or 'Amount' in c), None)
doc_col = next((c for c in columns if 'DocInfo' in c), None)

print(f"Source Strd elements : {len(source)}")
print(f"Output rows          : {len(out_rows)}")
print(f"Amount column        : {amt_col!r}")

assert len(source) == len(out_rows), \
    f"Row count mismatch: {len(source)} source vs {len(out_rows)} output — cannot do row-by-row check"

# ── row-by-row comparison ─────────────────────────────────────────────────────
# Deduplication may blank the amount if it is identical to the previous row.
# We track the "last seen" amount per entry to reconstruct the intended value.
errors = []
last_amt = {}   # ntry_idx -> last non-empty output amount

for i, (ntry_i, strd_i, src_nb, src_amt) in enumerate(source):
    out_amt = out_rows[i].get(amt_col, '') if amt_col else ''
    out_doc = out_rows[i].get(doc_col, '') if doc_col else ''

    # Update last-seen tracker
    if out_amt:
        last_amt[ntry_i] = out_amt

    # Decide expected output amount:
    # - Empty source → output should be empty (no RmtdAmt in this Strd)
    # - Non-empty source:
    #     output is non-empty  → must equal source
    #     output is empty      → must be a dedup-cleared duplicate of previous row
    if src_amt == '':
        if out_amt != '':
            errors.append((i, ntry_i, strd_i, src_nb, src_amt, out_amt, out_doc,
                           f"expected empty (no RmtdAmt in source), got {out_amt!r}"))
    else:
        if out_amt != '':
            if out_amt != src_amt:
                errors.append((i, ntry_i, strd_i, src_nb, src_amt, out_amt, out_doc,
                               f"WRONG AMOUNT: source={src_amt!r} output={out_amt!r}"))
        else:
            # Output is empty: OK only if dedup is responsible
            # (i.e. previous non-empty output amount equals src_amt)
            prev = last_amt.get(ntry_i, '')
            if prev != src_amt:
                errors.append((i, ntry_i, strd_i, src_nb, src_amt, out_amt, out_doc,
                               f"MISSING AMOUNT: source={src_amt!r}, last seen={prev!r} — not a dedup blank"))

# ── report ────────────────────────────────────────────────────────────────────
if not errors:
    print(f"\nPASS — all {len(source)} rows have correct amounts (dedup blanks verified)")
else:
    print(f"\nFAIL — {len(errors)} problem rows:\n")
    for row_i, ntry_i, strd_i, nb, src, out, doc, reason in errors[:20]:
        print(f"  row {row_i:4d}  Ntry[{ntry_i}] Strd[{strd_i}]  nb={nb!r}")
        print(f"         DocInfo={doc!r}")
        print(f"         {reason}")
        print()
    if len(errors) > 20:
        print(f"  ... and {len(errors)-20} more")
