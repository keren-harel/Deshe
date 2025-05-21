import arcpy
import os
from PIL import Image
import shutil

# Settings
gdb_path = r"C:\Path\To\Your\Data.gdb"
attachment_table = "Points_ATTACH"  # Name of the attachment table
output_folder = r"C:\Temp\Exported_Images"
compressed_folder = r"C:\Temp\Compressed_Images"
feature_class = "Points"  # Name of the point feature class associated with the attachments

# Create folders
os.makedirs(output_folder, exist_ok=True)
os.makedirs(compressed_folder, exist_ok=True)

# Step 1: Export attachments
print("Exporting attachments...")
fields = ["ATTACHMENTID", "REL_GLOBALID", "ATT_NAME", "DATA"]
attachment_table_path = os.path.join(gdb_path, attachment_table)
export_log = []

with arcpy.da.SearchCursor(attachment_table_path, fields) as cursor:
    for row in cursor:
        att_id, rel_guid, name, data = row
        filename = f"{att_id}_{name}"
        export_path = os.path.join(output_folder, filename)
        with open(export_path, 'wb') as f:
            f.write(data)
        export_log.append((rel_guid, export_path))

# Step 2: Compress images
print("Compressing images...")
compressed_log = []

for rel_guid, original_path in export_log:
    filename = os.path.basename(original_path)
    compressed_path = os.path.join(compressed_folder, filename)

    try:
        with Image.open(original_path) as img:
            img = img.convert("RGB")
            img.save(compressed_path, "JPEG", quality=70, optimize=True)
        compressed_log.append((rel_guid, compressed_path))
    except Exception as e:
        print(f"Error in file {filename}: {e}")

# Step 3: Delete existing attachments (optional if working on a copy)
print("Deleting existing attachments...")
arcpy.DeleteAttachments_management(os.path.join(gdb_path, feature_class), "GLOBALID",
                                   os.path.join(gdb_path, attachment_table), "REL_GLOBALID")

# Step 4: Import compressed attachments
print("Importing compressed attachments...")
# Create a temporary mapping table to link files
temp_table = os.path.join("in_memory", "attach_table")
arcpy.CreateTable_management("in_memory", "attach_table")
arcpy.AddField_management(temp_table, "REL_GLOBALID", "GUID")
arcpy.AddField_management(temp_table, "ATT_NAME", "TEXT")
arcpy.AddField_management(temp_table, "FILE_PATH", "TEXT")

with arcpy.da.InsertCursor(temp_table, ["REL_GLOBALID", "ATT_NAME", "FILE_PATH"]) as cursor:
    for rel_guid, path in compressed_log:
        filename = os.path.basename(path)
        cursor.insertRow((rel_guid, filename, path))

# Add the attachments back
arcpy.AddAttachments_management(
    os.path.join(gdb_path, feature_class),
    "GLOBALID",
    temp_table,
    "REL_GLOBALID",
    "FILE_PATH"
)

print("Done! All images were compressed and reattached.")
