import arcpy
import os

# Path to the geodatabase
gdb_path = r"C:\Path\To\Your\Data.gdb"

# Name of the attachment table (usually ends with _ATTACH)
attachment_table = "your_attachment_table"  # Example: "Points_ATTACH"

# Path to the destination folder for exporting images
output_folder = r"C:\Exported_Images"

# Ensure the folder exists
os.makedirs(output_folder, exist_ok=True)

# Important fields in the attachment table
fields = ["ATTACHMENTID", "REL_GLOBALID", "ATT_NAME", "DATA"]

# Build the full path to the table
attachment_table_path = os.path.join(gdb_path, attachment_table)

# Read rows from the table
with arcpy.da.SearchCursor(attachment_table_path, fields) as cursor:
    for row in cursor:
        attachment_id = row[0]
        rel_globalid = row[1]
        file_name = row[2]
        binary_data = row[3]

        # Generate a safe filename for export
        safe_filename = f"{attachment_id}_{file_name}"
        output_path = os.path.join(output_folder, safe_filename)

        # Write the file to disk
        with open(output_path, 'wb') as file:
            file.write(binary_data)

        print(f"Saved: {output_path}")
