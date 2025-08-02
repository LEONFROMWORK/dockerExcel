#!/usr/bin/env python3
"""
Test Collabora URL Generation and Access
"""
import requests
import json

def test_collabora_url_generation():
    """Test the complete Collabora URL generation process"""
    
    print("🔧 TESTING COLLABORA URL GENERATION")
    print("=" * 60)
    
    file_id = 2
    
    # Step 1: Generate token
    print("\n1. Generating WOPI token...")
    token_response = requests.post(
        "http://localhost:3000/api/v1/collabora/generate-token",
        json={
            "file_id": file_id,
            "permissions": {
                "can_write": True,
                "can_export": True,
                "can_print": True
            }
        }
    )
    
    if token_response.status_code != 200:
        print(f"❌ Token generation failed: {token_response.status_code}")
        print(token_response.text)
        return None
    
    token_data = token_response.json()
    access_token = token_data['access_token']
    print(f"✅ Token generated: {access_token[:30]}...")
    print(f"   Permissions: {token_data['permissions']}")
    
    # Step 2: Test WOPI CheckFileInfo
    print("\n2. Testing WOPI CheckFileInfo...")
    check_response = requests.get(
        f"http://localhost:3000/api/v1/wopi/files/{file_id}",
        params={"access_token": access_token}
    )
    
    if check_response.status_code != 200:
        print(f"❌ CheckFileInfo failed: {check_response.status_code}")
        print(check_response.text)
        return None
    
    file_info = check_response.json()
    print(f"✅ CheckFileInfo successful")
    print(f"   File: {file_info['BaseFileName']}")
    print(f"   Size: {file_info['Size']} bytes")
    print(f"   UserCanWrite: {file_info['UserCanWrite']}")
    print(f"   SupportsUpdate: {file_info['SupportsUpdate']}")
    
    # Step 3: Test WOPI GetFile
    print("\n3. Testing WOPI GetFile...")
    getfile_response = requests.head(
        f"http://localhost:3000/api/v1/wopi/files/{file_id}/contents",
        params={"access_token": access_token}
    )
    
    if getfile_response.status_code != 200:
        print(f"❌ GetFile failed: {getfile_response.status_code}")
        return None
    
    print(f"✅ GetFile successful")
    print(f"   Content-Type: {getfile_response.headers.get('content-type')}")
    print(f"   Content-Length: {getfile_response.headers.get('content-length', 'Unknown')}")
    
    # Step 4: Generate complete Collabora URL
    print("\n4. Generating Collabora URL...")
    
    # Get discovery data
    discovery_response = requests.get("http://localhost:3000/api/v1/collabora/discovery")
    discovery_data = discovery_response.json()
    
    wopi_src = f"{discovery_data['wopi_base_url']}/files/{file_id}"
    action_url = discovery_data.get('action_url', '/browser/757e96e/cool.html')
    
    # Build complete URL
    collabora_url = f"http://localhost:9980{action_url}?" \
                   f"WOPISrc={wopi_src}&" \
                   f"access_token={access_token}&" \
                   f"permission=edit&" \
                   f"closebutton=1&" \
                   f"revisionhistory=0"
    
    print(f"✅ Collabora URL generated:")
    print(f"   WOPI Src: {wopi_src}")
    print(f"   Action URL: {action_url}")
    print(f"   Permission: edit")
    
    # Step 5: Test if Collabora can access the file
    print(f"\n5. Testing Collabora accessibility...")
    
    # Test that Collabora discovery is working
    collabora_discovery = requests.get("http://localhost:9980/hosting/discovery")
    if collabora_discovery.status_code == 200:
        print(f"✅ Collabora discovery endpoint accessible")
    else:
        print(f"❌ Collabora discovery failed: {collabora_discovery.status_code}")
    
    return {
        "file_id": file_id,
        "access_token": access_token,
        "collabora_url": collabora_url,
        "file_info": file_info,
        "wopi_src": wopi_src
    }

def main():
    result = test_collabora_url_generation()
    
    if result:
        print("\n" + "=" * 60)
        print("🎉 COLLABORA URL GENERATION SUCCESS!")
        print("=" * 60)
        
        print(f"\n📋 COMPLETE TEST URL:")
        print(f"{result['collabora_url']}")
        
        print(f"\n🔍 DEBUGGING INFORMATION:")
        print(f"- File ID: {result['file_id']}")
        print(f"- File Name: {result['file_info']['BaseFileName']}")
        print(f"- File Size: {result['file_info']['Size']} bytes")
        print(f"- Write Permission: {result['file_info']['UserCanWrite']}")
        print(f"- WOPI Source: {result['wopi_src']}")
        print(f"- Access Token: {result['access_token'][:30]}...")
        
        print(f"\n🎯 NEXT STEPS:")
        print(f"1. Open browser to: http://localhost:3000/ai/excel/analysis/{result['file_id']}")
        print(f"2. Check that edit mode button appears")
        print(f"3. Toggle edit mode and verify Collabora loads with editing enabled")
        print(f"4. If still getting 'cannot connect' error, check:")
        print(f"   - Rails server logs for detailed error messages")
        print(f"   - Collabora container logs for connection attempts")
        print(f"   - Network connectivity between Docker and host")
        
    else:
        print(f"\n❌ URL generation failed - check errors above")

if __name__ == "__main__":
    main()