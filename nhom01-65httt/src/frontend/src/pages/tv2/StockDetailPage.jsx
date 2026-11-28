// TV2 – Trang chi tiết mã cổ phiếu
// Dữ liệu từ API (đã thật): /api/stocks/:symbol, /prices, /flow, /api/news
// clusterLabels.js do việc 2.2 cung cấp
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Card from "../../components/Card.jsx";
import DataTable from "../../components/DataTable.jsx";
import PageHeader from "../../components/PageHeader.jsx";
import Spinner from "../../components/Spinner.jsx";
import Alert from "../../components/Alert.jsx";
import Disclaimer from "../../components/Disclaimer.jsx";
import useApi from "../../components/useApi.js";
import { getClusterLabel } from "./clusterLabels.js";
import { api } from "../../api/client.js";

// Định dạng số tiền tệ kiểu Việt (tỷ đồng)
function fmtBn(v) {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("vi-VN", { maximumFractionDigits: 1 }) + " tỷ";
}
// Định dạng giá (đồng)
function fmtVnd(v) {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("vi-VN") + " đ";
}
// Màu cho dòng tiền: xanh = dương, đỏ = âm
function flowColor(v) {
  if (v === null || v === undefined) return "";
  return v >= 0 ? "text-green-600 font-semibold" : "text-red-600 font-semibold";
}
// Nhãn cảm xúc tin tức
const sentimentLabel = { positive: "Tích cực 🟢", negative: "Tiêu cực 🔴", neutral: "Trung lập ⚪" };

export default function StockDetailPage() {
  const { symbol } = useParams();
  const navigate = useNavigate();
  const sym = symbol?.toUpperCase();

  // --- Chọn khoảng thời gian giá ---
  const [priceWindow, setPriceWindow] = useState(90); // ngày

  // --- Gọi API ---
  const detail = useApi(`/api/stocks/${sym}`);
  const prices = useApi(`/api/stocks/${sym}/prices`, { params: { days: priceWindow } });
  const flow   = useApi(`/api/stocks/${sym}/flow`,   { params: { days: 30 } });
  const news   = useApi("/api/news", { params: { symbol: sym, page_size: 10 } });

  // --- Xử lý thêm theo dõi ---
  const [watchMsg, setWatchMsg] = useState(null);
  async function addToWatchlist() {
    try {
      await api("/api/watchlist", {
        method: "POST",
        body: { entity_type: "STOCK", entity_code: sym },
      });
      setWatchMsg({ type: "success", text: `Đã thêm ${sym} vào danh sách theo dõi.` });
    } catch (e) {
      setWatchMsg({ type: "error", text: e.message ?? "Không thêm được." });
    }
  }

  // --- Trạng thái loading / lỗi ---
  if (detail.loading) return <div className="p-8"><Spinner /></div>;
  if (detail.error) {
    const is404 = detail.error?.status === 404;
    return (
      <div className="p-8">
        <Alert type="error">
          {is404 ? `Không tìm thấy mã "${sym}". Vui lòng kiểm tra lại.` : detail.error.message}
        </Alert>
        <button className="mt-4 text-blue-600 underline" onClick={() => navigate("/stocks")}>
          ← Quay lại danh sách
        </button>
      </div>
    );
  }

  const d = detail.data;
  const cluster = getClusterLabel(d.cluster_label);

  return (
    <div className="space-y-6 p-4">
      {/* Tiêu đề và nút theo dõi */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader
          title={`${d.symbol} – ${d.name_vi ?? "—"}`}
          subtitle={`${d.exchange ?? "—"} · ${d.icb_l2_name_vi ?? "—"} · ${d.icb_l4_name ?? "—"}`}
        />
        <button
          onClick={addToWatchlist}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
        >
          + Theo dõi
        </button>
      </div>
      {watchMsg && (
        <Alert type={watchMsg.type}>{watchMsg.text}</Alert>
      )}

      {/* Thông tin cơ bản */}
      <Card>
        <h2 className="mb-3 text-base font-semibold text-slate-700">Thông tin cơ bản</h2>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm md:grid-cols-3">
          <Info label="Mã" value={d.symbol} />
          <Info label="Sàn" value={d.exchange} />
          <Info label="Ngành ICB cấp 2" value={d.icb_l2_name_vi} />
          <Info label="Ngành ICB cấp 4" value={d.icb_l4_name} />
          <Info label="Nhóm vốn hóa" value={d.cap_group} />
          <Info label="VN30" value={d.is_vn30 ? "Có" : "Không"} />
          <Info label="Vốn hóa" value={d.market_cap_bn !== null ? fmtBn(d.market_cap_bn) : "—"} />
          <Info label="Ngày niêm yết" value={d.listing_date ?? "—"} />
        </div>

        {/* Nhãn cụm hành vi */}
        <div className="mt-4 rounded-md bg-slate-50 p-3">
          <p className="text-xs text-slate-500">Nhãn cụm hành vi dòng tiền</p>
          <p className="mt-1 font-medium text-slate-800">{cluster.label}</p>
          <p className="text-sm text-slate-600">{cluster.description}</p>
          <p className="mt-1 text-xs text-slate-400 italic">
            Nhãn gốc: {d.cluster_label ?? "chưa có"} · Cụm mô tả xu hướng, không phải tín hiệu giao dịch.
          </p>
        </div>
      </Card>

      {/* Lịch sử giá */}
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-700">Lịch sử giá (đóng cửa)</h2>
          <div className="flex gap-2">
            {[30, 90, 250].map((w) => (
              <button
                key={w}
                onClick={() => setPriceWindow(w)}
                className={`rounded px-3 py-1 text-xs ${
                  priceWindow === w ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600"
                }`}
              >
                {w} phiên
              </button>
            ))}
          </div>
        </div>
        {prices.loading && <Spinner />}
        {prices.data && (
          <DataTable
            rowKey="date"
            rows={prices.data.items.slice().reverse()}
            columns={[
              { key: "date", label: "Ngày" },
              { key: "close_vnd",  label: "Đóng cửa", render: fmtVnd },
              { key: "pct_change", label: "% thay đổi",
                render: (v) => (
                  <span className={v >= 0 ? "text-green-600" : "text-red-600"}>
                    {v !== null ? (v >= 0 ? "+" : "") + v.toFixed(2) + "%" : "—"}
                  </span>
                ),
              },
              { key: "total_value_bn", label: "GTGD (tỷ đ)", render: fmtBn },
            ]}
          />
        )}
      </Card>

      {/* Dòng tiền theo nhóm nhà đầu tư */}
      <Card>
        <h2 className="mb-3 text-base font-semibold text-slate-700">Dòng tiền 30 ngày gần nhất (tỷ đồng)</h2>
        {flow.loading && <Spinner />}
        {flow.data && (
          <DataTable
            rowKey="date"
            rows={flow.data.items.slice().reverse()}
            columns={[
              { key: "date", label: "Ngày" },
              {
                key: "foreign_net_bn", label: "Khối ngoại",
                render: (v) => <span className={flowColor(v)}>{fmtBn(v)}</span>,
              },
              {
                key: "proprietary_net_bn", label: "Tự doanh",
                render: (v) => <span className={flowColor(v)}>{fmtBn(v)}</span>,
              },
              {
                key: "retail_net_bn", label: "Trong nước khác",
                render: (v) => <span className={flowColor(v)}>{fmtBn(v)}</span>,
              },
            ]}
          />
        )}
        <p className="mt-2 text-xs text-slate-400">
          "Trong nước khác" = phần dẫn xuất; tự doanh theo mã chỉ có từ 17/05/2022.
        </p>
      </Card>

      {/* Tin tức liên quan */}
      <Card>
        <h2 className="mb-3 text-base font-semibold text-slate-700">10 tin tức liên quan gần nhất</h2>
        {news.loading && <Spinner />}
        {news.data && news.data.items.length === 0 && (
          <p className="text-sm text-slate-500">Chưa có tin tức.</p>
        )}
        {news.data && (
          <ul className="divide-y divide-slate-100">
            {news.data.items.map((item) => (
              <li key={item.id} className="py-2">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-blue-700 hover:underline"
                >
                  {item.title}
                </a>
                <div className="mt-0.5 flex flex-wrap gap-3 text-xs text-slate-400">
                  <span>{item.source}</span>
                  <span>{item.published_date}</span>
                  <span>{sentimentLabel[item.sentiment_label] ?? item.sentiment_label}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Disclaimer />
    </div>
  );
}

// Component nhỏ dùng nội bộ
function Info({ label, value }) {
  return (
    <div>
      <span className="text-slate-500">{label}: </span>
      <span className="text-slate-800">{value ?? "—"}</span>
    </div>
  );
}