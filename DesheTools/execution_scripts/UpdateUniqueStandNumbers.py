
#----------------------------
# Last updated: 29/04/2025 
#----------------------------

import arcpy
from collections import defaultdict

def update_stand_numbers(polygon_layer):
    helka_stands = defaultdict(list)
    changes = []
    warnings = []

    # שלב ראשון: איסוף כל הערכים הקיימים לפי HELKA
    with arcpy.da.SearchCursor(polygon_layer, ["HELKA", "STAND_NO"]) as cursor:
        for helka, stand_no in cursor:
            if helka != 0 and stand_no is not None:
                helka_stands[helka].append(stand_no)

    # שלב שני: עדכון העומדים הכפולים
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

            if stand_no in existing_ids_by_helka[helka]:
                max_existing = max(helka_stands[helka])
                base = (max_existing // 10 + 1) * 10
                new_no = base + counter_by_helka[helka]
                counter_by_helka[helka] += 1

                cursor.updateRow((helka, new_no, oid))
                changes.append((helka, f"OID {oid} (HELKA {helka}): {stand_no} → {new_no}"))
            else:
                existing_ids_by_helka[helka].add(stand_no)

    # מיון פלט השינויים לפי HELKA
    changes.sort(key=lambda x: x[0])

    if changes:
        arcpy.AddMessage("Changes made (sorted by HELKA):")
        for _, change_msg in changes:
            arcpy.AddMessage(change_msg)
    else:
        arcpy.AddMessage("No changes were necessary.")

    if warnings:
        arcpy.AddWarning("Warnings:")
        for warning in warnings:
            arcpy.AddWarning(warning)

# הרצה
if __name__ == "__main__":
    layer = arcpy.GetParameterAsText(0)
    update_stand_numbers(layer)
