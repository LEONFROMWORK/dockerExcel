#!/usr/bin/env python3
"""Test WOPI integration with Rails."""

import requests
import json


def test_rails_download_endpoint():
    """Test if Rails download endpoint works."""
    file_id = 25  # Use the file ID from the frontend
    rails_url = "http://localhost:3000/api/v1/excel_analysis/files/{}/download".format(
        file_id
    )

    headers = {"X-Internal-Api-Key": "development-key", "Accept": "application/json"}

    print(f"Testing Rails download endpoint: {rails_url}")

    try:
        response = requests.get(rails_url, headers=headers)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("Success! File info retrieved:")
            print(f"  - Filename: {data.get('filename')}")
            print(f"  - Size: {data.get('size')} bytes")
            print(f"  - Download URL: {data.get('download_url')}")
            return data
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        return None


def test_wopi_check_file_info():
    """Test WOPI CheckFileInfo endpoint."""
    file_id = 25
    wopi_url = f"http://localhost:8000/wopi/files/{file_id}"

    params = {"access_token": "test-token"}

    print(f"\nTesting WOPI CheckFileInfo endpoint: {wopi_url}")

    try:
        response = requests.get(wopi_url, params=params)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("Success! WOPI file info:")
            print(json.dumps(data, indent=2))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception occurred: {str(e)}")


def test_wopi_get_file():
    """Test WOPI GetFile endpoint."""
    file_id = 25
    wopi_url = f"http://localhost:8000/wopi/files/{file_id}/contents"

    params = {"access_token": "test-token"}

    print(f"\nTesting WOPI GetFile endpoint: {wopi_url}")

    try:
        response = requests.get(wopi_url, params=params)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            print("Success! File content retrieved")
            print(f"Content-Type: {response.headers.get('Content-Type')}")
            print(f"Content-Length: {response.headers.get('Content-Length')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception occurred: {str(e)}")


if __name__ == "__main__":
    print("=== Testing WOPI Integration ===\n")

    # First test Rails endpoint
    file_data = test_rails_download_endpoint()

    if file_data:
        # Then test WOPI endpoints
        test_wopi_check_file_info()
        test_wopi_get_file()
    else:
        print(
            "\nFailed to get file data from Rails. Check if the file exists and Rails is running."
        )
