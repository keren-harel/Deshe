#----------------------------
# Last updated: 21/07/2025 
#----------------------------

import arcpy

try:
    # קלט מהמשתמש
    input_layer = arcpy.GetParameterAsText(0)
    area_field = arcpy.GetParameterAsText(1)

    # בדיקת מערכת קואורדינטות
    spatial_ref = arcpy.Describe(input_layer).spatialReference
    arcpy.AddMessage(f"Detected coordinate system: {spatial_ref.name} (EPSG:{spatial_ref.factoryCode})")

    if spatial_ref.factoryCode not in [2039, 6991]:
        arcpy.AddError("Warning: The coordinate system is not ITM (EPSG:2039) or ICS (EPSG:6991). Area calculations may be inaccurate.")

    # בדיקה אם השדה קיים
    fields = [f.name for f in arcpy.ListFields(input_layer)]
    if area_field not in fields:
        arcpy.AddWarning(f"The field '{area_field}' does not exist. Creating it...")
        arcpy.AddField_management(input_layer, area_field, 'DOUBLE')
        arcpy.AddMessage(f"The field '{area_field}' was created successfully.")
    else:
        arcpy.AddMessage(f"The field '{area_field}' already exists. Existing values will be overwritten.")

    # חישוב שטח בדונמים עם עיגול לשתי ספרות
    count = 0
    with arcpy.da.UpdateCursor(input_layer, ['SHAPE@AREA', area_field]) as cursor:
        for row in cursor:
            if row[0] is not None:
                row[1] = round(row[0] / 1000, 2)
                cursor.updateRow(row)
                count += 1

    arcpy.AddMessage(f"Calculation completed successfully. {count} features were updated.")

except Exception as e:
    arcpy.AddError(f"Field update failed: {str(e)}")
