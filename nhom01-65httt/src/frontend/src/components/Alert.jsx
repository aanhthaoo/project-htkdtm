const STYLES = {
  info: "border-blue-200 bg-blue-50 text-blue-800",
  error: "border-red-200 bg-red-50 text-red-800",
  success: "border-green-200 bg-green-50 text-green-800",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
};

export default function Alert({ kind = "info", title, children }) {
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`rounded-md border p-3 text-sm ${STYLES[kind]}`}>
      {title && <p className="font-semibold">{title}</p>}
      {children}
    </div>
  );
}
