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


def execute(layer_name_excel,layer_path):

    configuration_path = os.path.join(ROOT, "configuration")
    excel_path = os.path.join(configuration_path, "fields.xlsx")
    gdb_path = os.path.dirname(layer_path)
    layer_name = os.path.basename(layer_path)

    df = load_excel_data(excel_path, SHEET_NAME)
    layer_df = df[df[ExcelColumns.TABLE_NAME.value] == layer_name_excel]

    is_verified = verify_required_fields(layer_path, layer_df)
    if not is_verified:
        return

    remove_extra_fields_from_layer(layer_df, layer_path)

    to_add_df = layer_df[layer_df[ExcelColumns.TO_ADD.value].notna()]
    add_fields_to_layer_from_excel(to_add_df, layer_name, gdb_path)


if __name__ == "__main__":
    layer_name_excel = arcpy.GetParameterAsText(0)
    layer_name = arcpy.GetParameterAsText(1)
    desc = arcpy.Describe(layer_name)
    gdb_path = desc.path
    layer_path = os.path.join(gdb_path, layer_name)

    execute(layer_name_excel, layer_path)

