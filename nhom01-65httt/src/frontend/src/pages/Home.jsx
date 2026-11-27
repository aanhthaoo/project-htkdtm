import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import Alert from "../components/Alert.jsx";
import Card from "../components/Card.jsx";
import KpiCard from "../components/KpiCard.jsx";
import PageHeader from "../components/PageHeader.jsx";
import Spinner from "../components/Spinner.jsx";
import SupersetEmbed from "../components/SupersetEmbed.jsx";
import useApi from "../components/useApi.js";

const fmt = (v, digits = 1) =>
  v === null || v === undefined ? null : v.toLocaleString("vi-VN", { maximumFractionDigits: digits });

// Trang tổng quan (khách xem được): KPI phiên gần nhất + dashboard nhúng + tin nổi bật
export default function Home() {
  const { user } = useAuth();
  const overview = useApi("/api/market/overview");
  const highlights = useApi("/api/news/highlights");
  const o = overview.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tổng quan thị trường"
        subtitle={o ? `Phiên giao dịch ${o.date}` : "Phiên giao dịch gần nhất"}
      />
      {overview.loading && <Spinner />}
      {overview.error && <Alert kind="error">{overview.error.message}</Alert>}
      {o && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <KpiCard label="VN-Index" value={fmt(o.vnindex.close, 2)} delta={o.vnindex.change} />
          <KpiCard label="Giá trị giao dịch" value={fmt(o.total_value_bn, 0)} unit="tỷ" />
          <KpiCard label="Khối ngoại ròng" value={fmt(o.foreign.net_bn)} unit="tỷ" delta={o.foreign.net_bn} />
          <KpiCard label="Tự doanh ròng" value={fmt(o.prop.net_bn)} unit="tỷ" delta={o.prop.net_bn} />
        </div>
      )}

      <Card title="Dòng tiền theo nhóm nhà đầu tư">
        <SupersetEmbed dashboardKey="overview" height={520} />
      </Card>

      {!user && (
        <Alert kind="info" title="Xem đầy đủ hơn">
          <Link to="/register" className="font-medium underline">
            Đăng ký
          </Link>{" "}
          tài khoản nhà đầu tư để xem dashboard luân chuyển ngành, chi tiết mã và dự báo.
        </Alert>
      )}

      <Card title="Tin nổi bật">
        {highlights.loading && <Spinner />}
        <ul className="divide-y divide-slate-100">
          {highlights.data?.items.map((n) => (
            <li key={n.url} className="py-2 text-sm">
              <a href={n.url} target="_blank" rel="noreferrer" className="font-medium text-brand-700 hover:underline">
                {n.title}
              </a>
              <span className="ml-2 text-slate-500">
                {n.source} · {n.session_date}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
