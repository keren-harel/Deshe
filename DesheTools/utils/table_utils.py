import arcpy
import os
import sys
from pathlib import Path
from importlib import reload
import pandas as pd

ROOT = str(Path(__file__).parents[1].absolute())  # ../pyt_framework

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if rf"{ROOT}\enums" not in sys.path:
    sys.path.insert(1, rf"{ROOT}\enums")

# Inline reloader of dynamic modules
[
    print(f"Reloaded {reload(module).__name__}")
    for module_name, module in globals().items()
    if module_name.startswith("pyt_reload")
]

# Import the Tool Importer function
import enums.domains as domains
from enums.excel_values import ExcelColumns


def load_excel_data(excel_path, sheet_name):
    return pd.read_excel(excel_path, sheet_name=sheet_name)


def add_field(layer_path, field_name, field_alias, field_type):
    arcpy.AddField_management(
        layer_path,
        field_name,
        field_type,
        field_alias=field_alias
    )


def add_domain_if_needed(gdb_path, layer_path, field_name, domain_name):
    existing_domains = [d.name for d in arcpy.da.ListDomains(gdb_path)]

    if domain_name not in existing_domains:
        arcpy.CreateDomain_management(gdb_path, domain_name, field_type="TEXT")

    domain_dict = {e.value: e.name for e in getattr(domains, domain_name)}
    for code, name in domain_dict.items():
        arcpy.AddCodedValueToDomain_management(gdb_path, domain_name, name, code)

    arcpy.AssignDomainToField_management(layer_path, field_name, domain_name)


def set_default_value(layer_path, field_name, default_value):
    arcpy.management.CalculateField(
        layer_path,
        field_name,
        default_value,
        "PYTHON3"
    )

def get_layer_fields(layer_path):
    return [field.name for field in arcpy.ListFields(layer_path)]

def create_field(gdb_path, layer_name, field_name, field_alias, field_type, domain_name, default_value ):
    layer_path = os.path.join(gdb_path, layer_name)

    layer_fields = get_layer_fields(layer_path)
    if field_name not in layer_fields:
        add_field(layer_path, field_name, field_alias, field_type)

    if pd.notna(domain_name):
        add_domain_if_needed(gdb_path, layer_path, field_name, domain_name)

    if pd.notna(default_value):
        set_default_value(layer_path, field_name, default_value)


def add_fields_to_layer_from_excel(layer_df, layer_name, gdb_path):

    for _, row in layer_df.iterrows():
        field_name = row[ExcelColumns.NAME.value]
        field_alias = row[ExcelColumns.ALIAS.value]
        field_type = row[ExcelColumns.TYPE.value]
        domain_name = row[ExcelColumns.DOMAIN.value]
        default_value = row[ExcelColumns.DEFAULT_VALUE.value]

        create_field(gdb_path, layer_name, field_name, field_alias, field_type, domain_name, default_value)

def verify_required_fields(layer_path, layer_df):
    layer_fields = get_layer_fields(layer_path)

    common_error_df = layer_df[
    layer_df[ExcelColumns.COMMON_ERROR.value].notna() &
    layer_df[ExcelColumns.EXISTS.value].notna()
]

    # Handle common errors and rename fields
    for _, row in common_error_df.iterrows():
        if row[ExcelColumns.COMMON_ERROR.value] in layer_fields and row[ExcelColumns.NAME.value] not in layer_fields:
            arcpy.management.AlterField(
                in_table=layer_path,
                field=row[ExcelColumns.COMMON_ERROR.value],
                new_field_name=row[ExcelColumns.NAME.value],
                new_field_alias=row[ExcelColumns.ALIAS.value]
            )

    layer_fields = get_layer_fields(layer_path)
    exists_layer_df = layer_df[layer_df[ExcelColumns.EXISTS.value].notna()][ExcelColumns.NAME.value].tolist()

    missing_fields = [field for field in exists_layer_df if field not in layer_fields]

    if missing_fields:
        arcpy.AddError(f"The following fields are missing in the input layer: {', '.join(missing_fields)}")
        return False

    return True


def remove_extra_fields_from_layer(layer_df, layer_path):

    layer_fields = [field.name for field in arcpy.ListFields(layer_path) if not field.required]
    fields_to_delete = [field for field in layer_fields if field not in layer_df[ExcelColumns.NAME.value].values]

    if fields_to_delete:
        arcpy.DeleteField_management(layer_path, fields_to_delete)