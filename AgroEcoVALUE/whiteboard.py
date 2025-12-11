
# -*- coding: utf-8 -*-
import arcpy
import os
import re
from eco_score_enum import NaturalArea_type

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

agricultural_layer = "GB_LandCover"
landscape_units_layer = "ClipEcoUnits"
NaturalArea_score_field = "test"

"""
_______________________________________________
Whiteboard below for testing code snippets:
_______________________________________________
"""

# Calculate Natural Area score 
try:
    with arcpy.da.SearchCursor(landscape_units_layer, ["SHAPE@"]) as eco_cursor:
        for eco_geom in eco_cursor:
            sum_open_area = 0
            sum_agro_area = 0
            sum_other_area = 0
            sum_total_area = 0
            # Open an update cursor on parcels and update only those that are contained/overlap with the current ECO geometry
            with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", NaturalArea_score_field, "LandCov"]) as parcel_cursor:
                for oid, geom, current_score, landcov in parcel_cursor:
                    if geom.overlaps(eco_geom[0]) or geom.within(eco_geom[0]) or eco_geom[0].within(geom):
                        
                        if re.search(NaturalArea_type.OPEN.value[1], landcov) or re.search(NaturalArea_type.OPEN.value[0], landcov): 
                            sum_open_area += geom.area
                        elif re.search(NaturalArea_type.AGRICULTURAL.value[0], landcov):
                            sum_agro_area += geom.area
                        else:
                            sum_other_area += geom.area

                        sum_total_area += geom.area
                    else:   
                        continue  # Skip parcels that do not overlap or are not contained
            
            print(eco_geom)
            print(f"%_open_area: {sum_open_area/sum_total_area:.2%}")
            print(f"%_agro_area: {sum_agro_area/sum_total_area:.2%}")
            print(f"%_other_area: {sum_other_area/sum_total_area:.2%}")
except Exception as e:
    arcpy.AddError(f"Error calculating Natural Area scores: {e}")

