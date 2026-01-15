import requests
import json
from requests.auth import HTTPDigestAuth
import requests
from urllib.parse import urlencode

BASE_URL = "http://127.0.0.1:5000"  # CHANGE THIS
USERS_FILE = "users.json"
USERNAME = "Yosh"
TIMEOUT = 5

# -----------------------------
# Load user credentials
# -----------------------------

with open(USERS_FILE, "r", encoding="utf-8") as f:
    users = json.load(f)

if isinstance(users[USERNAME], dict):
    PASSWORD = users[USERNAME]["password"]
else:
    PASSWORD = users[USERNAME]

auth = HTTPDigestAuth(USERNAME, PASSWORD)

session = requests.Session()
session.auth = auth
session.headers.update({
    "User-Agent": "Inventory-Endpoint-Tester/1.0",
    "Accept": "application/json",
})
# -----------------------------
# Endpoint definitions
# -----------------------------

GET_ENDPOINTS = [
    ("/", {}),
    ("/inventory", {}),

    ("/api/items", {}),
    ("/api/items", {"price_min": 0}),
    ("/api/items", {"tag_partial": "a"}),

    # Search endpoints
    ("/api/items/tag", {"q": "a"}),
    ("/api/items/location", {"q": "a"}),
    ("/api/items/group", {"q": "a"}),
    ("/api/items/voltage", {"q": 5}),
    ("/api/items/current", {"q": 1}),
    ("/api/items/capacity", {"q": 1000}),
    ("/api/items/charging-type", {"q": "usb"}),
    ("/api/items/bought-place", {"q": "a"}),
    ("/api/items/variant", {"q": "a"}),
    ("/api/items/color", {"q": "a"}),
    ("/api/items/status", {"q": "a"}),
    ("/api/items/price", {"q": 10}),
    ("/api/items/last-seen", {"q": "2025"}),
    ("/api/items/last-use", {"q": "2025"}),
    ("/api/items/acquired", {"q": "2025"}),
    ("/api/items/id", {"q": 1}),
    ("/api/items/group-id", {"q": 1}),
]

AUTOCOMPLETE_ENDPOINTS = [
    (path, {**params, "autocomplete": 1})
    for path, params in GET_ENDPOINTS
    if path.startswith("/api/")
]

# -----------------------------
# Helpers
# -----------------------------

def test_endpoint(path, params):
    url = BASE_URL + path
    try:
        r = session.get(url, params=params, timeout=TIMEOUT)
        content_type = r.headers.get("Content-Type", "")
        preview = r.text[:2000].replace("\n", " ")

        print(f"[{r.status_code}] {path}?{urlencode(params)}")
        print(f"     Content-Type: {content_type}")
        print(f"     Body preview: {preview!r}")
        if r.status_code >= 400:
            print("     ⚠️  ERROR")
        print()

    except Exception as e:
        print(f"[!!!] {path}?{params}")
        print(f"     Exception: {e}")
        print()

# -----------------------------
# Run tests
# -----------------------------

print("=== BASIC GET ENDPOINTS ===\n")
for path, params in GET_ENDPOINTS:
    test_endpoint(path, params)

print("\n=== AUTOCOMPLETE ENDPOINTS ===\n")
for path, params in AUTOCOMPLETE_ENDPOINTS:
    test_endpoint(path, params)

print("\n=== DONE ===")
