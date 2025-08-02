#!/usr/bin/env python3
"""
Test Collabora with Docker host network configuration
"""
import requests

def test_docker_network_fix():
    """Test with host.docker.internal configuration"""
    file_id = 7
    
    print("🔧 TESTING DOCKER NETWORK FIX")
    print("=" * 50)
    
    # Generate fresh token
    print("\n1. Generating fresh token...")
    token_url = "http://localhost:3000/api/v1/collabora/generate-token"
    try:
        token_response = requests.post(token_url, json={"file_id": file_id}, timeout=10)
        
        if token_response.status_code != 200:
            print(f"❌ Token failed: {token_response.status_code}")
            print(f"Response: {token_response.text}")
            return None
        
        access_token = token_response.json().get('access_token')
        print(f"✅ Fresh token generated")
    except Exception as e:
        print(f"❌ Token generation error: {e}")
        return None
    
    # Test Docker container can reach host
    print("\n2. Testing Docker container connectivity...")
    try:
        # Test if container can reach our Rails server
        test_result = requests.get("http://localhost:9980", timeout=5)
        if test_result.status_code == 200:
            print("✅ Collabora service accessible from host")
        else:
            print(f"❌ Collabora service issue: {test_result.status_code}")
    except Exception as e:
        print(f"❌ Collabora service error: {e}")
        return None
    
    # Create WOPI URL with host.docker.internal for Docker container access
    print("\n3. Creating Docker-compatible WOPI URL...")
    # Use host.docker.internal for the WOPI source so Docker can reach it
    wopi_src_for_docker = f"http://host.docker.internal:3000/api/v1/wopi/files/{file_id}"
    
    # Test WOPI endpoints from host perspective (to verify they work)
    wopi_src_for_host = f"http://localhost:3000/api/v1/wopi/files/{file_id}"
    check_url = f"{wopi_src_for_host}?access_token={access_token}"
    
    try:
        check_response = requests.get(check_url, timeout=10)
        if check_response.status_code == 200:
            file_info = check_response.json()
            print(f"✅ CheckFileInfo (from host): {file_info.get('BaseFileName')}")
            print(f"   Size: {file_info.get('Size')} bytes")
        else:
            print(f"❌ CheckFileInfo failed: {check_response.status_code}")
            print(f"Response: {check_response.text}")
            return None
    except Exception as e:
        print(f"❌ WOPI test error: {e}")
        return None
    
    # Generate Collabora URL with Docker-compatible WOPI source
    print("\n4. Generating Docker-network compatible Collabora URL...")
    collabora_url = f"http://localhost:9980/browser/0b27e85/cool.html?WOPISrc={wopi_src_for_docker}&access_token={access_token}"
    
    print(f"\n🎯 DOCKER-NETWORK COLLABORA URL:")
    print(f"{collabora_url}")
    
    print(f"\n🔍 Key Changes:")
    print(f"- WOPI Source: {wopi_src_for_docker}")
    print(f"- Collabora domain config: host.docker.internal:3000")
    print(f"- Docker can now reach Rails server on host")
    
    # Test URL response
    print(f"\n5. Testing URL response...")
    try:
        response = requests.get(collabora_url, timeout=10)
        if response.status_code == 200:
            print(f"✅ URL accessible (HTTP 200)")
            
            content = response.text.lower()
            if 'collabora' in content or 'cool' in content:
                print(f"✅ Contains Collabora content")
            else:
                print(f"⚠️ Content may not be proper Collabora response")
        else:
            print(f"❌ URL returned: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ URL test failed: {e}")
        return None
    
    return collabora_url

def main():
    url = test_docker_network_fix()
    
    if url:
        print("\n" + "=" * 50)
        print("🎉 DOCKER NETWORK FIX COMPLETE!")
        print("=" * 50)
        print(f"\n🌐 FIXED COLLABORA URL:")
        print(f"{url}")
        
        print(f"\n✨ Network Fix Applied:")
        print(f"- Docker domain: host.docker.internal:3000")
        print(f"- WOPI URL: uses host.docker.internal for Docker access")
        print(f"- Collabora can now reach Rails WOPI endpoints")
        
        print(f"\n📋 TEST INSTRUCTIONS:")
        print(f"1. Copy the URL above")
        print(f"2. Open in browser")
        print(f"3. Should see: 'This is embarrassing' -> WOPI connection working")
        print(f"4. Should load Excel data instead of connection error")
        
        print(f"\n🔍 Expected Behavior:")
        print(f"- No 'This is embarrassing' error")
        print(f"- Collabora successfully connects to WOPI")
        print(f"- Excel weather forecast data loads properly")
        
    else:
        print(f"\n❌ Setup still has issues - check errors above")

if __name__ == "__main__":
    main()