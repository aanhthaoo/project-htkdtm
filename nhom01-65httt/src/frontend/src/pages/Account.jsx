import { useState } from "react";
import { api } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { ROLE_LABEL } from "../auth/roles.js";
import Alert from "../components/Alert.jsx";
import Button from "../components/Button.jsx";
import Card from "../components/Card.jsx";
import DataTable from "../components/DataTable.jsx";
import PageHeader from "../components/PageHeader.jsx";
import Spinner from "../components/Spinner.jsx";
import useApi from "../components/useApi.js";

// Trang tài khoản + danh sách theo dõi (mẫu dùng API thật; TV4 hoàn thiện giao diện)
export default function Account() {
  const { user } = useAuth();
  const watch = useApi("/api/watchlist");
  const [symbol, setSymbol] = useState("");
  const [error, setError] = useState(null);

  async function add(event) {
    event.preventDefault();
    setError(null);
    try {
      await api("/api/watchlist", { method: "POST", body: { entity_type: "STOCK", entity_code: symbol } });
      setSymbol("");
      watch.reload();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(id) {
    await api(`/api/watchlist/${id}`, { method: "DELETE" });
    watch.reload();
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Tài khoản" />
      <Card title="Thông tin">
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <dt className="text-slate-500">Email</dt>
          <dd>{user.email}</dd>
          <dt className="text-slate-500">Họ tên</dt>
          <dd>{user.full_name || "—"}</dd>
          <dt className="text-slate-500">Vai trò</dt>
          <dd>{ROLE_LABEL[user.role]}</dd>
        </dl>
      </Card>
      <Card title="Danh sách theo dõi">
        <form onSubmit={add} className="mb-3 flex gap-2">
          <input
            required
            placeholder="Mã cổ phiếu, ví dụ VNM"
            className="rounded-md border border-slate-300 px-3 py-2 text-sm uppercase"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          />
          <Button type="submit">Thêm</Button>
        </form>
        {error && <Alert kind="error">{error}</Alert>}
        {watch.loading && <Spinner />}
        {watch.data && (
          <DataTable
            rows={watch.data}
            empty="Chưa theo dõi mã nào"
            columns={[
              { key: "entity_code", label: "Mã / ngành" },
              { key: "entity_type", label: "Loại" },
              {
                key: "actions",
                label: "",
                align: "right",
                render: (row) => (
                  <Button variant="secondary" onClick={() => remove(row.id)}>
                    Bỏ theo dõi
                  </Button>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
}
