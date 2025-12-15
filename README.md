# Passport MRZ Scanner

A Python application that extracts Machine-Readable Zone (MRZ) data from passport images and PDF files. The scanner automatically rotates images to find the MRZ data and returns parsed information in JSON or human-readable format.

## Features

- 📄 Supports both image files (JPG, PNG) and PDF files
- 📑 Multi-page PDF support - automatically checks all pages if MRZ not found on first page
- 🏁 Optional `start_page` hint for PDFs to jump directly to the likely MRZ page (huge speedup when known)
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
4. **(Optional)** Download the MRZ language model for improved fallback OCR accuracy:
   - Download `mrz.traineddata` from [Tesseract OCR tessdata repository](https://github.com/tesseract-ocr/tessdata)
   - Copy it to: `C:\Program Files\Tesseract-OCR\tessdata\`
   - **Note:** The scanner works without this file (fastmrz has built-in models), but the fallback OCR will use English instead

#### macOS:
```bash
brew install tesseract
# Optional: Install MRZ language model for improved fallback OCR accuracy
cd /usr/local/share/tessdata
wget https://github.com/tesseract-ocr/tessdata/raw/main/mrz.traineddata
# Note: Scanner works without this - fastmrz has built-in models
```

#### Linux (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
# Optional: Install MRZ language model for improved fallback OCR accuracy
cd /usr/share/tesseract-ocr/5/tessdata
sudo wget https://github.com/tesseract-ocr/tessdata/raw/main/mrz.traineddata
# Note: Scanner works without this - fastmrz has built-in models
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
# Optional fast path for known pages (used when --start-page is provided)
# Recommended: 200 (fast) or 250 (balanced-fast)
PDF_DPI_FAST=200

# Resize safeguard for very large images (pixels on longest side)
# Increase if MRZ is small in the image; default keeps typical A4 at 300 DPI unscaled
MAX_IMAGE_DIMENSION=4000

# OCR Configuration
# PSM (Page Segmentation Mode) for Tesseract
# 6 = Uniform block of text (default, good for MRZ)
# 11 = Sparse text (alternative for MRZ)
OCR_PSM_MODE=6
# Faster PSM used only for the start_page hint to speed up OCR
OCR_PSM_MODE_FAST=11

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

Scan a PDF and hint the MRZ page (big speedup if known):
```bash
python mrz_scanner.py <pdf_file> --start-page 3
```

Override page limit (optional):
```bash
python mrz_scanner.py <pdf_file> --max-pages 5
```

**Note:** By default, the script limits PDF processing to prevent long-running scans. Configure `MAX_PAGES_DEFAULT` in `.env` to adjust the default limit, or use `--max-pages` to override per-file.

### API Usage (start_page)
- `/scan` (multipart) and `/scan/base64` accept an optional `start_page` field for PDFs.
- `/scan/url` accepts `start_page` in the JSON body.
- Authentication: provide `X-API-Key` or `Authorization: Bearer <key>` if enabled.

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

## API Deployment

This application can be deployed as a containerized API service using Docker. This is ideal for production use with Laravel or other web applications.

The API version is located in the `api/` folder. The Docker image is generic and can be deployed to any platform (AWS ECS Fargate, local server, VPS, Kubernetes, etc.). See [api/README.md](api/README.md) for API documentation and [api/DEPLOYMENT.md](api/DEPLOYMENT.md) for detailed deployment instructions.

## Troubleshooting

### Tesseract Not Found
- Ensure Tesseract is installed and in your system PATH
- Or update the `TESSERACT_PATH` in your `.env` file to match your installation
- If Tesseract is in your PATH, you can leave `TESSERACT_PATH` empty in `.env`

### MRZ Language Model Missing (Optional)
The scanner uses the `mrz` language model for the fallback OCR method. If you encounter errors like:
```
Error opening data file .../tessdata/mrz.traineddata
```

**Important:** The scanner will still work without this file! The `fastmrz` library has its own built-in models and will function normally. The MRZ language model is only needed for the fallback OCR method, which may improve accuracy in some edge cases.

**To install the MRZ language model (optional):**

1. **Windows:**
   - Download `mrz.traineddata` from [Tesseract OCR tessdata](https://github.com/tesseract-ocr/tessdata)
   - Copy it to: `C:\Program Files\Tesseract-OCR\tessdata\`

2. **macOS:**
   ```bash
   cd /usr/local/share/tessdata
   wget https://github.com/tesseract-ocr/tessdata/raw/main/mrz.traineddata
   ```

3. **Linux (Ubuntu/Debian):**
   ```bash
   cd /usr/share/tesseract-ocr/5/tessdata
   sudo wget https://github.com/tesseract-ocr/tessdata/raw/main/mrz.traineddata
   ```

**Note:** The `fastmrz` library's primary OCR method uses its own models and doesn't require this file. The MRZ language model is only used by the fallback OCR method if `fastmrz` doesn't find MRZ data initially.

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

### MRZ Language Model Missing (Optional)
If you see errors about `mrz.traineddata` not found, the scanner will still work using the `fastmrz` library's built-in models. However, the fallback OCR will use English language instead of the specialized MRZ model, which may reduce accuracy.

**To install the MRZ language model:**

1. **Windows:**
   - Download `mrz.traineddata` from [Tesseract OCR tessdata](https://github.com/tesseract-ocr/tessdata)
   - Copy to: `C:\Program Files\Tesseract-OCR\tessdata\`

2. **macOS:**
   ```bash
   cd /usr/local/share/tessdata
   wget https://github.com/tesseract-ocr/tessdata/raw/main/mrz.traineddata
   ```

3. **Linux:**
   ```bash
   cd /usr/share/tesseract-ocr/5/tessdata
   sudo wget https://github.com/tesseract-ocr/tessdata/raw/main/mrz.traineddata
   ```

**Note:** The `fastmrz` library has its own models and will work without this file. The MRZ language model is only needed for the fallback OCR method.

## Project Structure

```
passport-mrz-scanner/
├── mrz_scanner.py          # Main CLI application script
├── requirements.txt        # Python dependencies (CLI version)
├── .env.example            # Environment configuration template
├── .env                    # Local environment configuration (create from .env.example)
├── README.md               # This file (CLI documentation)
├── .gitignore              # Git ignore file
└── api/                    # API deployment (Docker-based)
    ├── app.py              # Flask API wrapper
    ├── Dockerfile          # Docker image definition
    ├── .dockerignore       # Docker ignore file
    ├── requirements.txt    # Python dependencies (includes API deps)
    ├── ecs-task-definition.json # ECS Fargate task definition template (optional)
    ├── DEPLOYMENT.md       # Deployment guide
    └── README.md           # API documentation
```

## Dependencies

- `fastmrz` - Fast MRZ parsing library
- `pdf2image` - PDF to image conversion
- `Pillow` (PIL) - Image processing
- `pytesseract` - Python wrapper for Tesseract OCR
- `python-dotenv` - Environment variable management

> **Note:** For API deployment, additional dependencies (Flask, Flask-CORS, Gunicorn) are listed in `api/requirements.txt`.
