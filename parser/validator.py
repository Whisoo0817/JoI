import os
import re
import sys
import json

# Add 'generated' folder to path for ANTLR imports
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_GENERATED_DIR = os.path.join(_CURRENT_DIR, 'generated')
if _GENERATED_DIR not in sys.path:
    sys.path.append(_GENERATED_DIR)

try:
    from antlr4 import InputStream, CommonTokenStream, error
    from JOILangLexer import JOILangLexer
    from JOILangParser import JOILangParser
except ImportError:
    # Fallback for environments without antlr4 or generated files
    InputStream = None
    JOILangLexer = None
    JOILangParser = None

def validate_joi(script, connected_devices, service_map, debug=False):
    """
    Validates JOI script for grammar, tag existence, and service validity.
    Returns a list of error messages. empty list means success.
    """
    errors = []
    if not script:
        return ["Script is empty"]

    # 1. Grammar Check
    if InputStream and JOILangLexer and JOILangParser:
        try:
            class ParserErrorListener(error.ErrorListener.ErrorListener):
                def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
                    errors.append(f"Grammar Error: Line {line}:{column} - {msg}")

            input_stream = InputStream(script)
            lexer = JOILangLexer(input_stream)
            stream = CommonTokenStream(lexer)
            parser = JOILangParser(stream)
            parser.removeErrorListeners()
            parser.addErrorListener(ParserErrorListener())
            parser.scenario()
        except Exception as e:
            if not errors: errors.append(f"Parser Invocation Error: {e}")
    elif debug:
        print("⚠️ ANTLR4 parser not available. Skipping grammar check.")

    # 2. Tag & Service Check
    # Collect all valid tags from connected_devices
    valid_tags = set()
    devices_dict = {}
    if isinstance(connected_devices, str):
        try:
            import ast
            devices_dict = ast.literal_eval(connected_devices)
        except:
            pass
    elif isinstance(connected_devices, dict):
        devices_dict = connected_devices

    for info in devices_dict.values():
        valid_tags.update(info.get("tags", []))
        valid_tags.update(info.get("category", []))

    # Extract Tags (#Tag)
    used_tags = re.findall(r'#(\w+)', script)
    for tag in used_tags:
        if tag not in valid_tags:
            errors.append(f"Tag Error: '#{tag}' not found in connected devices.")

    # Extract Service Calls (.Method())
    calls = re.findall(r'\.([A-Z]\w+)\(', script)
    for method in calls:
        if method not in service_map:
            errors.append(f"Service Error: Method '{method}' not found in SERVICE_DATA.")

    if debug:
        if errors:
            print(f"❌ Script Validation Failed:\n" + "\n".join(f"  - {e}" for e in errors))
        else:
            print("✅ Script Validation Passed")
            
    return errors
