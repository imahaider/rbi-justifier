# core/schema.py

REQUIRED_COLUMNS = [
    "Component",
    "Risk Category",
    "Driving PoF",
    "Int Corr Rate",
    "Ext Corr Rate",
    "Inspection Priority",
    "Flamm Conseq Categ",
    "Toxic Conseq Cat",
    "Lost Production Category",
    "Representative Fluid",
    "Fluid Type",
    "Initial Fluid Phase",
    "Toxic Fluid",
    "Inventory",
    "Flammable Affected Area",
    "Int Controlling Corrosion Rate",   # NEW: preferred CCR input column
]

# Back-compat alias (optional). The app still works if older sheets use this.
OPTIONAL_COLUMNS = [
    "Controlling Corr Rate",
]

CATEGORY_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}  # lower = worse

def missing_columns(df):
    return [c for c in REQUIRED_COLUMNS if c not in df.columns]
