"""Kiểm thử công cụ kiểm tra nhãn cảm xúc của người (không cần cơ sở dữ liệu)."""

import pandas as pd
import pytest

from ml import sentiment_check as sc


def frame(labels):
    return pd.DataFrame(
        {"sample_id": [f"S{i:05d}" for i in range(len(labels))], "label_human": labels}
    )


def test_nhan_hop_le_duoc_chuan_hoa_va_chap_nhan_ten_tieng_viet():
    df, errors = sc.validate(frame(["positive", " NEGATIVE ", "Trung lập", "tích cực"]))
    assert errors == []
    assert df["label_human"].tolist() == ["positive", "negative", "neutral", "positive"]


def test_bao_dong_thieu_nhan_va_nhan_sai_theo_so_dong_trong_tep():
    df, errors = sc.validate(frame(["positive", "", "tốt", "neutral"]))
    assert len(errors) == 2
    assert (
        "Dòng 3" in errors[0] and "chưa điền" in errors[0]
    )  # phần tử thứ hai nằm ở dòng 3 của tệp (dòng 1 là tiêu đề)
    assert "Dòng 4" in errors[1] and "không hợp lệ" in errors[1]


def test_so_sanh_hai_luot_gan_tinh_dung_accuracy_kappa_va_ma_tran_nham():
    human = pd.Series(["positive", "positive", "negative", "neutral", "neutral", "negative"])
    other = pd.Series(["positive", "neutral", "negative", "neutral", "neutral", "negative"])
    m = sc.compare(human, other)
    assert m["n"] == 6 and m["accuracy"] == pytest.approx(5 / 6)
    assert m["confusion_matrix_rows_human_cols_other"] == [[2, 0, 0], [0, 2, 0], [0, 1, 1]]
    assert 0.7 < m["cohen_kappa"] < 0.8
    same = sc.compare(human, human)
    assert same["accuracy"] == 1.0 and same["cohen_kappa"] == pytest.approx(1.0)
