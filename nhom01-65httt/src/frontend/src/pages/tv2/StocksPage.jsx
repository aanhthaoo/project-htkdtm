import { useState } from "react";
import Card from "../../components/Card.jsx";
import DataTable from "../../components/DataTable.jsx";
import PageHeader from "../../components/PageHeader.jsx";
import Spinner from "../../components/Spinner.jsx";
import useApi from "../../components/useApi.js";

// TRANG MẪU (TV2): tìm mã cổ phiếu bằng API /api/stocks. TV2 thay bằng trang chi tiết mã.
export default function StocksPage() {
  const [query, setQuery] = useState("");
  const stocks = useApi("/api/stocks", { params: { query, page_size: 15 } });
  return (
    <div className="space-y-4">
      <PageHeader title="Cổ phiếu" subtitle="Tìm theo mã hoặc tên công ty" />
      <Card>
        <input
          placeholder="Ví dụ: VNM, Hòa Phát..."
          className="mb-3 w-full max-w-sm rounded-md border border-slate-300 px-3 py-2 text-sm"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {stocks.loading && <Spinner />}
        {stocks.data && (
          <DataTable
            rowKey="symbol"
            rows={stocks.data.items}
            columns={[
              { key: "symbol", label: "Mã" },
              { key: "name_vi", label: "Tên" },
              { key: "exchange", label: "Sàn" },
              { key: "icb_l2_name_vi", label: "Ngành" },
            ]}
          />
        )}
      </Card>
    </div>
  );
}
