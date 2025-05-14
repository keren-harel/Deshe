import arcpy
import sys
import os
from pathlib import Path
from importlib import reload


ROOT = str(Path(__file__).parents[1].absolute())
sys.path.append(str(ROOT))

import utils.table_utils as pyt_reload_table_utils

[
    print(f"Reloaded {reload(module).__name__}")
    for module_name, module in globals().items()
    if module_name.startswith("pyt_reload")
]


import utils.table_utils as table_utils
import enums.excel_values as excel_values


SHEET_NAME = "table_modification"

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

    df = pyt_reload_table_utils.load_excel_data(excel_path, SHEET_NAME)
    layer_df = df[df[excel_values.ExcelColumns.TABLE_NAME.value] == layer_name]
    pyt_reload_table_utils.add_fields_to_layer_from_excel(layer_df, layer_name, gdb_path)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    active_map = aprx.activeMap
    active_map.addDataFromPath(os.path.join(gdb_path, layer_name))

if __name__ == "__main__":
    layer_name = arcpy.GetParameter(0)
    execute(layer_name)
