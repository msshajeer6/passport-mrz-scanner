# Passport MRZ Scanner

A Python application that extracts Machine-Readable Zone (MRZ) data from passport images and PDF files. The scanner automatically rotates images to find the MRZ data and returns parsed information in JSON or human-readable format.

## Features

- 📄 Supports both image files (JPG, PNG) and PDF files
- 📑 Multi-page PDF support - automatically checks all pages if MRZ not found on first page
- 🔄 Automatically rotates images (0°, -90°, 90°) to find MRZ data
- 📊 Output in JSON or human-readable text format
- ⏱️ Processing time tracking - includes execution time in all results
- 🔍 Extracts passport information including:
  - Document type and issuer
  - Name (surname and given name)
  - Document number
  - Nationality
  - Birth date
  - Sex
  - Expiry date
  - Raw MRZ text

## Prerequisites

Before installing and running this application, you need to have the following installed:

### 1. Python
- Python 3.7 or higher
- Download from [python.org](https://www.python.org/downloads/)

### 2. Tesseract OCR
The application requires Tesseract OCR to be installed on your system.

#### Windows:
1. Download the installer from [GitHub Tesseract releases](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run the installer and install to the default location: `C:\Program Files\Tesseract-OCR\`
3. Add Tesseract to your system PATH, or configure the path in your `.env` file (see Configuration section)

#### macOS:
```bash
brew install tesseract
```

#### Linux (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

#### Linux (Fedora):
```bash
sudo dnf install tesseract
```

### 3. Poppler (for PDF support)
Required for converting PDF files to images.

#### Windows:
1. Download from [Poppler for Windows](http://blog.alivate.com.au/poppler-windows/)
2. Extract and add the `bin` folder to your system PATH

#### macOS:
```bash
brew install poppler
```

#### Linux (Ubuntu/Debian):
```bash
sudo apt-get install poppler-utils
```

#### Linux (Fedora):
```bash
sudo dnf install poppler-utils
```

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/msshajeer6/passport-mrz-scanner.git
cd passport-mrz-scanner
```

### 2. Create a Virtual Environment
It's recommended to use a virtual environment to isolate dependencies:

**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file from the example template:

**Windows:**
```powershell
Copy-Item .env.example .env
```

**macOS/Linux:**
```bash
cp .env.example .env
```

Then edit `.env` and set your Tesseract path and other configuration options (see [Configuration](#configuration) section below).

## Configuration

Configuration is managed through a `.env` file. This allows you to customize settings without modifying the code.

### 1. Create Environment File

Copy the example environment file:
```bash
cp .env.example .env
```

**Windows:**
```powershell
Copy-Item .env.example .env
```

### 2. Edit Configuration

Open `.env` and configure the following settings:

```env
# Tesseract OCR Configuration
# Path to Tesseract executable
# Windows default: C:\Program Files\Tesseract-OCR\tesseract.exe
# macOS/Linux: Leave empty if Tesseract is in PATH, or specify full path
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe

# PDF Processing Configuration
# DPI for PDF to image conversion (higher = better quality but slower)
# Recommended: 300 (good balance), 400 (high quality), 200 (faster)
PDF_DPI=300

# OCR Configuration
# PSM (Page Segmentation Mode) for Tesseract
# 6 = Uniform block of text (default, good for MRZ)
# 11 = Sparse text (alternative for MRZ)
OCR_PSM_MODE=6

# Maximum Pages Configuration
# Default maximum number of PDF pages to check if --max-pages is not specified
# Set to 'none' or leave empty to check all pages (not recommended for large PDFs)
# Recommended: 10-20 pages for most use cases
MAX_PAGES_DEFAULT=10
```

### Configuration Options

- **TESSERACT_PATH**: Path to Tesseract executable
  - Windows: `C:\Program Files\Tesseract-OCR\tesseract.exe`
  - macOS/Linux: Leave empty if in PATH, or specify full path like `/usr/bin/tesseract`
  
- **PDF_DPI**: Resolution for PDF to image conversion
  - `200`: Faster processing, lower quality
  - `300`: Balanced (recommended)
  - `400`: Higher quality, slower processing
  
- **OCR_PSM_MODE**: Page Segmentation Mode for Tesseract
  - `6`: Uniform block of text (default, recommended for MRZ)
  - `11`: Sparse text (alternative for MRZ)
  - Other modes: See [Tesseract documentation](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html#page-segmentation-method)

### Notes

- If `TESSERACT_PATH` is empty or not set, the script will attempt to use Tesseract from the system PATH
- The `.env` file is excluded from git (see `.gitignore`) to keep your local configuration private

## Usage

### Basic Usage
Scan an image file:
```bash
python mrz_scanner.py <image_file>
```

Scan a PDF file (checks pages up to MAX_PAGES_DEFAULT from .env, or all pages if not set):
```bash
python mrz_scanner.py <pdf_file>
```

Override page limit (optional):
```bash
python mrz_scanner.py <pdf_file> --max-pages 5
```

**Note:** By default, the script limits PDF processing to prevent long-running scans. Configure `MAX_PAGES_DEFAULT` in `.env` to adjust the default limit, or use `--max-pages` to override per-file.

### Output Formats

**Text format (default):**
Shows progress messages and formatted output:
```bash
python mrz_scanner.py passport_sample.jpg
```

**JSON format:**
Returns structured JSON output:
```bash
python mrz_scanner.py passport_sample.jpg --format json
```

### Examples

**Windows:**
```powershell
# Using virtual environment
.\venv\Scripts\python.exe mrz_scanner.py passport_sample.jpg

# JSON output
.\venv\Scripts\python.exe mrz_scanner.py passport_sample.jpg --format json

# PDF with page limit
.\venv\Scripts\python.exe mrz_scanner.py document.pdf --max-pages 5
```

**macOS/Linux:**
```bash
# Using virtual environment
python mrz_scanner.py passport_sample.jpg

# JSON output
python mrz_scanner.py passport_sample.jpg --format json

# PDF with page limit
python mrz_scanner.py document.pdf --max-pages 5
```

## Output Example

### Text Format Output:
```
Processing image: 'passport_sample.jpg'...
--- Attempting to read MRZ at 0 degrees rotation ---
--- MRZ Data Found! ---

--- JSON Data ---
{
    "mrz_type": "TD3",
    "document_code": "P",
    "issuer_code": "GBR",
    "surname": "PUDARSAN",
    "given_name": "HENERT",
    "document_number": "707797979",
    "nationality_code": "GBR",
    "birth_date": "1995-05-20",
    "sex": "M",
    "expiry_date": "2017-04-22",
    "optional_data": "",
    "mrz_text": "...",
    "status": "SUCCESS",
    "raw_text": "...",
    "processing_time_seconds": 1.48
}

--- Raw MRZ Text ---
P<GBRPUDARSAN<<HENERT<<<<<<<<<<<<<<<<<<<<<<<
7077979792GBR9505209M1704224<<<<<<<<<<<<<<00

--- Found on page 3 of 6 ---
--- Processing Time: 43.92 seconds ---
```

### JSON Format Output:
```json
{
    "status": "success",
    "data": {
        "mrz_type": "TD3",
        "document_code": "P",
        "issuer_code": "GBR",
        "surname": "PUDARSAN",
        "given_name": "HENERT",
        "document_number": "707797979",
        "nationality_code": "GBR",
        "birth_date": "1995-05-20",
        "sex": "M",
        "expiry_date": "2017-04-22",
        "page_number": 3,
        "total_pages": 6,
        ...
    },
    "processing_time_seconds": 43.92
}
```

**Notes:**
- For PDF files, the output includes `page_number` and `total_pages` fields indicating which page contained the MRZ data.
- All responses include `processing_time_seconds` field showing the total time taken to process the file (in seconds).

## Supported File Formats

- **Images:** JPG, JPEG, PNG
- **Documents:** PDF (all pages - automatically checks multiple pages if MRZ not found on first page)

## Troubleshooting

### Tesseract Not Found
- Ensure Tesseract is installed and in your system PATH
- Or update the `TESSERACT_PATH` in your `.env` file to match your installation
- If Tesseract is in your PATH, you can leave `TESSERACT_PATH` empty in `.env`

### PDF Conversion Errors
- Ensure Poppler is installed and the `pdftoppm` utility is accessible
- Check that the PDF file is not corrupted or password-protected

### No MRZ Data Found
- Ensure the image quality is good and the MRZ area is clearly visible
- For PDFs, the scanner checks all pages automatically - wait for it to complete
- Try using `--max-pages` option to limit pages checked if PDF is very large
- Try cropping the image to focus on the MRZ area
- Check that the image is not too blurry or low resolution
- For rotated images, the scanner tries multiple orientations automatically
- Check the `processing_time_seconds` in the output - if it's very short, the MRZ might not have been detected properly

## Project Structure

```
passport-mrz-scanner/
├── mrz_scanner.py      # Main application script
├── requirements.txt    # Python dependencies
├── .env.example        # Environment configuration template
├── .env                # Local environment configuration (create from .env.example)
├── README.md          # This file
└── .gitignore         # Git ignore file
```

## Dependencies

- `fastmrz` - Fast MRZ parsing library
- `pdf2image` - PDF to image conversion
- `Pillow` (PIL) - Image processing
- `pytesseract` - Python wrapper for Tesseract OCR
- `python-dotenv` - Environment variable management
