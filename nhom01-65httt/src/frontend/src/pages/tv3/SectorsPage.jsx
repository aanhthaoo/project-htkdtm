import Alert from "../../components/Alert.jsx";
import Card from "../../components/Card.jsx";
import PageHeader from "../../components/PageHeader.jsx";
import Spinner from "../../components/Spinner.jsx";
import useApi from "../../components/useApi.js";

// TRANG MẪU (TV3): ma trận dòng tiền ròng khối ngoại, ngành x tuần, bằng API /api/sectors/flow.
export default function SectorsPage() {
  const flow = useApi("/api/sectors/flow", { params: { granularity: "week", investor_type: "FOREIGN" } });
  const f = flow.data;
  const recent = f ? f.periods.slice(-6) : [];
  const offset = f ? f.periods.length - recent.length : 0;
  return (
    <div className="space-y-4">
      <PageHeader title="Phân tích ngành" subtitle="Khối ngoại mua/bán ròng theo ngành ICB cấp 2 (tỷ đồng)" />
      {flow.loading && <Spinner />}
      {flow.error && <Alert kind="error">{flow.error.message}</Alert>}
      {f && (
        <Card>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-100 text-slate-600">
                <tr>
                  <th className="px-3 py-2 text-left">Ngành</th>
                  {recent.map((p) => (
                    <th key={p} className="px-3 py-2 text-right">
                      {p.slice(5)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {f.sectors.map((s) => (
                  <tr key={s.icb_l2_code} className="border-t border-slate-100">
                    <td className="px-3 py-2">{s.name_vi}</td>
                    {s.net_bn.slice(offset).map((v, i) => (
                      <td
                        key={recent[i]}
                        className={`px-3 py-2 text-right tabular-nums ${v > 0 ? "text-up" : v < 0 ? "text-down" : ""}`}
                      >
                        {v === null ? "—" : v.toLocaleString("vi-VN", { maximumFractionDigits: 0 })}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
