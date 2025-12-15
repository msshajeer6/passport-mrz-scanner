import sys
import os
import json
import argparse
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastmrz import FastMRZ
from PIL import Image
import pytesseract
from dotenv import load_dotenv

# Try PyMuPDF first (faster), fallback to pdf2image
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    try:
        from pdf2image import convert_from_path, pdfinfo_from_path
    except ImportError:
        convert_from_path = None
        pdfinfo_from_path = None

# Load environment variables from .env file
load_dotenv()

# Get configuration from environment variables with fallback defaults
TESSERACT_PATH = os.getenv('TESSERACT_PATH', r'C:\Program Files\Tesseract-OCR\tesseract.exe')
PDF_DPI = int(os.getenv('PDF_DPI', '300'))
PDF_DPI_FAST = int(os.getenv('PDF_DPI_FAST', '200'))  # Lower DPI for faster processing (priority pages)
OCR_PSM_MODE = int(os.getenv('OCR_PSM_MODE', '6'))
OCR_PSM_MODE_FAST = int(os.getenv('OCR_PSM_MODE_FAST', '11'))  # Faster PSM mode for known pages
MAX_IMAGE_DIMENSION = int(os.getenv('MAX_IMAGE_DIMENSION', '4000'))  # Resize images larger than this (increased to avoid breaking MRZ detection)
# Default max pages: None means all pages, or set a number to limit
MAX_PAGES_DEFAULT = os.getenv('MAX_PAGES_DEFAULT')
MAX_PAGES_DEFAULT = int(MAX_PAGES_DEFAULT) if MAX_PAGES_DEFAULT and MAX_PAGES_DEFAULT.lower() != 'none' else None


def get_pdf_info(pdf_path):
    """
    Get PDF information (page count) using PyMuPDF or pdf2image as fallback.
    
    Args:
        pdf_path (str): Path to PDF file
        
    Returns:
        dict: Dictionary with 'Pages' key containing page count
    """
    if PYMUPDF_AVAILABLE:
        try:
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
            return {"Pages": page_count}
        except Exception:
            pass
    
    # Fallback to pdf2image
    if pdfinfo_from_path:
        try:
            return pdfinfo_from_path(pdf_path)
        except Exception:
            pass
    
    # Default fallback
    return {"Pages": 1}


def convert_pdf_page_to_image(pdf_path, page_num, dpi=300, doc=None):
    """
    Convert a single PDF page to PIL Image using PyMuPDF or pdf2image as fallback.
    
    Args:
        pdf_path (str): Path to PDF file
        page_num (int): Page number (1-indexed)
        dpi (int): DPI for conversion
        doc: Optional already-opened PyMuPDF document (for reuse)
        
    Returns:
        PIL.Image: Image object or None if conversion fails
    """
    if PYMUPDF_AVAILABLE:
        should_close = False
        try:
            # Use provided document or open new one
            if doc is None:
                doc = fitz.open(pdf_path)
                should_close = True
            
            if page_num > len(doc):
                if should_close:
                    doc.close()
                return None
            
            # Convert page to image (PyMuPDF uses 72 DPI as base, so scale accordingly)
            page = doc[page_num - 1]  # 0-indexed
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.tobytes("ppm"))
            
            # Only close if we opened it
            if should_close:
                doc.close()
            return img
        except Exception as e:
            # If PyMuPDF fails, close document if we opened it, then fallback to pdf2image
            if should_close and doc is not None:
                try:
                    doc.close()
                except:
                    pass
            pass
    
    # Fallback to pdf2image (can't reuse handle, so always open/close)
    if convert_from_path:
        try:
            images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=dpi)
            if images:
                return images[0]
        except Exception:
            pass
    
    return None


def process_image(image_path, show_progress=False, use_fast_psm=False):
    """
    Takes an image path and tries to find MRZ data by rotating it.

    Args:
        image_path (str): The path to the image file to process.
        show_progress (bool): If True, prints progress for each rotation attempt.
        use_fast_psm (bool): If True, use faster PSM mode (11 instead of 6) for speed optimization.

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
        # For fast mode, try fewer rotations first
        if use_fast_psm:
            rotations_to_try = [0, -90]  # Skip 90° initially for speed
        else:
            rotations_to_try = [0, -90, 90]
        
        for angle in rotations_to_try:
            if show_progress:
                print(f"--- Attempting to read MRZ at {angle} degrees rotation ---")

            try:
                image_to_scan = original_image.rotate(-angle, expand=True)
                scan_width, scan_height = image_to_scan.size
                
                # Try full image first
                temp_image_path = None
                try:
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_f:
                        temp_image_path = temp_f.name
                    
                    image_to_scan.save(temp_image_path)
                    
                    passport_mrz_json = fast_mrz.get_details(temp_image_path, include_checkdigit=False)

                    # Check for a successful parse - accept even if checksum fails (status might be 'FAILURE' but data is extracted)
                    # Accept if we have document_number or given_name (some passports have empty surname)
                    if passport_mrz_json and (passport_mrz_json.get("document_number") or passport_mrz_json.get("given_name")):
                        if show_progress:
                            print("--- MRZ Data Found! ---")
                        # On success, also get the raw text and add it to the result
                        raw_text = fast_mrz.get_details(temp_image_path, ignore_parse=True)
                        passport_mrz_json['raw_text'] = raw_text
                        return passport_mrz_json
                    
                    # If image-based parsing failed, try text-based parsing as fallback
                    # Sometimes OCR text parsing works better than image parsing
                    raw_text_from_img = None
                    try:
                        raw_text_from_img = fast_mrz.get_details(temp_image_path, ignore_parse=True)
                        if raw_text_from_img and len(raw_text_from_img.strip()) > 10:
                            cleaned_text = "\n".join([line.strip() for line in raw_text_from_img.strip().split("\n") if line.strip()])
                            passport_mrz_json_text = fast_mrz.get_details(cleaned_text, input_type="text", include_checkdigit=False)
                            if passport_mrz_json_text and (passport_mrz_json_text.get("document_number") or passport_mrz_json_text.get("given_name")):
                                if show_progress:
                                    print("--- MRZ Data Found via text-based parsing! ---")
                                passport_mrz_json_text['raw_text'] = cleaned_text
                                return passport_mrz_json_text
                    except Exception:
                        pass  # Continue to region checks if text parsing also fails
                    
                    # If fastmrz didn't find it on full image, try bottom 30% (MRZ is usually at bottom)
                    # Only try this for first rotation to save time
                    if angle == 0:
                        bottom_region = image_to_scan.crop((0, int(scan_height * 0.7), scan_width, scan_height))
                        
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_f2:
                            temp_bottom_path = temp_f2.name
                        bottom_region.save(temp_bottom_path)
                        
                        try:
                            passport_mrz_json = fast_mrz.get_details(temp_bottom_path, include_checkdigit=False)
                            if passport_mrz_json and (passport_mrz_json.get("document_number") or passport_mrz_json.get("given_name")):
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
            except Exception as rotation_error:
                # If this rotation fails, continue to next rotation
                if show_progress:
                    print(f"Rotation {angle}° failed: {str(rotation_error)[:100]}")
                continue
        
        # If fastmrz didn't find it, try direct pytesseract OCR with MRZ language (optimized)
        if show_progress:
            print("--- Trying direct OCR with MRZ language ---")
        
        try:
            original_image = Image.open(image_path)
            img_width, img_height = original_image.size
            
            # Prioritize most likely scenarios: rotated bottom region first (most common case)
            # Only try 90° rotation for fallback OCR
            ocr_rotations = [
                (90, "counterclockwise"),     # Rotated left (MRZ on right side)
            ]
            
            for rot_angle, rot_name in ocr_rotations:
                if show_progress:
                    print(f"--- Trying OCR with {rot_name} rotation ({rot_angle}°) ---")
                
                rotated_img = original_image.rotate(rot_angle, expand=True)
                rot_width, rot_height = rotated_img.size
                
                # Define regions based on rotation
                if rot_angle == 0:
                    # Normal: check bottom
                    regions_to_try = [
                        ("bottom_30", rotated_img.crop((0, int(rot_height * 0.7), rot_width, rot_height))),
                        ("full", rotated_img),
                    ]
                elif rot_angle == 90:
                    # Rotated left: check bottom (original right) and full image
                    regions_to_try = [
                        ("bottom_30_rotated", rotated_img.crop((0, int(rot_height * 0.7), rot_width, rot_height))),
                        ("full_rotated", rotated_img),
                    ]
                else:
                    regions_to_try = [("full_rotated", rotated_img)]
                
                # Use PSM mode from configuration
                for region_name, region_img in regions_to_try:
                    try:
                        # Try direct OCR with MRZ language
                        # Use faster PSM mode if specified
                        psm_mode = OCR_PSM_MODE_FAST if use_fast_psm else OCR_PSM_MODE
                        custom_config = f'--oem 3 --psm {psm_mode} -l mrz'
                        raw_mrz_text = pytesseract.image_to_string(region_img, config=custom_config)
                        
                        if raw_mrz_text and len(raw_mrz_text.strip()) > 10:
                            # Clean up the text
                            cleaned_text = "\n".join([line.strip() for line in raw_mrz_text.strip().split("\n") if line.strip()])
                            
                            # Try to parse the raw text
                            tesseract_path = TESSERACT_PATH if TESSERACT_PATH else ""
                            fast_mrz = FastMRZ(tesseract_path=tesseract_path)
                            passport_mrz_json = fast_mrz.get_details(cleaned_text, input_type="text", include_checkdigit=False)
                            
                            if passport_mrz_json and (passport_mrz_json.get("document_number") or passport_mrz_json.get("given_name")):
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


def _process_single_page(pdf_path, page_num, total_pages, show_progress=False, doc=None, use_fast_dpi=False):
    """
    Helper function to process a single PDF page.
    Used for parallel processing.
    
    Args:
        pdf_path (str): Path to PDF file
        page_num (int): Page number to process (1-indexed)
        total_pages (int): Total number of pages in PDF
        show_progress (bool): Whether to show progress
        doc: Optional already-opened PyMuPDF document (for reuse)
        use_fast_dpi (bool): If True, use lower DPI for faster processing
        
    Returns:
        dict: MRZ data if found, None otherwise
    """
    try:
        if show_progress:
            print(f"\n--- Processing page {page_num} of {total_pages} ---")
        
        # Use lower DPI for faster processing if specified (e.g., for priority pages)
        dpi = PDF_DPI_FAST if use_fast_dpi else PDF_DPI
        if show_progress and use_fast_dpi:
            print(f"Using fast DPI ({dpi}) for faster processing...")
        
        # Convert specific page to image with DPI from configuration
        image = convert_pdf_page_to_image(pdf_path, page_num, dpi, doc=doc)
        
        if not image:
            if show_progress:
                print(f"Could not convert page {page_num} to image.")
            return None
        
        # Optimize image size - resize very large images to speed up OCR
        img_width, img_height = image.size
        max_dim = max(img_width, img_height)
        if max_dim > MAX_IMAGE_DIMENSION:
            # Calculate scaling factor to reduce image size
            scale_factor = MAX_IMAGE_DIMENSION / max_dim
            new_width = int(img_width * scale_factor)
            new_height = int(img_height * scale_factor)
            if show_progress:
                print(f"Resizing image from {img_width}x{img_height} to {new_width}x{new_height} for faster OCR...")
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save page to temporary file
        temp_page_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_f:
                temp_page_path = temp_f.name
            image.save(temp_page_path, 'PNG')
            
            # Save page 3 as a permanent file for inspection
            if page_num == 3:
                inspection_path = f"page_3_inspection_{os.path.basename(pdf_path).replace('.pdf', '')}.png"
                image.save(inspection_path, 'PNG')
                if show_progress:
                    print(f"Saved page 3 for inspection: {inspection_path}")
            
            # Process this page (disable progress for parallel processing to avoid output conflicts)
            # Use faster PSM mode for priority pages
            result = process_image(temp_page_path, show_progress=False, use_fast_psm=use_fast_dpi)
            
            # If MRZ data found, add page number and return
            if result and (result.get("document_number") or result.get("given_name")):
                result['page_number'] = page_num
                result['total_pages'] = total_pages
                if show_progress:
                    print(f"MRZ data found on page {page_num}!")
                return result
            else:
                if show_progress:
                    print(f"No MRZ data found on page {page_num}.")
                return None
                
        finally:
            # Cleanup temporary page file
            if temp_page_path and os.path.exists(temp_page_path):
                os.remove(temp_page_path)
                
    except Exception as e:
        if show_progress:
            print(f"Error processing page {page_num}: {str(e)}")
        return None


def process_pdf(pdf_path, show_progress=False, max_pages=None, parallel=True, start_page=None):
    """
    Process a PDF file, checking multiple pages if MRZ data is not found on the first page.
    Uses parallel processing by default for better performance on multi-page PDFs.
    Uses smart page ordering: for multi-page PDFs, checks page 2 first (most common MRZ location),
    then page 1, then remaining pages.
    
    Args:
        pdf_path (str): The path to the PDF file to process.
        show_progress (bool): If True, prints progress for each page and rotation attempt.
        max_pages (int): Maximum number of pages to check. If None, checks all pages.
        parallel (bool): If True, process pages in parallel. Default: True.
        start_page (int): Optional page number to start checking from (1-indexed). 
                         If provided, this page is checked FIRST (sequentially) before others.
                         If not provided, uses smart ordering (page 2, then 1, then 3, 4...).
    
    Returns:
        dict: A dictionary containing the parsed MRZ data on success, with page number.
        None: If no valid MRZ data is found after checking all pages.
    """
    doc = None
    try:
        # Get total number of pages in PDF
        pdf_info = get_pdf_info(pdf_path)
        total_pages = pdf_info.get("Pages", 1)
        
        # Limit pages to check if max_pages is specified
        pages_to_check = min(total_pages, max_pages) if max_pages else total_pages
        
        if show_progress:
            print(f"PDF has {total_pages} page(s). Checking up to {pages_to_check} page(s)...")
        
        # Validate and handle start_page
        if start_page is not None:
            if start_page < 1 or start_page > total_pages:
                if show_progress:
                    print(f"Warning: start_page {start_page} is out of range (1-{total_pages}). Using default ordering.")
                start_page = None
            elif start_page > pages_to_check:
                if show_progress:
                    print(f"Warning: start_page {start_page} exceeds max_pages ({pages_to_check}). Using default ordering.")
                start_page = None
        
        # If start_page is specified, check it FIRST (sequentially) before checking others
        if start_page is not None:
            if show_progress:
                print(f"Checking start_page {start_page} first...")
            
            # Open document for sequential check
            if PYMUPDF_AVAILABLE:
                try:
                    doc = fitz.open(pdf_path)
                except Exception:
                    doc = None
            
            # Check start_page first (use fast DPI for speed optimization)
            result = _process_single_page(pdf_path, start_page, total_pages, show_progress, doc, use_fast_dpi=True)
            if result and (result.get("document_number") or result.get("given_name")):
                if doc is not None:
                    try:
                        doc.close()
                    except:
                        pass
                return result
            
            # Start page didn't have MRZ, now check remaining pages
            remaining_pages = [p for p in range(1, pages_to_check + 1) if p != start_page]
            if not remaining_pages:
                if show_progress:
                    print(f"\nNo MRZ data found on page {start_page}.")
                if doc is not None:
                    try:
                        doc.close()
                    except:
                        pass
                return None
            
            if show_progress:
                print(f"Page {start_page} had no MRZ. Checking remaining pages: {remaining_pages}")
            
            # Continue with remaining pages (can use parallel if applicable)
            pages_to_check = len(remaining_pages)
        else:
            # Determine smart page order (page 2 first for multi-page PDFs)
            if total_pages >= 2 and pages_to_check >= 2:
                # Smart ordering: page 2, then 1, then 3, 4, 5...
                remaining_pages = [2, 1]
                for page_num in range(3, pages_to_check + 1):
                    remaining_pages.append(page_num)
                if show_progress:
                    print(f"Using smart page order: {remaining_pages}")
            else:
                # Single page: just check page 1
                remaining_pages = [1]
        
        # Open PDF document once for reuse (only if PyMuPDF is available and sequential)
        if PYMUPDF_AVAILABLE and not parallel:
            if doc is None:
                try:
                    doc = fitz.open(pdf_path)
                except Exception:
                    doc = None  # Fallback to opening per page if this fails
        
        # Use parallel processing only for PDFs with 3+ pages (overhead not worth it for 1-2 pages)
        use_parallel = parallel and len(remaining_pages) >= 3
        
        if show_progress and use_parallel:
            print(f"Using parallel processing for {len(remaining_pages)} remaining page(s)...")
        
        # Use parallel processing for multiple pages
        if use_parallel:
            # For parallel processing, each thread opens its own document handle
            # (PyMuPDF documents are not thread-safe for concurrent access)
            with ThreadPoolExecutor(max_workers=min(len(remaining_pages), 4)) as executor:
                # Submit all remaining pages for processing in priority order
                future_to_page = {}
                for page_num in remaining_pages:
                    future = executor.submit(_process_single_page, pdf_path, page_num, total_pages, show_progress, None)
                    future_to_page[future] = page_num
                
                # Process results as they complete (first result wins)
                found_result = None
                for future in as_completed(future_to_page):
                    page_num = future_to_page[future]
                    try:
                        result = future.result()
                        if result and (result.get("document_number") or result.get("given_name")):
                            # Found MRZ - cancel remaining tasks and return
                            if show_progress:
                                print(f"MRZ found on page {page_num}, canceling remaining tasks...")
                            found_result = result
                            # Cancel all remaining futures
                            for remaining_future in future_to_page:
                                if remaining_future != future:
                                    remaining_future.cancel()
                            if doc is not None:
                                try:
                                    doc.close()
                                except:
                                    pass
                            return found_result
                    except Exception as e:
                        if show_progress:
                            print(f"Error processing page {page_num}: {str(e)}")
                        continue
            
            # No MRZ data found in any page
            if show_progress:
                print(f"\nNo MRZ data found in any of the {len(remaining_pages)} page(s) checked.")
            if doc is not None:
                try:
                    doc.close()
                except:
                    pass
            return None
        else:
            # Sequential processing (for single page or if parallel disabled)
            # Reuse document handle for better performance
            for page_num in remaining_pages:
                result = _process_single_page(pdf_path, page_num, total_pages, show_progress, doc)
                if result and (result.get("document_number") or result.get("given_name")):
                    if doc is not None:
                        try:
                            doc.close()
                        except:
                            pass
                    return result
            
            # No MRZ data found in any page
            if show_progress:
                print(f"\nNo MRZ data found in any of the {len(remaining_pages)} page(s) checked.")
            if doc is not None:
                try:
                    doc.close()
                except:
                    pass
            return None
        
    except Exception as e:
        if show_progress:
            print(f"An error occurred during PDF processing: {str(e)}")
        return {"error": str(e)}
    finally:
        # Close document if we opened it
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


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
    parser.add_argument(
        "--start-page",
        type=int,
        default=None,
        help="Page number to start checking from (1-indexed). If specified, this page is checked FIRST before others."
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel processing for PDF files."
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
            final_result = process_pdf(input_file_path, show_progress, max_pages, parallel=not args.no_parallel, start_page=args.start_page)
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
        if final_result and (final_result.get("document_number") or final_result.get("given_name")):
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