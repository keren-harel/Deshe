# last edit: 01-09-2025 18:00

import arcpy
import pandas as pd
import numpy as np
from scipy.spatial.distance import pdist, squareform

# Converts an input layer to a new coordinate system
def project(input_points_layer, workspace_path):
    # Construct the full output path by combining the workspace and feature class name
    newLayerPoint = arcpy.CreateUniqueName("point_itm", workspace_path)

    arcpy.management.Project(
        in_dataset=input_points_layer,
        out_dataset=newLayerPoint,
        out_coor_system='PROJCS["Israel_TM_Grid",GEOGCS["GCS_Israel",DATUM["D_Israel",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",219529.584],PARAMETER["False_Northing",626907.39],PARAMETER["Central_Meridian",35.20451694444445],PARAMETER["Scale_Factor",1.0000067],PARAMETER["Latitude_Of_Origin",31.73439361111111],UNIT["Meter",1.0]]',
        transform_method="WGS_1984_To_Israel_CoordFrame",
        in_coor_system='GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]',
        preserve_shape="NO_PRESERVE_SHAPE",
        max_deviation=None,
        vertical="NO_VERTICAL")
    return newLayerPoint

# Extracts the coordinates of the points and the ID of the stands
def point_to_data(points_layer):
    points_list = []
    with arcpy.da.SearchCursor(points_layer, ["SHAPE@XY", "standID"]) as point_cursor:
        for point_row in point_cursor:
            point = arcpy.Point(point_row[0][0], point_row[0][1])
            points_list.append([point_row[1], point.X, point.Y])
    return points_list

# Creates a pandas DataFrame from the list of points and filters them to only those with more than one point
def reduced_table(points_list):
    data = pd.DataFrame(points_list, columns=['standID','point_x', 'point_y'])
    data_count = data.groupby("standID").size().reset_index(name="point_count")
    df_merge = data.merge(data_count, how='inner')
    df = df_merge.loc[df_merge["point_count"]>1]
    return df

# Performs a spatial join between the stands layer and the point layer
def spatial_join(input_points_layer,input_stands_layer, workspace_path):
    join_point = arcpy.CreateUniqueName("joinPoints", workspace_path)

    arcpy.analysis.SpatialJoin(
        target_features= input_points_layer,
        join_features= input_stands_layer,
        out_feature_class=join_point,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        match_option="INTERSECT",    
    )    
    return join_point

def dict_to_FeatureClass(my_dict, output_feature_class, spatial_reference):
    # Determine the maximum length of the lists
    max_length = max(len(v) for v in my_dict.values())

    # Fill the empty lists with np.nan to match the maximum length
    for key in my_dict:
        if len(my_dict[key]) < max_length:
            my_dict[key].extend([None] * (max_length - len(my_dict[key])))

    df = pd.DataFrame(my_dict, columns=['GlobalID', 'x', 'y', 'GeneralDensity', 'StartRepeatDominTree', 'PlantTypeCoverDistribut', 'VitalForest', 'InvasiveSpecies', 'note', 'receck'])
    
    # Custom join function that skips None values
    def custom_join(values):
        return ', '.join([str(v) for v in values if v is not None])

    # Define the aggregation functions for each column
    agg_funcs = {col: custom_join for col in df.columns if col not in ['x', 'y']}

    # Group by the duplicated fields and apply the aggregation functions
    df = df.groupby(['x', 'y'], as_index=False).agg(agg_funcs)
    
    # Define the data types for the fields
    dtype = [
        ('x', 'f8'),
        ('y', 'f8'),
        ('globalid', 'U100'),
        ('GeneralDensity',  'U100'),
        ('StartRepeatDominTree', 'U100'),
        ('PlantTypeCoverDistribut', 'U100'),
        ('VitalForest', 'U100'),
        ('InvasiveSpecies', 'U100'),
        ('note', 'U100'),
        ('receck', 'U100')
        ]
    
    array = np.array(df.to_records(index=False), dtype=dtype)
    
    arcpy.da.NumPyArrayToFeatureClass(array, output_feature_class,('x', 'y'), spatial_reference)

def find_nulls(data_frame, field_to_check):
    null_df = data_frame[pd.isna(data_frame[field_to_check])]
    return null_df

def sum_not_10(data_frame, id, calc_field):
    sum_fiels = data_frame.groupby(id).agg({
    'X_coords': 'first',
    'Y_coords': 'first',
    calc_field: 'sum'
    }).reset_index()

    not_10 = sum_fiels.loc[sum_fiels[calc_field] != 10]
    return not_10

def sum_less_than_100(data_frame, id, calc_field):
    sum_fields = data_frame.groupby(id).agg({
        'X_coords': 'first',
        'Y_coords': 'first',
        calc_field: 'sum'
    }).reset_index()
    
    less_than_100 = sum_fields.loc[sum_fields[calc_field] < 100]
    return less_than_100

def check_duplicates(data_frame, id, check_field):
    # Find duplicates in the check_field for the same ID
    duplicates = data_frame[data_frame.duplicated(subset=[id, check_field], keep=False)]
    
    grouped_duplicates = duplicates.groupby(id).agg({
    'X_coords': 'first',
    'Y_coords': 'first',
    }).reset_index()

    return grouped_duplicates

def error_to_dict(data_frame, eror_location, text_for_error):
    for index, row in data_frame.iterrows():
        globalid = row[0]
        x = row[1]
        y = row[2]

        if globalid not in error_dict["GlobalID"]:
            error_dict["GlobalID"].append(globalid)
            error_dict["x"].append(x)
            error_dict["y"].append(y)
            error_dict["GeneralDensity"].append("")
            error_dict["StartRepeatDominTree"].append("")
            error_dict["PlantTypeCoverDistribut"].append("")
            error_dict["VitalForest"].append("")
            error_dict["InvasiveSpecies"].append("")
            error_dict["note"].append("")
            error_dict["receck"].append("")

        index = error_dict["GlobalID"].index(globalid)
        if error_dict[eror_location][index]:
            error_dict[eror_location][index] += ", " + text_for_error
        else:
            error_dict[eror_location][index] = text_for_error

def emptyTable (df_point, df_table):
    missing_globalids = df_point[~df_point['globalid'].isin(df_table['globalid'])]
    return missing_globalids

error_dict = {
    "GlobalID":[],
    "x":[],
    "y":[],
    "GeneralDensity": [],
    "StartRepeatDominTree": [],
    "PlantTypeCoverDistribut": [],
    "VitalForest": [],
    "InvasiveSpecies": [],
    "note": [],
    "receck": []
    }

# Dictionary to store reception problems detected in the forest
dict_reception = {
    "TmiraTreeSpName1": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "TmiraTreeSpName2": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "TmiraTreeSpName3": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "HighTreeSpName1": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "HighTreeSpName2": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "HighTreeSpName3": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "MidTreeSpName1": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "MidTreeSpName2": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "MidTreeSpName3": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "MidTreeSpNames": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "SubTreeSpName1": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "SubTreeSpName2": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "SubTreeSpName3": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "SubTreeSpNames": ["פונקציות JavaScript מושבתות.", "פונקציות JavaScript מושבתות.,פונקציות JavaScript מושבתות.,פונקציות JavaScript מושבתות."],
    "SpShrub1": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "SpShrub2": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "SpShrub3": ["פונקציות JavaScript מושבתות.", "error_text2"],
    "SpShrubNames": ["פונקציות JavaScript מושבתות.", "פונקציות JavaScript מושבתות.,פונקציות JavaScript מושבתות.,פונקציות JavaScript מושבתות."],
}

# Function to find reception problems in the forest DataFrame
def find_reception_problems(df_point):
    reception_issues = {}

    for column, error_values in dict_reception.items():
        if column in df_point.columns:
            # Check if any error value appears as substring in the cell
            mask = df_point[column].astype(str).apply(
                lambda val: any(err in val for err in error_values if pd.notnull(val))
            )
            if mask.any():
                reception_issues[column] = df_point[mask]

    return reception_issues


# Input parameters from ArcGIS tool box
input_points_layer = arcpy.GetParameterAsText(0)
input_poligons_layer = arcpy.GetParameterAsText(1)
input_StartRepeatDominTree = arcpy.GetParameterAsText(2)
input_PlantTypeCoverDistribut = arcpy.GetParameterAsText(3)
input_InvasiveSpecies = arcpy.GetParameterAsText(4)
input_VitalForest = arcpy.GetParameterAsText(5)

#!---------------------------------
#! Double Points
#!---------------------------------

input_smy_points = input_points_layer
input_stands = input_poligons_layer

# Add a new field to the stands layer and calculates its values ​​based on the object ID of the attribute
arcpy.management.AddField(input_stands, "standID", "SHORT")
arcpy.management.CalculateField(input_stands, "standID", "$feature.OBJECTID", "ARCADE")

# Setting the workspace path based on the input points layer
workspace = arcpy.Describe(input_smy_points).path
output_doublePoints = None
intermediate_layers = []

# When creating intermediate layers, add them to the list
points_ITM = project(input_smy_points, workspace)
intermediate_layers.append(points_ITM)

# The input points are converted to ITM and a spatial join between the stands layer and the point layer
points = spatial_join(points_ITM, input_stands, workspace)
intermediate_layers.append(points)

# Processes the connected points to create a DataFrame, which is then filtered to include only stands with more than one point.
points_data = point_to_data(points)
df = reduced_table(points_data) 

#Define the set of stand IDs
stands = set(df['standID'])


# For each stand, distances between each pair of points are calculated.
# Points with distances less than 110 units are considered valid pairs.
valid_pairs = []
point_list = []
for stand in stands:
    perStand = df.loc[df["standID"] == stand]
    point_list.clear()
    for x, y in zip(perStand["point_x"], perStand["point_y"]):
        point_list.append([x, y])
    point_dist = pdist(point_list)
    dist_matrix = squareform(point_dist)
    valid_indices = np.where(dist_matrix < 110)
    for i, j in zip(*valid_indices):
        if i < j:
            valid_pairs.append(point_list[i])
            valid_pairs.append(point_list[j])


# If valid pairs are found, they are converted to a Pandas DataFrame, then to a NumPy array,
# and finally output as a new GIS feature class.
# If no valid pairs are found, a message will be displayed.
if valid_pairs:
    output_doublePoints = arcpy.CreateUniqueName("double_points", workspace)
    sr = arcpy.SpatialReference(2039)
    df = pd.DataFrame(valid_pairs, columns=['x', 'y'])
    array = df.to_records(index=False)
    arcpy.da.NumPyArrayToFeatureClass(array, output_doublePoints, ("x", "y"),sr)
else:
    arcpy.AddWarning("No valid point pairs found.")


#!---------------------------------
#! reception_problems:
#!---------------------------------

# Input feature class
input_smy_points = input_points_layer

# List to store row data
data = []

# Extract field names from the dictionary
reception_fields = list(dict_reception.keys())

# Add basic fields
fields_needed = ["SHAPE@XY", "GlobalID"] + reception_fields

# Create a search cursor to iterate through the point features
with arcpy.da.SearchCursor(input_smy_points, fields_needed) as cursor:
    for rec in cursor:
        cor_x, cor_y = rec[0]
        row_dict = {
            "globalid": rec[1],
            "X_coords": cor_x,
            "Y_coords": cor_y
        }

        # Add reception fields dynamically
        for i, field in enumerate(reception_fields, start=2):  # start=2 because rec[0] and rec[1] are already used
            row_dict[field] = rec[i]

        data.append(row_dict)

# Create a DataFrame from the list
df_point = pd.DataFrame(data)

# Find reception problems
reception_issues = find_reception_problems(df_point)

# Add errors to the error dictionary
for field, issues_df in reception_issues.items():
    if not issues_df.empty:
        error_to_dict(issues_df, "note", "Reception problem detected – see message window for details")

#  Print summary of issues
for field, issues_df in reception_issues.items():
    if not issues_df.empty:
        arcpy.AddWarning(f"\nReception issues found in field: {field}")
        for _, row in issues_df.iterrows():
            arcpy.AddMessage(f"GlobalID: {row['globalid']}, X: {row['X_coords']}, Y: {row['Y_coords']}, Value: {row[field]}")


#!---------------------------------
#! Create basic table of coordinates and a GlobalID's for connectivity to related tables
#!---------------------------------
input_smy_points = input_points_layer

data = []

# Create a search cursor to iterate through the point features
with arcpy.da.SearchCursor(input_smy_points, ["SHAPE@XY", "GlobalID"]) as cursor:
    for rec in cursor:
        cor_x = rec[0][0]
        cor_y = rec[0][1]
        globalid = rec[1]
        
        # Append the row data to the list
        data.append([globalid, cor_x, cor_y])

# Create a DataFrame from the list
df_coords = pd.DataFrame(data, columns=["globalid", "X_coords", "Y_coords"])


#!---------------------------------
#! Point Layer:
#!---------------------------------

input_smy_points = input_points_layer

data = []

# Create a search cursor to iterate through the point features
with arcpy.da.SearchCursor(input_smy_points, ["SHAPE@XY", "GlobalID", "GeneralDensity", "StandDensity"]) as cursor:
    for rec in cursor:
        cor_x = rec[0][0]
        cor_y = rec[0][1]
        globalid = rec[1]
        general_density = rec[2]
        stand_density = rec[3]
        
        # Append the row data to the list
        data.append([globalid, cor_x, cor_y , general_density, stand_density])

# Create a DataFrame from the list
df_point = pd.DataFrame(data, columns=["globalid", "X_coords", "Y_coords", "GeneralDensity", "StandDensity"])

null_data = find_nulls(df_point, "GeneralDensity")
if not null_data.empty:
    error_to_dict(null_data, "GeneralDensity", "GeneralDensity_na")

null_data = find_nulls(df_point, "StandDensity")
if not null_data.empty:
    error_to_dict(null_data, "GeneralDensity", "StandDensity_na")

#!---------------------------------
#! StartRepeatDominTree Table:
#!---------------------------------

# Input parameters from ArcGIS tool box
relc = input_StartRepeatDominTree

# Define parameters
relationship_class = relc

data = []

# Create a search cursor to iterate through the point features
with arcpy.da.SearchCursor(relationship_class, ["parentglobalid", "DominTree", "Proportion"]) as cursor:
    for rec in cursor:
        globalid = cursor[0]
        DominTree = cursor[1]
        if cursor[2] is not None:
            Proportion = int(cursor[2])
        else:
            Proportion = None  
        
        # Append the row data to the list
        data.append([globalid, DominTree, Proportion])

# Create a DataFrame from the list
df_StartRepeatDominTree = pd.DataFrame(data, columns=["globalid", "DominTree", "Proportion"])

# Perform the merge based on the 'globalid' column
joined_df = df_StartRepeatDominTree.merge(df_coords, on='globalid')

# Select the desired columns from the merged DataFrame
df_StartRepeatDominTree = joined_df[['globalid', 'X_coords', 'Y_coords', 'DominTree', 'Proportion']]

# Check for missing values in 'DominTree' and 'Proportion'
empty_StartRepeatDominTree = emptyTable(df_coords, df_StartRepeatDominTree)
missing_domin_tree = find_nulls(df_StartRepeatDominTree, "DominTree")
missing_proportion = find_nulls(df_StartRepeatDominTree, "Proportion")
error_proportion = sum_not_10(df_StartRepeatDominTree, "globalid", "Proportion")
duplicates_DominTree = check_duplicates(df_StartRepeatDominTree, "globalid", "DominTree")

if df_StartRepeatDominTree.empty: 
    arcpy.AddWarning("StartRepeatDominTree: {EMPTY_TABLE}")
else:
    if not empty_StartRepeatDominTree.empty:
        error_to_dict(empty_StartRepeatDominTree, "StartRepeatDominTree", "{EMPTY_TABLE}")
    if not duplicates_DominTree.empty:
        error_to_dict(duplicates_DominTree, "StartRepeatDominTree", "{double_DominTree}")
    if not missing_domin_tree.empty:
        error_to_dict(missing_domin_tree, "StartRepeatDominTree", "{NA_DOMAIN}")
    if not missing_proportion.empty:
        error_to_dict(missing_proportion, "StartRepeatDominTree", "{NA_PROPORTION}")
    if not error_proportion.empty:
        error_to_dict(error_proportion, "StartRepeatDominTree", "{NOT_10}")

#!---------------------------------
#! PlantTypeCoverDistribut Table:
#!---------------------------------

relationship_class = input_PlantTypeCoverDistribut

data = []

# Create a search cursor to iterate through the point features
with arcpy.da.SearchCursor(relationship_class, ["parentglobalid", "PercentByTen", "PlantType"]) as cursor:
    for rec in cursor:
        globalid = cursor[0]
        if cursor[1] is not None:
            PercentByTen = int(cursor[1])
        else:
            PercentByTen = None  
        PlantType = cursor[2]
        # Append the row data to the list        
        data.append([globalid, PercentByTen, PlantType])

# Create a DataFrame from the list
df_PlantTypeCoverDistribut = pd.DataFrame(data, columns=["globalid", "PercentByTen", "PlantType"])

# Perform the merge based on the 'globalid' column
joined_df = df_PlantTypeCoverDistribut.merge(df_coords, on='globalid')

# Select the desired columns from the merged DataFrame
df_PlantTypeCoverDistribut = joined_df[['globalid', 'X_coords', 'Y_coords', 'PercentByTen', 'PlantType']]

# Check for missing values in 'DominTree' and 'Proportion'
empty_PlantTypeCoverDistribut = emptyTable(df_coords, df_PlantTypeCoverDistribut)
missing_PercentByTen = find_nulls(df_PlantTypeCoverDistribut, "PercentByTen")
missing_PlantType = find_nulls(df_PlantTypeCoverDistribut, "PlantType")
smaller_PercentByTen = sum_less_than_100(df_PlantTypeCoverDistribut, "globalid", "PercentByTen")
duplicates_PlantType  = check_duplicates(df_PlantTypeCoverDistribut, "globalid", "PlantType")

if df_PlantTypeCoverDistribut.empty: 
    arcpy.AddWarning("PlantTypeCoverDistribut Table is empty!")
else:
    if not empty_StartRepeatDominTree.empty:
        error_to_dict(empty_StartRepeatDominTree, "PlantTypeCoverDistribut", "{EMPTY_TABLE}")
    if not duplicates_PlantType.empty:
        error_to_dict(duplicates_PlantType, "PlantTypeCoverDistribut", "{double_PlantType}")
    if not missing_PercentByTen.empty:
        error_to_dict(missing_PercentByTen,"PlantTypeCoverDistribut", "{NA_PercentByTen}")
    if not missing_PlantType.empty:
        error_to_dict(missing_PlantType,"PlantTypeCoverDistribut", "{NA_PlantType}")
    if not smaller_PercentByTen.empty:
        error_to_dict(smaller_PercentByTen, "PlantTypeCoverDistribut", "{NOT_100}")

#!---------------------------------
#! InvasiveSpecies Table:
#!---------------------------------

# Define parameters
relationship_class = input_InvasiveSpecies

data = []

# Create a search cursor to iterate through the point features
with arcpy.da.SearchCursor(relationship_class, ["parentglobalid", "InvasiveSpecie", "EpicenterType"]) as cursor:
    for rec in cursor:
        globalid = cursor[0]
        InvasiveSpecie = cursor[1]
        EpicenterType = cursor[2]
        # Append the row data to the list
        data.append([globalid, InvasiveSpecie, EpicenterType])


# Create a DataFrame from the list
df_InvasiveSpecies = pd.DataFrame(data, columns=["globalid", "InvasiveSpecie", "EpicenterType"])

# Perform the merge based on the 'globalid' column
joined_df = df_InvasiveSpecies.merge(df_coords, on='globalid')

# Select the desired columns from the merged DataFrame
df_InvasiveSpecies = joined_df[['globalid', 'X_coords', 'Y_coords', 'InvasiveSpecie', 'EpicenterType']]


# Drop rows where the 'InvasiveSpecie' column has NULL values or the value "אין"
filtered_df = df_InvasiveSpecies.dropna(subset=['InvasiveSpecie'])
filtered_df = filtered_df[filtered_df['InvasiveSpecie'] != 'אין']

missing_EpicenterType = find_nulls(filtered_df,"EpicenterType")
duplicates_InvasiveSpecie  = check_duplicates(df_InvasiveSpecies, "globalid", "InvasiveSpecie")

if df_InvasiveSpecies.empty:
    arcpy.AddWarning("Invasive Species Table is Empty!")
else:
    if not duplicates_InvasiveSpecie.empty:
        error_to_dict(duplicates_InvasiveSpecie, "InvasiveSpecies", "{double_InvasiveSpecie}")
    if not missing_EpicenterType.empty:
        error_to_dict(missing_EpicenterType, "InvasiveSpecies", "{NA_EpicenterType}")

#!---------------------------------
#! VitalForest Table
#!---------------------------------

# Define parameters
relationship_class = input_VitalForest

data = []

# Create a search cursor to iterate through the point features
with arcpy.da.SearchCursor(relationship_class, ["parentglobalid", "ForestDefect", "PercentImpact"]) as cursor:
    for rec in cursor:
        globalid = cursor[0]
        ForestDefect = cursor[1]
        PercentImpact = cursor[2]
        # Append the row data to the list
        data.append([globalid, ForestDefect, PercentImpact])


# Create a DataFrame from the list
df_VitalForest = pd.DataFrame(data, columns=["globalid", "ForestDefect", "PercentImpact"])

# Perform the merge based on the 'globalid' column
joined_df = df_VitalForest.merge(df_coords, on='globalid')

# Select the desired columns from the merged DataFrame
df_VitalForest = joined_df[['globalid', 'X_coords', 'Y_coords', 'ForestDefect', 'PercentImpact']]

# Drop rows where the 'InvasiveSpecie' column has NULL values or the value "אין"
filtered_df = df_VitalForest.dropna(subset=['ForestDefect'])
filtered_df = filtered_df[filtered_df['ForestDefect'] != 'אין']

missing_PercentImpact = find_nulls(filtered_df,"PercentImpact")
duplicates_ForestDefect  = check_duplicates(df_VitalForest, "globalid", "ForestDefect")


if df_VitalForest.empty:
    arcpy.AddWarning("Invasive Species Table is Empty!")
else:
    if not duplicates_ForestDefect.empty:
        error_to_dict(duplicates_ForestDefect, "VitalForest", "{double_ForestDefect}")
    if not missing_PercentImpact.empty:
        error_to_dict(missing_PercentImpact, "VitalForest", "{NA_PercentImpact}")

# Define the output feature class name
workspace = arcpy.Describe(input_points_layer).path
output_markErrorPoints = arcpy.CreateUniqueName("mark_error_points", workspace)
sr = arcpy.SpatialReference(4326)
dict_to_FeatureClass(error_dict, output_markErrorPoints, sr)

try:
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map = aprx.activeMap
    map.addDataFromPath(output_markErrorPoints)
    if output_doublePoints:
        map.addDataFromPath(output_doublePoints)
        arcpy.AddMessage("The point layers have been exported and added to the map successfully!")
except Exception as e:
    arcpy.AddError(f"An error occurred while adding layers to the map: {str(e)}")
arcpy.AddMessage("Clears temporary layers and updates symbology...")

#!---------------------------------
#! Cosmetic repairs
#!---------------------------------

for layer in intermediate_layers:
    if arcpy.Exists(layer):
        arcpy.Delete_management(layer)
        arcpy.AddMessage(f"Layer {layer} deleted successfully.")
    else:
        arcpy.AddMessage(f"Layer {layer} does not exist.")
