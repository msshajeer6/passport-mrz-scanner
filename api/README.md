# MRZ Scanner API

This folder contains the API version of the MRZ Scanner. The API provides REST endpoints for scanning MRZ data from passport images and PDFs. It can be deployed using Docker to any platform (AWS ECS Fargate, local server, VPS, Kubernetes, etc.).

## Structure

```
api/
├── app.py                      # Flask API wrapper
├── Dockerfile                  # Docker image definition
├── .dockerignore              # Docker ignore file
├── requirements.txt           # Python dependencies (includes API deps)
├── ecs-task-definition.json   # ECS Fargate task definition template (optional)
├── DEPLOYMENT.md              # Detailed deployment guide
└── README.md                  # This file
```

## Quick Start

### Local Testing

1. Install dependencies:
   ```bash
   cd api
   pip install -r requirements.txt
   ```

2. Run the API:
   ```bash
   python app.py
   ```

3. Test the health endpoint:
   ```bash
   curl http://localhost:5000/health
   ```

### Docker Build

**Important:** Build from the project root directory:

```bash
# From project root
docker build -f api/Dockerfile -t mrz-scanner-api .
docker run -p 5000:5000 mrz-scanner-api
```

## API Endpoints

- `GET /health` - Health check endpoint (no authentication required)
- `POST /scan` - Scan MRZ from uploaded file (JSON or multipart/form-data)
- `POST /scan/url` - Scan MRZ from a URL (e.g., S3 URL)
- `GET /api-docs` - **Swagger API Documentation** (interactive documentation)

## API Documentation (Swagger)

The API includes interactive Swagger documentation for easy testing and integration.

**Access Swagger UI:**
```
http://localhost:5000/api-docs
```

**Swagger JSON Spec:**
```
http://localhost:5000/apispec.json
```

The Swagger documentation includes:
- Complete API endpoint descriptions
- Request/response schemas
- Authentication methods
- Example requests and responses
- Interactive testing interface

**Note:** You can test API endpoints directly from the Swagger UI. If authentication is enabled, you'll need to click the "Authorize" button and enter your API key.

## Authentication (Optional)

The API supports optional authentication via API key(s). If the `API_KEY` or `API_KEYS` environment variable is set, all endpoints (except `/health`) will require authentication.

**Authentication Methods:**
1. **Bearer Token** (recommended): `Authorization: Bearer <your-api-key>`
2. **X-API-Key Header**: `X-API-Key: <your-api-key>`

**Multiple API Keys:**
You can configure multiple API keys by providing a comma-separated or space-separated list:
```bash
# Multiple keys (comma-separated)
export API_KEYS="key1,key2,key3"

# Or space-separated
export API_KEYS="key1 key2 key3"

# Single key (backward compatible)
export API_KEY=your-secret-api-key-here
```

**To enable authentication:**
```bash
# Single API key
docker run -p 5000:5000 -e API_KEY=your-secret-api-key-here mrz-scanner-api

# Multiple API keys
docker run -p 5000:5000 -e API_KEYS="key1,key2,key3" mrz-scanner-api
```

**If `API_KEY`/`API_KEYS` is not set, the API will be publicly accessible (no authentication required).**

## Rate Limiting

The API includes rate limiting to prevent abuse. Rate limits are applied per API key (or per IP address if no authentication is used).

**Default Rate Limit:** 100 requests per hour per API key

**Configure Rate Limits:**
```bash
# Set custom rate limit (format: "X per hour" or "X per minute")
docker run -p 5000:5000 \
  -e API_KEY=your-secret-api-key-here \
  -e RATE_LIMIT_PER_KEY="200 per hour" \
  mrz-scanner-api
```

**Rate Limit Headers:**
When rate limiting is active, the API returns the following headers:
- `X-RateLimit-Limit`: Maximum number of requests allowed
- `X-RateLimit-Remaining`: Number of requests remaining
- `X-RateLimit-Reset`: Time when the rate limit resets

**Rate Limit Exceeded Response:**
```json
{
  "status": "error",
  "message": "429 Too Many Requests: Rate limit exceeded"
}
```

## Usage Examples

### Using multipart form data:
```bash
curl -X POST http://localhost:5000/scan \
  -F "file=@../passport_sample.jpg" \
  -F "max_pages=10"
```

### Using JSON with base64:
```bash
# Encode file to base64 first (Windows PowerShell)
$fileBytes = [System.IO.File]::ReadAllBytes("..\passport_sample.jpg")
$fileB64 = [System.Convert]::ToBase64String($fileBytes)

# Or on Linux/Mac
FILE_B64=$(base64 -i ../passport_sample.jpg)

# Without authentication (if API_KEY not set)
curl -X POST http://localhost:5000/scan \
  -H "Content-Type: application/json" \
  -d "{
    \"file\": \"$FILE_B64\",
    \"filename\": \"passport_sample.jpg\",
    \"max_pages\": 10
  }"

# With authentication (if API_KEY is set)
curl -X POST http://localhost:5000/scan \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key-here" \
  -d "{
    \"file\": \"$FILE_B64\",
    \"filename\": \"passport_sample.jpg\",
    \"max_pages\": 10
  }"
```

### Using URL endpoint (for S3 or other storage):

```bash
# Without authentication (if API_KEY not set)
curl -X POST http://localhost:5000/scan/url \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/passport.pdf",
    "max_pages": 10
  }'

# With authentication (if API_KEY is set)
curl -X POST http://localhost:5000/scan/url \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key-here" \
  -d '{
    "url": "https://example.com/passport.pdf",
    "max_pages": 10
  }'
```

### Laravel Integration

**Option 1: Upload file directly**
```php
use Illuminate\Support\Facades\Http;

$response = Http::post('http://YOUR_FARGATE_ENDPOINT/scan', [
    'file' => base64_encode(file_get_contents($file->getRealPath())),
    'filename' => $file->getClientOriginalName(),
    'max_pages' => 10
]);

$result = $response->json();
```

**Option 2: Upload to S3 first, then scan from URL**
```php
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;

// Upload to S3
$path = $request->file('passport')->store('passports', 's3');
$url = Storage::disk('s3')->url($path);

// Scan from S3 URL (with authentication if API_KEY is set)
$response = Http::withHeaders([
    'Authorization' => 'Bearer ' . env('MRZ_API_KEY'), // Optional: only if API_KEY is set
    // Or use: 'X-API-Key' => env('MRZ_API_KEY'),
])->post('http://YOUR_FARGATE_ENDPOINT/scan/url', [
    'url' => $url,
    'max_pages' => 10
]);

$result = $response->json();

if ($result['status'] === 'success') {
    $mrzData = $result['data'];
    // Process MRZ data
}
```

## Deployment

The Docker image can be deployed to any platform:
- **Local machine or VPS**: `docker run -p 5000:5000 mrz-scanner-api`
- **AWS ECS Fargate**: See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions
- **Kubernetes**: Use the Dockerfile with your K8s manifests
- **Docker Compose**: See examples in DEPLOYMENT.md
- **Any Docker-compatible platform**: The Dockerfile is generic and works everywhere

## Configuration

Environment variables (set in ECS task definition):
- `PORT`: API port (default: 5000)
- `HOST`: Bind address (default: 0.0.0.0)
- `PDF_DPI`: PDF conversion DPI (default: 300)
- `OCR_PSM_MODE`: OCR segmentation mode (default: 6)
- `MAX_PAGES_DEFAULT`: Default max pages (default: 10)

## Notes

- The API uses the `mrz_scanner.py` module from the parent directory
- CORS is enabled for Laravel integration
- Gunicorn is used as the production WSGI server
- Health checks are configured for ECS

