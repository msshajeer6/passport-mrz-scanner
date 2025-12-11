import sys
import os
import json
import argparse 
import tempfile
from fastmrz import FastMRZ
from pdf2image import convert_from_path
from PIL import Image

def process_image(image_path, show_progress=False):
    """
    Takes an image path and tries to find MRZ data by rotating it.

    Args:
        image_path (str): The path to the image file to process.
        show_progress (bool): If True, prints progress for each rotation attempt.

    Returns:
        dict: A dictionary containing the parsed MRZ data on success.
        None: If no valid MRZ data is found after all rotations.
    """
    try:
        fast_mrz = FastMRZ(tesseract_path=r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe')
        # fast_mrz = FastMRZ()

        original_image = Image.open(image_path)

        for i in range(4):
            angle = i * 90
            if show_progress:
                print(f"--- Attempting to read MRZ at {angle} degrees rotation ---")

            image_to_scan = original_image.rotate(-angle, expand=True)
            
            temp_image_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_f:
                    temp_image_path = temp_f.name
                
                image_to_scan.save(temp_image_path)
                
                passport_mrz_json = fast_mrz.get_details(temp_image_path, include_checkdigit=False)

                # Check for a successful parse
                if passport_mrz_json and "surname" in passport_mrz_json:
                    if show_progress:
                        print("--- MRZ Data Found! ---")
                    # On success, also get the raw text and add it to the result
                    raw_text = fast_mrz.get_details(temp_image_path, ignore_parse=True)
                    passport_mrz_json['raw_text'] = raw_text
                    return passport_mrz_json

            finally:
                if temp_image_path and os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
        
        return None

    except Exception as e:
        return {"error": str(e)}


# --- Main script execution starts here ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan an image or PDF for Machine-Readable Zone (MRZ) data.")
    parser.add_argument("input_file", help="Path to the image or PDF file to be scanned.")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="The output format. 'text' for human-readable progress, 'json' for a single JSON output."
    )
    args = parser.parse_args()

    show_progress = args.format == 'text'
    
    input_file_path = args.input_file
    image_to_process = None
    is_temp_file = False
    final_result = None

    try:
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(f"The file was not found: {input_file_path}")

        if input_file_path.lower().endswith('.pdf'):
            if show_progress:
                print(f"PDF file detected. Converting '{input_file_path}' to an image...")
            images = convert_from_path(input_file_path, first_page=1, last_page=1)
            
            if images:
                image_to_process = "temp_passport_page.png"
                images[0].save(image_to_process, 'PNG')
                is_temp_file = True
                if show_progress:
                    print(f"Successfully converted to '{image_to_process}'.")
            else:
                raise IOError("Could not convert PDF to image.")
        else:
            image_to_process = input_file_path

        if image_to_process:
            if show_progress:
                print(f"\nProcessing image: '{image_to_process}'...")
            final_result = process_image(image_to_process, show_progress)

    except Exception as e:
        final_result = {"error": str(e)}
        
    finally:
        if is_temp_file and os.path.exists(image_to_process):
            if show_progress:
                print(f"\nCleaning up temporary file: '{image_to_process}'...")
            os.remove(image_to_process)
            if show_progress:
                print("Cleanup complete.")

    # --- Final Output ---
    if args.format == 'json':
        output_json = {}
        if final_result and "error" in final_result:
            output_json = {"status": "error", "message": final_result["error"]}
        elif final_result:
            output_json = {"status": "success", "data": final_result}
        else:
            output_json = {"status": "failure", "message": "Could not find any valid MRZ data after trying all four rotations."}
        print(json.dumps(output_json, indent=4))
    else:
        if final_result and "surname" in final_result:
             print("\n--- JSON Data ---")
             print(json.dumps(final_result, indent=4))
             print("\n--- Raw MRZ Text ---")
             # <<< MODIFICATION: The string is now on a single line >>>
             print(final_result.get('raw_text', 'Not available.'))
        elif not final_result:
             print("\n--- MRZ Data Not Found ---")
             print("Could not find any valid MRZ data after trying all four rotations.")
        elif "error" in final_result:
             print(f"\nAn error occurred: {final_result['error']}")