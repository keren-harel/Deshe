
# -*- coding: utf-8 -*-
import arcpy
import re
from eco_score_enum import CorridorScore, FloodplainScore, NaturalArea_type

# Get layers to process
agricultural_layer = arcpy.GetParameterAsText(0)  # Agricultural parcels layer
eco_layer = arcpy.GetParameterAsText(1)           # ECO layer
floodplain_layer = arcpy.GetParameterAsText(2)    # Floodplain layer
landscape_units_layer = arcpy.GetParameterAsText(7)  # Landscape Units layer

# Get fields to store scores 
corridor_score_field = arcpy.GetParameterAsText(3)  # Field for corridor score
floodplain_score_field = arcpy.GetParameterAsText(4) # Field for floodplain score
NaturalArea_score_field = arcpy.GetParameterAsText(6)    # Field for Land Cover score

# Get other values from user  
max_distance = float(arcpy.GetParameterAsText(5))    # Max distance (e.g., 500)

# Add fields if they do not exist
for field_name in [corridor_score_field, floodplain_score_field]:
    if field_name not in [f.name for f in arcpy.ListFields(agricultural_layer)]:
        arcpy.AddField_management(agricultural_layer, field_name, "SHORT")

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

# Ensure WARNING field exists to store collected warnings (TEXT large enough for concatenated messages)
if 'WARNING' not in [f.name for f in arcpy.ListFields(agricultural_layer)]:
    arcpy.AddField_management(agricultural_layer, 'WARNING', 'TEXT', field_length=2000)

# Calculate corridor score
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

# Calculate floodplain score
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


# Calculate Natural Area score 
try:
    with arcpy.da.SearchCursor(landscape_units_layer, ["SHAPE@"]) as eco_cursor:
        for eco_geom in eco_cursor:
            # Open an update cursor on parcels and update only those that are contained/overlap with the current ECO geometry
            with arcpy.da.UpdateCursor(agricultural_layer, ["OID@", "SHAPE@", NaturalArea_score_field, "LandCov"]) as parcel_cursor:
                for oid, geom, current_score, landcov in parcel_cursor:
                    if geom.overlaps(eco_geom[0]) or geom.within(eco_geom[0]) or eco_geom[0].within(geom):
                        print(f"Processing parcel OID {oid} with LandCov '{landcov}'")
                    else:
                        continue  # Skip parcels that do not overlap or are not contained
except Exception as e:
    arcpy.AddError(f"Error calculating Natural Area scores: {e}")

# After processing, write collected warnings into the WARNING field per OID
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
