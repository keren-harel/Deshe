import arcpy
import os

def update_attachments_in_gdb(gdb_path, attachment_table_name, compressed_images_folder):
    """
    Updates existing attachments in a Geodatabase (GDB) table with compressed image files
    from a specified folder.

    Arguments:
        gdb_path (str): The full path to the Geodatabase file.
        attachment_table_name (str): The name of the attachment table within the GDB (e.g., "Points_ATTACH").
        compressed_images_folder (str): The path to the folder containing the compressed images.
    """
    # Build the full path to the attachment table
    attachment_table_path = os.path.join(gdb_path, attachment_table_name)

    # Fields required for updating: ATT_NAME to find the record, DATA to update the binary data,
    # and 'OID@' to get the unique object ID of the row for the UpdateCursor.
    fields_to_update = ["ATT_NAME", "DATA", "OID@"] 

    print(f"Starting to update attachments in: {attachment_table_path}")
    print(f"Reading compressed images from: {compressed_images_folder}")

    # Prepare a dictionary mapping filenames to their full paths for quick lookup
    compressed_files = {}
    for filename in os.listdir(compressed_images_folder):
        file_path = os.path.join(compressed_images_folder, filename)
        if os.path.isfile(file_path):
            compressed_files[filename] = file_path

    if not compressed_files:
        print("No compressed images found in the specified folder. Exiting.")
        return

    updated_count = 0
    skipped_count = 0

    try:
        # Use UpdateCursor to read and modify rows in the attachment table
        with arcpy.da.UpdateCursor(attachment_table_path, fields_to_update) as cursor:
            for row in cursor:
                att_name = row[0]  # Original filename from the GDB attachment table
                object_id = row[2] # Object ID of the attachment record (using OID@ token)

                # Check if a compressed file with this name exists
                if att_name in compressed_files:
                    compressed_file_path = compressed_files[att_name]
                    try:
                        # Read the binary data of the compressed image
                        with open(compressed_file_path, 'rb') as file:
                            binary_data_new = file.read()

                        # Update the DATA field of the current row
                        row[1] = binary_data_new # Assign the new binary data to the 'DATA' field
                        cursor.updateRow(row) # Commit the changes to the row

                        print(f"Updated attachment for '{att_name}' (OBJECTID: {object_id}) with compressed data.")
                        updated_count += 1
                        # Remove the file from our dictionary to track processed files
                        # This also helps identify files that were not matched/processed
                        del compressed_files[att_name] 

                    except Exception as e:
                        print(f"Failed to read/update file '{att_name}' (OBJECTID: {object_id}): {e}")
                        skipped_count += 1
                else:
                    # This case means an attachment exists in GDB but no corresponding compressed file was found
                    print(f"No compressed file found for attachment '{att_name}' (OBJECTID: {object_id}). Skipping.")
                    skipped_count += 1

        print(f"Attachment update completed. Updated {updated_count} attachments.")
        if skipped_count > 0:
            print(f"Skipped {skipped_count} attachments due to errors or missing compressed files.")
        if compressed_files: # Check if there are any remaining files in the dictionary
            print(f"Warning: The following compressed files were not found in the GDB attachment table:")
            for filename in compressed_files.keys():
                print(f"- {filename}")

    except arcpy.ExecuteError:
        # Handle ArcPy specific errors
        print(f"ArcPy Error: {arcpy.GetMessages(2)}")
    except Exception as e:
        # Handle other general errors
        print(f"An error occurred: {e}")

# Example usage of the function:
if __name__ == "__main__":
    # Define the parameters for updating attachments
    gdb_path_for_update = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\smy4129.gdb"
    attachment_table_for_update = "samples__ATTACH"
    # This should be the output folder from the image compression step
    compressed_images_folder_path = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\Compressed_Images"

    # Call the function to update attachments
    update_attachments_in_gdb(gdb_path_for_update, attachment_table_for_update, compressed_images_folder_path)