"""Đặc tả dataset và metric dùng chung cho Superset (nguồn duy nhất; provision.py nạp vào Superset,
docs/superset_dataset_metric.md mô tả cho TV3, tests/smoke/test_superset.py đối chiếu với SQL gốc).

Mọi dataset là bảng/view trong schema `dw` (do dbt dựng ở src/dbt_dw/models/superset/), Superset đọc bằng tài khoản bi_readonly.
"""

from dataclasses import dataclass, field

DATABASE_NAME = "BI_DW"
SCHEMA = "dw"


@dataclass(frozen=True)
class Metric:
    name: str
    expression: str
    verbose: str
    description: str = ""
    d3format: str | None = None


@dataclass(frozen=True)
class Dataset:
    table: str
    description: str
    main_dttm_col: str | None
    metrics: list[Metric] = field(default_factory=list)
    # biểu đồ thử: (tên, loại biểu đồ, tham số riêng)
    test_chart: tuple[str, str, dict] | None = None


BN = ",.1f"  # tỷ đồng, 1 số lẻ
PCT = ",.2f"

DATASETS: list[Dataset] = [
    Dataset(
        table="ds_flow_daily",
        description=(
            "Dòng tiền theo ngày x ngành ICB cấp 2 x sàn x nhóm vốn hóa x nhóm nhà đầu tư (chỉ cổ phiếu). "
            "Dùng cho các bộ lọc chung: thời gian, sàn, ngành, nhóm nhà đầu tư, nhóm vốn hóa."
        ),
        main_dttm_col="trade_date",
        metrics=[
            Metric(
                "net_value_bn", "SUM(net_value_bn)", "Giá trị ròng (tỷ đồng)", "Mua trừ bán", BN
            ),
            Metric("buy_value_bn", "SUM(buy_value_bn)", "Giá trị mua (tỷ đồng)", "", BN),
            Metric("sell_value_bn", "SUM(sell_value_bn)", "Giá trị bán (tỷ đồng)", "", BN),
            Metric(
                "turnover_bn",
                "SUM(buy_value_bn) + SUM(sell_value_bn)",
                "Giá trị giao dịch mua + bán (tỷ đồng)",
                "",
                BN,
            ),
            Metric(
                "net_ratio_pct",
                "100.0 * SUM(net_value_bn) / NULLIF(SUM(buy_value_bn) + SUM(sell_value_bn), 0)",
                "Tỷ lệ mua ròng / giao dịch (%)",
                "Giá trị ròng chia tổng mua + bán",
                PCT,
            ),
            Metric(
                "n_trading_days",
                "COUNT(DISTINCT trade_date)",
                "Số phiên",
                "Số ngày có dòng tiền trong phạm vi lọc",
                ",d",
            ),
        ],
        test_chart=(
            "[Thử] Mua/bán ròng theo nhóm nhà đầu tư",
            "echarts_timeseries_line",
            {"metrics": ["net_value_bn"], "groupby": ["investor_type"], "time_grain_sqla": "P1W"},
        ),
    ),
    Dataset(
        table="ds_sector_flow_weekly",
        description=(
            "Dòng tiền ngành ICB cấp 2 x tuần x nhóm nhà đầu tư, kèm tỷ trọng giao dịch của ngành trong toàn thị trường. "
            "Nguồn của dashboard Luân chuyển ngành."
        ),
        main_dttm_col="week_start_date",
        metrics=[
            Metric("net_value_bn", "SUM(net_value_bn)", "Giá trị ròng (tỷ đồng)", "", BN),
            Metric(
                "turnover_bn", "SUM(turnover_bn)", "Giá trị giao dịch mua + bán (tỷ đồng)", "", BN
            ),
            Metric(
                "turnover_share_pct",
                "AVG(turnover_share_pct)",
                "Tỷ trọng dòng tiền ngành (%)",
                "Giao dịch của ngành / giao dịch toàn thị trường cùng tuần, cùng nhóm nhà đầu tư. "
                "Chỉ đúng khi lọc một nhóm nhà đầu tư và nhóm theo ngành x tuần.",
                PCT,
            ),
        ],
        test_chart=(
            "[Thử] Tỷ trọng dòng tiền ngành theo tuần",
            "echarts_area",
            {
                "metrics": ["turnover_share_pct"],
                "groupby": ["icb_l2_name_vi"],
                "time_grain_sqla": "P1W",
                "adhoc_filters_sql": "investor_type = 'FOREIGN'",
            },
        ),
    ),
    Dataset(
        table="ds_market_flow_series",
        description=(
            "Chuỗi mua/bán ròng toàn thị trường theo ngày x nhóm nhà đầu tư, có lũy kế, cuốn chiếu 20 phiên và VN-Index."
        ),
        main_dttm_col="trade_date",
        metrics=[
            Metric("net_value_bn", "SUM(net_value_bn)", "Giá trị ròng (tỷ đồng)", "", BN),
            Metric(
                "cum_net_value_bn",
                "MAX(cum_net_value_bn)",
                "Lũy kế ròng (tỷ đồng)",
                "Dùng khi nhóm theo ngày x nhóm NĐT",
                BN,
            ),
            Metric(
                "net_value_20d_bn",
                "MAX(net_value_20d_bn)",
                "Ròng cuốn chiếu 20 phiên (tỷ đồng)",
                "",
                BN,
            ),
            Metric("vnindex_close", "MAX(vnindex_close)", "VN-Index", "", PCT),
        ],
        test_chart=(
            "[Thử] Lũy kế mua/bán ròng",
            "echarts_timeseries_line",
            {
                "metrics": ["cum_net_value_bn"],
                "groupby": ["investor_type"],
                "time_grain_sqla": "P1D",
            },
        ),
    ),
    Dataset(
        table="ds_stock_flow_daily",
        description="Dòng tiền theo mã x ngày x nhóm nhà đầu tư. Dùng cho top mã gom/xả và drill xuống từng mã.",
        main_dttm_col="trade_date",
        metrics=[
            Metric("net_value_bn", "SUM(net_value_bn)", "Giá trị ròng (tỷ đồng)", "", BN),
            Metric("buy_value_bn", "SUM(buy_value_bn)", "Giá trị mua (tỷ đồng)", "", BN),
            Metric("sell_value_bn", "SUM(sell_value_bn)", "Giá trị bán (tỷ đồng)", "", BN),
            Metric("net_volume", "SUM(net_volume)", "Khối lượng ròng (cổ phiếu)", "", ",.0f"),
            Metric(
                "n_net_buy_days",
                "COUNT(DISTINCT CASE WHEN net_value_bn > 0 THEN trade_date END)",
                "Số phiên mua ròng",
                "",
                ",d",
            ),
        ],
        test_chart=(
            "[Thử] Top 10 mã khối ngoại mua ròng",
            "table",
            {
                "metrics": ["net_value_bn"],
                "groupby": ["symbol"],
                "adhoc_filters_sql": "investor_type = 'FOREIGN'",
                "row_limit": 10,
                "order_desc": True,
            },
        ),
    ),
    Dataset(
        table="ds_stock_daily",
        description="Giá và dòng tiền theo mã x ngày (khối ngoại, tự doanh, trong nước khác là các cột riêng). Chỉ ngày có giao dịch.",
        main_dttm_col="trade_date",
        metrics=[
            Metric(
                "close_price",
                "MAX(close_price)",
                "Giá đóng cửa (nghìn đồng)",
                "Dùng khi lọc một mã",
                ",.2f",
            ),
            Metric("total_value_bn", "SUM(total_value_bn)", "Giá trị giao dịch (tỷ đồng)", "", BN),
            Metric("foreign_net_bn", "SUM(foreign_net_bn)", "Khối ngoại ròng (tỷ đồng)", "", BN),
            Metric(
                "prop_net_bn",
                "SUM(prop_net_bn)",
                "Tự doanh ròng (tỷ đồng)",
                "Chỉ có từ 17/05/2022",
                BN,
            ),
            Metric(
                "other_net_bn",
                "SUM(other_net_bn)",
                "Trong nước khác ròng (tỷ đồng)",
                "Suy ra, xem docs/thiet_ke_kho.md",
                BN,
            ),
        ],
        test_chart=(
            "[Thử] Giá và khối ngoại ròng của một mã",
            "echarts_timeseries_line",
            {
                "metrics": ["close_price"],
                "groupby": [],
                "time_grain_sqla": "P1D",
                "adhoc_filters_sql": "symbol = 'VNM'",
            },
        ),
    ),
    Dataset(
        table="ds_macro_daily",
        description="Chỉ số vĩ mô và quốc tế theo ngày (USD/VND, DXY, S&P 500, dầu, vàng, lợi suất Mỹ 10 năm).",
        main_dttm_col="trade_date",
        metrics=[
            Metric("value", "MAX(value)", "Giá trị", "Dùng khi lọc một chỉ số", ",.2f"),
            Metric(
                "pct_change_prev", "AVG(pct_change_prev)", "Thay đổi so với kỳ trước (%)", "", PCT
            ),
        ],
        test_chart=(
            "[Thử] Chỉ số vĩ mô theo ngày",
            "echarts_timeseries_line",
            {
                "metrics": ["pct_change_prev"],
                "groupby": ["indicator_name"],
                "time_grain_sqla": "P1M",
            },
        ),
    ),
    Dataset(
        table="ds_news_article",
        description=(
            "Bài viết theo phiên giao dịch (đã loại bài trùng, bài chưa gán được phiên). "
            "Cột is_market_related cho biết bài có liên quan chứng khoán. Cảm xúc sẽ thêm ở giai đoạn ML."
        ),
        main_dttm_col="session_date",
        metrics=[
            Metric("n_articles", "COUNT(*)", "Số bài", "", ",d"),
            Metric(
                "n_market_articles",
                "SUM(CASE WHEN is_market_related THEN 1 ELSE 0 END)",
                "Số bài liên quan chứng khoán",
                "",
                ",d",
            ),
            Metric(
                "n_articles_with_stock",
                "SUM(CASE WHEN n_stock_mentions > 0 THEN 1 ELSE 0 END)",
                "Số bài nhắc ít nhất một mã",
                "",
                ",d",
            ),
        ],
        test_chart=(
            "[Thử] Số bài liên quan chứng khoán theo tháng",
            "echarts_timeseries_bar",
            {
                "metrics": ["n_market_articles"],
                "groupby": ["publisher"],
                "time_grain_sqla": "P1M",
            },
        ),
    ),
    Dataset(
        table="ds_news_stock_daily",
        description="Bài viết liên quan chứng khoán nhắc tới từng mã theo phiên giao dịch (mỗi bài x mã một dòng).",
        main_dttm_col="session_date",
        metrics=[
            Metric("n_articles", "COUNT(DISTINCT article_key)", "Số bài nhắc mã", "", ",d"),
            Metric(
                "n_title_articles",
                "COUNT(DISTINCT CASE WHEN in_title THEN article_key END)",
                "Số bài nhắc mã ở tiêu đề",
                "",
                ",d",
            ),
        ],
        test_chart=(
            "[Thử] Top mã được nhắc nhiều nhất",
            "table",
            {"metrics": ["n_articles"], "groupby": ["symbol"], "row_limit": 10},
        ),
    ),
    Dataset(
        table="ds_news_sentiment",
        description=(
            "Cảm xúc tin tức theo phiên giao dịch (mỗi bài x mã hoặc ngành được nhắc một dòng). "
            "Điểm = P(tích cực) - P(tiêu cực) trong [-1, 1]; cảm xúc ở mức bài. Mô hình TF-IDF + hồi quy logistic (xem docs/ml_ket_qua.md)."
        ),
        main_dttm_col="session_date",
        metrics=[
            Metric("n_articles", "COUNT(DISTINCT article_key)", "Số bài", "", ",d"),
            Metric(
                "avg_sentiment",
                "AVG(sentiment_score)",
                "Điểm cảm xúc trung bình",
                "Từ -1 (tiêu cực) đến 1 (tích cực)",
                ",.3f",
            ),
            Metric(
                "pct_positive",
                "100.0 * AVG(CASE WHEN sentiment_label = 'positive' THEN 1.0 ELSE 0.0 END)",
                "Tỷ lệ bài tích cực (%)",
                "",
                PCT,
            ),
            Metric(
                "pct_negative",
                "100.0 * AVG(CASE WHEN sentiment_label = 'negative' THEN 1.0 ELSE 0.0 END)",
                "Tỷ lệ bài tiêu cực (%)",
                "",
                PCT,
            ),
        ],
        test_chart=(
            "[Thử] Điểm cảm xúc ngành theo tuần",
            "echarts_timeseries_line",
            {
                "metrics": ["avg_sentiment"],
                "groupby": ["icb_l2_name_vi"],
                "time_grain_sqla": "P1M",
                "adhoc_filters_sql": "entity_type = 'SECTOR'",
            },
        ),
    ),
    Dataset(
        table="ds_prediction",
        description=(
            "Dự báo chiều dòng tiền khối ngoại của ngành ICB cấp 2 theo tuần kèm giá trị thực tế "
            "(dự báo ngoài mẫu walk-forward 2023-2026). Chỉ mô hình dự báo mới nhất; hit = 1 nếu dự báo đúng chiều."
        ),
        main_dttm_col="target_week_start",
        metrics=[
            Metric(
                "accuracy",
                "AVG(hit)",
                "Độ chính xác dự báo",
                "Tỷ lệ dự báo đúng chiều (0 đến 1)",
                ",.3f",
            ),
            Metric("n_predictions", "COUNT(*)", "Số dự báo", "", ",d"),
            Metric(
                "avg_prob_inflow",
                "AVG(prob_inflow)",
                "Xác suất dòng tiền vào trung bình",
                "",
                ",.3f",
            ),
            Metric(
                "predicted_net_bn", "SUM(predicted_net_value_bn)", "Ròng dự báo (tỷ đồng)", "", BN
            ),
            Metric("actual_net_bn", "SUM(actual_net_value_bn)", "Ròng thực tế (tỷ đồng)", "", BN),
        ],
        test_chart=(
            "[Thử] Độ chính xác dự báo theo quý",
            "echarts_timeseries_line",
            {"metrics": ["accuracy"], "groupby": [], "time_grain_sqla": "P3M"},
        ),
    ),
]

BY_TABLE = {d.table: d for d in DATASETS}


@dataclass(frozen=True)
class DashboardSpec:
    slug: str  # khớp với DASHBOARDS trong src/backend/app/routers/core_superset.py
    title: str
    chart_names: list[str]


# Dashboard mẫu để kiểm tra vòng nhúng + phân quyền (TV3 dựng 6 dashboard thật theo cùng cách này)
DASHBOARDS: list[DashboardSpec] = [
    DashboardSpec(
        "tong-quan-demo",
        "Tổng quan (mẫu, khách xem được)",
        ["[Thử] Mua/bán ròng theo nhóm nhà đầu tư", "[Thử] Lũy kế mua/bán ròng"],
    ),
    DashboardSpec(
        "luan-chuyen-nganh-demo",
        "Luân chuyển ngành (mẫu, nhà đầu tư)",
        ["[Thử] Tỷ trọng dòng tiền ngành theo tuần", "[Thử] Top 10 mã khối ngoại mua ròng"],
    ),
]
