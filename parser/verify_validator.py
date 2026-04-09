import sys
import os

# Ensure we can import from the current project structure
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.append(_BASE_DIR)

from parser.validator import validate_joi
from loader import SERVICE_DATA

# 1. Setup Mock Data (Same as test.py)
CUSTOM_DEVICES = {
    'tc0_Speaker': {'category': ['Switch', 'Speaker'], 'tags': ['Bedroom']},
    'tc0_Light': {'category': ['Switch', 'Light'], 'tags': ['Office', 'LivingRoom']},
}

# 2. Extract Service Map (Similar to run_local.py)
def _build_service_category_map(service_data):
    mapping = {}
    for cat, services in service_data.items():
        for svc in services:
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
    
    errors = validate_joi(test['script'], CUSTOM_DEVICES, SERVICE_MAP, debug=False)
    
    if errors:
        for err in errors:
            print(f"  ❌ {err}")
    else:
        print("  ✅ No errors found")
    print()

print("=== Verification Complete ===")
