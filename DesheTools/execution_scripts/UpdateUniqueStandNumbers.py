"""
איך להגדיר את הכלי ב-ArcGIS Toolbox:

    פרמטר ראשון – polygon_layer (שכבת פוליגונים)
    פרמטר שני – assign_to_invalid (Boolean: כן/לא)
        תיאור: "האם לעדכן גם עומדים עם ערך 0 או NULL?
"""
#----------------------------
# Last updated: 24/11/2026
#----------------------------

import os
import arcpy
from collections import defaultdict


def get_gdb_workspace(layer):
    """מחזיר את נתיב ה-GDB (גם כשהשכבה בתוך Feature Dataset)."""
    path = arcpy.Describe(layer).catalogPath
    ws = os.path.dirname(path)
    while not ws.lower().endswith((".gdb", ".sde")):
        parent = os.path.dirname(ws)
        if parent == ws:
            break
        ws = parent
    return ws


def update_stand_numbers(polygon_layer, assign_to_invalid=True):
    helka_stands = defaultdict(list)
    changes = []
    warnings = []

    # שלב ראשון: איסוף כל הערכים הקיימים לפי HELKA
    with arcpy.da.SearchCursor(polygon_layer, ["HELKA", "STAND_NO"]) as cursor:
        for helka, stand_no in cursor:
            if helka != 0 and isinstance(stand_no, int) and stand_no != 0:
                helka_stands[helka].append(stand_no)

    # שלב שני: עדכון עומדים בתוך סשן עריכה שהסקריפט פותח בעצמו
    edit = arcpy.da.Editor(get_gdb_workspace(polygon_layer))
    edit.startEditing(False, False)
    edit.startOperation()
    try:
        with arcpy.da.UpdateCursor(polygon_layer, ["HELKA", "STAND_NO", "OID@"]) as cursor:
            counter_by_helka = defaultdict(int)
            existing_ids_by_helka = defaultdict(set)

            for helka, stand_no, oid in cursor:
                if helka == 0:
                    if stand_no != 0:
                        changes.append((helka, f"OID {oid} (HELKA 0): {stand_no} → 0"))
                        cursor.updateRow((helka, 0, oid))
                    warnings.append(f"OID {oid} has HELKA = 0 – no valid assignment.")
                    continue

                is_invalid = stand_no is None or not isinstance(stand_no, int) or stand_no == 0

                if is_invalid and assign_to_invalid:
                    max_existing = max(helka_stands[helka], default=0)
                    base = (max_existing // 10 + 1) * 10
                    new_no = base + counter_by_helka[helka]
                    counter_by_helka[helka] += 1

                    cursor.updateRow((helka, new_no, oid))
                    helka_stands[helka].append(new_no)
                    existing_ids_by_helka[helka].add(new_no)
                    changes.append((helka, f"OID {oid} (HELKA {helka}): {stand_no} → {new_no}"))
                    continue

                if stand_no in existing_ids_by_helka[helka]:
                    max_existing = max(helka_stands[helka], default=0)
                    base = (max_existing // 10 + 1) * 10
                    new_no = base + counter_by_helka[helka]
                    counter_by_helka[helka] += 1

                    cursor.updateRow((helka, new_no, oid))
                    changes.append((helka, f"OID {oid} (HELKA {helka}): {stand_no} → {new_no}"))
                else:
                    existing_ids_by_helka[helka].add(stand_no)

        edit.stopOperation()
        edit.stopEditing(True)   # שמירת השינויים
    except Exception:
        edit.abortOperation()
        edit.stopEditing(False)  # ביטול – לא נשמר כלום
        raise

    # מיון פלט השינויים לפי HELKA
    changes.sort(key=lambda x: x[0])

    if changes:
        arcpy.AddMessage("Changes made (sorted by HELKA):")
        for _, change_msg in changes:
            arcpy.AddMessage(change_msg)
        arcpy.AddMessage(f"Total changes made: {len(changes)}")
    else:
        arcpy.AddMessage("No changes were necessary.")

    if warnings:
        arcpy.AddWarning("Warnings:")
        for warning in warnings:
            arcpy.AddWarning(warning)
        arcpy.AddWarning(f"Total warnings: {len(warnings)}")


# הרצה
if __name__ == "__main__":
    layer = arcpy.GetParameterAsText(0)
    assign_invalid_param = arcpy.GetParameterAsText(1).lower() == 'true'

    try:
        update_stand_numbers(layer, assign_to_invalid=assign_invalid_param)
    except RuntimeError as e:
        if "edit session" in str(e).lower():
            arcpy.AddError(
                "Could not edit the stands layer. Stop any active edit session "
                "in the project and run the tool again."
            )
        else:
            raise