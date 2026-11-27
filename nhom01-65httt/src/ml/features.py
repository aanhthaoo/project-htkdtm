"""N8c: đặc trưng theo ngành ICB cấp 2 x tuần cho mô hình dự báo dòng tiền.

QUY TẮC CHỐNG RÒ RỈ: đặc trưng ở tuần t chỉ dùng dữ liệu đến hết tuần t (kể cả các đại lượng chuẩn hóa dạng cuốn chiếu).
Nhãn của dòng tuần t là dòng tiền tuần t+1. Có test tự động (tests/unit/test_ml.py) đổi toàn bộ dữ liệu sau tuần t
và kiểm tra đặc trưng tại t không đổi.

Dữ liệu vào (DataFrame, `week` là ngày thứ Hai của tuần):
  flow    : week, sector, net, buy, sell, prop_net   (khối ngoại; tự doanh có từ 17/05/2022, trước đó NaN)
  price   : week, sector, ret, value                 (lợi suất tuần của ngành có trọng số giá trị, tổng giá trị giao dịch)
  market  : week, foreign_net, vnindex_ret, vnindex_vol
  macro   : week + một cột mỗi chỉ số (giá trị cuối tuần)
"""

import numpy as np
import pandas as pd

SCALE_WINDOW = 26  # tuần dùng để chuẩn hóa độ lớn dòng tiền của từng ngành
SCALE_MIN = 8

FLOW_FEATURES = [
    "net_s0", "net_s1", "net_s2", "net_s3", "net_ma4", "net_ma8", "ratio0", "ratio1",
    "streak", "turnover_chg", "sector_bias",
]  # fmt: skip
PRICE_FEATURES = ["ret0", "ret1", "ret4", "value_chg"]
MARKET_FEATURES = ["mkt_net_s0", "mkt_net_s1", "vnindex_ret0", "vnindex_ret1", "vnindex_vol0"]
PROP_FEATURES = ["prop_net_s0"]
CROSS_FEATURES = [
    "net_rank0",
    "net_rel0",
    "ret_rank0",
    "ret_rel0",
    "breadth0",
]  # so sánh chéo giữa các ngành cùng tuần
SENTIMENT_FEATURES = ["sent_mean0", "sent_mean4", "sent_n0"]
ROOM_FEATURES = ["room_fill", "room_fill_chg1", "room_fill_chg4", "room_tight"]
CALENDAR_FEATURES = [
    "cal_month", "cal_week_of_month", "cal_expiry_next", "cal_vn30_review_next",
    "cal_quarter_rebalance_next", "cal_earnings_next", "cal_month_end_next", "cal_tet_dist_next",
]  # fmt: skip

# Mùng 1 Tết Nguyên đán (lịch cố định, biết trước nhiều năm nên dùng làm đặc trưng không gây rò rỉ)
TET_DATES = [
    "2020-01-25", "2021-02-12", "2022-02-01", "2023-01-22", "2024-02-10", "2025-01-29",
    "2026-02-17", "2027-02-06", "2028-01-26",
]  # fmt: skip


def sentiment_features(weekly: pd.DataFrame) -> pd.DataFrame:
    """Đặc trưng cảm xúc ngành x tuần từ bảng (week, sector, sent_mean0, sent_n0).

    sent_mean4 = trung bình 4 tuần gần nhất (gồm tuần t, chỉ dữ liệu quá khứ). Bài đăng sau 15h đã được gán vào phiên kế tiếp
    ở bước làm sạch tin nên không lọt vào tuần của phiên đã đóng. Tuần không có tin: sent_mean0 = NaN, sent_n0 = 0.
    """
    mean = weekly.pivot(index="week", columns="sector", values="sent_mean0").sort_index()
    count = weekly.pivot(index="week", columns="sector", values="sent_n0").sort_index().fillna(0)
    mean4 = mean.rolling(4, min_periods=1).mean()
    out = pd.concat(
        {
            "sent_mean0": mean.stack(dropna=False),
            "sent_mean4": mean4.stack(dropna=False),
            "sent_n0": count.stack(dropna=False),
        },
        axis=1,
    )
    out.index.names = ["week", "sector"]
    return out.reset_index()


def _third_weekday(year: int, month: int, weekday: int) -> pd.Timestamp:
    """Ngày thứ `weekday` (0 = thứ Hai) thứ ba của tháng."""
    first = pd.Timestamp(year=year, month=month, day=1)
    offset = (weekday - first.weekday()) % 7
    return first + pd.Timedelta(days=offset + 14)


def calendar_features(weeks) -> pd.DataFrame:
    """Đặc trưng lịch của TUẦN MỤC TIÊU (tuần t+1) cho mỗi tuần t (`week` là thứ Hai).

    Chỉ phụ thuộc ngày tháng nên biết trước hoàn toàn, không có rò rỉ. Quy tắc (xấp xỉ, theo thông lệ thị trường):
      cal_expiry_next            tuần t+1 chứa thứ Năm thứ ba của tháng (đáo hạn phái sinh VN30)
      cal_vn30_review_next       tuần t+1 chứa thứ Sáu thứ ba của tháng 1/4/7/10 (kỳ xem xét rổ VN30)
      cal_quarter_rebalance_next tuần t+1 chứa thứ Sáu thứ ba của tháng 3/6/9/12 (kỳ cơ cấu quỹ ETF, FTSE)
      cal_earnings_next          thứ Hai của tuần t+1 rơi vào cửa sổ hạn nộp báo cáo quý (10/1-5/2, 10/4-5/5, 10/7-5/8, 10/10-5/11)
      cal_month_end_next         tuần t+1 chứa ngày làm việc cuối cùng của tháng
      cal_tet_dist_next          số tuần từ tuần t+1 tới Tết (âm: sau Tết), cắt ở [-4, 4]; ngoài khoảng đó là 9
    """
    tets = [pd.Timestamp(d) for d in TET_DATES]
    rows = []
    for w in pd.to_datetime(sorted(set(weeks))):
        nxt = w + pd.Timedelta(days=7)
        end = nxt + pd.Timedelta(days=4)  # thứ Sáu của tuần mục tiêu
        thu3 = _third_weekday(nxt.year, nxt.month, 3)
        fri3 = _third_weekday(nxt.year, nxt.month, 4)
        month_last = (nxt + pd.offsets.BMonthEnd(0)).normalize()
        earnings = any(
            pd.Timestamp(year=nxt.year, month=m1, day=d1)
            <= nxt
            <= pd.Timestamp(year=nxt.year, month=m2, day=d2)
            for m1, d1, m2, d2 in ((1, 10, 2, 5), (4, 10, 5, 5), (7, 10, 8, 5), (10, 10, 11, 5))
        )
        tet_dist = min(((t - nxt).days // 7 for t in tets), key=abs)
        rows.append(
            {
                "week": w,
                "cal_month": nxt.month,
                "cal_week_of_month": (nxt.day - 1) // 7 + 1,
                "cal_expiry_next": int(nxt <= thu3 <= end),
                "cal_vn30_review_next": int(nxt.month in (1, 4, 7, 10) and nxt <= fri3 <= end),
                "cal_quarter_rebalance_next": int(
                    nxt.month in (3, 6, 9, 12) and nxt <= fri3 <= end
                ),
                "cal_earnings_next": int(earnings),
                "cal_month_end_next": int(nxt <= month_last <= end),
                "cal_tet_dist_next": tet_dist if abs(tet_dist) <= 4 else 9,
            }
        )
    return pd.DataFrame(rows)


def macro_features(macro: pd.DataFrame) -> list[str]:
    return [c for c in macro.columns if c != "week"]


def _streak(net: pd.Series) -> pd.Series:
    """Số tuần liên tiếp cùng chiều tính đến tuần hiện tại (dương: mua ròng, âm: bán ròng), cắt ở ±8."""
    out, run = [], 0
    for value in np.sign(net.to_numpy()):
        if value == 0:
            run = 0
        elif run == 0 or np.sign(run) != value:
            run = int(value)
        else:
            run += int(value)
        out.append(max(-8, min(8, run)))
    return pd.Series(out, index=net.index)


def _per_sector(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("week").copy()
    net = g["net"]
    # độ lớn thường lệ của ngành: trung bình |net| 26 tuần gần nhất, gồm cả tuần hiện tại (không nhìn tương lai)
    scale = net.abs().rolling(SCALE_WINDOW, min_periods=SCALE_MIN).mean().replace(0, np.nan)
    s = net / scale
    g["scale"] = scale
    for lag in range(4):
        g[f"net_s{lag}"] = s.shift(lag)
    g["net_ma4"] = s.rolling(4, min_periods=4).mean()
    g["net_ma8"] = s.rolling(8, min_periods=8).mean()
    turnover = g["buy"] + g["sell"]
    ratio = (net / turnover.replace(0, np.nan)).fillna(0)
    g["ratio0"], g["ratio1"] = ratio, ratio.shift(1)
    g["streak"] = _streak(net)
    past_turnover = turnover.shift(1).rolling(4, min_periods=4).mean().replace(0, np.nan)
    g["turnover_chg"] = (turnover / past_turnover - 1).clip(-1, 3)
    g["sector_bias"] = (
        (net > 0).astype(float).expanding(min_periods=8).mean()
    )  # tỷ lệ tuần mua ròng từ trước tới nay
    # chỉ số cho tuần kế tiếp (nhãn)
    g["y_net"] = net.shift(-1)
    g["y_scaled"] = (net.shift(-1) / scale).clip(-5, 5)
    g["y_cls"] = np.where(g["y_net"].isna(), np.nan, (g["y_net"] > 0).astype(float))
    # lợi suất ngành tuần kế tiếp, chỉ dùng cho backtest (không phải đặc trưng); ưu tiên lợi suất có thể đầu tư nếu có
    g["y_ret"] = (g["ret_inv"] if "ret_inv" in g else g["ret"]).shift(-1)
    # giá và thanh khoản ngành
    ret = g["ret"]
    g["ret0"], g["ret1"] = ret, ret.shift(1)
    g["ret4"] = (1 + ret).rolling(4, min_periods=4).apply(np.prod, raw=True) - 1
    past_value = g["value"].shift(1).rolling(4, min_periods=4).mean().replace(0, np.nan)
    g["value_chg"] = (g["value"] / past_value - 1).clip(-1, 3)
    # tự doanh (NaN trước 17/05/2022)
    prop_scale = (
        g["prop_net"].abs().rolling(SCALE_WINDOW, min_periods=SCALE_MIN).mean().replace(0, np.nan)
    )
    g["prop_net_s0"] = g["prop_net"] / prop_scale
    return g


def build_features(
    flow: pd.DataFrame,
    price: pd.DataFrame,
    market: pd.DataFrame,
    macro: pd.DataFrame,
    sentiment: pd.DataFrame | None = None,
    room: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Bảng đặc trưng: mỗi dòng một (week, sector); cột nhãn y_net, y_scaled, y_cls (tuần kế tiếp, NaN ở tuần cuối)."""
    weeks = sorted(set(flow["week"]))
    sectors = sorted(set(flow["sector"]))
    grid = pd.MultiIndex.from_product([weeks, sectors], names=["week", "sector"]).to_frame(
        index=False
    )
    df = grid.merge(flow, on=["week", "sector"], how="left").merge(
        price, on=["week", "sector"], how="left"
    )
    for col in ("net", "buy", "sell"):
        df[col] = df[col].fillna(0.0)
    df["ret"] = df["ret"].fillna(0.0)
    df["value"] = df["value"].fillna(0.0)
    df = pd.concat([_per_sector(g) for _, g in df.groupby("sector")], ignore_index=True)

    m = market.sort_values("week").copy()
    mscale = (
        m["foreign_net"]
        .abs()
        .rolling(SCALE_WINDOW, min_periods=SCALE_MIN)
        .mean()
        .replace(0, np.nan)
    )
    m["mkt_net_s0"] = m["foreign_net"] / mscale
    m["mkt_net_s1"] = m["mkt_net_s0"].shift(1)
    m["vnindex_ret0"] = m["vnindex_ret"]
    m["vnindex_ret1"] = m["vnindex_ret"].shift(1)
    m["vnindex_vol0"] = m["vnindex_vol"]
    df = df.merge(m[["week", *MARKET_FEATURES]], on="week", how="left")

    mac = macro.sort_values("week").copy()
    for code in macro_features(macro):
        mac[f"macro_{code}_chg0"] = mac[code].pct_change(1)
        mac[f"macro_{code}_chg4"] = mac[code].pct_change(4)
    keep = ["week", *[c for c in mac.columns if c.startswith("macro_")]]
    df = df.merge(mac[keep], on="week", how="left")

    # So sánh chéo giữa các ngành trong CÙNG tuần t (chỉ dùng dữ liệu tuần t): xếp hạng, chênh lệch so với trung bình, độ rộng
    by_week = df.groupby("week")
    df["net_rank0"] = by_week["net_s0"].rank(pct=True)
    df["net_rel0"] = df["net_s0"] - by_week["net_s0"].transform("mean")
    df["ret_rank0"] = by_week["ret0"].rank(pct=True)
    df["ret_rel0"] = df["ret0"] - by_week["ret0"].transform("mean")
    df["breadth0"] = by_week["net"].transform(lambda x: (x > 0).mean())

    df = df.merge(calendar_features(weeks), on="week", how="left")

    if room is not None:
        # room ngoại (tỷ lệ đã dùng, 0..1) trung bình có trọng số giá trị giao dịch trong tuần t; chỉ dữ liệu đến hết tuần t
        df = df.merge(room, on=["week", "sector"], how="left").sort_values(["sector", "week"])
        by_sector = df.groupby("sector")["room_fill"]
        df["room_fill_chg1"] = df["room_fill"] - by_sector.shift(1)
        df["room_fill_chg4"] = df["room_fill"] - by_sector.shift(4)

    if sentiment is not None:
        df = df.merge(sentiment, on=["week", "sector"], how="left")
    return df.sort_values(["sector", "week"]).reset_index(drop=True)


def feature_groups(df: pd.DataFrame) -> dict[str, list[str]]:
    macro_cols = [c for c in df.columns if c.startswith("macro_")]
    groups = {
        "flow": FLOW_FEATURES,
        "price": PRICE_FEATURES,
        "market": MARKET_FEATURES,
        "macro": macro_cols,
        "prop": PROP_FEATURES,
        "cross": CROSS_FEATURES,
        "calendar": CALENDAR_FEATURES,
    }
    if all(c in df.columns for c in ROOM_FEATURES):
        groups["room"] = ROOM_FEATURES
    if all(c in df.columns for c in SENTIMENT_FEATURES):
        groups["sentiment"] = SENTIMENT_FEATURES
    return groups


def complete_weeks(
    all_weeks: list[pd.Timestamp], latest_trade_date: pd.Timestamp
) -> list[pd.Timestamp]:
    """Tuần đã đủ: đã tới thứ Sáu của tuần đó, hoặc tuần kế tiếp đã có giao dịch. Tuần đang chạy dở bị loại.

    Nhờ đó dự báo cho tuần kế tiếp có thể lập vào chiều thứ Sáu (sau phiên) hoặc cuối tuần, trước khi tuần đó bắt đầu.
    """
    return [w for w in all_weeks if latest_trade_date >= w + pd.Timedelta(days=4)]
