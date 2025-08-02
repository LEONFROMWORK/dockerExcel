#!/usr/bin/env python3
"""
Test the cell consistency API endpoint
"""

import requests
import json

def test_cell_api():
    """Test the cell consistency API"""
    url = "http://localhost:8000/api/v1/test-cell-consistency"
    
    # Test case: Frontend cell at row=0, col=0 (A1)
    test_data = {
        "frontend_cell": {
            "row": 0,
            "col": 0,
            "address": "A1",
            "value": "Test Value"
        }
    }
    
    try:
        response = requests.post(url, json=test_data)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            
            # Check if addresses match
            frontend_addr = test_data["frontend_cell"]["address"]
            backend_addr = result.get("backend_cell", {}).get("address", "")
            
            if frontend_addr == backend_addr:
                print(f"\n✅ SUCCESS: Both systems recognize cell as {frontend_addr}")
            else:
                print(f"\n❌ MISMATCH: Frontend={frontend_addr}, Backend={backend_addr}")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Connection Error: {e}")
        print("\nMake sure the Python service is running on port 8000")

if __name__ == "__main__":
    print("Testing Cell Consistency API...")
    print("-" * 40)
    test_cell_api()