"""
Flask API wrapper for MRZ Scanner
Deployable using Docker to any platform (AWS ECS Fargate, local server, VPS, Kubernetes, etc.)
"""
import os
import json
import base64
import tempfile
import time
import sys
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flasgger import Swagger
import logging

# Add parent directory to path to import mrz_scanner
# This allows the module to work both when run from api/ and when deployed in Docker
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from mrz_scanner import process_image, process_pdf

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for Laravel integration

# Initialize Swagger documentation
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api-docs"
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "MRZ Scanner API",
        "description": "API for scanning Machine-Readable Zone (MRZ) data from passport images and PDFs",
        "version": "1.0.0",
        "contact": {
            "name": "API Support"
        }
    },
    "securityDefinitions": {
        "ApiKeyAuth": {
            "type": "apiKey",
            "name": "X-API-Key",
            "in": "header",
            "description": "Enter your API key once at the top (click 'Authorize' button). It will be used for all authenticated endpoints. Alternative: You can also use 'Authorization: Bearer <key>' header in your requests."
        }
    },
    "security": [
        {"ApiKeyAuth": []}
    ]
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# Initialize rate limiter
# Use in-memory storage (for production, consider Redis)
limiter = Limiter(
    app=app,
    key_func=lambda: g.api_key if hasattr(g, 'api_key') and g.api_key else get_remote_address(),
    default_limits=["1000 per hour"],  # Default limit if no API key
    storage_uri="memory://"
)

# Get API keys from environment (optional)
# Supports multiple keys: comma-separated or space-separated
API_KEYS_STR = os.getenv('API_KEYS', None) or os.getenv('API_KEY', None)
API_KEYS = None
if API_KEYS_STR:
    # Support both comma and space separation
    # Split by comma first, then by space, and flatten
    keys = []
    for part in API_KEYS_STR.split(','):
        keys.extend([k.strip() for k in part.split() if k.strip()])
    API_KEYS = [k for k in keys if k]  # Remove empty strings
    logger.info(f"Loaded {len(API_KEYS)} API key(s) from environment")

# Rate limit configuration per API key (can be overridden via env)
# Format: "100 per hour" or "10 per minute"
RATE_LIMIT_PER_KEY = os.getenv('RATE_LIMIT_PER_KEY', '100 per hour')

def get_api_key_from_request():
    """Extract API key from request headers"""
    auth_header = request.headers.get('Authorization', '')
    api_key_header = request.headers.get('X-API-Key', '')
    
    # Check Bearer token (case-insensitive for "Bearer" prefix)
    auth_lower = auth_header.lower()
    if auth_lower.startswith('bearer '):
        # Extract key after "bearer " (7 characters)
        key = auth_header[7:].strip()
        return key if key else None
    
    # Check X-API-Key header
    if api_key_header:
        return api_key_header.strip()
    
    return None

def require_auth():
    """Check if authentication is required and validate it"""
    if not API_KEYS:
        # Authentication is optional, skip if not configured
        return None
    
    # Get API key from request
    provided_key = get_api_key_from_request()
    
    if not provided_key:
        return jsonify({
            "status": "error",
            "message": "Authentication required. Provide API key via 'Authorization: Bearer <key>' or 'X-API-Key: <key>' header."
        }), 401
    
    # Check if provided key matches any valid key
    # API_KEYS is always a list at this point
    # Normalize the provided key (strip whitespace)
    provided_key_normalized = provided_key.strip()
    
    if provided_key_normalized not in API_KEYS:
        # Log for debugging (first 10 chars only for security)
        logger.warning(
            f"Invalid API key attempt from {get_remote_address()}. "
            f"Provided key (first 10 chars): '{provided_key_normalized[:10]}...' (length: {len(provided_key_normalized)}), "
            f"Valid keys count: {len(API_KEYS)}"
        )
        return jsonify({
            "status": "error",
            "message": "Invalid API key. Authentication failed."
        }), 401
    
    # Store API key in request context for rate limiting
    g.api_key = provided_key
    
    return None

@app.before_request
def authenticate():
    """Optional authentication middleware"""
    # Skip authentication for health check and Swagger documentation endpoints
    if request.path in ['/health', '/api-docs', '/apispec.json', '/flasgger_static'] or request.path.startswith('/flasgger_static/'):
        return None
    
    # Check authentication if API_KEYS is set
    return require_auth()

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded errors"""
    return jsonify({
        "status": "error",
        "message": f"429 Too Many Requests: Rate limit exceeded. {str(e.description)}"
    }), 429

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    ---
    tags:
      - Health
    summary: Health check
    description: Returns the health status of the API. No authentication required.
    responses:
      200:
        description: API is healthy
        schema:
          type: object
          properties:
            status:
              type: string
              example: healthy
            service:
              type: string
              example: mrz-scanner-api
    """
    return jsonify({
        "status": "healthy",
        "service": "mrz-scanner-api"
    }), 200

@app.route('/scan/base64', methods=['POST'])
@limiter.limit(RATE_LIMIT_PER_KEY)
def scan_mrz_base64():
    """
    Scan MRZ from Base64 Encoded File
    ---
    tags:
      - Scanning
    summary: Upload file as base64 encoded JSON
    description: |
      Upload a passport image or PDF file as base64 encoded JSON to extract MRZ data.
      
      **Authentication:** Required if API_KEY/API_KEYS is set (enter API key once at the top)
      
      **Rate Limit:** Configurable per API key (default: 100 per hour)
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - file
            - filename
          properties:
            file:
              type: string
              description: Base64 encoded file data
              example: "iVBORw0KGgoAAAANSUhEUgAA..."
            filename:
              type: string
              description: Original filename (e.g., passport.pdf or passport.jpg)
              example: "passport.pdf"
            max_pages:
              type: integer
              description: Maximum number of PDF pages to check (optional, only for PDFs)
              example: 10
            start_page:
              type: integer
              description: Page number to start checking from (optional, only for PDFs, 1-indexed). If specified, this page is checked FIRST before others.
              example: 2
            start_page_only:
              type: boolean
              description: When start_page is specified, only check that page and skip remaining pages if MRZ not found (optional, only for PDFs). Default: false.
              example: true
    responses:
      200:
        description: Success or failure response
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              description: MRZ data (if found)
              properties:
                surname:
                  type: string
                  example: "SMITH"
                given_name:
                  type: string
                  example: "JOHN"
                document_number:
                  type: string
                  example: "123456789"
                birth_date:
                  type: string
                  example: "1990-01-01"
                expiry_date:
                  type: string
                  example: "2025-12-31"
                nationality_code:
                  type: string
                  example: "USA"
                sex:
                  type: string
                  example: "M"
                raw_text:
                  type: string
                  description: Raw MRZ text
                processing_time_seconds:
                  type: number
                  example: 2.5
            message:
              type: string
              description: Error or failure message
              example: "Could not find any valid MRZ data"
            processing_time_seconds:
              type: number
              example: 2.5
      400:
        description: Bad request (missing file or invalid data)
      401:
        description: Authentication required or invalid API key
      429:
        description: Rate limit exceeded
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "status": "error",
                "message": "Request must be JSON with 'file' and 'filename' fields"
            }), 400
            
        file_data_b64 = data.get('file')
        filename = data.get('filename', 'document.pdf')
        max_pages = data.get('max_pages')
        start_page = data.get('start_page')
        if start_page:
            try:
                start_page = int(start_page)
            except (ValueError, TypeError):
                start_page = None
        
        start_page_only = data.get('start_page_only', False)
        if start_page_only:
            try:
                start_page_only = bool(start_page_only) if isinstance(start_page_only, bool) else str(start_page_only).lower() in ('true', '1', 'yes', 'on')
            except (ValueError, TypeError):
                start_page_only = False
        
        if not file_data_b64:
            return jsonify({
                "status": "error",
                "message": "Missing 'file' field with base64 encoded data"
            }), 400
        
        # Decode base64 file
        try:
            file_data = base64.b64decode(file_data_b64)
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Invalid base64 encoding: {str(e)}"
            }), 400
        
        # Determine file type
        is_pdf = filename.lower().endswith('.pdf')
        
        # Save to temporary file
        suffix = '.pdf' if is_pdf else '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            temp_file.write(file_data)
        
        try:
            # Process the file with timing
            start_time = time.time()
            if is_pdf:
                result = process_pdf(temp_path, show_progress=False, max_pages=max_pages, start_page=start_page, start_page_only=start_page_only)
            else:
                result = process_image(temp_path, show_progress=False)
            processing_time = round(time.time() - start_time, 2)
            
            # Add processing time to result if not already present
            if result and isinstance(result, dict):
                result['processing_time_seconds'] = processing_time
            
            # Format response
            if result and "surname" in result:
                return jsonify({
                    "status": "success",
                    "data": result,
                    "processing_time_seconds": processing_time
                }), 200
            elif result and "error" in result:
                return jsonify({
                    "status": "error",
                    "message": result["error"]
                }), 500
            else:
                return jsonify({
                    "status": "failure",
                    "message": "Could not find any valid MRZ data after trying all pages and rotations."
                }), 200
                
        finally:
            # Cleanup temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        logger.error(f"Error processing MRZ scan: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500

@app.route('/scan/file', methods=['POST'])
@limiter.limit(RATE_LIMIT_PER_KEY)
def scan_mrz_file():
    """
    Scan MRZ from File Upload
    ---
    tags:
      - Scanning
    summary: Upload file as multipart/form-data
    description: |
      Upload a passport image or PDF file directly to extract MRZ data.
      
      **Authentication:** Required if API_KEY/API_KEYS is set (enter API key once at the top)
      
      **Rate Limit:** Configurable per API key (default: 100 per hour)
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: The image or PDF file to upload
      - in: formData
        name: max_pages
        type: integer
        required: false
        description: Maximum number of PDF pages to check (optional, only for PDFs)
      - in: formData
        name: start_page
        type: integer
        required: false
        description: Page number to start checking from (optional, only for PDFs, 1-indexed). If specified, this page is checked FIRST before others.
      - in: formData
        name: start_page_only
        type: boolean
        required: false
        description: When start_page is specified, only check that page and skip remaining pages if MRZ not found (optional, only for PDFs). Default: false.
    responses:
      200:
        description: Success or failure response
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              description: MRZ data (if found)
              properties:
                surname:
                  type: string
                  example: "SMITH"
                given_name:
                  type: string
                  example: "JOHN"
                document_number:
                  type: string
                  example: "123456789"
                birth_date:
                  type: string
                  example: "1990-01-01"
                expiry_date:
                  type: string
                  example: "2025-12-31"
                nationality_code:
                  type: string
                  example: "USA"
                sex:
                  type: string
                  example: "M"
                raw_text:
                  type: string
                  description: Raw MRZ text
                processing_time_seconds:
                  type: number
                  example: 2.5
            message:
              type: string
              description: Error or failure message
              example: "Could not find any valid MRZ data"
            processing_time_seconds:
              type: number
              example: 2.5
      400:
        description: Bad request (missing file or invalid data)
      401:
        description: Authentication required or invalid API key
      429:
        description: Rate limit exceeded
      500:
        description: Internal server error
    """
    try:
        # Handle multipart/form-data
        if 'file' not in request.files:
            return jsonify({
                "status": "error",
                "message": "Missing 'file' in form data"
            }), 400
        
        file = request.files['file']
        filename = file.filename or 'document.pdf'
        file_data = file.read()
        max_pages = request.form.get('max_pages')
        if max_pages:
            try:
                max_pages = int(max_pages)
            except ValueError:
                max_pages = None
        
        start_page = request.form.get('start_page')
        if start_page:
            try:
                start_page = int(start_page)
            except ValueError:
                start_page = None
        
        start_page_only = request.form.get('start_page_only', 'false').lower() in ('true', '1', 'yes', 'on')
        
        # Determine file type
        is_pdf = filename.lower().endswith('.pdf')
        
        # Save to temporary file
        suffix = '.pdf' if is_pdf else '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            temp_file.write(file_data)
        
        try:
            # Process the file with timing
            start_time = time.time()
            if is_pdf:
                result = process_pdf(temp_path, show_progress=False, max_pages=max_pages, start_page=start_page, start_page_only=start_page_only)
            else:
                result = process_image(temp_path, show_progress=False)
            processing_time = round(time.time() - start_time, 2)
            
            # Add processing time to result if not already present
            if result and isinstance(result, dict):
                result['processing_time_seconds'] = processing_time
            
            # Format response
            if result and "surname" in result:
                return jsonify({
                    "status": "success",
                    "data": result,
                    "processing_time_seconds": processing_time
                }), 200
            elif result and "error" in result:
                return jsonify({
                    "status": "error",
                    "message": result["error"]
                }), 500
            else:
                return jsonify({
                    "status": "failure",
                    "message": "Could not find any valid MRZ data after trying all pages and rotations."
                }), 200
                
        finally:
            # Cleanup temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        logger.error(f"Error processing MRZ scan: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500

@app.route('/scan/url', methods=['POST'])
@limiter.limit(RATE_LIMIT_PER_KEY)
def scan_from_url():
    """
    Scan MRZ from a URL
    ---
    tags:
      - Scanning
    summary: Scan MRZ from file URL
    description: |
      Download a file from a URL (e.g., S3 presigned URL) and extract MRZ data.
      Useful when files are already stored in cloud storage.
      
      **Authentication:** Required if API_KEY/API_KEYS is set (enter API key once at the top)
      
      **Rate Limit:** Configurable per API key (default: 100 per hour)
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - url
          properties:
            url:
              type: string
              format: uri
              description: URL to download the file from (supports S3 presigned URLs with query parameters)
              example: "https://s3.amazonaws.com/bucket/passport.pdf?X-Amz-Algorithm=..."
            max_pages:
              type: integer
              description: Maximum number of PDF pages to check (optional, only for PDFs)
              example: 10
            start_page:
              type: integer
              description: Page number to start checking from (optional, only for PDFs, 1-indexed). If specified, this page is checked FIRST before others.
              example: 2
            start_page_only:
              type: boolean
              description: When start_page is specified, only check that page and skip remaining pages if MRZ not found (optional, only for PDFs). Default: false.
              example: true
    responses:
      200:
        description: Success or failure response
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              description: MRZ data (if found)
            message:
              type: string
              description: Error or failure message
            processing_time_seconds:
              type: number
              example: 3.2
      400:
        description: Bad request (missing URL, invalid URL, or download failed)
      401:
        description: Authentication required or invalid API key
      429:
        description: Rate limit exceeded
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({
                "status": "error",
                "message": "Missing 'url' field"
            }), 400
        
        url = data['url']
        max_pages = data.get('max_pages')
        start_page = data.get('start_page')
        if start_page:
            try:
                start_page = int(start_page)
            except (ValueError, TypeError):
                start_page = None
        
        start_page_only = data.get('start_page_only', False)
        if start_page_only:
            try:
                start_page_only = bool(start_page_only) if isinstance(start_page_only, bool) else str(start_page_only).lower() in ('true', '1', 'yes', 'on')
            except (ValueError, TypeError):
                start_page_only = False
        
        # Extract file extension from URL (handle query parameters)
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        url_path = parsed_url.path.lower()
        is_pdf = url_path.endswith('.pdf')
        file_ext = '.pdf' if is_pdf else '.jpg'
        
        # Download file from URL
        import urllib.request
        import urllib.error
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                temp_path = temp_file.name
                urllib.request.urlretrieve(url, temp_path)
        except urllib.error.HTTPError as e:
            return jsonify({
                "status": "error",
                "message": f"Failed to download file from URL: HTTP {e.code} {e.reason}. The URL may have expired or be invalid."
            }), 400
        except urllib.error.URLError as e:
            return jsonify({
                "status": "error",
                "message": f"Failed to download file from URL: {str(e)}"
            }), 400
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Failed to download file: {str(e)}"
            }), 400
        
        try:
            # Process the file with timing
            start_time = time.time()
            if is_pdf:
                result = process_pdf(temp_path, show_progress=False, max_pages=max_pages, start_page=start_page, start_page_only=start_page_only)
            else:
                result = process_image(temp_path, show_progress=False)
            processing_time = round(time.time() - start_time, 2)
            if result and isinstance(result, dict):
                result['processing_time_seconds'] = processing_time
                
            if result and "surname" in result:
                return jsonify({
                    "status": "success",
                    "data": result,
                    "processing_time_seconds": processing_time
                }), 200
            elif result and "error" in result:
                return jsonify({
                    "status": "error",
                    "message": result["error"]
                }), 500
            else:
                return jsonify({
                    "status": "failure",
                    "message": "Could not find any valid MRZ data after trying all pages and rotations."
                }), 200
                
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        logger.error(f"Error processing MRZ scan from URL: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500

if __name__ == '__main__':
    # Get port from environment or default to 5000
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    
    logger.info(f"Starting MRZ Scanner API on {host}:{port}")
    app.run(host=host, port=port, debug=False)

