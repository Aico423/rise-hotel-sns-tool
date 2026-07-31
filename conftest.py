import sys
from pathlib import Path

# rise_sns パッケージは admin/ 配下にある（Vercelのビルド範囲(Root Directory=admin)に
# 収める必要があるため、admin/api/index.py からも import できるようにここに置いている）。
ADMIN_DIR = Path(__file__).resolve().parent / "admin"
if str(ADMIN_DIR) not in sys.path:
    sys.path.insert(0, str(ADMIN_DIR))
