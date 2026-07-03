"""Trigger routing page to load graph and return stats."""
import requests

r = requests.get(
    "http://localhost:8501/streamlit/routing",
    headers={"User-Agent": "test"},
    timeout=60,
)
print(f"Status: {r.status_code}, Len: {len(r.text)}")
