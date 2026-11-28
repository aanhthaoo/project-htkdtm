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

// TRANG MẪU (TV5): tin tức. Khách chỉ thấy 5 tin mới nhất, nhà đầu tư thấy đầy đủ (backend quyết định).
export default function NewsPage() {
  const { user } = useAuth();
  const [symbol, setSymbol] = useState("");
  const [draft, setDraft] = useState("");
  const news = useApi("/api/news", { params: { page_size: 20, symbol: symbol || undefined } });

  function applyFilter(event) {
    event.preventDefault();
    const code = draft.trim().toUpperCase();
    setDraft(code);
    setSymbol(code);
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
        <Button type="submit">Lọc tin</Button>
        {symbol && (
          <Button type="button" variant="secondary" onClick={() => { setDraft(""); setSymbol(""); }}>
            Xóa bộ lọc
          </Button>
        )}
      </form>
      {news.loading && <Spinner />}
      {news.error && <Alert kind="error">Không tải được tin tức. <button className="underline" onClick={news.reload}>Thử lại</button></Alert>}
      {!news.loading && news.data && (
        <Card>
          {news.data.items.length === 0 && (
            <p>{symbol ? `Không tìm thấy tin cho mã ${symbol}.` : "Chưa có tin tức."}</p>
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
        </Card>
      )}
    </div>
  );
}
