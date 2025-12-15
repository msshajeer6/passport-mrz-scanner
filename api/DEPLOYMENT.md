# Deployment Guide

This guide explains how to deploy the MRZ Scanner API. The Docker image is generic and can be deployed to any platform. This guide includes instructions for AWS ECS Fargate as well as other deployment options.

## Prerequisites

- AWS CLI configured
- Docker installed locally
- AWS ECR repository created
- ECS cluster created
- Application Load Balancer (optional, for production)

## Step 1: Build and Push Docker Image

### 1.1 Authenticate Docker to ECR

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
```

### 1.2 Build Docker Image

**Important:** Build from the project root directory:

```bash
# From project root
docker build -f api/Dockerfile -t mrz-scanner-api .
```

### Alternative: Local/Docker Compose Deployment

The Docker image works on any platform. For local or VPS deployment:

```bash
# Build
docker build -f api/Dockerfile -t mrz-scanner-api .

# Run locally (without authentication)
docker run -p 5000:5000 mrz-scanner-api

# Run with authentication (optional)
docker run -p 5000:5000 -e API_KEY=your-secret-api-key-here mrz-scanner-api

# Or with Docker Compose (create docker-compose.yml)
version: '3.8'
services:
  mrz-scanner:
    build:
      context: .
      dockerfile: api/Dockerfile
    ports:
      - "5000:5000"
    environment:
      - API_KEY=${API_KEY}  # Optional: set to enable authentication
      - PDF_DPI=300
      - MAX_PAGES_DEFAULT=10
```

### 1.3 Tag Image for ECR

```bash
docker tag mrz-scanner-api:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/mrz-scanner-api:latest
```

### 1.4 Push to ECR

```bash
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/mrz-scanner-api:latest
```

## Step 2: Create ECS Task Definition

### 2.1 Update Task Definition

1. Edit `ecs-task-definition.json`
2. Replace `YOUR_ECR_REPOSITORY_URI` with your actual ECR repository URI
3. Update `awslogs-region` to your AWS region
4. Adjust CPU/memory if needed (current: 1 vCPU, 3GB RAM)
5. **Optional:** Set `API_KEY` environment variable to enable authentication (recommended for production)
   - **For production:** Use AWS Secrets Manager (see below) instead of plain text in task definition
   - If `API_KEY` is not set, the API will be publicly accessible

### 2.1.1 Using AWS Secrets Manager (Recommended for Production)

Instead of storing the API key in plain text, use AWS Secrets Manager:

1. **Create a secret in AWS Secrets Manager:**
   ```bash
   aws secretsmanager create-secret \
     --name mrz-scanner-api-key \
     --secret-string "your-secret-api-key-here" \
     --region us-east-1
   ```

2. **Update `ecs-task-definition.json`** - Replace the `API_KEY` environment variable with a secret reference:
   ```json
   "secrets": [
     {
       "name": "API_KEY",
       "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:mrz-scanner-api-key"
     }
   ]
   ```
   
   Remove the `API_KEY` entry from the `environment` array and add it to a `secrets` array instead.

3. **Grant ECS task execution role permission to access the secret:**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "secretsmanager:GetSecretValue"
         ],
         "Resource": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:mrz-scanner-api-key*"
       }
     ]
   }
   ```

### 2.2 Register Task Definition

```bash
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
```

## Step 3: Create ECS Service

### 3.1 Create Service (with Application Load Balancer)

```bash
aws ecs create-service \
  --cluster your-cluster-name \
  --service-name mrz-scanner-api \
  --task-definition mrz-scanner-api \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:region:account:targetgroup/xxx,containerName=mrz-scanner-api,containerPort=5000"
```

### 3.2 Create Service (without Load Balancer - for testing)

```bash
aws ecs create-service \
  --cluster your-cluster-name \
  --service-name mrz-scanner-api \
  --task-definition mrz-scanner-api \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

## Step 4: Configure CloudWatch Logs

Create log group (if not exists):

```bash
aws logs create-log-group --log-group-name /ecs/mrz-scanner-api
```

## Step 5: Test the API

### Get Service Endpoint

```bash
# If using Load Balancer
aws elbv2 describe-load-balancers --names your-alb-name

# If not using Load Balancer, get task public IP
aws ecs list-tasks --cluster your-cluster-name --service-name mrz-scanner-api
aws ecs describe-tasks --cluster your-cluster-name --tasks TASK_ARN
```

### Test Health Endpoint

```bash
curl http://YOUR_ENDPOINT/health
```

### Test MRZ Scanning

```bash
# Without authentication (if API_KEY not set)
curl -X POST http://YOUR_ENDPOINT/scan \
  -H "Content-Type: application/json" \
  -d '{
    "file": "BASE64_ENCODED_FILE_DATA",
    "filename": "passport.pdf",
    "max_pages": 10
  }'

# With authentication (if API_KEY is set)
curl -X POST http://YOUR_ENDPOINT/scan \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key-here" \
  -d '{
    "file": "BASE64_ENCODED_FILE_DATA",
    "filename": "passport.pdf",
    "max_pages": 10
  }'

# Using multipart form data
curl -X POST http://YOUR_ENDPOINT/scan \
  -F "file=@passport.pdf" \
  -F "max_pages=10"
```

## Step 6: Laravel Integration

### Using Laravel HTTP Client

```php
use Illuminate\Support\Facades\Http;

// Upload file and scan
$file = $request->file('passport');
$base64 = base64_encode(file_get_contents($file->getRealPath()));

$response = Http::post('http://YOUR_FARGATE_ENDPOINT/scan', [
    'file' => $base64,
    'filename' => $file->getClientOriginalName(),
    'max_pages' => 10
]);

$result = $response->json();

if ($result['status'] === 'success') {
    $mrzData = $result['data'];
    // Process MRZ data
}
```

### Using S3 + URL Endpoint

```php
// Upload to S3 first
$path = $request->file('passport')->store('passports', 's3');
$url = Storage::disk('s3')->url($path);

// Scan from S3 URL
$response = Http::post('http://YOUR_FARGATE_ENDPOINT/scan/url', [
    'url' => $url,
    'max_pages' => 10
]);
```

## Configuration

### Environment Variables (in Task Definition)

- `PORT`: API port (default: 5000)
- `HOST`: Bind address (default: 0.0.0.0)
- `PDF_DPI`: PDF conversion DPI (default: 300)
- `OCR_PSM_MODE`: OCR segmentation mode (default: 6)
- `MAX_PAGES_DEFAULT`: Default max pages (default: 10)
- `TESSERACT_PATH`: Leave empty (uses system PATH)
- `API_KEY` or `API_KEYS`: **Optional** - API key(s) for authentication. Supports multiple keys (comma or space separated). If set, all endpoints (except `/health`) require authentication via `Authorization: Bearer <key>` or `X-API-Key: <key>` header. If not set, API is publicly accessible.
  - **For production:** Use AWS Secrets Manager (see Step 2.1.1) instead of plain text
  - **For development/testing:** Plain text in environment variables is acceptable
  - **Multiple keys example:** `API_KEYS="key1,key2,key3"` or `API_KEYS="key1 key2 key3"`
- `RATE_LIMIT_PER_KEY`: **Optional** - Rate limit per API key (default: "100 per hour"). Format: "X per hour" or "X per minute". Rate limiting is applied per API key to prevent abuse.

### Resource Allocation

- **CPU**: 1024 (1 vCPU) - recommended for OCR
- **Memory**: 3072 (3GB) - required for OCR processing
- **Workers**: 2 (configured in Dockerfile CMD)

## Auto Scaling (Optional)

Create auto-scaling configuration:

```bash
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/your-cluster-name/mrz-scanner-api \
  --min-capacity 1 \
  --max-capacity 10

aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/your-cluster-name/mrz-scanner-api \
  --policy-name cpu-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    }
  }'
```

## Monitoring

- **CloudWatch Logs**: `/ecs/mrz-scanner-api`
- **CloudWatch Metrics**: ECS service metrics
- **Health Checks**: `/health` endpoint

## Cost Estimation

- **1 vCPU, 3GB RAM**: ~$0.04/hour
- **1,000 requests/month (avg 1 min each)**: ~$0.67/month
- **Always-on (24/7)**: ~$29/month

## Troubleshooting

### Check Service Status

```bash
aws ecs describe-services --cluster your-cluster-name --services mrz-scanner-api
```

### View Logs

```bash
aws logs tail /ecs/mrz-scanner-api --follow
```

### Restart Service

```bash
aws ecs update-service --cluster your-cluster-name --service mrz-scanner-api --force-new-deployment
```

