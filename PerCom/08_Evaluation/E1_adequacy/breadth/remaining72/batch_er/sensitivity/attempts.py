import runpy
from pathlib import Path
ATTEMPTS=runpy.run_path(str(Path(__file__).resolve().parents[1]/'attempts.py'))['ATTEMPTS']
