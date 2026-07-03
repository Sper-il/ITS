import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/webapp")
sys.path.insert(0, os.getcwd())

from backend.core.routing_engine import _load_graph, find_nearest_node

G = _load_graph()
print("graph:", G.number_of_nodes(), "nodes,", G.number_of_edges(), "edges")
print()
# Print 3 sample nodes with their actual coords
print("Sample nodes:")
for i, (n, data) in enumerate(G.nodes(data=True)):
    print(f"  node {n}: lat={data.get('lat')}, lon={data.get('lon')}")
    if i >= 5: break

# Test find_nearest_node
test_points = [
    (10.7799, 106.6989, "Bến Thành"),
    (10.7954, 106.7226, "Landmark 81"),
    (10.7629, 106.6297, "HCM centre (default)"),
]
for lat, lon, name in test_points:
    nearest = find_nearest_node(lat, lon)
    print(f"{name} ({lat}, {lon}): nearest node = {nearest}")
