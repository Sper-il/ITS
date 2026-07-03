import requests

query = """
[out:json][timeout:30];
(
  way["highway"="motorway"](10.75,106.55,10.85,106.72);
  way["highway"="trunk"](10.75,106.55,10.85,106.72);
  way["highway"="primary"](10.75,106.55,10.85,106.72);
  way["highway"="secondary"](10.75,106.55,10.85,106.72);
  way["highway"="tertiary"](10.75,106.55,10.85,106.72);
  way["highway"="residential"](10.75,106.55,10.85,106.72);
);
out body;
>;
out skel qt;
"""

resp = requests.post(
    "https://overpass-api.de/api/interpreter",
    data={"data": query},
    timeout=40,
    headers={"User-Agent": "ITS-TD/1.0"},
)
print(f"Status: {resp.status_code}")
d = resp.json()
ways = [e for e in d.get("elements", []) if e.get("type") == "way"]
nodes = [e for e in d.get("elements", []) if e.get("type") == "node"]
print(f"Ways: {len(ways)}, Nodes: {len(nodes)}")
