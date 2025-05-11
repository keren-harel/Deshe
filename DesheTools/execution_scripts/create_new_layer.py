import arcpy
import sys
import os
from pathlib import Path
from importlib import reload

ROOT = str(Path(__file__).parents[1].absolute())
SHEET_NAME = "table_modification"

def add_to_root(folders):
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    for folder in folders:
        if rf"{ROOT}\{folder}" not in sys.path:
            sys.path.insert(1, rf"{ROOT}\{folder}")

add_to_root(['utils', 'enums', 'configuration'])

# Import dynamic modules with pyt_reload prefix
import utils.table_utils as pyt_reload_table_utils
import enums.excel_values as pyt_reload_excel_values

# Inline reloader of dynamic modules
[
    print(f"Reloaded {reload(module).__name__}")
    for module_name, module in globals().items()
    if module_name.startswith("pyt_reload")
]

# Import the Tool Importer function
from utils.table_utils import *
from enums.excel_values import LayerNameExcel

def execute(layer_name):

    SPATIAL_REFERENCE = arcpy.SpatialReference(2039)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    gdb_path = aprx.defaultGeodatabase
    configuration_path = os.path.join(ROOT, "configuration")
    excel_path = os.path.join(configuration_path, "fields.xlsx")

    arcpy.env.overwriteOutput = True
    arcpy.CreateFeatureclass_management(gdb_path,
                                        layer_name,
                                        "Polyline",
                                        spatial_reference=SPATIAL_REFERENCE)

    df = load_excel_data(excel_path, SHEET_NAME)
    layer_df = df[df[ExcelColumns.TABLE_NAME.value] == layer_name]
    add_fields_to_layer_from_excel(layer_df, layer_name, gdb_path)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    active_map = aprx.activeMap
    active_map.addDataFromPath(os.path.join(gdb_path, layer_name))

if __name__ == "__main__":
    layer_name = arcpy.GetParameter(0)
    execute(layer_name)