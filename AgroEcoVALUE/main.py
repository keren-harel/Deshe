
# -*- coding: utf-8 -*-
import arcpy
import os
import re
from eco_score_enum import CorridorScore, FloodplainScore

# Validate if the provided path is a valid ArcGIS geodatabase and load datasets
def validate_geodatabase(gdb_path):
    """
    Validates if the provided path is a valid ArcGIS geodatabase and loads datasets.
    Args:
        gdb_path (str): The path to the geodatabase.
    Returns:
        str: A success message if the geodatabase is valid and datasets are loaded,
             or an error message if any validation fails.
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
            return "Warning: Geodatabase is valid, but no Feature Classes or Tables were found."
        return "Success: Geodatabase and datasets loaded successfully."
    except Exception as e:
        return f"Error: Geodatabase validation failed. {e}"

# Path to geodatabase
gdb_path = r"C:\\Users\\galisraeli\\Documents\\ArcGIS\\Packages\\ערכיות_אקולוגית_בשטחים_חקלאיים_בגולן061125_7da204\\commondata\\gb_survey.gdb"
validation_result = validate_geodatabase(gdb_path)
print(validation_result)

if "Error" not in validation_result:
    arcpy.env.workspace = gdb_path
    list_Feature_Classes = arcpy.ListFeatureClasses()
    list_Tables = arcpy.ListTables()
    datasets = list_Feature_Classes + list_Tables

# Define informative variable names for layers
agricultural_parcels_layer = "GB_LandCover"  # Agricultural parcels layer

# Check if agricultural layer exists
if agricultural_parcels_layer not in datasets:
    raise Exception(f"Error: Layer '{agricultural_parcels_layer}' not found in the geodatabase.")


ecological_zones_layer = "ECO"  # ECO layer

# Define informative field names
agricultural_score_field = "test"  # Field to store calculated score for agricultural parcels
ecological_type_field = "Type"  # Field in ECO layer that determines score

# Add the score field if it does not exist
if agricultural_score_field not in [f.name for f in arcpy.ListFields(agricultural_parcels_layer)]:
    arcpy.AddField_management(agricultural_parcels_layer, agricultural_score_field, "SHORT")

# Calculate corridor score by type
try:
    with arcpy.da.UpdateCursor(agricultural_parcels_layer, ["OID@", "SHAPE@", agricultural_score_field]) as parcel_cursor:
        for parcel_oid, parcel_geom, current_score in parcel_cursor:
            is_contained = False
            score = CorridorScore.NONE.value  # Default score
            with arcpy.da.SearchCursor(ecological_zones_layer, ["OID@", "SHAPE@", ecological_type_field]) as eco_cursor:
                for eco_oid, eco_geom, eco_type in eco_cursor:
                    if eco_geom.contains(parcel_geom):
                        is_contained = True
                        # Assign score based on ENUM
                        if re.search(r'ליבה', eco_type):
                            score = CorridorScore.CORE.value
                        elif re.search(r'מעבר', eco_type):
                            score = CorridorScore.TRANSITION.value
                        elif re.search(r'מסדרון', eco_type):
                            score = CorridorScore.CORRIDOR.value
            if not is_contained:
                score = CorridorScore.NONE.value
            # Update the parcel with the calculated score
            parcel_cursor.updateRow([parcel_oid, parcel_geom, score])

    print(f"Success: Scores have been calculated and saved in the '{agricultural_score_field}' field.")
except Exception as e:
    print(f"Error: Failed to calculate and save scores. Details: {e}")



# Calculate floodplain score by distanceTo()
floodplain_score_field = "test"
floodplain_layer_url = "https://services7.arcgis.com/Z0U0ULsiGzgmGVPW/arcgis/rest/services/FludAreaTMA34/FeatureServer/0"

# Create a feature layer from the floodplain URL
floodplain_layer = "FloodplainLayer"
arcpy.MakeFeatureLayer_management(floodplain_layer_url, floodplain_layer) # to add condition that layer exists


try:
    with arcpy.da.UpdateCursor(agricultural_parcels_layer, ["OID@", "SHAPE@", floodplain_score_field]) as parcel_cursor:
        for parcel_oid, parcel_geom, current_score in parcel_cursor:
            min_distance = None
            is_inside = False

            # Loop through floodplain polygons
            with arcpy.da.SearchCursor(floodplain_layer, ["SHAPE@"]) as flood_cursor:
                for flood_geom, in flood_cursor:
                    # Check if parcel is inside floodplain
                    if flood_geom.contains(parcel_geom):
                        is_inside = True
                        break
                    # Calculate distance
                    distance = parcel_geom.distanceTo(flood_geom)
                    if min_distance is None or distance < min_distance:
                        min_distance = distance
                        
            # Assign score based on containment or distance
            if is_inside:
                score = FloodplainScore.MAXIMUM.value  # Inside floodplain
            elif min_distance is not None and min_distance <= 500:
                score = FloodplainScore.MEDIUM.value   # Within 500 meters
            else:
                score = FloodplainScore.LOW.value      # Farther than 500 meters
            parcel_cursor.updateRow([parcel_oid, parcel_geom, score])

    print(f"Success: Floodplain scores saved in '{floodplain_score_field}'.")
except Exception as e:
    print(f"Error: Failed floodplain score calculation. Details: {e}")
