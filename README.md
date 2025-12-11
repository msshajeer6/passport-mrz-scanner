# Passport MRZ Scanner

A Python application that extracts Machine-Readable Zone (MRZ) data from passport images and PDF files. The scanner automatically rotates images to find the MRZ data and returns parsed information in JSON or human-readable format.

## Features

- 📄 Supports both image files (JPG, PNG) and PDF files
- 🔄 Automatically rotates images (0°, 90°, 180°, 270°) to find MRZ data
- 📊 Output in JSON or human-readable text format
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
3. Add Tesseract to your system PATH, or the script will use the hardcoded path

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

## Configuration

If your Tesseract installation is in a different location, you can modify the path in `mrz_scanner.py`:

```python
fast_mrz = FastMRZ(tesseract_path=r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe')
```

Or if Tesseract is in your system PATH, you can use:
```python
fast_mrz = FastMRZ()
```

## Usage

### Basic Usage
Scan an image file:
```bash
python mrz_scanner.py <image_file>
```

Scan a PDF file:
```bash
python mrz_scanner.py <pdf_file>
```

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
```

**macOS/Linux:**
```bash
# Using virtual environment
python mrz_scanner.py passport_sample.jpg

# JSON output
python mrz_scanner.py passport_sample.jpg --format json
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
    "raw_text": "..."
}

--- Raw MRZ Text ---
P<GBRPUDARSAN<<HENERT<<<<<<<<<<<<<<<<<<<<<<<
7077979792GBR9505209M1704224<<<<<<<<<<<<<<00
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
        ...
    }
}
```

## Supported File Formats

- **Images:** JPG, JPEG, PNG
- **Documents:** PDF (first page only)

## Troubleshooting

### Tesseract Not Found
- Ensure Tesseract is installed and in your system PATH
- Or update the `tesseract_path` in `mrz_scanner.py` to match your installation

### PDF Conversion Errors
- Ensure Poppler is installed and the `pdftoppm` utility is accessible
- Check that the PDF file is not corrupted or password-protected

### No MRZ Data Found
- Ensure the image quality is good and the MRZ area is clearly visible
- Try cropping the image to focus on the MRZ area
- Check that the image is not too blurry or low resolution

## Project Structure

```
passport-mrz-scanner/
├── mrz_scanner.py      # Main application script
├── requirements.txt    # Python dependencies
├── README.md          # This file
└── .gitignore         # Git ignore file
```

## Dependencies

- `fastmrz` - Fast MRZ parsing library
- `pdf2image` - PDF to image conversion
- `Pillow` (PIL) - Image processing
- `pytesseract` - Python wrapper for Tesseract OCR
