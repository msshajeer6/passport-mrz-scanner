# PowerShell script to generate Postman JSON body with base64 encoded file
# Usage: .\generate_postman_body.ps1 -FilePath "passport_sample.jpg"

param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath
)

if (-not (Test-Path $FilePath)) {
    Write-Host "Error: File not found: $FilePath" -ForegroundColor Red
    exit 1
}

$fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
$base64 = [System.Convert]::ToBase64String($fileBytes)
$fileName = Split-Path -Leaf $FilePath

$jsonBody = @{
    file = $base64
    filename = $fileName
    max_pages = 10
} | ConvertTo-Json

Write-Host "`n=== Copy this JSON to Postman Body (raw JSON) ===" -ForegroundColor Green
Write-Host $jsonBody
Write-Host "`n=== End of JSON ===" -ForegroundColor Green
Write-Host "`nFile: $FilePath" -ForegroundColor Cyan
Write-Host "Base64 length: $($base64.Length) characters" -ForegroundColor Cyan


