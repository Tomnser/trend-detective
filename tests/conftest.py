import sys
from pathlib import Path

# Make repo-root modules (data_access, analysis, ...) importable from tests/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
