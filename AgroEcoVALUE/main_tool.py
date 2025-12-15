
# -*- coding: utf-8 -*-
import arcpy
import re
from eco_score_enum import CorridorScore, FloodplainScore, NaturalArea_type, NaturalAreaScore

# Get layers to process
agricultural_layer = arcpy.GetParameterAsText(0)  # Agricultural parcels layer
eco_layer = arcpy.GetParameterAsText(1)           # ECO layer
floodplain_layer = arcpy.GetParameterAsText(2)    # Floodplain layer
landscape_units_layer = arcpy.GetParameterAsText(7)  # Landscape Units layer

# Get fields to store scores 
corridor_score_field = arcpy.GetParameterAsText(3)  # Field for corridor score
floodplain_score_field = arcpy.GetParameterAsText(4) # Field for floodplain score
NaturalArea_score_field = arcpy.GetParameterAsText(6)    # Field for Natural Area score

# Get other values from user  
max_distance = float(arcpy.GetParameterAsText(5))    # Max distance (e.g., 500)

# Warning collection: collect warning messages per OID and store later in 'WARNING' field
warnings_by_oid = {}
def add_warning(oid, message):
    """Record a warning message for parcel OID and emit an ArcPy warning."""
    try:
        arcpy.AddWarning(message)
    except Exception:
        # If ArcPy AddWarning fails for any reason, ignore so collection still continues
        pass
    warnings_by_oid.setdefault(oid, []).append(message)

def calculate_corridor_scores(agricultural_layer, eco_layer, corridor_score_field):
    try:
        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", corridor_score_field]) as parcel_cursor:
            for oid, geom, current_score in parcel_cursor:
                score = CorridorScore.NONE.value[0]
                with arcpy.da.SearchCursor(eco_layer, ["SHAPE@", "Type"]) as eco_cursor:
                    for eco_geom, eco_type in eco_cursor:
                        if eco_geom.contains(geom):
                            if re.search(CorridorScore.CORE.value[1], eco_type):
                                score = CorridorScore.CORE.value[0]
                            elif re.search(CorridorScore.TRANSITION.value[1], eco_type):
                                score = CorridorScore.TRANSITION.value[0]
                            elif re.search(CorridorScore.CORRIDOR.value[1], eco_type):
                                score = CorridorScore.CORRIDOR.value[0]
                            break
                parcel_cursor.updateRow([oid, geom, score])
        arcpy.AddMessage(f"Corridor scores saved in '{corridor_score_field}'.")
    except Exception as e:
        arcpy.AddError(f"Failed to calculate corridor scores: {e}")

def calculate_floodplain_scores(agricultural_layer, floodplain_layer, floodplain_score_field, max_distance):
    try:
        overlap_threshold = 0.2  # 20% overlap threshold
        
        # Update cursor for agricultural parcels
        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", floodplain_score_field]) as parcel_cursor:
            for oid, geom, current_score in parcel_cursor:
                min_distance = None
                max_overlap_ratio = 0.0  # Track maximum overlap ratio across all floodplain polygons

                # Search cursor for floodplain polygons
                with arcpy.da.SearchCursor(floodplain_layer, ["SHAPE@"]) as flood_cursor:
                    for (flood_geom,) in flood_cursor:
                        # Calculate intersection area
                        if geom.overlaps(flood_geom) or geom.within(flood_geom) or flood_geom.within(geom):
                            intersection = geom.intersect(flood_geom, 4)
                            if intersection.area > 0:
                                overlap_area = intersection.area
                                parcel_area = geom.area
                                overlap_ratio = overlap_area / parcel_area
                                if overlap_ratio > max_overlap_ratio:
                                    max_overlap_ratio = overlap_ratio

                        # Calculate distance to floodplain
                        distance = geom.distanceTo(flood_geom)
                        if min_distance is None or distance < min_distance:
                            min_distance = distance
                
                # Assign score based on overlap or distance
                if max_overlap_ratio >= overlap_threshold:
                    score = FloodplainScore.MAXIMUM.value
                    add_warning(oid, f"FloodplainScore: {min_distance:.1f} m from floodplain; max overlap = {max_overlap_ratio:.2%}")
                elif min_distance is not None and min_distance <= max_distance:
                    score = FloodplainScore.MEDIUM.value
                    # record as a warning tied to this parcel OID and also emit it
                    add_warning(oid, f"FloodplainScore: {min_distance:.1f} m from floodplain; max overlap = {max_overlap_ratio:.2%}")
                else:
                    score = FloodplainScore.LOW.value

                # Update the score field
                parcel_cursor.updateRow([oid, geom, score])

        arcpy.AddMessage(f"Floodplain scores saved in '{floodplain_score_field}'.")

    except Exception as e:
        arcpy.AddError(f"Error calculating floodplain scores: {e}")

def calculate_natural_area_scores(agricultural_layer, landscape_units_layer, NaturalArea_score_field):
    try:
        # Dictionary to store the maximum score for each parcel OID
        parcel_max_scores = {}
        # Dictionary to count how many units each parcel overlaps
        parcel_unit_count = {}
        
        with arcpy.da.SearchCursor(landscape_units_layer, ["SHAPE@"]) as eco_cursor:
            for eco_geom in eco_cursor:
                # Accumulate areas for this landscape unit
                sum_open_area = 0.0
                sum_total_area = 0.0
                with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", NaturalArea_score_field, "LandCov"]) as parcel_cursor:
                    for oid, geom, current_score, landcov in parcel_cursor:
                        if geom.overlaps(eco_geom[0]) or geom.within(eco_geom[0]) or eco_geom[0].within(geom):
                            # Accumulate based on landcov
                            if re.search(NaturalArea_type.OPEN.value[1], landcov) or re.search(NaturalArea_type.OPEN.value[0], landcov): 
                                sum_open_area += geom.area
                            sum_total_area += geom.area
                # Now, if total_area > 0, calculate ratio and score for this unit
                if sum_total_area > 0:
                    ratio = sum_open_area / sum_total_area
                    if ratio < 0.2:
                        unit_score = NaturalAreaScore.LOW.value
                    elif 0.2 <= ratio < 0.8:
                        unit_score = NaturalAreaScore.MEDIUM.value
                    elif ratio >= 0.8:
                        unit_score = NaturalAreaScore.MAXIMUM.value
                    
                    # Update max score for parcels in this unit
                    with arcpy.da.SearchCursor(agricultural_layer, ["OID@", "SHAPE@"]) as parcel_cursor:
                        for oid, geom in parcel_cursor:
                            if geom.overlaps(eco_geom[0]) or geom.within(eco_geom[0]) or eco_geom[0].within(geom):
                                if oid not in parcel_max_scores:
                                    parcel_max_scores[oid] = unit_score
                                else:
                                    parcel_max_scores[oid] = max(parcel_max_scores[oid], unit_score)
                                parcel_unit_count[oid] = parcel_unit_count.get(oid, 0) + 1
        
        # Now update all parcels with their maximum score
        with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", NaturalArea_score_field]) as parcel_cursor:
            for oid, current_score in parcel_cursor:
                if oid in parcel_max_scores:
                    new_score = parcel_max_scores[oid]
                    parcel_cursor.updateRow([oid, new_score])
                    if parcel_unit_count.get(oid, 0) > 1:
                        add_warning(oid, "Parcel overlaps two units with different scores, the higher score was entered.")

        arcpy.AddMessage(f"Natural Area scores saved in '{NaturalArea_score_field}'.")
    except Exception as e:
        arcpy.AddError(f"Error calculating Natural Area scores: {e}")

def write_warnings(agricultural_layer):
    try:
        if warnings_by_oid:
            with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "WARNING"]) as warn_cursor:
                for oid, cur_warn in warn_cursor:
                    msgs = warnings_by_oid.get(oid)
                    if msgs:
                        # join multiple messages with semicolon and space
                        warn_text = "; ".join(msgs)
                        warn_cursor.updateRow([oid, warn_text])
        arcpy.AddMessage("Warnings written to 'WARNING' field where applicable.")
    except Exception as e:
        arcpy.AddError(f"Failed to write warnings to WARNING field: {e}")

# Main execution
# Add fields if they do not exist
for field_name in [corridor_score_field, floodplain_score_field, NaturalArea_score_field]:
    if field_name not in [f.name for f in arcpy.ListFields(agricultural_layer)]:
        arcpy.AddField_management(agricultural_layer, field_name, "SHORT")

# Ensure WARNING field exists to store collected warnings (TEXT large enough for concatenated messages)
if 'WARNING' not in [f.name for f in arcpy.ListFields(agricultural_layer)]:
    arcpy.AddField_management(agricultural_layer, 'WARNING', 'TEXT', field_length=2000)

arcpy.AddMessage("Now calculating corridor scores...")
calculate_corridor_scores(agricultural_layer, eco_layer, corridor_score_field)

arcpy.AddMessage("Now calculating floodplain scores...")
calculate_floodplain_scores(agricultural_layer, floodplain_layer, floodplain_score_field, max_distance)

arcpy.AddMessage("Now calculating Natural Area scores...")
calculate_natural_area_scores(agricultural_layer, landscape_units_layer, NaturalArea_score_field)

arcpy.AddMessage("Now writing warnings to WARNING field...")
write_warnings(agricultural_layer)
