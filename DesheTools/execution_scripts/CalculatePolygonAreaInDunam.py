#----------------------------
# Calculate Polygon Area In Dunam
# Geodesic version - works in ANY coordinate system
# (ITM, WGS84, Web Mercator, UTM, ...)
#----------------------------

import arcpy

try:
    # קלט מהמשתמש
    input_layer = arcpy.GetParameterAsText(0)
    area_field = arcpy.GetParameterAsText(1)

    # בדיקת מערכת קואורדינטות (מידע בלבד - החישוב גאודזי ולכן לא תלוי בהטלה)
    spatial_ref = arcpy.Describe(input_layer).spatialReference
    if spatial_ref is None or spatial_ref.type == "Unknown":
        raise ValueError("The layer has no coordinate system defined. Define it first (Define Projection).")

    arcpy.AddMessage(f"Detected coordinate system: {spatial_ref.name} (EPSG:{spatial_ref.factoryCode})")
    arcpy.AddMessage("Calculating GEODESIC area, independent of the layer's projection.")

    if spatial_ref.factoryCode in (3857, 102100, 102113):
        arcpy.AddWarning("The layer is in Web Mercator. Planar areas (Shape_Area) in this system are inflated by ~41% in Israel; "
                         "the geodesic result written here is correct, but Shape_Area is not.")

    # בדיקה אם השדה קיים
    fields = [f.name for f in arcpy.ListFields(input_layer)]
    if area_field not in fields:
        arcpy.AddWarning(f"The field '{area_field}' does not exist. Creating it...")
        arcpy.AddField_management(input_layer, area_field, 'DOUBLE')
        arcpy.AddMessage(f"The field '{area_field}' was created successfully.")
    else:
        arcpy.AddMessage(f"The field '{area_field}' already exists. Existing values will be overwritten.")

    # חישוב שטח גאודזי בדונמים (מ"ר / 1000), עיגול לשתי ספרות
    count = 0
    skipped = 0
    total_dunam = 0.0
    with arcpy.da.UpdateCursor(input_layer, ['SHAPE@', area_field]) as cursor:
        for row in cursor:
            geom = row[0]
            if geom is None:
                skipped += 1
                continue
            area_m2 = geom.getArea("GEODESIC", "SQUAREMETERS")
            dunam = round(area_m2 / 1000.0, 2)
            row[1] = dunam
            cursor.updateRow(row)
            total_dunam += dunam
            count += 1

    arcpy.AddMessage(f"Calculation completed successfully. {count} features were updated, {skipped} skipped (null geometry).")
    arcpy.AddMessage(f"Total area: {total_dunam:,.2f} dunam")

except Exception as e:
    arcpy.AddError(f"Field update failed: {str(e)}")