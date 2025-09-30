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
]

CATEGORY_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}

def missing_columns(df):
    return [c for c in REQUIRED_COLUMNS if c not in df.columns]
