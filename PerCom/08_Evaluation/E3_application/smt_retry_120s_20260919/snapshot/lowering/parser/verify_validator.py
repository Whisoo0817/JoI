import sys
import os

# Ensure the repository root is importable when this file is run directly.
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT_DIR not in sys.path:
    sys.path.append(_ROOT_DIR)

from lowering.parser.validator import validate_joi
from timeline_ir.loader import SERVICE_DATA

# 1. Setup Mock Data (Same as test.py)
CUSTOM_DEVICES = {
    'tc0_Speaker': {'category': ['Switch', 'Speaker'], 'tags': ['Bedroom']},
    'tc0_Light': {'category': ['Switch', 'Light'], 'tags': ['Office', 'LivingRoom']},
}

# 2. Extract Service Map (similar to lowering/run_local_ir.py)
def _build_service_category_map(service_data):
    mapping = {}
    for cat, item in service_data.items():
        for entry in item.get("values", []) + item.get("functions", []):
            svc = entry["id"]
            if svc not in mapping:
                mapping[svc] = cat
    return mapping

SERVICE_MAP = _build_service_category_map(SERVICE_DATA)

# 3. Test Cases
TEST_CASES = [
    {
        "name": "Case 1: Grammar Error (Syntax Error)",
        "script": "if (any(#Light) On() { delay(1 SEC) }",  # Missing parenthesis and dot
    },
    {
        "name": "Case 2: Tag Error (Unknown Tag)",
        "script": "all(#UnknownLocation #Light).On()",      # #UnknownLocation doesn't exist
    },
    {
        "name": "Case 3: Service Error (Non-existent Method)",
        "script": "(#Light).Dance()",                       # .Dance() is not a valid Light service
    }
]

print("=== Starting Validator Verification ===\n")

for test in TEST_CASES:
    print(f"--- {test['name']} ---")
    print(f"Script: {test['script']}")
    
    errors = validate_joi(test['script'], CUSTOM_DEVICES, SERVICE_MAP)
    
    if errors:
        for err in errors:
            print(f"  ❌ {err}")
    else:
        print("  ✅ No errors found")
    print()

print("=== Verification Complete ===")
