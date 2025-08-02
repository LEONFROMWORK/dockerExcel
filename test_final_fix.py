#\!/usr/bin/env python3
"""
Final test after fixing Docker networking issue
"""
import requests
import json

print("🔧 FINAL COLLABORA FIX TEST")
print("=" * 60)

file_id = 2

# 1. Get discovery data
print("\n1. Getting discovery data...")
discovery_response = requests.get("http://localhost:3000/api/v1/collabora/discovery")
discovery_data = discovery_response.json()

print(f"   WOPI Base URL: {discovery_data['wopi_base_url']}")
print(f"   Action URL: {discovery_data['action_url']}")

# 2. Generate token with edit permissions
print("\n2. Generating token with edit permissions...")
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

token_data = token_response.json()
access_token = token_data['access_token']

print(f"   ✅ Token generated")
print(f"   Permissions: {token_data['permissions']}")

# 3. Build Collabora URL
print("\n3. Building Collabora URL...")

wopi_src = f"{discovery_data['wopi_base_url']}/files/{file_id}"
action_url = discovery_data['action_url']

collabora_url = f"{action_url}?" \
               f"WOPISrc={wopi_src}&" \
               f"access_token={access_token}&" \
               f"permission=edit&" \
               f"closebutton=1&" \
               f"revisionhistory=0"

print(f"   WOPI Src (for Docker): {wopi_src}")
print(f"\n   Full Collabora URL:")
print(f"   {collabora_url}")

print("\n" + "=" * 60)
print("✅ FIX SUMMARY:")
print("=" * 60)
print("• CollaboraDiscoveryService: case sensitivity fixed ('Calc' → 'calc')")
print("• CollaboraController: action type fixed ('view' → 'edit')")
print("• CollaboraController: WOPI URL fixed ('localhost' → 'host.docker.internal')")
print("• collaboraService.js: URL duplication fixed")
print("• ExcelCollaboraViewer.vue: permission keys fixed ('canWrite' → 'can_write')")

print("\n🎯 EXPECTED RESULT:")
print("• WOPI URL now uses host.docker.internal:3000")
print("• Docker container can access Rails WOPI endpoints")
print("• 'Cannot connect to document' error should be resolved")

print("\n📋 NEXT STEPS:")
print("1. Open http://localhost:3000/ai/excel/analysis/2")
print("2. Excel file should load successfully")
print("3. Click '편집 모드' to enable editing")
print("4. File should be editable and saveable")
EOF < /dev/null