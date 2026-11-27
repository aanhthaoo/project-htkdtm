import { useState } from "react";
import { api } from "../api/client.js";
import Alert from "../components/Alert.jsx";
import Button from "../components/Button.jsx";
import Card from "../components/Card.jsx";
import DataTable from "../components/DataTable.jsx";
import PageHeader from "../components/PageHeader.jsx";
import Spinner from "../components/Spinner.jsx";
import useApi from "../components/useApi.js";

const JOBS = [
  { value: "after_close", label: "Chuỗi sau phiên (giá, quốc tế, dbt, chất lượng)" },
  { value: "rss", label: "Thu thập RSS" },
  { value: "dbt", label: "Dựng lại kho (dbt run)" },
  { value: "quality", label: "Kiểm thử và kiểm tra chất lượng" },
  { value: "news", label: "Làm sạch tin (30-40 phút)" },
];

// Trang quản trị mẫu: người dùng, chạy lại ETL, nhật ký chạy. TV2 hoàn thiện.
export default function Admin() {
  const users = useApi("/api/admin/users");
  const runs = useApi("/api/admin/etl/runs", { params: { page_size: 10 } });
  const dq = useApi("/api/admin/dq-log", { params: { page_size: 10, failed_only: true } });
  const [job, setJob] = useState("after_close");
  const [message, setMessage] = useState(null);

  async function runEtl() {
    setMessage(null);
    try {
      const r = await api("/api/admin/etl/run", { method: "POST", body: { job } });
      setMessage({ kind: "success", text: `Đã bắt đầu lần chạy #${r.run_id}` });
      runs.reload();
    } catch (err) {
      setMessage({ kind: "error", text: err.message });
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Quản trị" />
      <Card
        title="Chạy lại ETL"
        actions={
          <Button variant="secondary" onClick={runs.reload}>
            Làm mới
          </Button>
        }
      >
        <div className="mb-3 flex gap-2">
          <select
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={job}
            onChange={(e) => setJob(e.target.value)}
          >
            {JOBS.map((j) => (
              <option key={j.value} value={j.value}>
                {j.label}
              </option>
            ))}
          </select>
          <Button onClick={runEtl}>Chạy</Button>
        </div>
        {message && <Alert kind={message.kind}>{message.text}</Alert>}
        {runs.loading && <Spinner />}
        {runs.data && (
          <DataTable
            rows={runs.data.items}
            columns={[
              { key: "id", label: "#" },
              { key: "job", label: "Công việc" },
              { key: "trigger_type", label: "Nguồn kích hoạt" },
              { key: "status", label: "Trạng thái" },
              { key: "started_at", label: "Bắt đầu", render: (r) => new Date(r.started_at).toLocaleString("vi-VN") },
            ]}
          />
        )}
      </Card>
      <Card title="Kiểm tra chất lượng chưa đạt (mới nhất)">
        {dq.data && (
          <DataTable
            rows={dq.data.items}
            empty="Không có kiểm tra nào chưa đạt"
            columns={[
              { key: "check_name", label: "Kiểm tra" },
              { key: "severity", label: "Mức" },
              { key: "business_date", label: "Ngày" },
              { key: "metric_value", label: "Giá trị", align: "right" },
            ]}
          />
        )}
      </Card>
      <Card title="Người dùng">
        {users.data && (
          <DataTable
            rows={users.data.items}
            columns={[
              { key: "email", label: "Email" },
              { key: "role", label: "Vai trò" },
              { key: "is_active", label: "Hoạt động", render: (u) => (u.is_active ? "Có" : "Khóa") },
            ]}
          />
        )}
      </Card>
    </div>
  );
}
