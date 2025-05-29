import arcpy
import sys
import os
from pathlib import Path
from importlib import reload


DESHE_TOOLS_FOLDER_PATH = str(Path(__file__).parents[1].absolute())

def add_to_root(folders):
    if DESHE_TOOLS_FOLDER_PATH not in sys.path:
        sys.path.insert(0, DESHE_TOOLS_FOLDER_PATH)
    for folder in folders:
        if rf"{DESHE_TOOLS_FOLDER_PATH}\{folder}" not in sys.path:
            sys.path.insert(1, rf"{DESHE_TOOLS_FOLDER_PATH}\{folder}")


add_to_root(['utils', 'enums'])

import table_utils
reload(table_utils)
import excel_values
reload(excel_values)

SHEET_NAME = "table_modification"


def execute(layer_name):

    SPATIAL_REFERENCE = arcpy.SpatialReference(2039)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    gdb_path = aprx.defaultGeodatabase
    configuration_path = os.path.join(DESHE_TOOLS_FOLDER_PATH, "configuration")
    excel_path = os.path.join(configuration_path, "fields.xlsx")

    arcpy.env.overwriteOutput = True
    arcpy.CreateFeatureclass_management(gdb_path,
                                        layer_name,
                                        "Polyline",
                                        spatial_reference=SPATIAL_REFERENCE)

    df = table_utils.load_excel_data(excel_path, SHEET_NAME)
    layer_df = df[df[excel_values.ExcelColumns.TABLE_NAME.value] == layer_name]
    table_utils.add_fields_to_layer_from_excel(layer_df, layer_name, gdb_path)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    active_map = aprx.activeMap
    active_map.addDataFromPath(os.path.join(gdb_path, layer_name))

if __name__ == "__main__":
    layer_name = arcpy.GetParameter(0)
    execute(layer_name)
