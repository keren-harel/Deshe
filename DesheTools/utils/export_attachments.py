import arcpy
import os

def export_attachments_from_gdb(gdb_path, attachment_table_name, output_folder):
    """
    Exports image files from an attachment table in a Geodatabase (GDB) to a specified folder.

    Arguments:
        gdb_path (str): The full path to the Geodatabase file.
        attachment_table_name (str): The name of the attachment table within the GDB (e.g., "Points_ATTACH").
        output_folder (str): The path to the folder where the image files will be exported.
    """
    # Ensure the output folder exists; create it if it doesn't.
    os.makedirs(output_folder, exist_ok=True)

    # Essential fields in the attachment table
    # ATTACHMENTID: Unique identifier for the attachment.
    # REL_GLOBALID: Global ID linking the attachment to the original feature class record.
    # ATT_NAME: Original filename of the attachment.
    # DATA: Binary data of the attachment.
    fields = ["ATTACHMENTID", "REL_GLOBALID", "ATT_NAME", "DATA"]

    # Build the full path to the attachment table
    attachment_table_path = os.path.join(gdb_path, attachment_table_name)

    print(f"Starting to export attachments from: {attachment_table_path}")
    print(f"To folder: {output_folder}")

    try:
        # Read rows from the table using SearchCursor
        with arcpy.da.SearchCursor(attachment_table_path, fields) as cursor:
            exported_count = 0
            for row in cursor:
                attachment_id = row[0]
                rel_globalid = row[1]
                file_name = row[2]
                binary_data = row[3]

                # Generate a safe filename for export.
                # Additional logic can be added here to handle duplicate filenames or invalid characters.
                safe_filename = file_name

                output_path = os.path.join(output_folder, safe_filename)

                # Write the file to disk
                with open(output_path, 'wb') as file:
                    file.write(binary_data)

                print(f"Saved: {output_path}")
                exported_count += 1
        print(f"Export completed. A total of {exported_count} files were saved.")

    except arcpy.ExecuteError:
        # Handle ArcPy specific errors
        print(f"ArcPy Error: {arcpy.GetMessages(2)}")
    except Exception as e:
        # Handle other general errors
        print(f"An error occurred: {e}")

# Example usage of the function:
if __name__ == "__main__":
    # Define the parameters
    gdb_path_example = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\smy4129.gdb"
    attachment_table_example = "samples__ATTACH"
    output_folder_example = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\Exported_Images"

    # Call the function
    export_attachments_from_gdb(gdb_path_example, attachment_table_example, output_folder_example)

