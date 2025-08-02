#!/usr/bin/env python3
"""
Diagnose WOPI communication issues causing blank document
"""
import requests
import json

def diagnose_wopi_issue():
    """Detailed WOPI diagnosis"""
    file_id = 7
    
    print("🔍 DIAGNOSING WOPI COMMUNICATION ISSUES")
    print("=" * 50)
    
    # Step 1: Generate token
    print("\n1. Generating WOPI token...")
    token_url = "http://localhost:3000/api/v1/collabora/generate-token"
    token_response = requests.post(token_url, json={"file_id": file_id}, timeout=10)
    
    if token_response.status_code != 200:
        print(f"❌ Token generation failed: {token_response.status_code}")
        print(token_response.text)
        return False
    
    token_data = token_response.json()
    access_token = token_data.get('access_token')
    print(f"✅ Token: {access_token[:20]}...")
    
    # Step 2: Test CheckFileInfo endpoint
    print("\n2. Testing WOPI CheckFileInfo...")
    check_url = f"http://localhost:3000/api/v1/wopi/files/{file_id}?access_token={access_token}"
    check_response = requests.get(check_url, timeout=10)
    
    print(f"   Status: {check_response.status_code}")
    print(f"   Headers: {dict(check_response.headers)}")
    
    if check_response.status_code == 200:
        file_info = check_response.json()
        print(f"   ✅ Response:")
        for key, value in file_info.items():
            print(f"      {key}: {value}")
        
        # Check required WOPI fields
        required_fields = ['BaseFileName', 'Size', 'UserId', 'UserCanWrite']
        missing_fields = [field for field in required_fields if field not in file_info]
        if missing_fields:
            print(f"   ⚠️  Missing required fields: {missing_fields}")
    else:
        print(f"   ❌ CheckFileInfo failed")
        print(f"   Response: {check_response.text}")
        return False
    
    # Step 3: Test GetFile endpoint
    print("\n3. Testing WOPI GetFile...")
    get_file_url = f"http://localhost:3000/api/v1/wopi/files/{file_id}/contents?access_token={access_token}"
    get_file_response = requests.get(get_file_url, timeout=10)
    
    print(f"   Status: {get_file_response.status_code}")
    print(f"   Content-Type: {get_file_response.headers.get('content-type')}")
    print(f"   Content-Length: {len(get_file_response.content)} bytes")
    print(f"   Headers: {dict(get_file_response.headers)}")
    
    if get_file_response.status_code != 200:
        print(f"   ❌ GetFile failed")
        print(f"   Response: {get_file_response.text[:200]}")
        return False
    
    # Check if content is valid Excel file
    if len(get_file_response.content) > 0:
        # Check Excel file magic bytes
        magic_bytes = get_file_response.content[:4]
        if magic_bytes == b'PK\x03\x04':  # ZIP/Excel magic bytes
            print(f"   ✅ Valid Excel file content detected")
        else:
            print(f"   ⚠️  Unexpected file format (magic: {magic_bytes.hex()})")
    else:
        print(f"   ❌ Empty file content!")
        return False
    
    # Step 4: Test Collabora discovery
    print("\n4. Testing Collabora discovery...")
    discovery_response = requests.get("http://localhost:9980/hosting/discovery", timeout=10)
    
    if discovery_response.status_code == 200:
        print(f"   ✅ Discovery available")
        # Check for Excel support
        discovery_content = discovery_response.text
        if 'xlsx' in discovery_content:
            print(f"   ✅ Excel (.xlsx) support found")
        else:
            print(f"   ⚠️  Excel support not found in discovery")
    else:
        print(f"   ❌ Discovery failed: {discovery_response.status_code}")
    
    # Step 5: Test WOPI access check
    print("\n5. Testing WOPI access from Collabora...")
    wopi_check_url = "http://localhost:9980/hosting/wopiAccessCheck"
    wopi_check_data = {"callbackUrl": "http://localhost:3000"}
    
    try:
        wopi_check_response = requests.post(wopi_check_url, json=wopi_check_data, timeout=10)
        print(f"   Status: {wopi_check_response.status_code}")
        print(f"   Response: {wopi_check_response.text}")
    except Exception as e:
        print(f"   ❌ WOPI access check failed: {e}")
    
    # Step 6: Generate URLs for comparison
    print("\n6. Generated URLs:")
    wopi_src = f"http://localhost:3000/api/v1/wopi/files/{file_id}"
    collabora_url = f"http://localhost:9980/browser/0b27e85/cool.html?WOPISrc={wopi_src}&access_token={access_token}&permission=readonly"
    
    print(f"   WOPI Source: {wopi_src}")
    print(f"   Full URL: {collabora_url}")
    
    return True

def main():
    success = diagnose_wopi_issue()
    
    if success:
        print("\n" + "=" * 50)
        print("🎯 DIAGNOSIS COMPLETE")
        print("=" * 50)
        print("\nIf all checks passed but document is still blank:")
        print("1. Check browser console (F12) for JavaScript errors")
        print("2. Look for Content Security Policy (CSP) blocks")
        print("3. Check for mixed HTTP/HTTPS content warnings")
        print("4. Try opening URL in incognito/private mode")
    else:
        print("\n❌ WOPI communication issues detected!")
        print("Fix the above errors before testing Collabora viewer")

if __name__ == "__main__":
    main()