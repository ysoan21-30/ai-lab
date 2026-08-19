import sys
from pathlib import Path

# Make `src` importable regardless of where pytest is invoked from.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
