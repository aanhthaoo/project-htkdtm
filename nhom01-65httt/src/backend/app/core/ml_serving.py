"""Phục vụ mô hình cho API `/ml/*`.

- Dự báo và cụm: đọc kết quả mô hình đã ghi trong `dw` (không cần thư viện học máy trong backend).
- Cảm xúc văn bản tự do: cần mô hình đã huấn luyện (`python -m ml.sentiment` lưu `data/ml_cache/sentiment_ensemble.joblib`) và các
  thư viện học máy (scikit-learn, sentence-transformers, torch). Image backend hiện KHÔNG có các thư viện này nên endpoint trả dữ liệu
  mẫu (`stub: true`); chạy backend trực tiếp trong môi trường đã cài `src/ml/requirements.txt` thì trả điểm thật.
"""

import logging
import sys
from pathlib import Path
from threading import Lock

log = logging.getLogger("app.ml_serving")

SRC = Path(__file__).resolve().parents[3]  # src/
ARTIFACT = SRC.parent / "data" / "ml_cache" / "sentiment_ensemble.joblib"
_lock = Lock()
_state: dict = {"tried": False, "model": None, "version": None, "sentiment": None}


def _load() -> bool:
    """Nạp mô hình cảm xúc một lần; trả True nếu dùng được."""
    with _lock:
        if _state["tried"]:
            return _state["model"] is not None
        _state["tried"] = True
        if not ARTIFACT.exists():
            log.info("Chưa có %s: /ml/sentiment trả dữ liệu mẫu", ARTIFACT)
            return False
        try:
            if str(SRC) not in sys.path:
                sys.path.insert(0, str(SRC))
            import joblib

            from ml import sentiment

            blob = joblib.load(ARTIFACT)
            _state.update(model=blob["model"], version=blob["version"], sentiment=sentiment)
            return True
        except (
            Exception
        ) as exc:  # thiếu thư viện học máy hoặc tệp hỏng: dùng dữ liệu mẫu, không làm sập API
            log.warning("Không nạp được mô hình cảm xúc (%s): trả dữ liệu mẫu", exc)
            return False


def sentiment_available() -> bool:
    return _load()


def score_texts(texts: list[str]) -> tuple[str, list[dict]]:
    """Chấm cảm xúc từng văn bản (coi toàn bộ là phần tiêu đề + nội dung). Trả (phiên bản mô hình, kết quả)."""
    import numpy as np

    sentiment, model = _state["sentiment"], _state["model"]
    clean = [sentiment.make_text(t, "") for t in texts]
    emb = sentiment.embed_texts([sentiment.emb_text(t, "") for t in texts])
    score, label, conf = sentiment.score_from_proba(
        model.predict_proba(clean, emb), list(model.classes_)
    )
    return _state["version"], [
        {
            "label": str(label[i]),
            "score": float(np.clip(score[i], -1, 1)),
            "confidence": float(conf[i]),
        }
        for i in range(len(texts))
    ]
