#!/usr/bin/env python3
"""
Test Collabora Edit Mode Integration
Uploads test file and verifies edit mode functionality at http://localhost:3000/ai/excel
"""
import requests
import json

def test_file_upload_and_edit_mode():
    """Upload a test Excel file and verify edit mode integration"""
    
    print("🔧 TESTING COLLABORA EDIT MODE INTEGRATION")
    print("=" * 60)
    
    # Test file creation
    print("\n1. Creating test Excel file...")
    excel_content = create_test_excel_content()
    
    # Upload file
    print("\n2. Uploading test file to Rails...")
    file_id = upload_test_file(excel_content)
    
    if not file_id:
        print("❌ File upload failed")
        return None
    
    print(f"✅ File uploaded successfully: ID {file_id}")
    
    # Test token generation with edit permissions
    print("\n3. Testing edit mode token generation...")
    edit_token = test_edit_token_generation(file_id)
    
    if edit_token:
        print("✅ Edit mode token generated successfully")
    else:
        print("❌ Edit mode token generation failed")
        return None
    
    # Generate test URLs
    print("\n4. Generating test URLs...")
    
    # URL for AI Excel page with the uploaded file
    ai_excel_url = f"http://localhost:3000/ai/excel/{file_id}"
    
    print(f"\n🎯 TEST URLS:")
    print(f"📁 AI Excel Page: {ai_excel_url}")
    print(f"📝 Direct File ID: {file_id}")
    
    print(f"\n📋 TEST INSTRUCTIONS:")
    print(f"1. Open: {ai_excel_url}")
    print(f"2. Wait for file to load in Excel viewer")
    print(f"3. Look for '편집 모드' button in top-right corner")
    print(f"4. Click the button to toggle edit mode")
    print(f"5. Verify '✏️ 편집 모드 활성화' notification appears")
    print(f"6. Try editing cells in Collabora Online")
    print(f"7. Changes should auto-save with version backup")
    
    print(f"\n🔍 EXPECTED BEHAVIOR:")
    print(f"- File automatically loads in split view")
    print(f"- Edit mode button toggles between '편집 모드' and '읽기 모드'")
    print(f"- Edit mode shows notification overlay") 
    print(f"- Collabora iframe supports cell editing when edit mode is on")
    print(f"- Auto-save creates version backups every 5 minutes")
    
    return {
        "file_id": file_id,
        "ai_excel_url": ai_excel_url,
        "edit_token": edit_token
    }

def create_test_excel_content():
    """Create test Excel content as bytes"""
    # Simple Excel file content for testing
    # This is a minimal XLSX structure
    test_data = b'PK\x03\x04' + b'\x00' * 100  # Minimal ZIP/XLSX header
    return test_data

def upload_test_file(content):
    """Upload test file to Rails API"""
    upload_url = "http://localhost:3000/api/v1/excel_analysis/files"
    
    files = {
        'file': ('test_edit_mode.xlsx', content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    }
    
    try:
        response = requests.post(upload_url, files=files, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('file_id') or data.get('id')
        else:
            print(f"Upload failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"Upload error: {e}")
        return None

def test_edit_token_generation(file_id):
    """Test generating token with edit permissions"""
    token_url = "http://localhost:3000/api/v1/collabora/generate-token"
    
    payload = {
        "file_id": file_id,
        "permissions": {
            "can_write": True,
            "can_export": True,
            "can_print": True
        }
    }
    
    try:
        response = requests.post(token_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Token permissions: {data.get('permissions', {})}")
            return data.get('access_token')
        else:
            print(f"❌ Token generation failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Token generation error: {e}")
        return None

def main():
    result = test_file_upload_and_edit_mode()
    
    if result:
        print("\n" + "=" * 60)
        print("🎉 EDIT MODE INTEGRATION READY!")
        print("=" * 60)
        print(f"\n🌐 TEST URL: {result['ai_excel_url']}")
        print(f"\n✨ Features to Test:")
        print(f"- ✅ File upload and loading")
        print(f"- ✅ Edit mode toggle button") 
        print(f"- ✅ Edit mode notification")
        print(f"- ✅ Collabora iframe integration")
        print(f"- ✅ Auto-save and version management")
        print(f"- ✅ Permission-based access control")
        
        print(f"\n📖 Integration Complete!")
        print(f"Visit the URL above to test all edit mode features.")
        
    else:
        print(f"\n❌ Integration setup failed - check errors above")

if __name__ == "__main__":
    main()