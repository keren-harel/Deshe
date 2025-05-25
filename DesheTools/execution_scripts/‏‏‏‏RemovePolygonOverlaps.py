# ----------------------------
# Merged version: combines user logic and updated erase handling
# Last updated: 11/05/2025
# ----------------------------

import arcpy
import os

def validate_geodatabase(gdb_path):
    try:
        if not os.path.exists(gdb_path):
            raise Exception(f"Geodatabase does not exist: {gdb_path}")

        arcpy.env.workspace = gdb_path
        desc = arcpy.Describe(gdb_path)
        if desc.workspaceType != "LocalDatabase":
            raise Exception(f"Invalid geodatabase: {gdb_path}")

        datasets = arcpy.ListFeatureClasses() + arcpy.ListTables()
        if not datasets:
            arcpy.AddError("No feature classes or tables found.")
            return None

        return datasets
    except Exception as e:
        arcpy.AddError(f"Geodatabase validation failed: {e}")
        return None

# --- Start ---
aprx = arcpy.mp.ArcGISProject("CURRENT")
map_obj = aprx.activeMap

gdb_path = aprx.defaultGeodatabase
datasets = validate_geodatabase(gdb_path)
if not datasets:
    raise Exception("Geodatabase validation failed.")

# Get layer name
input_layer_name = arcpy.GetParameterAsText(0).strip().lower()
selected_layer = None
for layer in datasets:
    if layer.strip().lower() == input_layer_name:
        selected_layer = layer
        desc = arcpy.Describe(layer)
        arcpy.AddMessage(f"Layer type: {desc.datatype}")
        break

if not selected_layer:
    raise Exception(f"Layer '{input_layer_name}' not found.")

# Copy the layer
processed_layer_path = os.path.join(gdb_path, arcpy.CreateUniqueName("stands_cleaned", gdb_path))
arcpy.CopyFeatures_management(selected_layer, processed_layer_path)

OUTPUT_LAYER = processed_layer_path
problematic_oids = []
erase_operations = []

# Main loop
with arcpy.da.SearchCursor(OUTPUT_LAYER, ["OID@", "SHAPE@"]) as cursor1:
    for oid1, shape1 in cursor1:
        with arcpy.da.SearchCursor(OUTPUT_LAYER, ["OID@", "SHAPE@"]) as cursor2:
            for oid2, shape2 in cursor2:
                if oid2 <= oid1:
                    continue
                if shape1.overlaps(shape2) or shape1.within(shape2) or shape1.contains(shape2):
                    arcpy.AddWarning(f"Spatial relation: OID {oid1} <-> OID {oid2}")
                    problematic_oids.extend([oid1, oid2])

                    temp_fc1 = "in_memory/temp_fc1"
                    temp_fc2 = "in_memory/temp_fc2"
                    for fc in [temp_fc1, temp_fc2]:
                        if arcpy.Exists(fc):
                            arcpy.Delete_management(fc)

                    arcpy.management.CreateFeatureclass("in_memory", "temp_fc1", "POLYGON", spatial_reference=shape1.spatialReference)
                    arcpy.management.CreateFeatureclass("in_memory", "temp_fc2", "POLYGON", spatial_reference=shape2.spatialReference)

                    with arcpy.da.InsertCursor(temp_fc1, ["SHAPE@"]) as icur:
                        icur.insertRow([shape1])
                    with arcpy.da.InsertCursor(temp_fc2, ["SHAPE@"]) as icur:
                        icur.insertRow([shape2])

                    if shape1.overlaps(shape2):
                        intersect_fc = f"in_memory/intersect_{oid1}_{oid2}"
                        erase_fc = f"in_memory/erase_{oid1}_{oid2}"
                        for fc in [intersect_fc, erase_fc]:
                            if arcpy.Exists(fc):
                                arcpy.Delete_management(fc)

                        arcpy.analysis.Intersect([temp_fc1, temp_fc2], intersect_fc)
                        with arcpy.da.SearchCursor(intersect_fc, ["SHAPE@"]) as icur:
                            for intersect_shape, in icur:
                                arcpy.analysis.Erase(temp_fc1, intersect_fc, erase_fc)
                                with arcpy.da.SearchCursor(erase_fc, ["SHAPE@"]) as ecur:
                                    for new_shape, in ecur:
                                        with arcpy.da.UpdateCursor(OUTPUT_LAYER, ["OID@", "SHAPE@"]) as ucur:
                                            for row in ucur:
                                                if row[0] == oid1:
                                                    row[1] = new_shape
                                                    ucur.updateRow(row)
                                                    arcpy.AddMessage(f"Updated OID {oid1} after overlap erase")
                        erase_operations.append((oid1, oid2))

                    elif shape1.within(shape2) or shape1.contains(shape2):
                        erase_from_oid = oid2 if shape1.within(shape2) else oid1
                        erase_by_shape = shape1 if shape1.within(shape2) else shape2

                        erase_fc = f"in_memory/erase_{erase_from_oid}"
                        if arcpy.Exists(erase_fc):
                            arcpy.Delete_management(erase_fc)

                        with arcpy.da.SearchCursor(OUTPUT_LAYER, ["OID@", "SHAPE@"]) as s_cur:
                            for oid, shape in s_cur:
                                if oid == erase_from_oid:
                                    arcpy.management.CreateFeatureclass("in_memory", "temp_to_erase", "POLYGON", spatial_reference=shape.spatialReference)
                                    with arcpy.da.InsertCursor("in_memory/temp_to_erase", ["SHAPE@"]) as icur:
                                        icur.insertRow([shape])
                                    arcpy.analysis.Erase("in_memory/temp_to_erase", erase_by_shape, erase_fc)
                                    with arcpy.da.SearchCursor(erase_fc, ["SHAPE@"]) as ecur:
                                        for new_shape, in ecur:
                                            with arcpy.da.UpdateCursor(OUTPUT_LAYER, ["OID@", "SHAPE@"]) as ucur:
                                                for row in ucur:
                                                    if row[0] == erase_from_oid:
                                                        row[1] = new_shape
                                                        ucur.updateRow(row)
                                                        arcpy.AddMessage(f"Cleaned overlap from OID {erase_from_oid}")
                                    break

# Add cleaned layer to map
map_obj.addDataFromPath(OUTPUT_LAYER)

# Optional: Create layer of problematic polygons
if problematic_oids:
    problem_layer = os.path.join(gdb_path, arcpy.CreateUniqueName("problematic_polygons", gdb_path))
    temp_layer = "in_memory/problem_layer"
    if arcpy.Exists(temp_layer):
        arcpy.Delete_management(temp_layer)
    arcpy.MakeFeatureLayer_management(OUTPUT_LAYER, temp_layer)
    where_clause = f"OBJECTID IN ({','.join(map(str, set(problematic_oids)))})"
    arcpy.SelectLayerByAttribute_management(temp_layer, "NEW_SELECTION", where_clause)
    arcpy.CopyFeatures_management(temp_layer, problem_layer)
    map_obj.addDataFromPath(problem_layer)
    arcpy.AddMessage(f"Problematic polygons saved to: {problem_layer}")

# Summary
arcpy.AddMessage("\n--- Summary ---")
arcpy.AddMessage(f"Total erase operations: {len(erase_operations)}")
if erase_operations:
    for oid1, oid2 in erase_operations:
        arcpy.AddMessage(f"OID {oid1} - cleaned overlap with OID {oid2}")
if problematic_oids:
    arcpy.AddMessage(f"Total problematic polygons: {len(set(problematic_oids))}")
