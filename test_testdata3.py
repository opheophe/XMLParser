"""Verify no values are lost when parsing Testdata3.XML with the CAMT config."""
import sys, os, types, xml.etree.ElementTree as ET
from collections import Counter

# ── minimal tkinter stub ──────────────────────────────────────────────────────
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
tk = types.ModuleType('tkinter')
tk.Tk = _TkBase
for _n in 'Widget Frame LabelFrame Label Button Entry Text Scrollbar Canvas Menu Toplevel OptionMenu Listbox'.split():
    setattr(tk, _n, _B)
tk.StringVar = tk.IntVar = tk.BooleanVar = _Var
for _c in 'END BOTH LEFT RIGHT TOP BOTTOM X Y W E N S NW NE SW SE NSEW WORD NORMAL DISABLED ACTIVE HORIZONTAL VERTICAL FLAT RAISED SUNKEN GROOVE RIDGE SOLID CURRENT ANCHOR'.split():
    setattr(tk, _c, _c.lower())
tk.YES = True; tk.NO = False
ttk = types.ModuleType('tkinter.ttk')
for _n in 'Frame Label Button Entry Combobox Treeview Scrollbar Notebook Style Separator Progressbar'.split():
    setattr(ttk, _n, _B)
fd = types.ModuleType('tkinter.filedialog')
fd.askopenfilenames = fd.asksaveasfilename = lambda **kw: ''
mb = types.ModuleType('tkinter.messagebox')
for _n in 'showerror showwarning showinfo'.split(): setattr(mb, _n, lambda *a, **kw: None)
mb.askyesno = lambda *a, **kw: True
sys.modules.update({'tkinter': tk, 'tkinter.ttk': ttk,
                    'tkinter.filedialog': fd, 'tkinter.messagebox': mb})

PROJ     = r'C:\Users\opheo\eclipse-workspace\XMLParser\.claude\worktrees\flamboyant-northcutt-6cce8f'
SETTINGS = r'C:\Users\opheo\eclipse-workspace\XMLParser\Settings.ini'
XML_FILE = r'C:\Users\opheo\eclipse-workspace\XMLParser\Testdata\Testdata3.XML'

sys.path.insert(0, PROJ)
os.chdir(PROJ)
import XMLParser as xp

sm = xp.SettingsManager(settings_file=SETTINGS)
config_tags = sm.configs.get('CAMT', [])
merge_rules  = sm.merge_columns.get('CAMT', [])
assert config_tags, "No CAMT config found in Settings.ini"

parser = object.__new__(xp.XMLParserApp)
tree   = ET.parse(XML_FILE)
root   = parser.strip_namespaces(tree.getroot())

# ── ground truth from source XML ──────────────────────────────────────────────
# One row per Strd; RmtdAmt may be absent (→ empty string)
def strd_data(root_elem):
    """Return list of (nb, rmtd_amt) for every Strd, in document order."""
    result = []
    for strd in root_elem.iter('Strd'):
        nb   = strd.find('.//Nb')
        rmtd = strd.find('.//RmtdAmt')
        result.append((
            nb.text.strip()   if nb   is not None and nb.text   else '',
            rmtd.text.strip() if rmtd is not None and rmtd.text else '',
        ))
    return result

source_rows = strd_data(root)
total_strd  = len(source_rows)

print(f"Source XML  : {sum(1 for _ in root.iter('Ntry'))} Ntry elements")
print(f"             {total_strd} total Strd elements "
      f"({sum(1 for _,a in source_rows if a)} with RmtdAmt, "
      f"{sum(1 for _,a in source_rows if not a)} without)")

# ── run parser ────────────────────────────────────────────────────────────────
tabs = parser.parse_with_config(root, config_tags, merge_rules)
_, columns, out_rows, _ = next(t for t in tabs if t[0] == 'Ntry')
amt_col = next((c for c in columns if 'AmountCol1' in c or 'Amount' in c), None)
doc_col = next((c for c in columns if 'DocInfo' in c), None)

print(f"\nOutput      : {len(out_rows)} rows, amount col={amt_col!r}, doc col={doc_col!r}")

all_passed = True

# ── check 1: row count matches total Strd count ───────────────────────────────
print("\n--- Check 1: Row count ---")
if len(out_rows) == total_strd:
    print(f"  PASS: {len(out_rows)} output rows == {total_strd} source Strd elements")
else:
    print(f"  FAIL: {len(out_rows)} output rows != {total_strd} source Strd elements")
    all_passed = False

# ── check 2: each Strd's DocInfo (Nb) appears in output ──────────────────────
print("\n--- Check 2: Document numbers present ---")
source_nbs  = Counter(nb for nb, _ in source_rows if nb)
output_nbs  = Counter(r.get(doc_col, '') for r in out_rows if doc_col and r.get(doc_col))
missing_nbs = source_nbs - output_nbs
extra_nbs   = output_nbs - source_nbs

if not missing_nbs:
    print(f"  PASS: all {sum(source_nbs.values())} source document numbers present in output")
else:
    print(f"  FAIL: {len(missing_nbs)} document numbers missing from output:")
    for nb, cnt in list(missing_nbs.items())[:10]:
        print(f"    {nb!r} (expected {cnt}, got {output_nbs.get(nb,0)})")
    all_passed = False
if extra_nbs:
    print(f"  NOTE: {len(extra_nbs)} document numbers in output but not source "
          f"(merged/combined values may be expected)")

# ── check 3: amounts match row-by-row (by Nb key) ────────────────────────────
print("\n--- Check 3: Amount values per document number ---")
# Build source map: nb → list of amounts (in order, since Nb may repeat)
from collections import defaultdict
src_by_nb  = defaultdict(list)
for nb, amt in source_rows:
    src_by_nb[nb].append(amt)

out_by_nb = defaultdict(list)
for row in out_rows:
    nb  = row.get(doc_col, '') if doc_col else ''
    amt = row.get(amt_col, '') if amt_col else ''
    out_by_nb[nb].append(amt)

mismatches = 0
for nb, src_amts in src_by_nb.items():
    out_amts = out_by_nb.get(nb, [])
    # Strip deduplication: output may leave amount blank when same as previous row
    # for entries with only one Strd per TxDtls. We allow empty when source also empty.
    if src_amts != out_amts:
        # Check if the difference is only empty-vs-nonempty (dedup cleared it)
        mismatch_detail = [(s, o) for s, o in zip(src_amts, out_amts) if s != o and o != '']
        if mismatch_detail or len(src_amts) != len(out_amts):
            mismatches += 1
            if mismatches <= 5:
                print(f"  MISMATCH nb={nb!r}: source={src_amts} output={out_amts}")

if mismatches == 0:
    print(f"  PASS: all document amounts match (or were correctly deduplicated)")
else:
    print(f"  FAIL: {mismatches} document numbers have wrong amounts")
    all_passed = False

# ── check 4: per-entry amount sums ───────────────────────────────────────────
print("\n--- Check 4: Per-entry amount sums ---")
def to_f(s):
    try: return float((s or '').replace(',', '.'))
    except: return 0.0

entry_src_amts = []
for ntry in root.iter('Ntry'):
    entry_src_amts.append([
        (rmtd.text.strip() if rmtd.text else '')
        for strd in ntry.iter('Strd')
        for rmtd in [strd.find('.//RmtdAmt')]
        if rmtd is not None
    ])

row_idx   = 0
failed    = 0
for i, src_amts in enumerate(entry_src_amts):
    strd_count = sum(1 for _ in list(root.iter('Ntry'))[i].iter('Strd'))
    entry_rows = out_rows[row_idx:row_idx + strd_count]
    row_idx   += strd_count
    src_sum = sum(to_f(a) for a in src_amts)
    out_sum = sum(to_f(r.get(amt_col, '')) for r in entry_rows)
    if abs(src_sum - out_sum) > 0.01:
        failed += 1
        print(f"  FAIL entry {i+1}: source_sum={src_sum:.2f}  output_sum={out_sum:.2f}")
    else:
        print(f"  PASS entry {i+1}: sum={src_sum:.2f}")

if failed:
    all_passed = False

# ── summary ───────────────────────────────────────────────────────────────────
print(f"\n{'ALL CHECKS PASSED' if all_passed else 'SOME CHECKS FAILED'}")
