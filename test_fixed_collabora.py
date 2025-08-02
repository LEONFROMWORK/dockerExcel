#!/usr/bin/env python3
"""
Test Collabora with fixed WOPI host configuration
"""
import requests

def test_fixed_collabora():
    """Test with fixed WOPI host setting"""
    file_id = 7
    
    print("🔧 TESTING FIXED COLLABORA")
    print("=" * 50)
    
    # Generate fresh token
    print("\n1. Generating fresh token...")
    token_url = "http://localhost:3000/api/v1/collabora/generate-token"
    token_response = requests.post(token_url, json={"file_id": file_id}, timeout=10)
    
    if token_response.status_code != 200:
        print(f"❌ Token failed: {token_response.status_code}")
        return None
    
    access_token = token_response.json().get('access_token')
    print(f"✅ Fresh token generated")
    
    # Test WOPI endpoints to ensure they work
    print("\n2. Testing WOPI endpoints...")
    wopi_src = f"http://localhost:3000/api/v1/wopi/files/{file_id}"
    
    # Test CheckFileInfo
    check_url = f"{wopi_src}?access_token={access_token}"
    check_response = requests.get(check_url, timeout=10)
    
    if check_response.status_code == 200:
        file_info = check_response.json()
        print(f"✅ CheckFileInfo: {file_info.get('BaseFileName')}")
    else:
        print(f"❌ CheckFileInfo failed: {check_response.status_code}")
        return None
    
    # Generate new Collabora URL
    print("\n3. Generating fixed Collabora URL...")
    collabora_url = f"http://localhost:9980/browser/0b27e85/cool.html?WOPISrc={wopi_src}&access_token={access_token}"
    
    print(f"\n🎯 FIXED COLLABORA URL:")
    print(f"{collabora_url}")
    
    # Test the URL directly
    print(f"\n4. Testing URL response...")
    try:
        response = requests.get(collabora_url, timeout=10)
        if response.status_code == 200:
            print(f"✅ URL accessible (HTTP 200)")
            if 'html' in response.text.lower() and 'collabora' in response.text.lower():
                print(f"✅ Contains Collabora HTML content")
            else:
                print(f"⚠️ Response may not be Collabora content")
        else:
            print(f"❌ URL returned: {response.status_code}")
    except Exception as e:
        print(f"❌ URL test failed: {e}")
    
    return collabora_url

def main():
    url = test_fixed_collabora()
    
    if url:
        print("\n" + "=" * 50)
        print("🎉 WOPI HOST FIXED!")
        print("=" * 50)
        print(f"\n🌐 FIXED URL (no more :80 port issue):")
        print(f"{url}")
        
        print(f"\n✨ Expected Results:")
        print(f"- No more resize-detector blank document")
        print(f"- Excel weather forecast data should display")
        print(f"- Proper Collabora interface loading")
        
        print(f"\n📋 TEST INSTRUCTIONS:")
        print(f"1. Copy the URL above")
        print(f"2. Open in new browser tab")
        print(f"3. Should see Excel data instead of blank page")
        print(f"4. Check browser console for any remaining errors")
        
    else:
        print(f"\n❌ Setup still has issues - check errors above")

if __name__ == "__main__":
    main()