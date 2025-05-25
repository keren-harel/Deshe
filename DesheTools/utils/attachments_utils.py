import arcpy
import os
from PIL import Image # Make sure you have Pillow installed: pip install Pillow


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

def compress_images_in_folder(input_folder, output_folder, scale_factor=0.5):
    """
    Resizes and saves images from an input folder to an output folder,
    reducing their dimensions by a specified scale factor.

    Arguments:
        input_folder (str): The path to the folder containing the original images.
        output_folder (str): The path to the folder where the compressed images will be saved.
        scale_factor (float): The factor by which to scale down the image dimensions.
                              For example, 0.5 for 50% of the original size.
    """
    # Ensure the output folder exists; create it if it doesn't.
    os.makedirs(output_folder, exist_ok=True)

    print(f"Starting image compression from: {input_folder}")
    print(f"Saving compressed images to: {output_folder}")
    print(f"Scaling factor: {scale_factor * 100}% of original dimensions.")

    processed_count = 0
    skipped_count = 0

    # List of common image extensions to process
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')

    for filename in os.listdir(input_folder):
        file_path = os.path.join(input_folder, filename)

        # Check if it's a file and has an image extension
        if os.path.isfile(file_path) and filename.lower().endswith(image_extensions):
            try:
                with Image.open(file_path) as img:
                    original_width, original_height = img.size
                    
                    # Calculate new dimensions
                    new_width = int(original_width * scale_factor)
                    new_height = int(original_height * scale_factor)

                    # Resize the image
                    # Image.LANCZOS is a high-quality downsampling filter.
                    resized_img = img.resize((new_width, new_height), Image.LANCZOS)

                    # Construct the output path
                    output_file_path = os.path.join(output_folder, filename)

                    # Save the resized image
                    # For JPEGs, you can also control quality (0-100).
                    # For PNGs, compression level can be set.
                    if filename.lower().endswith(('.jpg', '.jpeg')):
                        resized_img.save(output_file_path, quality=85) # Default quality for JPEG save is usually 75-85
                    else:
                        resized_img.save(output_file_path) # For PNGs, etc., save without specific quality parameter

                    print(f"Compressed and saved: {filename} (Original: {original_width}x{original_height}, New: {new_width}x{new_height})")
                    processed_count += 1

            except Exception as e:
                print(f"Could not process {filename}: {e}")
                skipped_count += 1
        else:
            print(f"Skipping non-image file: {filename}")
            skipped_count += 1

    print(f"Image compression completed. Processed {processed_count} images, skipped {skipped_count} files.")

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
    # Define the parameters
    gdb_path_example = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\smy4129.gdb"
    attachment_table_example = "samples__ATTACH"
    output_folder_example = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\Exported_Images"

    # Call the function
    export_attachments_from_gdb(gdb_path_example, attachment_table_example, output_folder_example)

    # Define your input and output folders
    # This should be the same output folder you used in the previous function to export images
    input_images_folder = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\Exported_Images"
    
    # Define a new folder for the compressed images
    output_compressed_folder = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\Compressed_Images"

    # Call the compression function
    compress_images_in_folder(input_images_folder, output_compressed_folder, scale_factor=0.5)

    # You can also try other scale factors, e.g., 0.25 for 25% of original dimensions
    # compress_images_in_folder(input_images_folder, r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\Compressed_Images_25_percent", scale_factor=0.25)

    # Define the parameters for updating attachments
    gdb_path = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\smy4129.gdb"
    attachment_table = "samples__ATTACH"
    # This should be the output folder from the image compression step
    compressed_folder = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\Compressed_Images"

    # Call the function to update attachments
    update_attachments_in_gdb(gdb_path, attachment_table, compressed_folder, run_compact=True)