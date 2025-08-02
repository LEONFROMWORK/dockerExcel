#!/usr/bin/env python3
"""
Debug Collabora URL generation and test direct access
"""
import requests
import json

def debug_collabora_url():
    """Debug and generate proper Collabora URL"""
    file_id = 7
    
    print("🔍 COLLABORA URL DEBUG")
    print("=" * 50)
    
    # Step 1: Get discovery info
    print("\n1. Checking Collabora Discovery...")
    try:
        discovery_response = requests.get("http://localhost:9980/hosting/discovery", timeout=10)
        if discovery_response.status_code == 200:
            print("✅ Discovery accessible")
            # Find xlsx action URL
            if 'xlsx' in discovery_response.text and 'cool.html' in discovery_response.text:
                print("✅ Excel (.xlsx) support confirmed")
            else:
                print("❌ Excel support not found in discovery")
        else:
            print(f"❌ Discovery failed: {discovery_response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Discovery error: {e}")
        return None
    
    # Step 2: Generate token
    print("\n2. Generating JWT token...")
    token_url = "http://localhost:3000/api/v1/collabora/generate-token"
    try:
        token_response = requests.post(token_url, json={"file_id": file_id}, timeout=10)
        if token_response.status_code == 200:
            access_token = token_response.json().get('access_token')
            print("✅ Token generated successfully")
        else:
            print(f"❌ Token generation failed: {token_response.status_code}")
            print(f"Response: {token_response.text}")
            return None
    except Exception as e:
        print(f"❌ Token error: {e}")
        return None
    
    # Step 3: Test WOPI endpoints
    print("\n3. Testing WOPI endpoints...")
    wopi_src = f"http://localhost:3000/api/v1/wopi/files/{file_id}"
    
    # Test CheckFileInfo
    check_url = f"{wopi_src}?access_token={access_token}"
    try:
        check_response = requests.get(check_url, timeout=10)
        if check_response.status_code == 200:
            file_info = check_response.json()
            print(f"✅ CheckFileInfo OK - File: {file_info.get('BaseFileName', 'Unknown')}")
            print(f"   Size: {file_info.get('Size', 0)} bytes")
        else:
            print(f"❌ CheckFileInfo failed: {check_response.status_code}")
            print(f"Response: {check_response.text}")
            return None
    except Exception as e:
        print(f"❌ CheckFileInfo error: {e}")
        return None
    
    # Test GetFile
    get_file_url = f"{wopi_src}/contents?access_token={access_token}"
    try:
        get_file_response = requests.head(get_file_url, timeout=10)  # Use HEAD for quick check
        if get_file_response.status_code == 200:
            print("✅ GetFile endpoint accessible")
        else:
            print(f"❌ GetFile failed: {get_file_response.status_code}")
            return None
    except Exception as e:
        print(f"❌ GetFile error: {e}")
        return None
    
    # Step 4: Generate different URL formats to test
    print("\n4. Generating Collabora URLs...")
    
    # Format 1: HTTP with explicit protocol
    url1 = f"http://localhost:9980/browser/0b27e85/cool.html?WOPISrc={wopi_src}&access_token={access_token}&permission=readonly"
    
    # Format 2: Try without permission parameter
    url2 = f"http://localhost:9980/browser/0b27e85/cool.html?WOPISrc={wopi_src}&access_token={access_token}"
    
    # Format 3: Use HTTPS as per discovery
    url3 = f"https://localhost:9980/browser/0b27e85/cool.html?WOPISrc={wopi_src}&access_token={access_token}"
    
    return {
        'wopi_src': wopi_src,
        'access_token': access_token,
        'urls': {
            'http_with_permission': url1,
            'http_without_permission': url2,  
            'https_format': url3
        }
    }

def test_collabora_direct():
    """Test direct access to Collabora"""
    print("\n5. Testing direct Collabora access...")
    
    try:
        # Test main page
        main_response = requests.get("http://localhost:9980", timeout=5)
        print(f"   Main page: {main_response.status_code}")
        
        # Test cool.html directly
        cool_response = requests.get("http://localhost:9980/browser/0b27e85/cool.html", timeout=5)
        print(f"   cool.html: {cool_response.status_code}")
        
        if cool_response.status_code == 200 and 'html' in cool_response.text.lower():
            print("✅ Collabora interface accessible")
            return True
        else:
            print("❌ Collabora interface not responding properly")
            return False
            
    except Exception as e:
        print(f"❌ Direct access error: {e}")
        return False

def main():
    result = debug_collabora_url()
    collabora_working = test_collabora_direct()
    
    print("\n" + "=" * 50)
    print("🏁 DEBUG RESULTS")
    print("=" * 50)
    
    if result and collabora_working:
        print("\n🌐 TEST THESE URLS:")
        print(f"\n1. HTTP with permission:")
        print(f"   {result['urls']['http_with_permission']}")
        
        print(f"\n2. HTTP without permission:")
        print(f"   {result['urls']['http_without_permission']}")
        
        print(f"\n3. HTTPS format (as per discovery):")
        print(f"   {result['urls']['https_format']}")
        
        print(f"\n🔍 WOPI Source: {result['wopi_src']}")
        print(f"\n🎫 Access Token: {result['access_token'][:50]}...")
        
        print(f"\n📋 TROUBLESHOOTING:")
        print(f"- Try each URL in browser")
        print(f"- Check browser developer console for errors")
        print(f"- Verify if HTTPS/HTTP protocol matters")
        
    else:
        print("\n❌ Setup incomplete - fix issues above first")

if __name__ == "__main__":
    main()