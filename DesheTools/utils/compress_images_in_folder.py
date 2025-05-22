import os
from PIL import Image # Make sure you have Pillow installed: pip install Pillow

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


# Example usage of the function:
if __name__ == "__main__":
    # Define your input and output folders
    # This should be the same output folder you used in the previous function to export images
    input_images_folder = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\Exported_Images"
    
    # Define a new folder for the compressed images
    output_compressed_folder = r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\Compressed_Images"

    # Call the compression function
    compress_images_in_folder(input_images_folder, output_compressed_folder, scale_factor=0.5)

    # You can also try other scale factors, e.g., 0.25 for 25% of original dimensions
    # compress_images_in_folder(input_images_folder, r"D:\Yoav\OneDrive - Tel-Aviv University\GIS\Products\Compressed_Images_25_percent", scale_factor=0.25)