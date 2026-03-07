"""conftest.py — make the scripts/ directory importable by name in tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
