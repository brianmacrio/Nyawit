import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

# Tes tidak boleh bergantung pada internet: peta kawasan online diuji dengan respons tiruan.
os.environ.setdefault("PK_KAWASAN_SOURCE", "lokal")
