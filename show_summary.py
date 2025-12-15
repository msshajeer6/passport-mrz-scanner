import json

with open('test_results_comprehensive.json', 'r') as f:
    data = json.load(f)

print("=" * 80)
print("COMPREHENSIVE TEST SUMMARY")
print("=" * 80)

for test_type, results in data.items():
    success = sum(1 for r in results if r.get('status') == 'success')
    failure = sum(1 for r in results if r.get('status') == 'failure')
    error = sum(1 for r in results if r.get('status') == 'error')
    skipped = sum(1 for r in results if r.get('status') == 'skipped')
    total_time = sum(r.get('processing_time_seconds', 0) for r in results)
    avg_time = total_time / success if success > 0 else 0
    
    print(f"\n{test_type.upper().replace('_', ' ')}:")
    print(f"  Success: {success:2d} | Failure: {failure:2d} | Error: {error:2d} | Skipped: {skipped:2d}")
    print(f"  Total Time: {total_time:7.2f}s | Avg Time: {avg_time:6.2f}s")

print("\n" + "=" * 80)
print("PERFORMANCE COMPARISON - PDF FILES")
print("=" * 80)

pdfs = [
    'EMPLOYEE-83BCC531-B9EF-4797-782F-FF41DD9CE565.pdf',
    'EMPLOYEE-9179D7D4-DA03-F5CA-AFC1-CB7E75DBC714.pdf',
    'EMPLOYEE-EEB784E1-2249-7FA9-2B5D-A66B3CA0245F.pdf',
    'EMPLOYEE-F6A142C6-575D-F041-D02B-B2B954BD610F.pdf'
]

for pdf in pdfs:
    print(f"\n{pdf}:")
    cli_no = next((r for r in data['cli_no_start_page'] if r.get('filename') == pdf), None)
    cli_yes = next((r for r in data['cli_with_start_page'] if r.get('filename') == pdf), None)
    api_no = next((r for r in data['api_no_start_page'] if r.get('filename') == pdf), None)
    api_yes = next((r for r in data['api_with_start_page'] if r.get('filename') == pdf), None)
    
    if cli_no and cli_no.get('status') == 'success':
        t = cli_no.get('processing_time_seconds', 0)
        print(f"  CLI (no start_page):     {t:6.2f}s")
    if cli_yes and cli_yes.get('status') == 'success':
        t = cli_yes.get('processing_time_seconds', 0)
        t_no = cli_no.get('processing_time_seconds', 0) if cli_no and cli_no.get('status') == 'success' else 0
        improvement = ((t_no - t) / t_no * 100) if t_no > 0 else 0
        print(f"  CLI (with start_page):   {t:6.2f}s ({improvement:+.1f}% faster)")
    if api_no and api_no.get('status') == 'success':
        t = api_no.get('processing_time_seconds', 0)
        print(f"  API (no start_page):     {t:6.2f}s")
    if api_yes and api_yes.get('status') == 'success':
        t = api_yes.get('processing_time_seconds', 0)
        t_no = api_no.get('processing_time_seconds', 0) if api_no and api_no.get('status') == 'success' else 0
        improvement = ((t_no - t) / t_no * 100) if t_no > 0 else 0
        print(f"  API (with start_page):   {t:6.2f}s ({improvement:+.1f}% faster)")

