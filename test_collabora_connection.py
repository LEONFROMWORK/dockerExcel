#!/usr/bin/env python3
"""
Test Collabora connection and debug the 'cannot connect' error
"""
import requests
import json
import time

def test_wopi_from_collabora():
    """Test if Collabora can actually reach WOPI endpoints"""
    
    print("🔧 TESTING COLLABORA CONNECTION TO WOPI")
    print("=" * 60)
    
    file_id = 2
    
    # First generate a fresh token
    print("\n1. Generating fresh WOPI token...")
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
        return
    
    token_data = token_response.json()
    access_token = token_data['access_token']
    print(f"✅ Token generated: {access_token[:30]}...")
    
    # Test WOPI endpoints from localhost (simulating Collabora)
    print("\n2. Testing WOPI endpoints from localhost...")
    
    # Test with host.docker.internal (what Collabora would use)
    docker_host_url = f"http://host.docker.internal:3000/api/v1/wopi/files/{file_id}"
    
    print(f"\n   Testing Docker host URL: {docker_host_url}")
    try:
        # Test from Docker perspective
        docker_test = requests.get(
            docker_host_url,
            params={"access_token": access_token},
            timeout=5
        )
        print(f"   ✅ Docker host accessible: {docker_test.status_code}")
    except Exception as e:
        print(f"   ❌ Docker host not accessible: {e}")
    
    # Test normal localhost
    localhost_url = f"http://localhost:3000/api/v1/wopi/files/{file_id}"
    print(f"\n   Testing localhost URL: {localhost_url}")
    
    check_response = requests.get(
        localhost_url,
        params={"access_token": access_token}
    )
    
    if check_response.status_code == 200:
        file_info = check_response.json()
        print(f"   ✅ CheckFileInfo successful")
        print(f"      BaseFileName: {file_info.get('BaseFileName')}")
        print(f"      Size: {file_info.get('Size')}")
        print(f"      PostMessageOrigin: {file_info.get('PostMessageOrigin')}")
    else:
        print(f"   ❌ CheckFileInfo failed: {check_response.status_code}")
        print(f"      Response: {check_response.text}")
    
    # Test GetFile endpoint
    print("\n3. Testing GetFile endpoint...")
    getfile_response = requests.get(
        f"{localhost_url}/contents",
        params={"access_token": access_token}
    )
    
    if getfile_response.status_code == 200:
        print(f"   ✅ GetFile successful")
        print(f"      Content-Type: {getfile_response.headers.get('content-type')}")
        print(f"      Content-Length: {getfile_response.headers.get('content-length')}")
        print(f"      X-WOPI-ItemVersion: {getfile_response.headers.get('x-wopi-itemversion')}")
    else:
        print(f"   ❌ GetFile failed: {getfile_response.status_code}")
    
    # Check if Collabora iframe would work
    print("\n4. Building Collabora iframe URL...")
    
    discovery_response = requests.get("http://localhost:3000/api/v1/collabora/discovery")
    discovery_data = discovery_response.json()
    
    action_url = discovery_data.get('action_url')
    wopi_base = discovery_data.get('wopi_base_url')
    
    # Build the URL as the frontend would
    if action_url and action_url.startswith('http'):
        # Already full URL
        collabora_base = action_url
    else:
        collabora_base = f"http://localhost:9980{action_url}"
    
    wopi_src = f"{wopi_base}/files/{file_id}"
    
    # Build final URL
    collabora_url = f"{collabora_base}?" \
                   f"WOPISrc={wopi_src}&" \
                   f"access_token={access_token}&" \
                   f"permission=edit&" \
                   f"closebutton=1&" \
                   f"revisionhistory=0"
    
    print(f"   Action URL: {action_url}")
    print(f"   WOPI Base: {wopi_base}")
    print(f"   WOPI Src: {wopi_src}")
    print(f"\n   Full Collabora URL:")
    print(f"   {collabora_url}")
    
    # Test if Collabora is actually running
    print("\n5. Testing Collabora server health...")
    try:
        collabora_health = requests.get("http://localhost:9980/hosting/discovery", timeout=2)
        if collabora_health.status_code == 200:
            print(f"   ✅ Collabora server is healthy")
        else:
            print(f"   ⚠️  Collabora server returned: {collabora_health.status_code}")
    except Exception as e:
        print(f"   ❌ Cannot reach Collabora server: {e}")
    
    # Check for common issues
    print("\n6. Checking for common issues...")
    
    # Check if WOPI URL is accessible from Docker
    print("\n   a) WOPI URL accessibility from Docker container:")
    docker_wopi_url = wopi_src.replace('localhost', 'host.docker.internal')
    print(f"      Docker would use: {docker_wopi_url}")
    
    # Check CORS headers
    print("\n   b) CORS headers on WOPI endpoint:")
    cors_check = requests.options(
        localhost_url,
        headers={
            'Origin': 'http://localhost:9980',
            'Access-Control-Request-Method': 'GET'
        }
    )
    print(f"      OPTIONS response: {cors_check.status_code}")
    if 'access-control-allow-origin' in cors_check.headers:
        print(f"      Allow-Origin: {cors_check.headers.get('access-control-allow-origin')}")
    else:
        print(f"      ⚠️  No CORS headers found")
    
    print("\n" + "=" * 60)
    print("📊 DIAGNOSIS SUMMARY")
    print("=" * 60)
    
    print("\nPossible issues to check:")
    print("1. WOPI URL in iframe might be using 'localhost' instead of 'host.docker.internal'")
    print("2. CORS headers might be blocking Collabora requests")
    print("3. Token might be expiring too quickly")
    print("4. Network connectivity between Docker container and Rails")
    print("\nCheck Docker container logs for more details:")
    print("  docker logs collabora-docker-host --tail 100")

if __name__ == "__main__":
    test_wopi_from_collabora()