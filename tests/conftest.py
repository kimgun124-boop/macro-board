import os
import sys
from pathlib import Path

os.environ["MACRO_MOCK"] = "1"          # 테스트는 인터넷 없이 가짜 데이터로
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
