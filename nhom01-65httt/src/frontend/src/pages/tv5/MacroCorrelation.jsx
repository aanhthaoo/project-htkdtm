import { useState } from "react";
import Alert from "../../components/Alert.jsx";
import Button from "../../components/Button.jsx";
import Card from "../../components/Card.jsx";
import Spinner from "../../components/Spinner.jsx";
import useApi from "../../components/useApi.js";

export default function MacroCorrelation({ codes, indicatorNames }) {
  const [window, setWindow] = useState(60);
  const { data, loading, error, reload } = useApi("/api/macro/correlation", {
    params: { codes, against: "foreign_net", window },
  });
  return (
    <Card title="Tương quan với dòng tiền ròng khối ngoại">
      <p className="mb-3 text-sm text-slate-600">
        Hệ số Pearson giữa thay đổi % hằng ngày của chỉ số và dòng tiền ròng khối ngoại
        cùng ngày, trong cửa sổ phiên gần nhất. Hệ số từ -1 đến 1; dấu âm là ngược chiều,
        dấu dương là cùng chiều.
      </p>
      <label className="mb-3 flex items-center gap-2 text-sm">
        Cửa sổ tương quan
        <select value={window} onChange={(event) => setWindow(Number(event.target.value))}
          className="rounded-md border border-slate-300 px-3 py-2">
          {[20, 60, 120, 250].map((size) => <option key={size} value={size}>{size} phiên</option>)}
        </select>
      </label>
      <Alert>
        Tương quan không thể hiện quan hệ nhân quả. Chỉ số quốc tế có thể đóng cửa sau
        thị trường Việt Nam. Thông tin chỉ phục vụ nghiên cứu, không phải khuyến nghị đầu tư.
      </Alert>
      {loading && <Spinner />}
      {error && <Alert kind="error">
        Không tải được tương quan. <Button variant="secondary" onClick={reload}>Thử lại tương quan</Button>
      </Alert>}
      {!loading && data && (
        data.items.length === 0 ? <Alert>Chưa đủ dữ liệu để tính tương quan trong cửa sổ đã chọn.</Alert> : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <caption className="my-2 text-left text-slate-500">Cửa sổ {window} phiên gần nhất; chỉ ghép dữ liệu cùng ngày.</caption>
              <thead className="bg-slate-100 text-slate-600">
                <tr>
                  <th scope="col" className="px-3 py-2 text-left">Chỉ số ngày</th>
                  <th scope="col" className="px-3 py-2 text-right">Hệ số tương quan</th>
                </tr>
              </thead>
              <tbody>
                {codes.split(",").map((code) => {
                  const item = data.items.find((item) => item.code === code);
                  return <tr key={code} className="border-t border-slate-100">
                    <th scope="row" className="px-3 py-2 text-left font-normal">{indicatorNames[code]} ({code})</th>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {item ? item.correlation.toLocaleString("vi-VN", { maximumFractionDigits: 4 }) : "Chưa đủ dữ liệu hoặc hệ số không xác định"}
                    </td>
                  </tr>;
                })}
              </tbody>
            </table>
          </div>
        )
      )}
    </Card>
  );
}
