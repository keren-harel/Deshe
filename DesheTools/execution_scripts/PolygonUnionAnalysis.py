import arcpy
import os

def main():
    # יצירת אובייקט ArcGIS Project
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    
    # קבלת פרמטרים מהמשתמש
    polygon_layer = arcpy.GetParameterAsText(0)  # שכבת הפוליגונים
    boundary_layer = arcpy.GetParameterAsText(1)  # שכבת הגבול
    output_gdb = aprx.defaultGeodatabase  # הגיאודטאבייס ברירת המחדל של הפרויקט
    
    try:
        # בדיקת תקינות הגיאודטאבייס
        if not os.path.exists(output_gdb):
            raise Exception(f"Geodatabase does not exist: {output_gdb}")
        
        arcpy.env.workspace = output_gdb

        # יצירת שם ייחודי לשכבת Union
        union_output = os.path.join(output_gdb, arcpy.CreateUniqueName("Union_Output", output_gdb))

        # ביצוע Union
        arcpy.AddMessage("Running Union analysis...")
        arcpy.analysis.Union([polygon_layer, boundary_layer], union_output, "ALL", "", "GAPS")
        arcpy.AddMessage(f"Union completed successfully: {union_output}")

        # ביצוע Multipart to Singlepart
        singlepart_output = os.path.join(output_gdb, arcpy.CreateUniqueName("stands_work", output_gdb))
        arcpy.AddMessage("Converting Multipart to Singlepart...")
        arcpy.management.MultipartToSinglepart(union_output, singlepart_output)
        arcpy.AddMessage(f"Multipart to Singlepart completed successfully: {singlepart_output}")

        # הוספת שדה TYPE לשכבה המאוחדת (לאחר המרה ל-Singlepart)
        arcpy.AddMessage("Adding TYPE field...")
        arcpy.management.AddField(singlepart_output, "TYPE", "TEXT", field_length=50)
        
        # עדכון הערכים בשדה TYPE על בסיס התנאים שהגדרת
        arcpy.AddMessage("Calculating TYPE field values...")
        with arcpy.da.UpdateCursor(singlepart_output, ["FID_" + os.path.basename(polygon_layer), 
                                                        "FID_" + os.path.basename(boundary_layer), 
                                                        "TYPE"]) as cursor:
            for row in cursor:
                fid_stands = row[0]
                fid_gvul_nihul = row[1]
                
                if fid_stands > 0 and fid_gvul_nihul > 0:
                    row[2] = "חפיפה"
                elif fid_stands < 0 and fid_gvul_nihul > 0:
                    row[2] = "תוספת"
                elif fid_stands > 0 and fid_gvul_nihul < 0:
                    row[2] = "הסרה"
                else:
                    row[2] = "Error"
                
                cursor.updateRow(row)
        
        arcpy.AddMessage("TYPE field values updated successfully.")

        # הוספת השכבה המעובדת למפה הפעילה
        map_obj = aprx.activeMap
        map_obj.addDataFromPath(singlepart_output)
        arcpy.AddMessage(f"Output layer added to the map: {singlepart_output}")

    except Exception as e:
        arcpy.AddError(f"Error: {e}")

if __name__ == "__main__":
    main()
