
# -*- coding: utf-8 -*-
import arcpy
from datetime import datetime
import re
from eco_score_enum import CorridorScore, FloodplainScore, NaturalAreaType, NaturalAreaScore, OpenSpaceCorridorType, OpenSpaceCorridorScore

# ---------------------------
# PARAMETERS FROM TOOL
# ---------------------------
agricultural_layer = arcpy.GetParameterAsText(0)  # Agricultural parcels layer
eco_layer = arcpy.GetParameterAsText(1)           # ECO layer
floodplain_layer = arcpy.GetParameterAsText(2)    # Floodplain layer
corridor_score_field = arcpy.GetParameterAsText(3)  # Field for corridor score
floodplain_score_field = arcpy.GetParameterAsText(4) # Field for floodplain score
max_distance = float(arcpy.GetParameterAsText(5))      # Max distance (e.g., 500)
NaturalArea_score_field = arcpy.GetParameterAsText(6) # Field for Natural Area score
landscape_units_layer = arcpy.GetParameterAsText(7)   # Landscape Units layer
rezef_score_layer = arcpy.GetParameterAsText(8)   # Rezef layer
rezef_score_field = arcpy.GetParameterAsText(9)   # Field for Rezef score
# ---------------------------
# VALIDATION
# ---------------------------
missing_params = []
if not agricultural_layer:
    missing_params.append("Agricultural parcels layer")
if not eco_layer:
    missing_params.append("ECO layer")
if not floodplain_layer:
    missing_params.append("Floodplain layer")
if not corridor_score_field:
    missing_params.append("Corridor score field name")
if not floodplain_score_field:
    missing_params.append("Floodplain score field name")
if not max_distance:
    missing_params.append("Max distance")
if not NaturalArea_score_field:
    missing_params.append("Natural Area score field name")
if not landscape_units_layer:
    missing_params.append("Landscape Units layer")

if missing_params:
    arcpy.AddError("Missing required parameters: " + ", ".join(missing_params))
    raise arcpy.ExecuteError  # Stop tool execution immediately

# Check for required fields
required_fields = ["LandCov"]
for field in required_fields:
    if field not in [f.name for f in arcpy.ListFields(agricultural_layer)]:
        arcpy.AddError(f"Required field '{field}' not found in agricultural layer.")
        raise arcpy.ExecuteError

# ---------------------------
# GLOBAL WARNING DICTIONARY
# ---------------------------
warnings_by_oid = {}

def add_warning(oid, message):
    """Add a warning message for a parcel and emit ArcPy warning."""
    try:
        arcpy.AddWarning(message)
    except:
        pass
    warnings_by_oid.setdefault(oid, []).append(message)

# ---------------------------
# CALCULATE CORRIDOR SCORE
# ---------------------------
def calculate_corridor_scores():
    """Calculate corridor scores based on ECO layer."""
    try:
        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", corridor_score_field]) as parcels:
            for oid, geom, _ in parcels:
                score = CorridorScore.NONE.value[0]
                with arcpy.da.SearchCursor(eco_layer, ["SHAPE@", "Type"]) as ecos:
                    for eco_geom, eco_type in ecos:
                        if eco_geom.contains(geom):
                            if re.search(CorridorScore.CORE.value[1], eco_type):
                                score = CorridorScore.CORE.value[0]
                            elif re.search(CorridorScore.TRANSITION.value[1], eco_type):
                                score = CorridorScore.TRANSITION.value[0]
                            elif re.search(CorridorScore.CORRIDOR.value[1], eco_type):
                                score = CorridorScore.CORRIDOR.value[0]
                            break
                parcels.updateRow([oid, geom, score])
        arcpy.AddMessage(f"Corridor scores saved in '{corridor_score_field}'.")
    except Exception as e:
        arcpy.AddError(f"Failed to calculate corridor scores: {e}")

# ---------------------------
# CALCULATE FLOODPLAIN SCORE
# ---------------------------
def calculate_floodplain_scores():
    """Calculate floodplain scores based on overlap and distance."""
    try:
        overlap_threshold = 0.2  # 20% overlap
        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", floodplain_score_field]) as parcels:
            for oid, geom, _ in parcels:
                min_distance = None
                max_overlap_ratio = 0.0
                with arcpy.da.SearchCursor(floodplain_layer, ["SHAPE@"]) as floods:
                    for (flood_geom,) in floods:
                        if geom.overlaps(flood_geom) or geom.within(flood_geom) or flood_geom.within(geom):
                            intersection = geom.intersect(flood_geom, 4)
                            if intersection.area > 0:
                                overlap_ratio = intersection.area / geom.area
                                max_overlap_ratio = max(max_overlap_ratio, overlap_ratio)
                        distance = geom.distanceTo(flood_geom)
                        if min_distance is None or distance < min_distance:
                            min_distance = distance
                # Assign score
                if max_overlap_ratio >= overlap_threshold:
                    score = FloodplainScore.MAXIMUM.value
                    if max_overlap_ratio < 0.95:
                        add_warning(oid, f"FloodplainScore: {min_distance:.1f} m from floodplain; max overlap = {max_overlap_ratio:.2%}")
                elif min_distance is not None and min_distance <= max_distance:
                    score = FloodplainScore.MEDIUM.value
                else:
                    score = FloodplainScore.LOW.value
                parcels.updateRow([oid, geom, score])
        arcpy.AddMessage(f"Floodplain scores saved in '{floodplain_score_field}'.")
    except Exception as e:
        arcpy.AddError(f"Error calculating floodplain scores: {e}")

# ---------------------------
# CALCULATE NATURAL AREA SCORE
# ---------------------------
def calculate_natural_area_scores():
    try:
        # First, calculate scores for each landscape unit
        unit_list = []
        with arcpy.da.SearchCursor(landscape_units_layer, ["SHAPE@"]) as eco_cursor:
            for eco_geom in eco_cursor:
                # Accumulate areas for this landscape unit
                sum_open_area = 0.0
                sum_total_area = 0.0
                with arcpy.da.SearchCursor(agricultural_layer, ["SHAPE@", "LandCov"]) as parcel_cursor:
                    for geom, landcov in parcel_cursor:
                        if geom.overlaps(eco_geom[0]) or geom.within(eco_geom[0]) or eco_geom[0].within(geom):
                            # Accumulate based on landcov
                            if re.search(NaturalAreaType.OPEN.value[1], landcov) or re.search(NaturalAreaType.OPEN.value[0], landcov): 
                                sum_open_area += geom.area
                            sum_total_area += geom.area
                # Calculate ratio and score
                if sum_total_area > 0:
                    ratio = sum_open_area / sum_total_area
                    if ratio < 0.2:
                        score = NaturalAreaScore.LOW.value
                    elif 0.2 <= ratio < 0.8:
                        score = NaturalAreaScore.MEDIUM.value
                    else:  # ratio >= 0.8
                        score = NaturalAreaScore.MAXIMUM.value
                else:
                    score = NaturalAreaScore.LOW.value  # Default if no parcels
                unit_list.append((eco_geom[0], score))

        # Now, assign scores to parcels based on largest overlapping unit
        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", NaturalArea_score_field]) as parcels:
            for oid, parcel_geom, _ in parcels:
                max_overlap = 0.0
                best_score = NaturalAreaScore.LOW.value
                overlap_count = 0
                for unit_geom, unit_score in unit_list:
                    if parcel_geom.overlaps(unit_geom) or parcel_geom.within(unit_geom) or unit_geom.within(parcel_geom):
                        intersection = parcel_geom.intersect(unit_geom, 4)
                        overlap_area = intersection.area
                        if overlap_area > 0:
                            overlap_count += 1
                            if overlap_area > max_overlap:
                                max_overlap = overlap_area
                                best_score = unit_score
                # Update parcel with best score
                parcels.updateRow([oid, parcel_geom, best_score])
                # Add warning if overlaps more than one unit
                if overlap_count > 1:
                    add_warning(oid, f"NaturalArea_score: the parcel overlaps {overlap_count} units. Score set based on largest overlapping unit.")
        arcpy.AddMessage(f"Natural Area scores saved in '{NaturalArea_score_field}' based on largest overlapping unit.")
    except Exception as e:
        arcpy.AddError(f"Error calculating natural area scores: {e}")


# ---------------------------
# CALCULATE OPEN SPACE CORRIDOR SCORE
# ---------------------------
def calculate_open_space_corridor_score():
    """Calculate open space corridor scores based on rezef gridcode."""
    try:
        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", rezef_score_field]) as parcels:
            for oid, geom, _ in parcels:
                score = OpenSpaceCorridorScore.DISTURBANCE.value[0]  # Default
                with arcpy.da.SearchCursor(rezef_score_layer, ["SHAPE@", "gridcode"]) as ecos:
                    for eco_geom, gridcode in ecos:
                        if eco_geom.contains(geom):
                            grid_val = int(gridcode)
                            if grid_val in OpenSpaceCorridorType.CORE.value:
                                score = OpenSpaceCorridorScore.CORE.value[0]
                            elif grid_val in OpenSpaceCorridorType.BUFFER.value:
                                score = OpenSpaceCorridorScore.BUFFER.value[0]
                            # DISTURBANCE is default
                            break
                parcels.updateRow([oid, geom, score])
        arcpy.AddMessage(f"Open space corridor scores saved in '{rezef_score_field}'.")
    except Exception as e:
        arcpy.AddError(f"Failed to calculate open space corridor scores: {e}")

# ---------------------------
# WRITE WARNINGS
# ---------------------------
def write_warnings():
    """Write collected warnings to WARNING field."""
    try:
        if warnings_by_oid:
            with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "WARNING"]) as cursor:
                for oid, current_warn in cursor:
                    msgs = warnings_by_oid.get(oid)
                    if msgs:
                        new_warn = "; ".join(msgs)
                        if current_warn:
                            new_warn = current_warn + "; " + new_warn
                        cursor.updateRow([oid, new_warn])
        arcpy.AddMessage("Warnings written to 'WARNING' field.")
    except Exception as e:
        arcpy.AddError(f"Failed to write warnings: {e}")

# ---------------------------
# MAIN EXECUTION
# ---------------------------
for field_name in [corridor_score_field, floodplain_score_field, NaturalArea_score_field, rezef_score_field]:
    if field_name not in [f.name for f in arcpy.ListFields(agricultural_layer)]:
        arcpy.AddField_management(agricultural_layer, field_name, "SHORT")
if 'WARNING' not in [f.name for f in arcpy.ListFields(agricultural_layer)]:
    arcpy.AddField_management(agricultural_layer, 'WARNING', 'TEXT', field_length=2000)



arcpy.AddMessage("========== AgroEco Analysis ==========")
arcpy.AddMessage("Start Time: {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
arcpy.AddMessage("--------------------------------------")

# Set progressor
arcpy.SetProgressor("step", "Running AgroEco Analysis...", 0, 5, 1)

arcpy.AddMessage("Step 1: Calculating corridor scores...")
calculate_corridor_scores()
arcpy.SetProgressorPosition(1)
arcpy.AddMessage("--------------------------------------")

arcpy.AddMessage("Step 2: Calculating floodplain scores...")
calculate_floodplain_scores()
arcpy.SetProgressorPosition(2)
arcpy.AddMessage("--------------------------------------")

arcpy.AddMessage("Step 3: Calculating natural area scores...")
calculate_natural_area_scores()
arcpy.SetProgressorPosition(3)
arcpy.AddMessage("--------------------------------------")

arcpy.AddMessage("Step 4: Calculating open space corridor scores...")
calculate_open_space_corridor_score()
arcpy.SetProgressorPosition(4)
write_warnings()
arcpy.SetProgressorPosition(5)

arcpy.AddMessage("======================================")
arcpy.AddMessage("Process completed successfully!")


