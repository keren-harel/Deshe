
# -*- coding: utf-8 -*-
import arcpy
from datetime import datetime
import re
from eco_score_enum import (
    CorridorScore, FloodplainScore, NaturalAreaType, DynamicScore,
    OpenSpaceCorridorType, OpenSpaceCorridorScore, CoverTypeScore, CoverType,
    WaterTypeScore, WaterType, spatialScaleScores
)

# -------------------------------
# PARAMETERS FROM TOOL
# -------------------------------
agricultural_layer = arcpy.GetParameterAsText(0)  # Agricultural parcels layer
eco_layer = arcpy.GetParameterAsText(1)           # ECO layer
floodplain_layer = arcpy.GetParameterAsText(2)    # Floodplain layer
max_distance = arcpy.GetParameterAsText(3)        # Max distance (optional)
landscape_units_layer = arcpy.GetParameterAsText(4)  # Landscape Units layer
rezef_score_layer = arcpy.GetParameterAsText(5)      # Rezef layer

corridor_score_field = arcpy.GetParameterAsText(6)
floodplain_score_field = arcpy.GetParameterAsText(7)
NaturalArea_score_field = arcpy.GetParameterAsText(8)
rezef_score_field = arcpy.GetParameterAsText(9)
covertype_score_field = arcpy.GetParameterAsText(10)
watertype_score_field = arcpy.GetParameterAsText(11)
corridor_unit_layer = arcpy.GetParameterAsText(12)
corridor_unit_field = arcpy.GetParameterAsText(13)

# -------------------------------
# VALIDATION: Agricultural layer is mandatory
# -------------------------------
if not agricultural_layer:
    arcpy.AddError("Agricultural parcels layer is required.")
    raise arcpy.ExecuteError

# Check required fields in agricultural layer
required_fields = ["LandCov", "CoverType", "WaterType"]
for field in required_fields:
    if field not in [f.name for f in arcpy.ListFields(agricultural_layer)]:
        arcpy.AddError(f"Required field '{field}' not found in agricultural layer.")
        raise arcpy.ExecuteError

# -------------------------------
# GLOBAL WARNING DICTIONARY
# -------------------------------
warnings_by_oid = {}

def add_warning(oid, message):
    """Add a warning message for a parcel and emit ArcPy warning."""
    try:
        arcpy.AddWarning(message)
    except:
        pass
    warnings_by_oid.setdefault(oid, []).append(message)

# -------------------------------
# Weighted Scoring Setup
# -------------------------------
categories = {
    "NATIONAL": {
        "fields": [corridor_score_field, corridor_unit_field],
        "total_max_score": spatialScaleScores.NATIONAL.value
    },
    "Agricultural_Landscape_Unit": {
        "fields": [floodplain_score_field, NaturalArea_score_field, rezef_score_field],
        "total_max_score": spatialScaleScores.Agricultural_Landscape_Unit.value
    },
    "Agricultural_Features": {
        "fields": [covertype_score_field, watertype_score_field],
        "total_max_score": spatialScaleScores.Agricultural_Features.value
    },
}

# Calculate per-metric score for each category
category_max_scores = {}

arcpy.AddMessage("========== Weighted Scoring Table ==========")
arcpy.AddMessage("{:<35} {:>12} {:>20}".format("Index", "Max Score", "Sub-Index Score"))
arcpy.AddMessage("-" * 70)

for category, info in categories.items():
    active_fields = [f for f in info["fields"] if f]
    if active_fields:
        per_metric_score = info["total_max_score"] / len(active_fields)
    else:
        per_metric_score = 0
    category_max_scores[category] = per_metric_score

    # Print row with proper spacing
    arcpy.AddMessage("{:<35} {:>12} {:>20.2f}".format(category, info["total_max_score"], per_metric_score))

arcpy.AddMessage("-" * 70)



# -------------------------------
# Add fields only if active
# -------------------------------
for category, info in categories.items():
    for field_name in info["fields"]:
        if field_name and field_name not in [f.name for f in arcpy.ListFields(agricultural_layer)]:
            arcpy.AddField_management(agricultural_layer, field_name, "SHORT")

# Add WARNING field if needed
if 'WARNING' not in [f.name for f in arcpy.ListFields(agricultural_layer)]:
    arcpy.AddField_management(agricultural_layer, 'WARNING', 'TEXT', field_length=2000)

# -------------------------------
# FUNCTIONS
# -------------------------------
def calculate_corridor_scores():
    """Calculate corridor scores based on ECO layer and apply weighted scoring using category_max_scores."""
    try:
        # Get total parcel count for progressor
        parcel_count = int(arcpy.GetCount_management(agricultural_layer).getOutput(0))
        arcpy.SetProgressor("step", "Processing parcels for corridor scores...", 0, parcel_count, 1)

        # Get per-metric score for NATIONAL category from pre-calculated dictionary
        per_metric_score = category_max_scores.get("NATIONAL", 0)

        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", corridor_score_field]) as parcels:
            for i, (oid, geom, _) in enumerate(parcels):
                # Default factor is NONE (0.0)
                base_factor = DynamicScore.NONE.value
                
                # Search ECO layer for matching geometry
                with arcpy.da.SearchCursor(eco_layer, ["SHAPE@", "Type"]) as ecos:
                    for eco_geom, eco_type in ecos:
                        if eco_geom.contains(geom):
                            # Assign factor based on corridor type
                            if any(re.search(str(pattern), str(eco_type)) for pattern in CorridorScore.CORE.value):
                                base_factor = DynamicScore.MAXIMUM.value
                            elif any(re.search(str(pattern), str(eco_type)) for pattern in CorridorScore.TRANSITION.value):
                                base_factor = DynamicScore.MEDIUM.value
                            elif any(re.search(str(pattern), str(eco_type)) for pattern in CorridorScore.CORRIDOR.value):
                                base_factor = DynamicScore.LOW.value
                            break


                # Multiply factor by per-metric score
                final_score = round(base_factor * per_metric_score)

                # Update row with calculated score
                parcels.updateRow([oid, geom, final_score])
                arcpy.SetProgressorPosition(i + 1)

        arcpy.AddMessage(f"Corridor scores saved in '{corridor_score_field}'.")
    except Exception as e:
        arcpy.AddError(f"Failed to calculate corridor scores: {e}")

def calculate_floodplain_scores():
    """Calculate floodplain scores using weighted logic."""
    try:
        arcpy.SetProgressorLabel("Analyzing floodplain overlaps...")
        overlap_threshold = 0.2
        parcel_count = int(arcpy.GetCount_management(agricultural_layer).getOutput(0))
        arcpy.SetProgressor("step", "Processing parcels for floodplain scores...", 0, parcel_count, 1)

        # Get per-metric score for Agricultural_Landscape_Unit category
        per_metric_score = category_max_scores.get("Agricultural_Landscape_Unit", 0)

        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", floodplain_score_field]) as parcels:
            for i, (oid, geom, _) in enumerate(parcels):
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

                # Determine factor based on overlap and distance
                if max_overlap_ratio >= overlap_threshold:
                    factor = DynamicScore.MAXIMUM.value
                    if max_overlap_ratio < 0.95:
                        add_warning(oid, f"FloodplainScore: {min_distance:.1f} m from floodplain; max overlap = {max_overlap_ratio:.2%}")
                elif min_distance is not None and float(max_distance) and min_distance <= float(max_distance):
                    factor = DynamicScore.MEDIUM.value
                else:
                    factor = DynamicScore.NONE.value

                final_score = round(factor * per_metric_score)
                parcels.updateRow([oid, geom, final_score])
                arcpy.SetProgressorPosition(i + 1)

        arcpy.AddMessage(f"Floodplain scores saved in '{floodplain_score_field}'.")
    except Exception as e:
        arcpy.AddError(f"Error calculating floodplain scores: {e}")

def calculate_natural_area_scores():
    """Calculate natural area scores using weighted logic."""
    try:
        unit_list = []
        # Pre-calculate scores for each landscape unit
        with arcpy.da.SearchCursor(landscape_units_layer, ["SHAPE@"]) as eco_cursor:
            for eco_geom in eco_cursor:
                sum_open_area = 0.0
                sum_total_area = 0.0
                with arcpy.da.SearchCursor(agricultural_layer, ["SHAPE@", "LandCov"]) as parcel_cursor:
                    for geom, landcov in parcel_cursor:
                        if geom.overlaps(eco_geom[0]) or geom.within(eco_geom[0]) or eco_geom[0].within(geom):
                            if re.search(NaturalAreaType.OPEN.value[1], landcov) or re.search(NaturalAreaType.OPEN.value[0], landcov):
                                sum_open_area += geom.area
                            sum_total_area += geom.area

                if sum_total_area > 0:
                    ratio = sum_open_area / sum_total_area
                    if ratio < 0.2:
                        factor = DynamicScore.NONE.value
                    elif 0.2 <= ratio < 0.8:
                        factor = DynamicScore.MEDIUM.value
                    else:
                        factor = DynamicScore.MAXIMUM.value
                else:
                    factor = DynamicScore.NONE.value

                unit_list.append((eco_geom[0], factor))

        # Assign scores to parcels
        parcel_count = int(arcpy.GetCount_management(agricultural_layer).getOutput(0))
        arcpy.SetProgressor("step", "Assigning natural area scores to parcels...", 0, parcel_count, 1)

        per_metric_score = category_max_scores.get("Agricultural_Landscape_Unit", 0)

        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", NaturalArea_score_field]) as parcels:
            for i, (oid, parcel_geom, _) in enumerate(parcels):
                max_overlap = 0.0
                best_factor = DynamicScore.NONE.value
                overlap_count = 0

                for unit_geom, factor in unit_list:
                    if parcel_geom.overlaps(unit_geom) or parcel_geom.within(unit_geom) or unit_geom.within(parcel_geom):
                        intersection = parcel_geom.intersect(unit_geom, 4)
                        overlap_area = intersection.area
                        if overlap_area > 0:
                            overlap_count += 1
                            if overlap_area > max_overlap:
                                max_overlap = overlap_area
                                best_factor = factor

                final_score = round(best_factor * per_metric_score)
                parcels.updateRow([oid, parcel_geom, final_score])

                if overlap_count > 1:
                    add_warning(oid, f"NaturalArea_score: parcel overlaps {overlap_count} units. Score set based on largest overlapping unit.")

                arcpy.SetProgressorPosition(i + 1)

        arcpy.AddMessage(f"Natural Area scores saved in '{NaturalArea_score_field}'.")
    except Exception as e:
        arcpy.AddError(f"Error calculating natural area scores: {e}")

def calculate_open_space_corridor_score():
    """Calculate open space corridor scores using weighted logic."""
    try:
        parcel_count = int(arcpy.GetCount_management(agricultural_layer).getOutput(0))
        arcpy.SetProgressor("step", "Processing parcels for open space corridor scores...", 0, parcel_count, 1)

        per_metric_score = category_max_scores.get("Agricultural_Landscape_Unit", 0)

        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", rezef_score_field]) as parcels:
            for i, (oid, geom, _) in enumerate(parcels):
                factor = DynamicScore.NONE.value
                with arcpy.da.SearchCursor(rezef_score_layer, ["SHAPE@", "gridcode"]) as ecos:
                    for eco_geom, gridcode in ecos:
                        if eco_geom.contains(geom):
                            grid_val = int(gridcode)
                            if grid_val in OpenSpaceCorridorType.CORE.value:
                                factor = DynamicScore.MAXIMUM.value
                            elif grid_val in OpenSpaceCorridorType.BUFFER.value:
                                factor = DynamicScore.MEDIUM.value
                            else:
                                factor = DynamicScore.NONE.value
                            break

                final_score = round(factor * per_metric_score)
                parcels.updateRow([oid, geom, final_score])
                arcpy.SetProgressorPosition(i + 1)

        arcpy.AddMessage(f"Open space corridor scores saved in '{rezef_score_field}'.")
    except Exception as e:
        arcpy.AddError(f"Failed to calculate open space corridor scores: {e}")

def calculate_covertype_scores():
    """Calculate cover type scores using weighted logic."""
    try:
        cov_type_dict = {}
        with arcpy.da.SearchCursor(agricultural_layer, ["OID@", "CoverType"]) as search_cursor:
            for oid, cov_type in search_cursor:
                cov_type_dict[oid] = cov_type

        parcel_count = int(arcpy.GetCount_management(agricultural_layer).getOutput(0))
        arcpy.SetProgressor("step", "Processing parcels for cover type scores...", 0, parcel_count, 1)

        per_metric_score = category_max_scores.get("Agricultural_Features", 0)

        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", covertype_score_field]) as parcels:
            for i, (oid, geom, _) in enumerate(parcels):
                cov_type = cov_type_dict.get(oid, "")
                factor = DynamicScore.NONE.value
                if any(re.search(pattern, cov_type or "") for pattern in CoverType.OPEN.value):
                    factor = DynamicScore.MAXIMUM.value

                final_score = round(factor * per_metric_score)
                parcels.updateRow([oid, geom, final_score])
                arcpy.SetProgressorPosition(i + 1)

        arcpy.AddMessage(f"Cover type scores saved in '{covertype_score_field}'.")
    except Exception as e:
        arcpy.AddError(f"Failed to calculate Cover type scores: {e}")

def calculate_watertype_scores():
    """Calculate water type scores using weighted logic."""
    try:
        water_type_dict = {}
        with arcpy.da.SearchCursor(agricultural_layer, ["OID@", "WaterType"]) as search_cursor:
            for oid, water_type in search_cursor:
                water_type_dict[oid] = water_type

        parcel_count = int(arcpy.GetCount_management(agricultural_layer).getOutput(0))
        arcpy.SetProgressor("step", "Processing parcels for water type scores...", 0, parcel_count, 1)

        per_metric_score = category_max_scores.get("Agricultural_Features", 0)

        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", watertype_score_field]) as parcels:
            for i, (oid, geom, _) in enumerate(parcels):
                water_type = water_type_dict.get(oid, "")
                factor = DynamicScore.NONE.value
                if any(re.search(pattern, water_type or "") for pattern in WaterType.BAAL.value):
                    factor = DynamicScore.MAXIMUM.value
                elif any(re.search(pattern, water_type or "") for pattern in WaterType.SHELACHIN.value):
                    factor = DynamicScore.NONE.value
                elif any(re.search(pattern, water_type or "") for pattern in WaterType.OTHER.value):
                    factor = DynamicScore.NONE.value
                else:
                    add_warning(oid, f"WaterType_score: Unrecognized WaterType '{water_type}'. Assigned 0 score.")

                final_score = round(factor * per_metric_score)
                parcels.updateRow([oid, geom, final_score])
                arcpy.SetProgressorPosition(i + 1)

        arcpy.AddMessage(f"Water type scores saved in '{watertype_score_field}'.")
    except Exception as e:
        arcpy.AddError(f"Failed to calculate Water type scores: {e}")

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

# -------------------------------
# MAIN EXECUTION
# -------------------------------
try:
    arcpy.AddMessage("========== AgroEco Analysis ==========")
    arcpy.AddMessage("Start Time: {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
    arcpy.AddMessage("--------------------------------------")

    arcpy.SetProgressor("step", "Running AgroEco Analysis...", 0, 6, 1)

    # Step 1: Corridor
    if eco_layer and corridor_score_field:
        arcpy.AddMessage("Step 1: Calculating corridor scores...")
        calculate_corridor_scores()
    else:
        arcpy.AddWarning("Corridor score skipped (missing ECO layer or field).")
    arcpy.SetProgressorPosition(1)

    # Step 2: Floodplain
    if floodplain_layer and floodplain_score_field:
        arcpy.AddMessage("Step 2: Calculating floodplain scores...")
        calculate_floodplain_scores()
    else:
        arcpy.AddWarning("Floodplain score skipped (missing floodplain layer or field).")
    arcpy.SetProgressorPosition(2)

    # Step 3: Natural Area
    if landscape_units_layer and NaturalArea_score_field:
        arcpy.AddMessage("Step 3: Calculating natural area scores...")
        calculate_natural_area_scores()
    else:
        arcpy.AddWarning("Natural area score skipped (missing landscape units layer or field).")
    arcpy.SetProgressorPosition(3)

    # Step 4: Open Space Corridor
    if rezef_score_layer and rezef_score_field:
        arcpy.AddMessage("Step 4: Calculating open space corridor scores...")
        calculate_open_space_corridor_score()
    else:
        arcpy.AddWarning("Open space corridor score skipped (missing rezef layer or field).")
    arcpy.SetProgressorPosition(4)

    # Step 5: Cover Type
    if covertype_score_field:
        arcpy.AddMessage("Step 5: Calculating cover type scores...")
        calculate_covertype_scores()
    else:
        arcpy.AddWarning("Cover type score skipped (missing field).")
    arcpy.SetProgressorPosition(5)

    # Step 6: Water Type
    if watertype_score_field:
        arcpy.AddMessage("Step 6: Calculating water type scores...")
        calculate_watertype_scores()
    else:
        arcpy.AddWarning("Water type score skipped (missing field).")
    arcpy.SetProgressorPosition(6)

    # Write warnings
    write_warnings()

    arcpy.AddMessage("--------------------------------------")
    arcpy.AddMessage("Process completed successfully!")
    arcpy.AddMessage("End Time: {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
    arcpy.AddMessage("======================================")

except Exception as e:
    arcpy.AddError(f"AgroEco Analysis failed: {e}")
