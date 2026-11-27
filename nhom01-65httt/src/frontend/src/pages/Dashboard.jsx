import Card from "../components/Card.jsx";
import PageHeader from "../components/PageHeader.jsx";
import SupersetEmbed from "../components/SupersetEmbed.jsx";

// Dashboard đầy đủ (nhà đầu tư). TV3 thay bằng 6 dashboard thật bằng cách thêm khóa mới ở backend.
export default function Dashboard() {
  return (
    <div className="space-y-4">
      <PageHeader title="Luân chuyển ngành" subtitle="Tỷ trọng dòng tiền ngành và top mã khối ngoại mua ròng" />
      <Card>
        <SupersetEmbed dashboardKey="sector-rotation" height={680} />
      </Card>
    </div>
  );
}
