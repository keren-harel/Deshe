#----------------------------
# Last updated: 07/05/2025 
#----------------------------

import arcpy

try:
    # Get input from the user
    input_layer = arcpy.GetParameterAsText(0)
    area_field = arcpy.GetParameterAsText(1)  # FIELDS input

    # Check if the coordinate system is Israeli TM (ITM - EPSG:2039) or ICS (EPSG:6991)
    spatial_ref = arcpy.Describe(input_layer).spatialReference
    arcpy.AddMessage(f"Detected coordinate system: {spatial_ref.name} (EPSG:{spatial_ref.factoryCode})")

    if spatial_ref.factoryCode not in [2039, 6991]:
        arcpy.AddWarning("Warning: The coordinate system is not ITM (EPSG:2039) or ICS (EPSG:6991). Area calculations may be inaccurate.")

    # Check if the user-specified field exists
    fields = [f.name for f in arcpy.ListFields(input_layer)]
    if area_field not in fields:
        arcpy.AddMessage(f"The field '{area_field}' does not exist. Creating it...")
        arcpy.AddField_management(input_layer, area_field, 'DOUBLE')
        arcpy.AddMessage(f"The field '{area_field}' was created successfully.")

    # Update the user-specified field with area values in dunams
    with arcpy.da.UpdateCursor(input_layer, ['SHAPE@AREA', area_field]) as cursor:
        for row in cursor:
            dunam_value = int(row[0] / 1000)  # 1 dunam = 1000 square meters
            row[1] = dunam_value
            cursor.updateRow(row)

    arcpy.AddMessage(f"Calculation completed successfully. The field '{area_field}' has been updated.")

except Exception as e:
    arcpy.AddError(f"Field update failed: {str(e)}")
