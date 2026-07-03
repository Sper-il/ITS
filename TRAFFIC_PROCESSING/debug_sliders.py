"""Debug: check what happens when sliders are set to 50%."""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "webapp/backend")

from core.los_engine import predict_ui, _try_trained_model

# Simulate what the test slider does: set each to 50% of range
# slider-length: 50-5000, value=2550
# slider-speed: 20-120, value=70
# slider-vc: 0-150, value=75 -> vc_ratio = 75/100 = 0.75
# slider-hour: 0-23, value=11.5

tests = [
    ("50% sliders",  2550, 70, 0.75, 11, False, False),
    ("25% sliders", 1275, 45, 0.375, 5, False, False),
    ("75% sliders", 3825, 95, 1.125, 17, False, True),
]

print("Testing los_engine:")
for name, *args in tests:
    try:
        result = predict_ui(*args)
        print(f"  {name}: {result[0]} (conf={result[1]:.3f})")
    except Exception as ex:
        print(f"  {name}: ERROR {ex}")

# Test if trained model is the issue
print("\nTesting trained RF model:")
for name, *args in tests:
    try:
        result = _try_trained_model(*args)
        if result is None:
            print(f"  {name}: no trained model (using HCM fallback)")
        else:
            print(f"  {name}: RF={result[0]}")
    except Exception as ex:
        print(f"  {name}: RF ERROR {type(ex).__name__}: {ex}")
