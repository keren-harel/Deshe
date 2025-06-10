
import arcpy
import os

def validate_geodatabase(gdb_path):
    """
    Validates if the provided path is a valid ArcGIS geodatabase and loads datasets.

    Args:
        gdb_path (str): The path to the geodatabase.

    Returns:
        list: List of feature classes and tables if valid, otherwise raises an error.
    """
    try:
        # Check if the geodatabase exists
        if not os.path.exists(gdb_path):
            raise Exception(f"Geodatabase does not exist: {gdb_path}")

        # Set workspace environment
        arcpy.env.workspace = gdb_path

        # Check if the workspace is a valid geodatabase
        desc = arcpy.Describe(gdb_path)
        if desc.workspaceType != "LocalDatabase":
            raise Exception(f"Workspace is not a valid geodatabase: {gdb_path}. Workspace type is: {desc.workspaceType}")

        # Load datasets
        list_Feature_Classes = arcpy.ListFeatureClasses()
        list_Tables = arcpy.ListTables()
        datasets = list_Feature_Classes + list_Tables

        # Check if datasets were loaded
        if not datasets:
            arcpy.AddWarning("Warning: Geodatabase is valid, but no Feature Classes or Tables were found.")
            return []

        arcpy.AddMessage("Success: Geodatabase and datasets loaded successfully.")
        return datasets

    except Exception as e:
        arcpy.AddError(f"Error: Geodatabase validation failed. {e}")
        return []

def process_point_layers(points_base, points_add, source_guid_field="globalid"):
    """
    Appends data from one point layer to another after preparing a custom GUID field.

    Args:
        points_base (str): The name of the base point layer.
        points_add (str): The name of the point layer to append.
        source_guid_field (str): The name of the GUID field in the source layer (e.g., "globalid").
    """
    print(f"Processing point layers: {points_add} to {points_base}")

    # Define the temporary field name for GUID in points_add
    temp_guid_field_add = "Apres" + source_guid_field.capitalize() # Capitalize for field name consistency
    
    # Add and calculate the temporary GUID field for the layer to be appended
    if temp_guid_field_add not in [field.name for field in arcpy.ListFields(points_add)]:
        arcpy.management.AddField(points_add, temp_guid_field_add, "GUID")
        print(f"Added {temp_guid_field_add} to {points_add}")
    arcpy.management.CalculateField(points_add, temp_guid_field_add, f"!{source_guid_field}!", "PYTHON3")
    print(f"Calculated {temp_guid_field_add} for {points_add} using {source_guid_field}")

    # Define the temporary field name for GUID in points_base
    temp_guid_field_base = "Apres" + source_guid_field.capitalize() # Capitalize for field name consistency

    # Add the temporary GUID field to the base layer if it doesn't exist
    if temp_guid_field_base not in [field.name for field in arcpy.ListFields(points_base)]:
        arcpy.management.AddField(points_base, temp_guid_field_base, "GUID")
        print(f"Added {temp_guid_field_base} to {points_base}")
    else:
        print(f"{temp_guid_field_base} already exists in {points_base}. Skipping field creation.")

    # Append points
    arcpy.management.Append(inputs=[points_add], target=points_base, schema_type="NO_TEST")
    print(f"Appended {points_add} into {points_base}.")


def process_related_table(add_table, base_table, points_base, join_field_add, source_guid_field_points, related_guid_field="ParentGlobalID", points_base_guid_field="ApresGlobalID"):
    """
    Processes and appends data from one related table to another, updating a related GUID field.

    Args:
        add_table (str): The name of the table to append.
        base_table (str): The name of the base table.
        points_base (str): The name of the base point layer (used for joining).
        join_field_add (str): The field in 'add_table' used for joining (e.g., "stand_ID").
        source_guid_field_points (str): The original GUID field name in the points_base layer (e.g., "globalid").
        related_guid_field (str): The name of the related GUID field in 'add_table' to update (e.g., "ParentGlobalID").
        points_base_guid_field (str): The name of the GUID field in 'points_base' used for the join and update (e.g., "ApresGlobalID").
    """
    print(f"Processing related table: {add_table} to {base_table}")

    # Add a temporary field for storing base GUIDs
    temp_global_id_field = "Table_add_Temp_GUID"
    if temp_global_id_field not in [field.name for field in arcpy.ListFields(add_table)]:
        arcpy.management.AddField(add_table, temp_global_id_field, "GUID")
        print(f"Added {temp_global_id_field} to {add_table}")
    else:
        print(f"{temp_global_id_field} already exists in {add_table}. Skipping field creation.")

    # Add join to link the add_table with the points_base layer
    joined_table_view_name = os.path.basename(add_table) # Use original table name as the view name

    # Note: We capture the result of AddJoin to ensure we operate on the correct view
    # even though it's not directly used for RemoveJoin in this modified version.
    arcpy.management.AddJoin(add_table, join_field_add, points_base, points_base_guid_field, "KEEP_ALL")
    print(f"Joined {add_table} with {points_base} using {join_field_add} and {points_base_guid_field}")

    # Calculate the new global variables in the temporary field
    # The 'joined_table_view_name' string should still work here as the view is active.
    arcpy.management.CalculateField(joined_table_view_name, temp_global_id_field, f"!{source_guid_field_points}!", "PYTHON3")
    print(f"Calculated {temp_global_id_field} using {source_guid_field_points} from {points_base}")

    # Calculate the related_guid_field in add_table using the temporary field
    arcpy.management.CalculateField(joined_table_view_name, related_guid_field, f"!{temp_global_id_field}!", "PYTHON3")
    print(f"Calculated {related_guid_field} in {add_table} using {temp_global_id_field}")

    # Remove the join - This line is commented out as per your request
    # arcpy.management.RemoveJoin(joined_table_view_name, os.path.basename(points_base))
    # print(f"Removed join from {add_table}")

    # Delete the temporary field
    arcpy.management.DeleteField(add_table, [temp_global_id_field])
    print(f"Deleted temporary field {temp_global_id_field} from {add_table}")

    # Append the processed table into the base table
    arcpy.management.Append(inputs=[add_table], target=base_table, schema_type="NO_TEST")
    print(f"Processed and appended {add_table} into {base_table}.")

if __name__ == "__main__":
    # Get the current ArcGIS Pro project and its default geodatabase
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    gdb_path = aprx.defaultGeodatabase
    arcpy.env.workspace = gdb_path

    print(f"Default Geodatabase: {gdb_path}")

    # Validate the geodatabase
    datasets = validate_geodatabase(gdb_path)
    if not datasets:
        print("Geodatabase validation failed or no datasets found. Exiting script.")
        raise SystemExit

    print("Geodatabase validation successful. Datasets found:")
    for dataset in datasets:
        print(f"- {dataset}")

    # --- Define common GUID field names ---
    # This is the original GUID field name in the source data (e.g., "globalid")
    SOURCE_GUID_FIELD = "globalid"

    # This is the field in the base point layer that stores the GUID for post-append operations
    # It's generated as "Apres" + SOURCE_GUID_FIELD (capitalized) in process_point_layers
    APRES_GUID_FIELD_FOR_POINTS = "Apres" + SOURCE_GUID_FIELD.capitalize()


    # --- Define point layers (only for 'samples') ---
    points_base_samples = "smy_Tzora"
    points_add_samples = "smy_Tzora_1"

    # --- Define related tables for 'samples' ---
    # Assuming 'parentglobalid' is the correct common field linking 'samples' point layer to its related tables
    samples_join_field = "parentglobalid"

    related_tables_info = {
        "PlantTypeCoverDistribut": {
            "base_name": "PlantTypeCoverDistribut",
            "add_name": "PlantTypeCoverDistribut_1",
            "join_field": samples_join_field
        },
        "VitalForest": {
            "base_name": "VitalForest",
            "add_name": "VitalForest_1",
            "join_field": samples_join_field
        },
        "InvasiveSpecies": {
            "base_name": "InvasiveSpecies",
            "add_name": "InvasiveSpecies_1",
            "join_field": samples_join_field
        },
        "StartRepeatDominTree": {
            "base_name": "StartRepeatDominTree",
            "add_name": "StartRepeatDominTree_1",
            "join_field": samples_join_field
        }
    }

    # --- Process point layer for 'samples' ---
    print("\n--- Starting Point Layer Processing (Samples) ---")
    process_point_layers(points_base_samples, points_add_samples, SOURCE_GUID_FIELD)
    print("--- Finished Point Layer Processing (Samples) ---\n")

    # --- Process related tables for 'samples' ---
    print("\n--- Starting Related Table Processing (Samples) ---")
    for table_name, info in related_tables_info.items():
        print(f"\nProcessing related table: {table_name}")
        process_related_table(
            add_table=info["add_name"],
            base_table=info["base_name"],
            points_base=points_base_samples,
            join_field_add=info["join_field"],
            source_guid_field_points=SOURCE_GUID_FIELD,
            related_guid_field="ParentGlobalID",
            points_base_guid_field=APRES_GUID_FIELD_FOR_POINTS
        )
    print("--- Finished Related Table Processing (Samples) ---")

    print("\nScript completed successfully.")
