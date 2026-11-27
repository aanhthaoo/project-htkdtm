"""Mật khẩu và token (không cần cơ sở dữ liệu)."""

import time

import jwt
import pytest

from app.config import get_settings
from app.core import security


def test_mat_khau_bam_bcrypt_khong_luu_dang_tho():
    h = security.hash_password("Matkhau-Rat-Dai-123")
    assert h != "Matkhau-Rat-Dai-123"
    assert "Matkhau" not in h
    assert h.startswith("$2")  # bcrypt
    assert security.verify_password("Matkhau-Rat-Dai-123", h)
    assert not security.verify_password("sai-mat-khau", h)


def test_hai_lan_bam_cung_mat_khau_cho_chuoi_khac_nhau():
    assert security.hash_password("abcdefgh") != security.hash_password("abcdefgh")


def test_verify_khong_nem_loi_voi_hash_hong():
    assert security.verify_password("x", "khong-phai-bcrypt") is False


def test_token_chua_dung_thong_tin_va_giai_ma_duoc():
    token, ttl = security.create_token(42, "investor", ttl_minutes=5)
    payload = security.decode_token(token)
    assert payload["sub"] == "42" and payload["role"] == "investor"
    assert ttl == 300
    assert payload["exp"] - payload["iat"] == 300


def test_token_het_han_bi_tu_choi():
    token, _ = security.create_token(1, "admin", ttl_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_token(token)


def test_token_bi_sua_hoac_ky_sai_khoa_bi_tu_choi():
    token, _ = security.create_token(1, "investor")
    head, body, sig = token.split(".")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_token(f"{head}.{body}.{sig[:-2]}xx")
    forged = jwt.encode(
        {"sub": "1", "exp": time.time() + 600}, "khoa-khac-hoan-toan-khac-xyz-123456", "HS256"
    )
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_token(forged)


def test_token_khong_co_exp_bi_tu_choi():
    no_exp = jwt.encode({"sub": "1"}, get_settings().jwt_secret, "HS256")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_token(no_exp)
