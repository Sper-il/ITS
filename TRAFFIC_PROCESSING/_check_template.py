import sys
sys.path.insert(0, 'webapp')
from backend.core.model import load_model, load_test_data
import pandas as pd

load_model()
df = load_test_data()
num = df.select_dtypes(include="number")
template = {c: float(num[c].median()) for c in num.columns if c not in {"los_label", "LOS"}}

user_keys = ['length', 'max_velocity', 'max_velocity_kmh', 'vc_ratio', 'hour', 'is_weekend', 'is_rush', 'period_hour', 'is_rush_hour']
for k in user_keys:
    if k in template:
        print(f'{k}: {template[k]} (FOUND)')
    else:
        print(f'{k}: NOT_IN_TEMPLATE')
print(f'Total template keys: {len(template)}')
