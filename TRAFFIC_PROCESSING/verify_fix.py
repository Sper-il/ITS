"""Verify: with fixed template, do user overrides actually change predictions?"""
import sys, warnings, math
warnings.filterwarnings("ignore")
sys.path.insert(0, "webapp/backend")

from importlib import reload
import core.model
reload(core.model)
from core.model import predict_row, _feature_default_template, load_model
import numpy as np

# Check template
tmpl = _feature_default_template()
print(f"Template has {len(tmpl)} keys")

# The real test: with fixed template, do extreme inputs give different results?
tests = [
    # (description, length, max_vel, vc, hour, is_weekend, is_rush)
    ("Very free flow",    50,   120, 0.01, 3,  False, False),
    ("Moderate traffic",  500,   60,  0.5, 12, False, False),
    ("Heavy congestion", 2000,  30,  1.2, 17, False, True),
    ("Peak rush hour",   3000, 40,  1.0,  8, False, True),
    ("Weekend noon",     1000,  60,  0.7, 13, True,  False),
    ("Late night",       2000,  80,  0.3, 23, False, False),
    ("Max length urban", 5000,  30,  1.5, 18, False, True),
]

print("\nPrediction tests with fixed template:")
for desc, *args in tests:
    pred, conf, proba = predict_row(*args)
    print(f"\n  {desc}: LOS={pred} (conf={conf:.3f})")
    sorted_probs = sorted(proba.items(), key=lambda x: -x[1])
    print(f"    Top 3: " + ", ".join(f"{k}={v:.3f}" for k, v in sorted_probs[:3]))

# Most important: compare with the default template values
print("\n\n--- Does varying inputs produce statistically different results? ---")
print("Testing 20 random configurations...")
results = []
for i in range(20):
    import random
    length = random.choice([50, 200, 500, 1000, 3000, 5000])
    max_v  = random.choice([20, 40, 60, 80, 100, 120])
    vc     = round(random.uniform(0.05, 1.5), 2)
    hour   = random.randint(0, 23)
    wknd   = random.choice([True, False])
    rush   = random.choice([True, False])
    pred, conf, proba = predict_row(length, max_v, vc, hour, wknd, rush)
    results.append((pred, conf))

from collections import Counter
pred_counts = Counter(r[0] for r in results)
conf_range = (min(r[1] for r in results), max(r[1] for r in results))
print(f"Predictions: {dict(pred_counts)}")
print(f"Confidence range: {conf_range[0]:.3f} - {conf_range[1]:.3f}")
if len(pred_counts) > 1:
    print("PASS: Different inputs -> Different predictions!")
else:
    print("FAIL: Same prediction for all inputs")
