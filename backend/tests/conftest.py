import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

# Tes tidak boleh bergantung pada internet: peta kawasan online diuji dengan respons tiruan.
os.environ.setdefault("PK_KAWASAN_SOURCE", "lokal")
os.environ.setdefault("PK_KAWASAN_GFW", "0")  # cadangan GFW diuji dengan server tile tiruan
os.environ.setdefault("PK_PETA_GFW", "0")  # lapisan peta nyata: tile buatan + tabel bawaan kebun contoh
