import urllib.request
import urllib.parse
import json
import ssl
import random
import time

# Configuration
BASE_URL = "http://127.0.0.1:8000/api"
ADMIN_EMAIL = "test@arca.com"
ADMIN_PASSWORD = "123"

# Disable SSL verification for localhost
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def get_auth_token():
    url = f"{BASE_URL}/auth/login"
    data = json.dumps({"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            if response.status == 200:
                body = response.read().decode('utf-8')
                json_body = json.loads(body)
                print(f"Login Response: {json_body}")
                return json_body['access_token']
            else:
                print(f"Login failed: {response.status}")
                return None
    except urllib.error.HTTPError as e:
        print(f"Login error: {e.code} - {e.read().decode('utf-8')}")
        return None

def test_admin_actions(token):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # 1. Cost Center
    print("\n--- Testing Cost Center ---")
    cc_code = f"CC-{random.randint(1000, 9999)}"
    cc_data = json.dumps({"code": cc_code, "name": "Test Center"}).encode('utf-8')
    cc_req = urllib.request.Request(f"{BASE_URL}/accounting/cost-centers", data=cc_data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(cc_req, context=ctx) as response:
            cc_id = json.loads(response.read().decode('utf-8'))['id']
            print(f"Created Cost Center ID: {cc_id}")
            
            # Delete
            del_req = urllib.request.Request(f"{BASE_URL}/accounting/cost-centers/{cc_id}", headers=headers, method='DELETE')
            with urllib.request.urlopen(del_req, context=ctx) as del_response:
                print(f"Delete Cost Center: {del_response.status}")
    except Exception as e:
        print(f"Cost Center Test Failed: {e}")

    # 2. Fiscal Period
    print("\n--- Testing Fiscal Period ---")
    period_data = json.dumps({"name": "Test Period 2026", "start_date": "2026-01-01", "end_date": "2026-12-31"}).encode('utf-8')
    fp_req = urllib.request.Request(f"{BASE_URL}/accounting/periods", data=period_data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(fp_req, context=ctx) as response:
            fp_id = json.loads(response.read().decode('utf-8'))['id']
            print(f"Created Period ID: {fp_id}")
            
            # Close
            close_req = urllib.request.Request(f"{BASE_URL}/accounting/periods/{fp_id}/close", headers=headers, method='POST')
            with urllib.request.urlopen(close_req, context=ctx) as close_response:
                print(f"Close Period: {close_response.status}")
                
            # Reopen
            reopen_req = urllib.request.Request(f"{BASE_URL}/accounting/periods/{fp_id}/reopen", headers=headers, method='POST')
            with urllib.request.urlopen(reopen_req, context=ctx) as reopen_response:
                print(f"Reopen Period: {reopen_response.status}")
                
            # Delete
            del_req = urllib.request.Request(f"{BASE_URL}/accounting/periods/{fp_id}", headers=headers, method='DELETE')
            with urllib.request.urlopen(del_req, context=ctx) as del_response:
                print(f"Delete Period: {del_response.status}")
    except Exception as e:
        print(f"Fiscal Period Test Failed: {e}")

if __name__ == "__main__":
    token = get_auth_token()
    if token:
        test_admin_actions(token)
