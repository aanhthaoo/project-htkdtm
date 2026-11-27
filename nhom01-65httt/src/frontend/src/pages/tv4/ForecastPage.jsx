import Alert from "../../components/Alert.jsx";
import Card from "../../components/Card.jsx";
import DataTable from "../../components/DataTable.jsx";
import PageHeader from "../../components/PageHeader.jsx";
import Spinner from "../../components/Spinner.jsx";
import useApi from "../../components/useApi.js";

// TRANG MẪU (TV4): dự báo dòng tiền ngành. API trả dữ liệu mẫu (stub = true) đến khi mô hình (N8) ghi vào dw.
export default function ForecastPage() {
  const forecast = useApi("/api/predictions");
  const f = forecast.data;
  return (
    <div className="space-y-4">
      <PageHeader title="Dự báo dòng tiền ngành" subtitle={f ? `Tuần bắt đầu ${f.target_week_start}` : ""} />
      {forecast.loading && <Spinner />}
      {f?.stub && (
        <Alert kind="warning" title="Dữ liệu mẫu">
          Mô hình dự báo chưa được kích hoạt; bảng dưới đây chỉ minh họa định dạng.
        </Alert>
      )}
      {f && (
        <Card>
          <DataTable
            rowKey="icb_l2_code"
            rows={f.items}
            columns={[
              { key: "name_vi", label: "Ngành" },
              { key: "predicted_class", label: "Dự báo" },
              { key: "prob_inflow", label: "Xác suất dòng tiền vào", align: "right" },
              { key: "predicted_net_bn", label: "Ròng dự kiến (tỷ)", align: "right" },
            ]}
          />
          <p className="mt-3 text-xs text-slate-500">{f.disclaimer}</p>
        </Card>
      )}
    </div>
  );
}
