import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
# Always cd into webapp/ so 'backend' is importable.
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/webapp")
sys.path.insert(0, os.getcwd())

print("cwd:", os.getcwd())
print("sys.path[0]:", sys.path[0])

from backend.core.model import get_live_predictions, load_training_metrics
from backend.core.routing_engine import graph_stats, find_all_paths_between

print('--- Live preds n=100 ---')
df = get_live_predictions(100)
print('rows:', len(df), 'counts:', dict(df['LOS_pred'].value_counts()))
print('mean conf:', round(df['confidence'].mean(), 3))

print()
print('--- Training metrics ---')
m = load_training_metrics()
for k in ['val_accuracy', 'val_macro_f1', 'cv_accuracy_mean']:
    print(f'  {k}: {m.get(k)}')

print()
print('--- Graph stats ---')
s = graph_stats()
print(s)

print()
print('--- Routes (Bến Thành -> Landmark 81) ---')
rs = find_all_paths_between(10.7799, 106.6989, 10.7954, 106.7226, vehicle='car')
print('routes:', len(rs))
for r in rs:
    strat = r['strategy']
    print(f'  [{strat}] {r["total_distance_display"]}, {r["total_travel_time_str"]}, edges={len(r["edges"])}')
    print(f'  LOS dist: {r["los_distribution"]}')
