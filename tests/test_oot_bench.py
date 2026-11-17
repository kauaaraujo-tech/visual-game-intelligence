"""Load OoT companion tests in the repository's regular CI test discovery."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "oot_bench" / "tests"))
from test_oot import OotTest
