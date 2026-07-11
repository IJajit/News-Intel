import urllib.request
import json

url = "http://localhost:5001/api/generate-brief"
payload = {
    "groundedTime": "2026-07-06T13:41:12.000Z",
    "category": "homepage"
}
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(
    url,
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
