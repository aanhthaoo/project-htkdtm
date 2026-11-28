import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext.jsx";
import Alert from "../../components/Alert.jsx";
import Button from "../../components/Button.jsx";
import Card from "../../components/Card.jsx";
import PageHeader from "../../components/PageHeader.jsx";
import Spinner from "../../components/Spinner.jsx";
import useApi from "../../components/useApi.js";

const sentimentText = {
  positive: "Tích cực",
  neutral: "Trung tính",
  negative: "Tiêu cực",
};

// Danh mục ICB cấp 2 từ dbt_dw/seeds/icb.csv. Giữ mã dạng chuỗi để bảo toàn số 0 đầu.
const sectors = [
  ["0500", "Dầu khí"], ["1300", "Hóa chất"], ["1700", "Tài nguyên cơ bản"],
  ["2300", "Xây dựng và vật liệu"], ["2700", "Hàng và dịch vụ công nghiệp"],
  ["3300", "Ô tô và phụ tùng"], ["3500", "Thực phẩm và đồ uống"], ["3700", "Hàng cá nhân và gia dụng"],
  ["4500", "Y tế"], ["5300", "Bán lẻ"], ["5500", "Truyền thông"], ["5700", "Du lịch và giải trí"],
  ["6500", "Viễn thông"], ["7500", "Điện, nước và khí đốt"], ["8300", "Ngân hàng"],
  ["8500", "Bảo hiểm"], ["8600", "Bất động sản"], ["8700", "Dịch vụ tài chính"], ["9500", "Công nghệ thông tin"],
];

// TRANG MẪU (TV5): tin tức. Khách chỉ thấy 5 tin mới nhất, nhà đầu tư thấy đầy đủ (backend quyết định).
export default function NewsPage() {
  const { user } = useAuth();
  const [symbol, setSymbol] = useState("");
  const [draft, setDraft] = useState("");
  const [sector, setSector] = useState("");
  const [draftSector, setDraftSector] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = user ? 20 : 5;
  const news = useApi("/api/news", {
    params: { page: user ? page : 1, page_size: pageSize, symbol, sector },
  });
  const pageCount = Math.ceil((news.data?.total ?? 0) / pageSize);

  function filterBy(code, sectorCode) {
    setDraft(code);
    setSymbol(code);
    setSector(sectorCode);
    setDraftSector(sectorCode);
    setPage(1);
  }
  function applyFilter(event) {
    event.preventDefault();
    filterBy(draft.trim().toUpperCase(), draftSector);
  }
  return (
    <div className="space-y-4">
      <PageHeader title="Tin tức liên quan chứng khoán" subtitle="Tiêu đề và liên kết đến bài gốc" />
      {!user && (
        <Alert kind="info">
          Khách chỉ xem được 5 tin mới nhất.{" "}
          <Link to="/login" className="underline">
            Đăng nhập
          </Link>{" "}
          để xem đầy đủ.
        </Alert>
      )}
      <form onSubmit={applyFilter} className="flex flex-wrap items-end gap-2">
        <label className="grid gap-1 text-sm">
          Mã cổ phiếu
          <input className="rounded-md border border-slate-300 px-3 py-2" placeholder="VD: FPT"
            value={draft} onChange={(event) => setDraft(event.target.value)} />
        </label>
        <label className="grid gap-1 text-sm">
          Ngành
          <select className="rounded-md border border-slate-300 px-3 py-2"
            value={draftSector} onChange={(event) => setDraftSector(event.target.value)}>
            <option value="">Tất cả ngành</option>
            {sectors.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
          </select>
        </label>
        <Button type="submit">Lọc tin</Button>
        {(symbol || sector) && (
          <Button type="button" variant="secondary" onClick={() => filterBy("", "")}>
            Xóa bộ lọc
          </Button>
        )}
      </form>
      {news.loading && <Spinner />}
      {news.error && <Alert kind="error">Không tải được tin tức. <button className="underline" onClick={news.reload}>Thử lại</button></Alert>}
      {!news.loading && news.data && (
        <Card>
          {news.data.items.length === 0 && (
            <p>{symbol || sector ? "Không tìm thấy tin phù hợp với bộ lọc." : "Chưa có tin tức."}</p>
          )}
          <ul className="divide-y divide-slate-100">
            {news.data.items.map((n) => (
              <li key={n.url} className="py-2 text-sm">
                <a href={n.url} target="_blank" rel="noreferrer" className="font-medium text-brand-700 hover:underline">
                  {n.title}
                </a>
                <span className="ml-2 text-slate-500">
                  {n.source} · {n.session_date}
                </span>
                <span className="ml-2 text-slate-600">
                  Cảm xúc: {sentimentText[n.sentiment_label] ?? "Chưa đánh giá"}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-slate-500">Tổng cộng {news.data.total.toLocaleString("vi-VN")} bài.</p>
          {user && (pageCount > 1 || page > 1) && (
            <nav aria-label="Phân trang tin tức" className="mt-3 flex items-center gap-3 text-sm">
              <Button variant="secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>
                Trang trước
              </Button>
              <span>Trang {page}</span>
              <Button variant="secondary" disabled={page >= pageCount} onClick={() => setPage(page + 1)}>
                Trang sau
              </Button>
            </nav>
          )}
        </Card>
      )}
    </div>
  );
}
