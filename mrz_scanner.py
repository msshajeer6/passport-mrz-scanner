import sys
import os
import json
import argparse 
import tempfile
import time
from fastmrz import FastMRZ
from pdf2image import convert_from_path, pdfinfo_from_path
from PIL import Image
import pytesseract
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get configuration from environment variables with fallback defaults
TESSERACT_PATH = os.getenv('TESSERACT_PATH', r'C:\Program Files\Tesseract-OCR\tesseract.exe')
PDF_DPI = int(os.getenv('PDF_DPI', '300'))
OCR_PSM_MODE = int(os.getenv('OCR_PSM_MODE', '6'))
# Default max pages: None means all pages, or set a number to limit
MAX_PAGES_DEFAULT = os.getenv('MAX_PAGES_DEFAULT')
MAX_PAGES_DEFAULT = int(MAX_PAGES_DEFAULT) if MAX_PAGES_DEFAULT and MAX_PAGES_DEFAULT.lower() != 'none' else None

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
        # Use TESSERACT_PATH from environment, or empty string if not set (will use system PATH)
        tesseract_path = TESSERACT_PATH if TESSERACT_PATH else ""
        fast_mrz = FastMRZ(tesseract_path=tesseract_path)
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH if TESSERACT_PATH else pytesseract.pytesseract.tesseract_cmd

        original_image = Image.open(image_path)
        img_width, img_height = original_image.size

        # Try rotations: 0, -90 (for pre-rotated images), 90
        # Most MRZ images are either 0 or -90 degrees, so prioritize those
        # Only try 180/270 if first 3 don't work (rare cases)
        rotations_to_try = [0, -90, 90]
        
        for angle in rotations_to_try:
            if show_progress:
                print(f"--- Attempting to read MRZ at {angle} degrees rotation ---")

            image_to_scan = original_image.rotate(-angle, expand=True)
            
            # Try full image first
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
                
                # If fastmrz didn't find it on full image, try bottom 30% (MRZ is usually at bottom)
                # Only try this for first rotation to save time
                if angle == 0:
                    scan_width, scan_height = image_to_scan.size
                    bottom_region = image_to_scan.crop((0, int(scan_height * 0.7), scan_width, scan_height))
                    
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_f2:
                        temp_bottom_path = temp_f2.name
                    bottom_region.save(temp_bottom_path)
                    
                    try:
                        passport_mrz_json = fast_mrz.get_details(temp_bottom_path, include_checkdigit=False)
                        if passport_mrz_json and "surname" in passport_mrz_json:
                            if show_progress:
                                print("--- MRZ Data Found in bottom region! ---")
                            raw_text = fast_mrz.get_details(temp_bottom_path, ignore_parse=True)
                            passport_mrz_json['raw_text'] = raw_text
                            return passport_mrz_json
                    finally:
                        if os.path.exists(temp_bottom_path):
                            os.remove(temp_bottom_path)

            finally:
                if temp_image_path and os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
        
        # If fastmrz didn't find it, try direct pytesseract OCR with MRZ language (optimized)
        if show_progress:
            print("--- Trying direct OCR with MRZ language ---")
        
        try:
            original_image = Image.open(image_path)
            img_width, img_height = original_image.size
            
            # Prioritize most likely scenarios: rotated bottom region first (most common case)
            # Only try 2 regions and 1 PSM mode to save time
            rotated_img = original_image.rotate(90, expand=True)
            rot_width, rot_height = rotated_img.size
            
            regions_to_try = [
                ("bottom_30_rotated", rotated_img.crop((0, int(rot_height * 0.7), rot_width, rot_height))),
                ("full_rotated", rotated_img),
            ]
            
            # Use PSM mode from configuration
            for region_name, region_img in regions_to_try:
                try:
                    # Try direct OCR with MRZ language
                    custom_config = f'--oem 3 --psm {OCR_PSM_MODE} -l mrz'
                    raw_mrz_text = pytesseract.image_to_string(region_img, config=custom_config)
                    
                    if raw_mrz_text and len(raw_mrz_text.strip()) > 10:
                        # Clean up the text
                        cleaned_text = "\n".join([line.strip() for line in raw_mrz_text.strip().split("\n") if line.strip()])
                        
                        # Try to parse the raw text
                        tesseract_path = TESSERACT_PATH if TESSERACT_PATH else ""
                        fast_mrz = FastMRZ(tesseract_path=tesseract_path)
                        passport_mrz_json = fast_mrz.get_details(cleaned_text, input_type="text", include_checkdigit=False)
                        
                        if passport_mrz_json and "surname" in passport_mrz_json:
                            if show_progress:
                                print(f"--- MRZ Data Found via direct OCR in {region_name} region! ---")
                            passport_mrz_json['raw_text'] = cleaned_text
                            return passport_mrz_json
                except Exception:
                    continue
        except Exception as direct_ocr_error:
            if show_progress:
                print(f"Direct OCR attempt failed: {str(direct_ocr_error)}")
        
        return None

    except Exception as e:
        return {"error": str(e)}


def process_pdf(pdf_path, show_progress=False, max_pages=None):
    """
    Process a PDF file, checking multiple pages if MRZ data is not found on the first page.
    
    Args:
        pdf_path (str): The path to the PDF file to process.
        show_progress (bool): If True, prints progress for each page and rotation attempt.
        max_pages (int): Maximum number of pages to check. If None, checks all pages.
    
    Returns:
        dict: A dictionary containing the parsed MRZ data on success, with page number.
        None: If no valid MRZ data is found after checking all pages.
    """
    try:
        # Get total number of pages in PDF
        pdf_info = pdfinfo_from_path(pdf_path)
        total_pages = pdf_info.get("Pages", 1)
        
        # Limit pages to check if max_pages is specified
        pages_to_check = min(total_pages, max_pages) if max_pages else total_pages
        
        if show_progress:
            print(f"PDF has {total_pages} page(s). Checking up to {pages_to_check} page(s)...")
        
        # Process each page sequentially
        for page_num in range(1, pages_to_check + 1):
            if show_progress:
                print(f"\n--- Processing page {page_num} of {total_pages} ---")
            
            # Convert specific page to image with DPI from configuration
            images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=PDF_DPI)
            
            if not images:
                if show_progress:
                    print(f"Could not convert page {page_num} to image.")
                continue
            
            # Save page to temporary file
            temp_page_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_f:
                    temp_page_path = temp_f.name
                images[0].save(temp_page_path, 'PNG')
                
                # Save page 3 as a permanent file for inspection
                if page_num == 3:
                    inspection_path = f"page_3_inspection_{os.path.basename(pdf_path).replace('.pdf', '')}.png"
                    images[0].save(inspection_path, 'PNG')
                    if show_progress:
                        print(f"Saved page 3 for inspection: {inspection_path}")
                
                # Process this page
                result = process_image(temp_page_path, show_progress)
                
                # If MRZ data found, add page number and return
                if result and "surname" in result:
                    result['page_number'] = page_num
                    result['total_pages'] = total_pages
                    if show_progress:
                        print(f"MRZ data found on page {page_num}!")
                    return result
                else:
                    # Try to get raw text even if parsing failed (for debugging)
                    if show_progress:
                        try:
                            tesseract_path = TESSERACT_PATH if TESSERACT_PATH else ""
                            fast_mrz_debug = FastMRZ(tesseract_path=tesseract_path)
                            raw_text = fast_mrz_debug.get_details(temp_page_path, ignore_parse=True)
                            if raw_text and len(raw_text.strip()) > 0:
                                print(f"Raw OCR text detected on page {page_num} (but parsing failed):")
                                print(raw_text[:200] + "..." if len(raw_text) > 200 else raw_text)
                            else:
                                print(f"No OCR text detected on page {page_num}.")
                        except Exception as debug_e:
                            if show_progress:
                                print(f"Debug check failed: {str(debug_e)}")
                    if show_progress and not (result and "surname" in result):
                        print(f"No MRZ data found on page {page_num}.")
                    
            finally:
                # Cleanup temporary page file
                if temp_page_path and os.path.exists(temp_page_path):
                    os.remove(temp_page_path)
        
        # No MRZ data found in any page
        if show_progress:
            print(f"\nNo MRZ data found in any of the {pages_to_check} page(s) checked.")
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
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum number of PDF pages to check (default: uses MAX_PAGES_DEFAULT from .env, or all pages if not set)."
    )
    args = parser.parse_args()

    show_progress = args.format == 'text'
    
    input_file_path = args.input_file
    final_result = None
    start_time = time.time()

    try:
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(f"The file was not found: {input_file_path}")

        if input_file_path.lower().endswith('.pdf'):
            if show_progress:
                print(f"PDF file detected: '{input_file_path}'")
            # Use command-line argument if provided, otherwise use env default, otherwise None (all pages)
            max_pages = args.max_pages if args.max_pages is not None else MAX_PAGES_DEFAULT
            final_result = process_pdf(input_file_path, show_progress, max_pages)
        else:
            if show_progress:
                print(f"\nProcessing image: '{input_file_path}'...")
            final_result = process_image(input_file_path, show_progress)

    except Exception as e:
        final_result = {"error": str(e)}
    
    # Calculate processing time
    processing_time = time.time() - start_time
    processing_time_rounded = round(processing_time, 2)
    
    # Add processing time to result data (for text format display)
    if final_result and isinstance(final_result, dict):
        final_result['processing_time_seconds'] = processing_time_rounded

    # --- Final Output ---
    if args.format == 'json':
        output_json = {}
        if final_result and "error" in final_result:
            output_json = {
                "status": "error", 
                "message": final_result["error"],
                "processing_time_seconds": processing_time_rounded
            }
        elif final_result:
            # Remove processing_time from data to avoid duplication, keep it at root level
            result_data = final_result.copy()
            result_data.pop('processing_time_seconds', None)
            output_json = {
                "status": "success", 
                "data": result_data,
                "processing_time_seconds": processing_time_rounded
            }
        else:
            output_json = {
                "status": "failure", 
                "message": "Could not find any valid MRZ data after trying all pages and rotations.",
                "processing_time_seconds": processing_time_rounded
            }
        print(json.dumps(output_json, indent=4))
    else:
        if final_result and "surname" in final_result:
             print("\n--- JSON Data ---")
             print(json.dumps(final_result, indent=4))
             print("\n--- Raw MRZ Text ---")
             print(final_result.get('raw_text', 'Not available.'))
             if 'page_number' in final_result:
                 print(f"\n--- Found on page {final_result['page_number']} of {final_result.get('total_pages', '?')} ---")
             print(f"\n--- Processing Time: {processing_time_rounded} seconds ---")
        elif not final_result:
             print("\n--- MRZ Data Not Found ---")
             print("Could not find any valid MRZ data after trying all pages and rotations.")
             print(f"--- Processing Time: {processing_time_rounded} seconds ---")
        elif "error" in final_result:
             print(f"\nAn error occurred: {final_result['error']}")
             print(f"--- Processing Time: {processing_time_rounded} seconds ---")