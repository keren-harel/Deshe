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
        arcpy.AddMessage(f"start! {folder}")
        if rf"{DESHE_TOOLS_FOLDER_PATH}\{folder}" not in sys.path:
            arcpy.AddMessage(f"here! {folder}")
            sys.path.insert(1, rf"{DESHE_TOOLS_FOLDER_PATH}\{folder}")


add_to_root(['utils', 'enums'])

import table_utils
reload(table_utils)
import excel_values
reload(excel_values)

SHEET_NAME = "table_modification"

def execute(layer_name_excel,layer_path):

    configuration_path = os.path.join(DESHE_TOOLS_FOLDER_PATH, "configuration")
    excel_path = os.path.join(configuration_path, "fields.xlsx")
    gdb_path = os.path.dirname(layer_path)
    layer_name = os.path.basename(layer_path)

    df = table_utils.load_excel_data(excel_path, SHEET_NAME)
    layer_df = df[df[excel_values.ExcelColumns.TABLE_NAME.value] == layer_name_excel]

    is_verified = table_utils.verify_required_fields(layer_path, layer_df)
    if not is_verified:
        return

    table_utils.remove_extra_fields_from_layer(layer_df, layer_path)

    to_add_df = layer_df[layer_df[excel_values.ExcelColumns.TO_ADD.value].notna()]
    table_utils.add_fields_to_layer_from_excel(to_add_df, layer_name, gdb_path)


if __name__ == "__main__":
    layer_name_excel = arcpy.GetParameterAsText(0)
    layer_name = arcpy.GetParameterAsText(1)
    desc = arcpy.Describe(layer_name)
    gdb_path = desc.path
    layer_path = os.path.join(gdb_path, layer_name)

    execute(layer_name_excel, layer_path)

