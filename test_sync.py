import requests

BASE = "http://localhost:5000/api"

# 1) Holen
r = requests.get(f"{BASE}/transactions", params={"user_id":1,"year":"2025","month":"0"})
print("GET:", r.json())

# 2) Posten
payload = {
  "user_id": 1,
  "date": "2025-05-04",
  "description": "CloudSync Test",
  "usage": "Sync",
  "amount": 99.99
}
r = requests.post(f"{BASE}/transaction", json=payload)
print("POST:", r.status_code, r.json())

# 3) Toggle paid
r = requests.post(f"{BASE}/transaction/123/toggle_paid", json={"user_id":1,"paid":0})
print("TOGGLE:", r.status_code, r.json())
