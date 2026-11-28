import { useState } from "react";
import Alert from "../../components/Alert.jsx";
import Button from "../../components/Button.jsx";
import Card from "../../components/Card.jsx";
import PageHeader from "../../components/PageHeader.jsx";
import Spinner from "../../components/Spinner.jsx";
import useApi from "../../components/useApi.js";
import MacroCorrelation from "./MacroCorrelation.jsx";

const dailyCodes = "USDVND,DXY,SP500,WTI,BRENT,GOLD,US10Y";
const monthlyCodes = "CPI_YOY,IIP_YOY,EXPORT_USD_BN,IMPORT_USD_BN";
const indicatorNames = {
  USDVND: "Tỷ giá USD/VND", DXY: "Chỉ số USD", SP500: "S&P 500",
  WTI: "Dầu thô WTI", BRENT: "Dầu thô Brent", GOLD: "Vàng", US10Y: "Lợi suất trái phiếu Mỹ 10 năm",
  CPI_YOY: "Lạm phát CPI", IIP_YOY: "Sản xuất công nghiệp",
  EXPORT_USD_BN: "Xuất khẩu", IMPORT_USD_BN: "Nhập khẩu",
};

function formatNumber(value) {
  return value == null ? "—" : value.toLocaleString("vi-VN", { maximumFractionDigits: 4 });
}

export default function MacroPage() {
  const [frequency, setFrequency] = useState("daily");
  const [indicator, setIndicator] = useState("");
  const monthly = frequency === "monthly";
  const availableCodes = monthly ? monthlyCodes : dailyCodes;
  const { data, loading, error, reload } = useApi("/api/macro/series", {
    params: { codes: indicator || availableCodes, frequency },
  });
  return (
    <div className="space-y-4">
      <PageHeader title="Vĩ mô" subtitle="Các chỉ số vĩ mô và quốc tế" />
      <label className="flex items-center gap-2 text-sm">
        Kỳ dữ liệu
        <select value={frequency} onChange={(event) => {
          setFrequency(event.target.value);
          setIndicator("");
        }}
          className="rounded-md border border-slate-300 px-3 py-2">
          <option value="daily">Theo ngày</option>
          <option value="monthly">Theo tháng</option>
        </select>
      </label>
      <label className="flex items-center gap-2 text-sm">
        Chỉ số
        <select value={indicator} onChange={(event) => setIndicator(event.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2">
          <option value="">Tất cả chỉ số</option>
          {availableCodes.split(",").map((code) => (
            <option key={code} value={code}>{indicatorNames[code]} ({code})</option>
          ))}
        </select>
      </label>
      {loading && <Spinner />}
      {error && (
        <Alert kind="error">
          Không tải được dữ liệu vĩ mô. <Button variant="secondary" onClick={reload}>Thử lại</Button>
        </Alert>
      )}
      {!loading && data && (
        data.series.length === 0 ? <Alert>Chưa có dữ liệu chỉ số {monthly ? "theo tháng" : "theo ngày"}.</Alert> :
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
                      <th scope="col" className="px-3 py-2 text-left">{monthly ? "Ngày cuối kỳ" : "Ngày"}</th>
                      {monthly && <th scope="col" className="px-3 py-2 text-left">Ngày công bố</th>}
                      <th scope="col" className="px-3 py-2 text-right">Giá trị</th>
                      <th scope="col" className="px-3 py-2 text-right">Thay đổi (%)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {series.points.slice().reverse().map((point) => (
                      <tr key={point.date} className="border-t border-slate-100">
                        <td className="px-3 py-2"><time dateTime={point.date}>{point.date}</time></td>
                        {monthly && (
                          <td className="px-3 py-2">
                            {point.published_date ? (
                              <time dateTime={point.published_date}>{point.published_date}</time>
                            ) : "Chưa có ngày công bố"}
                          </td>
                        )}
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
      <MacroCorrelation codes={dailyCodes} indicatorNames={indicatorNames} />
    </div>
  );
}
