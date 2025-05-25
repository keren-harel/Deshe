import arcpy
import os

def update_attachments_in_gdb(gdb_path, attachment_table_name, compressed_images_folder, run_compact=True):
    """
    Updates existing attachments in a Geodatabase (GDB) table with compressed image files
    from a specified folder. Optionally compacts the GDB after update.

    Arguments:
        gdb_path (str): Path to the Geodatabase.
        attachment_table_name (str): Name of the attachment table (e.g., "Points_ATTACH").
        compressed_images_folder (str): Folder containing the compressed images.
        run_compact (bool): If True, compacts the GDB after updating attachments.
    """

    attachment_table_path = os.path.join(gdb_path, attachment_table_name)
    fields_to_update = ["ATT_NAME", "DATA", "OID@"]

    print(f"Starting to update attachments in: {attachment_table_path}")
    print(f"Reading compressed images from: {compressed_images_folder}")

    compressed_files = {
        fn: os.path.join(compressed_images_folder, fn)
        for fn in os.listdir(compressed_images_folder)
        if os.path.isfile(os.path.join(compressed_images_folder, fn))
    }

    if not compressed_files:
        print("No compressed images found. Exiting.")
        return

    updated_count = 0
    skipped_count = 0

    try:
        with arcpy.da.UpdateCursor(attachment_table_path, fields_to_update) as cursor:
            for row in cursor:
                att_name, _, object_id = row
                if att_name in compressed_files:
                    try:
                        with open(compressed_files[att_name], 'rb') as f:
                            row[1] = f.read()
                        cursor.updateRow(row)
                        updated_count += 1
                        del compressed_files[att_name]
                        print(f"Updated '{att_name}' (OBJECTID: {object_id})")
                    except Exception as e:
                        print(f"Failed to update '{att_name}' (OBJECTID: {object_id}): {e}")
                        skipped_count += 1
                else:
                    print(f"No compressed file for '{att_name}' (OBJECTID: {object_id}). Skipping.")
                    skipped_count += 1

        print(f"Update complete. Updated: {updated_count}, Skipped: {skipped_count}")
        if compressed_files:
            print("Unused compressed files:")
            for name in compressed_files:
                print(f"- {name}")

        # Optional GDB compact
        if run_compact:
            print("Compacting Geodatabase...")
            arcpy.Compact_management(gdb_path)
            print("Compacting completed.")

    except arcpy.ExecuteError:
        print(f"ArcPy Error: {arcpy.GetMessages(2)}")
    except Exception as e:
        print(f"General error: {e}")

# Example usage of the function:
if __name__ == "__main__":
    # Define the parameters for updating attachments
    gdb_path = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\smy4129.gdb"
    attachment_table = "samples__ATTACH"
    # This should be the output folder from the image compression step
    compressed_folder = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\Compressed_Images"

    # Call the function to update attachments
    update_attachments_in_gdb(gdb_path, attachment_table, compressed_folder, run_compact=True)