import Alert from "../../components/Alert.jsx";
import Button from "../../components/Button.jsx";
import Card from "../../components/Card.jsx";
import PageHeader from "../../components/PageHeader.jsx";
import Spinner from "../../components/Spinner.jsx";
import useApi from "../../components/useApi.js";

const dailyCodes = "USDVND,DXY,SP500,WTI,BRENT,GOLD,US10Y";

function formatNumber(value) {
  return value == null ? "—" : value.toLocaleString("vi-VN", { maximumFractionDigits: 4 });
}

export default function MacroPage() {
  const { data, loading, error, reload } = useApi("/api/macro/series", {
    params: { codes: dailyCodes, frequency: "daily" },
  });
  return (
    <div className="space-y-4">
      <PageHeader title="Vĩ mô" subtitle="Các chỉ số vĩ mô và quốc tế theo ngày" />
      {loading && <Spinner />}
      {error && (
        <Alert kind="error">
          Không tải được dữ liệu vĩ mô. <Button variant="secondary" onClick={reload}>Thử lại</Button>
        </Alert>
      )}
      {!loading && data && (
        data.series.length === 0 ? <Alert>Chưa có dữ liệu chỉ số theo ngày.</Alert> :
        data.series.map((series) => (
          <Card key={series.code} title={`${series.name_vi} (${series.code})`}>
            {series.points.length === 0 ? <p>Chưa có dữ liệu.</p> : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <caption className="mb-2 text-left text-slate-500">
                    {series.unit ? `Đơn vị: ${series.unit}. ` : ""}Thay đổi so với kỳ trước tính bằng %.
                  </caption>
                  <thead className="bg-slate-100 text-slate-600">
                    <tr>
                      <th scope="col" className="px-3 py-2 text-left">Ngày</th>
                      <th scope="col" className="px-3 py-2 text-right">Giá trị</th>
                      <th scope="col" className="px-3 py-2 text-right">Thay đổi (%)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {series.points.slice().reverse().map((point) => (
                      <tr key={point.date} className="border-t border-slate-100">
                        <td className="px-3 py-2"><time dateTime={point.date}>{point.date}</time></td>
                        <td className="px-3 py-2 text-right tabular-nums">{formatNumber(point.value)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{formatNumber(point.pct_change_prev)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        ))
      )}
    </div>
  );
}
