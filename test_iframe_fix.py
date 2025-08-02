#!/usr/bin/env python3
"""
Test iframe fix for WOPI headers
"""
import requests

def test_iframe_fix():
    """Test if X-Frame-Options is fixed"""
    file_id = 7
    
    print("🔧 TESTING IFRAME FIX")
    print("=" * 40)
    
    # Generate new token
    print("\n1. Generating new token...")
    token_url = "http://localhost:3000/api/v1/collabora/generate-token"
    token_response = requests.post(token_url, json={"file_id": file_id}, timeout=10)
    
    if token_response.status_code != 200:
        print(f"❌ Token failed: {token_response.status_code}")
        return None
    
    access_token = token_response.json().get('access_token')
    print(f"✅ Token generated")
    
    # Test CheckFileInfo headers
    print("\n2. Testing CheckFileInfo headers...")
    check_url = f"http://localhost:3000/api/v1/wopi/files/{file_id}?access_token={access_token}"
    check_response = requests.get(check_url, timeout=10)
    
    headers = check_response.headers
    
    # Check X-Frame-Options
    frame_options = headers.get('X-Frame-Options', 'NOT_SET')
    print(f"   X-Frame-Options: {frame_options}")
    
    if frame_options == 'DENY':
        print(f"   ❌ Still DENY - iframe will be blocked")
        return None
    elif frame_options == 'SAMEORIGIN':
        print(f"   ✅ SAMEORIGIN - iframe allowed from same origin")
    else:
        print(f"   ⚠️  Unexpected value: {frame_options}")
    
    # Check Content-Security-Policy
    csp = headers.get('Content-Security-Policy', 'NOT_SET')
    if 'frame-ancestors' in csp:
        print(f"   ✅ CSP frame-ancestors configured")
        print(f"      {csp}")
    else:
        print(f"   ⚠️  No frame-ancestors in CSP")
    
    # Test GetFile headers
    print("\n3. Testing GetFile headers...")
    get_file_url = f"http://localhost:3000/api/v1/wopi/files/{file_id}/contents?access_token={access_token}"
    get_file_response = requests.get(get_file_url, timeout=10)
    
    get_headers = get_file_response.headers
    get_frame_options = get_headers.get('X-Frame-Options', 'NOT_SET')
    print(f"   GetFile X-Frame-Options: {get_frame_options}")
    
    # Generate final URL
    print("\n4. Generating fixed Collabora URL...")
    wopi_src = f"http://localhost:3000/api/v1/wopi/files/{file_id}"
    collabora_url = f"http://localhost:9980/browser/0b27e85/cool.html?WOPISrc={wopi_src}&access_token={access_token}&permission=readonly"
    
    return collabora_url

def main():
    url = test_iframe_fix()
    
    if url:
        print("\n" + "=" * 40)
        print("🎉 IFRAME FIX APPLIED!")
        print("=" * 40)
        print(f"\n🌐 FIXED COLLABORA URL:")
        print(f"{url}")
        print(f"\n✨ Expected Results:")
        print(f"- No more blank document")
        print(f"- Excel weather data should display")
        print(f"- No iframe blocking errors")
        print(f"\n📋 Test this URL in your browser now!")
        
    else:
        print(f"\n❌ Fix incomplete - check headers above")

if __name__ == "__main__":
    main()