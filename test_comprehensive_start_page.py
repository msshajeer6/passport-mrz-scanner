#!/usr/bin/env python3
"""
Comprehensive test: All files with and without start_page in both CLI and API modes
"""
import subprocess
import json
import os
import time
import requests
from pathlib import Path

# Files to test
test_files = [
    "britishp.jpg",
    "EMPLOYEE-83BCC531-B9EF-4797-782F-FF41DD9CE565.pdf",
    "EMPLOYEE-9179D7D4-DA03-F5CA-AFC1-CB7E75DBC714.pdf",
    "EMPLOYEE-EEB784E1-2249-7FA9-2B5D-A66B3CA0245F.pdf",
    "EMPLOYEE-F6A142C6-575D-F041-D02B-B2B954BD610F.pdf",
    "nzpassport.png",
    "passport_image2.jpg",
    "passport_image3.jpg",
    "passport_midhun.png",
    "passport_rider.png",
    "passport_sample.jpg",
    "passport_shahul.png",
    "passport_waleed.jpg",
    "passport_waleed.png",
    "philippines.jpg",
    "bc47ca02-2963-491b-98c1-e45af89fbeec-10020-image.avif",
    "874b303e-7091-46eb-8580-6b1406dcbf27-9962-image.avif",
    "1193efb8-3c0d-4d2b-b904-a8a12dadd5bf-9711-image.avif",
]

results = {
    "cli_no_start_page": [],
    "cli_with_start_page": [],
    "api_no_start_page": [],
    "api_with_start_page": []
}

container_name = "mrz-scanner-api"
api_url = "http://localhost:5000"
api_key = "test-key-1"

def test_cli(filename, start_page=None):
    """Test file with CLI version"""
    if not os.path.exists(filename):
        return {
            "filename": filename,
            "status": "skipped",
            "reason": "file not found"
        }
    
    start_time = time.time()
    cmd = f'python mrz_scanner.py "{filename}" --format json --max-pages 5'
    if start_page and filename.lower().endswith('.pdf'):
        cmd += f' --start-page {start_page}'
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120, cwd=os.getcwd())
        processing_time = round(time.time() - start_time, 2)
        
        if result.returncode == 0:
            try:
                output_json = json.loads(result.stdout)
                status = output_json.get("status", "unknown")
                
                if status == "success":
                    data = output_json.get("data", {})
                    return {
                        "filename": filename,
                        "status": "success",
                        "surname": data.get("surname", ""),
                        "given_name": data.get("given_name", ""),
                        "document_number": data.get("document_number", ""),
                        "page_number": data.get("page_number"),
                        "processing_time_seconds": output_json.get("processing_time_seconds", processing_time)
                    }
                elif status == "failure":
                    return {
                        "filename": filename,
                        "status": "failure",
                        "message": output_json.get("message", "Unknown failure"),
                        "processing_time_seconds": output_json.get("processing_time_seconds", processing_time)
                    }
                else:
                    return {
                        "filename": filename,
                        "status": status,
                        "output": output_json
                    }
            except json.JSONDecodeError:
                return {
                    "filename": filename,
                    "status": "error",
                    "error": "Invalid JSON output",
                    "output": result.stdout[:500]
                }
        else:
            return {
                "filename": filename,
                "status": "error",
                "error": f"Command failed: {result.stderr[:200]}",
                "returncode": result.returncode
            }
    except subprocess.TimeoutExpired:
        return {
            "filename": filename,
            "status": "timeout",
            "processing_time_seconds": 120
        }
    except Exception as e:
        return {
            "filename": filename,
            "status": "error",
            "error": str(e)
        }

def test_api(filename, start_page=None):
    """Test file with API version"""
    if not os.path.exists(filename):
        return {
            "filename": filename,
            "status": "skipped",
            "reason": "file not found"
        }
    
    start_time = time.time()
    
    try:
        # Read file
        with open(filename, 'rb') as f:
            file_data = f.read()
        
        # Determine if PDF
        is_pdf = filename.lower().endswith('.pdf')
        
        # Prepare request
        files = {'file': (os.path.basename(filename), file_data)}
        data = {}
        if is_pdf:
            data['max_pages'] = '5'
            if start_page:
                data['start_page'] = str(start_page)
        
        # Make request
        headers = {'X-API-Key': api_key}
        try:
            response = requests.post(f"{api_url}/scan/file", files=files, data=data, headers=headers, timeout=120)
        except requests.exceptions.ConnectionError:
            return {
                "filename": filename,
                "status": "error",
                "error": "Connection refused - API not available",
                "processing_time_seconds": round(time.time() - start_time, 2)
            }
        processing_time = round(time.time() - start_time, 2)
        
        if response.status_code == 200:
            result_json = response.json()
            status = result_json.get("status", "unknown")
            
            if status == "success":
                data_result = result_json.get("data", {})
                return {
                    "filename": filename,
                    "status": "success",
                    "surname": data_result.get("surname", ""),
                    "given_name": data_result.get("given_name", ""),
                    "document_number": data_result.get("document_number", ""),
                    "page_number": data_result.get("page_number"),
                    "processing_time_seconds": result_json.get("processing_time_seconds", processing_time)
                }
            elif status == "failure":
                return {
                    "filename": filename,
                    "status": "failure",
                    "message": result_json.get("message", "Unknown failure"),
                    "processing_time_seconds": result_json.get("processing_time_seconds", processing_time)
                }
            else:
                return {
                    "filename": filename,
                    "status": status,
                    "output": result_json
                }
        else:
            return {
                "filename": filename,
                "status": "error",
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
                "processing_time_seconds": processing_time
            }
    except requests.exceptions.Timeout:
        return {
            "filename": filename,
            "status": "timeout",
            "processing_time_seconds": 120
        }
    except Exception as e:
        return {
            "filename": filename,
            "status": "error",
            "error": str(e)
        }

def get_pdf_start_page(filename):
    """Determine appropriate start_page for PDF files"""
    if not filename.lower().endswith('.pdf'):
        return None
    
    # Known MRZ pages for specific files
    known_pages = {
        "EMPLOYEE-9179D7D4-DA03-F5CA-AFC1-CB7E75DBC714.pdf": 3,
        "EMPLOYEE-EEB784E1-2249-7FA9-2B5D-A66B3CA0245F.pdf": 1,
        "EMPLOYEE-F6A142C6-575D-F041-D02B-B2B954BD610F.pdf": 1,
    }
    
    return known_pages.get(filename, 2)  # Default to page 2 for multi-page PDFs

def main():
    print("=" * 80)
    print("COMPREHENSIVE TEST: All files with and without start_page")
    print("=" * 80)
    print()
    
    total_files = len([f for f in test_files if os.path.exists(f)])
    print(f"Testing {total_files} files...")
    print()
    
    # Test CLI without start_page
    print("=" * 80)
    print("1. CLI MODE - WITHOUT start_page")
    print("=" * 80)
    for i, filename in enumerate(test_files, 1):
        print(f"[{i}/{len(test_files)}] Testing CLI (no start_page): {filename}")
        result = test_cli(filename)
        results["cli_no_start_page"].append(result)
        status_icon = "[OK]" if result.get("status") == "success" else "[FAIL]"
        time_str = f"{result.get('processing_time_seconds', 0):.2f}s" if "processing_time_seconds" in result else "N/A"
        print(f"  {status_icon} {result.get('status', 'unknown')} ({time_str})")
    
    print()
    
    # Test CLI with start_page (for PDFs)
    print("=" * 80)
    print("2. CLI MODE - WITH start_page (PDFs only)")
    print("=" * 80)
    for i, filename in enumerate(test_files, 1):
        if filename.lower().endswith('.pdf'):
            start_page = get_pdf_start_page(filename)
            print(f"[{i}/{len(test_files)}] Testing CLI (start_page={start_page}): {filename}")
            result = test_cli(filename, start_page=start_page)
            results["cli_with_start_page"].append(result)
            status_icon = "[OK]" if result.get("status") == "success" else "[FAIL]"
            time_str = f"{result.get('processing_time_seconds', 0):.2f}s" if "processing_time_seconds" in result else "N/A"
            print(f"  {status_icon} {result.get('status', 'unknown')} ({time_str})")
        else:
            # Skip non-PDFs for start_page test
            results["cli_with_start_page"].append({
                "filename": filename,
                "status": "skipped",
                "reason": "not a PDF"
            })
    
    print()
    
    # Test API without start_page
    print("=" * 80)
    print("3. API MODE - WITHOUT start_page")
    print("=" * 80)
    for i, filename in enumerate(test_files, 1):
        print(f"[{i}/{len(test_files)}] Testing API (no start_page): {filename}")
        result = test_api(filename)
        results["api_no_start_page"].append(result)
        status_icon = "[OK]" if result.get("status") == "success" else "[FAIL]"
        time_str = f"{result.get('processing_time_seconds', 0):.2f}s" if "processing_time_seconds" in result else "N/A"
        print(f"  {status_icon} {result.get('status', 'unknown')} ({time_str})")
    
    print()
    
    # Test API with start_page (for PDFs)
    print("=" * 80)
    print("4. API MODE - WITH start_page (PDFs only)")
    print("=" * 80)
    for i, filename in enumerate(test_files, 1):
        if filename.lower().endswith('.pdf'):
            start_page = get_pdf_start_page(filename)
            print(f"[{i}/{len(test_files)}] Testing API (start_page={start_page}): {filename}")
            result = test_api(filename, start_page=start_page)
            results["api_with_start_page"].append(result)
            status_icon = "[OK]" if result.get("status") == "success" else "[FAIL]"
            time_str = f"{result.get('processing_time_seconds', 0):.2f}s" if "processing_time_seconds" in result else "N/A"
            print(f"  {status_icon} {result.get('status', 'unknown')} ({time_str})")
        else:
            # Skip non-PDFs for start_page test
            results["api_with_start_page"].append({
                "filename": filename,
                "status": "skipped",
                "reason": "not a PDF"
            })
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    # Calculate statistics
    for test_type, test_results in results.items():
        success_count = sum(1 for r in test_results if r.get("status") == "success")
        failure_count = sum(1 for r in test_results if r.get("status") == "failure")
        error_count = sum(1 for r in test_results if r.get("status") == "error")
        skipped_count = sum(1 for r in test_results if r.get("status") == "skipped")
        total_time = sum(r.get("processing_time_seconds", 0) for r in test_results if "processing_time_seconds" in r)
        
        print(f"\n{test_type.upper()}:")
        print(f"  Success: {success_count}")
        print(f"  Failure: {failure_count}")
        print(f"  Error: {error_count}")
        print(f"  Skipped: {skipped_count}")
        print(f"  Total Time: {total_time:.2f}s")
        if success_count > 0:
            avg_time = total_time / success_count
            print(f"  Avg Time (successful): {avg_time:.2f}s")
    
    # Save results to JSON
    output_file = "test_results_comprehensive.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")
    
    # Compare performance
    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON (PDFs only)")
    print("=" * 80)
    
    pdf_files = [f for f in test_files if f.lower().endswith('.pdf')]
    for pdf_file in pdf_files:
        cli_no_sp = next((r for r in results["cli_no_start_page"] if r.get("filename") == pdf_file), None)
        cli_with_sp = next((r for r in results["cli_with_start_page"] if r.get("filename") == pdf_file), None)
        api_no_sp = next((r for r in results["api_no_start_page"] if r.get("filename") == pdf_file), None)
        api_with_sp = next((r for r in results["api_with_start_page"] if r.get("filename") == pdf_file), None)
        
        if cli_no_sp and cli_with_sp and cli_no_sp.get("status") == "success" and cli_with_sp.get("status") == "success":
            time_no_sp = cli_no_sp.get("processing_time_seconds", 0)
            time_with_sp = cli_with_sp.get("processing_time_seconds", 0)
            improvement = ((time_no_sp - time_with_sp) / time_no_sp * 100) if time_no_sp > 0 else 0
            print(f"\n{pdf_file}:")
            print(f"  CLI - No start_page: {time_no_sp:.2f}s")
            print(f"  CLI - With start_page: {time_with_sp:.2f}s ({improvement:.1f}% faster)")
        
        if api_no_sp and api_with_sp and api_no_sp.get("status") == "success" and api_with_sp.get("status") == "success":
            time_no_sp = api_no_sp.get("processing_time_seconds", 0)
            time_with_sp = api_with_sp.get("processing_time_seconds", 0)
            improvement = ((time_no_sp - time_with_sp) / time_no_sp * 100) if time_no_sp > 0 else 0
            print(f"  API - No start_page: {time_no_sp:.2f}s")
            print(f"  API - With start_page: {time_with_sp:.2f}s ({improvement:.1f}% faster)")

if __name__ == "__main__":
    main()
