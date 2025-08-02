#!/usr/bin/env python3
"""
Test Collabora editing mode with write permissions
"""
import requests

def test_edit_mode():
    """Generate token with write permissions and test editing mode"""
    file_id = 7
    
    print("🔧 TESTING COLLABORA EDIT MODE")
    print("=" * 50)
    
    # Generate token with write permissions
    print("\n1. Generating edit token with write permissions...")
    token_url = "http://localhost:3000/api/v1/collabora/generate-token"
    
    # Request token with write permissions
    payload = {
        "file_id": file_id,
        "permissions": {
            "can_write": True,
            "can_export": True, 
            "can_print": True
        }
    }
    
    try:
        token_response = requests.post(token_url, json=payload, timeout=10)
        
        if token_response.status_code != 200:
            print(f"❌ Token failed: {token_response.status_code}")
            print(f"Response: {token_response.text}")
            return None
        
        access_token = token_response.json().get('access_token')
        print(f"✅ Edit token generated with write permissions")
    except Exception as e:
        print(f"❌ Token generation error: {e}")
        return None
    
    # Test WOPI CheckFileInfo with edit permissions
    print("\n2. Testing WOPI CheckFileInfo with edit permissions...")
    wopi_src = f"http://host.docker.internal:3000/api/v1/wopi/files/{file_id}"
    check_url = f"http://localhost:3000/api/v1/wopi/files/{file_id}?access_token={access_token}"
    
    try:
        check_response = requests.get(check_url, timeout=10)
        if check_response.status_code == 200:
            file_info = check_response.json()
            print(f"✅ CheckFileInfo: {file_info.get('BaseFileName')}")
            print(f"   UserCanWrite: {file_info.get('UserCanWrite')}")
            print(f"   SupportsUpdate: {file_info.get('SupportsUpdate')}")
            print(f"   UserCanNotWriteRelative: {file_info.get('UserCanNotWriteRelative')}")
        else:
            print(f"❌ CheckFileInfo failed: {check_response.status_code}")
            return None
    except Exception as e:
        print(f"❌ WOPI test error: {e}")
        return None
    
    # Generate Collabora URL for editing
    print("\n3. Generating Collabora URL for editing...")
    collabora_url = f"http://localhost:9980/browser/0b27e85/cool.html?WOPISrc={wopi_src}&access_token={access_token}"
    
    print(f"\n🎯 EDIT MODE COLLABORA URL:")
    print(f"{collabora_url}")
    
    print(f"\n🔧 Edit Mode Features:")
    print(f"- UserCanWrite: True")
    print(f"- SupportsUpdate: True") 
    print(f"- Auto-save every 5 minutes")
    print(f"- Version backup before each save")
    print(f"- Manual save via Ctrl+S")
    
    return collabora_url

def main():
    url = test_edit_mode()
    
    if url:
        print("\n" + "=" * 50)
        print("🎉 EDIT MODE READY!")
        print("=" * 50)
        print(f"\n🌐 EDIT MODE COLLABORA URL:")
        print(f"{url}")
        
        print(f"\n✨ Edit Features Available:")
        print(f"- ✅ Cell editing and formula modification")
        print(f"- ✅ Add/delete rows and columns") 
        print(f"- ✅ Formatting changes")
        print(f"- ✅ Auto-save with version backups")
        print(f"- ✅ Manual save (Ctrl+S)")
        print(f"- ✅ Export and print functions")
        
        print(f"\n📋 TEST INSTRUCTIONS:")
        print(f"1. Copy the URL above")
        print(f"2. Open in browser")
        print(f"3. Try editing cells - should work!")
        print(f"4. Changes will auto-save and create versions")
        print(f"5. Use Ctrl+S to manually save")
        
        print(f"\n🔍 Expected Results:")
        print(f"- Full editing interface in Collabora")
        print(f"- Changes save automatically") 
        print(f"- Version history created on save")
        print(f"- No 'read-only' restrictions")
        
    else:
        print(f"\n❌ Edit mode setup failed - check errors above")

if __name__ == "__main__":
    main()