"""Xuất contract OpenAPI của backend ra docs/openapi.json (chạy từ thư mục nhom01-65httt/).

    python src/backend/export_openapi.py

Tệp này là contract chốt; test tests/smoke/test_api.py so nó với API thực tế để không ai đổi API mà quên báo nhóm.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.main import app  # noqa: E402

out = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"
out.write_text(
    json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(f"Đã ghi {out} ({len(app.openapi()['paths'])} đường dẫn)")
