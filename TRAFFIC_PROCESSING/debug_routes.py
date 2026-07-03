import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/webapp")
sys.path.insert(0, os.getcwd())

from backend.core.routing_engine import (
    _load_graph, find_nearest_node, find_all_paths_between
)
import networkx as nx

G = _load_graph()
s = find_nearest_node(10.7799, 106.6989)
t = find_nearest_node(10.7954, 106.7226)
print(f"s={s}, t={t}")
print(f"s in G: {s in G}, t in G: {t in G}")
print(f"G reachable between? {nx.has_path(G, s, t)}")
try:
    p = nx.dijkstra_path(G, s, t, weight='los_weight')
    print(f"path length: {len(p)}")
except Exception as e:
    print(f"dijkstra failed: {type(e).__name__}: {e}")

print()
# Test find_all_paths_between directly
print("find_all_paths_between:")
rs = find_all_paths_between(10.7799, 106.6989, 10.7954, 106.7226, vehicle='car')
print(f"routes found: {len(rs)}")
