// Thẻ KPI: giá trị lớn, nhãn, và độ thay đổi (xanh = dương, đỏ = âm)
export default function KpiCard({ label, value, unit, delta }) {
  const tone = delta === undefined || delta === null ? "" : delta >= 0 ? "text-up" : "text-down";
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">
        {value ?? "—"}
        {unit && <span className="ml-1 text-sm font-normal text-slate-500">{unit}</span>}
      </p>
      {delta !== undefined && delta !== null && (
        <p className={`text-sm ${tone}`}>
          {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toLocaleString("vi-VN", { maximumFractionDigits: 2 })}
        </p>
      )}
    </div>
  );
}
