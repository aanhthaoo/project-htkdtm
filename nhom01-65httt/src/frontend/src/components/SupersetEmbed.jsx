import { useEffect, useRef, useState } from "react";
import { embedDashboard } from "@superset-ui/embedded-sdk";
import { api } from "../api/client.js";
import Alert from "./Alert.jsx";
import Spinner from "./Spinner.jsx";

// Nhúng một dashboard Superset. `dashboardKey` là khóa đăng ký ở backend (src/backend/app/routers/core_superset.py).
// Backend kiểm tra vai trò rồi cấp guest token ngắn hạn chỉ cho đúng dashboard này.
export default function SupersetEmbed({ dashboardKey, height = 600 }) {
  const mount = useRef(null);
  const [state, setState] = useState({ loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    const mountPoint = mount.current;
    api(`/api/superset/embed/${dashboardKey}`)
      .then((info) => {
        if (cancelled) return undefined;
        return embedDashboard({
          id: info.dashboard_id,
          supersetDomain: info.superset_domain,
          mountPoint,
          // SDK gọi lại hàm này khi token sắp hết hạn
          fetchGuestToken: async () => (await api(`/api/superset/embed/${dashboardKey}`)).guest_token,
          dashboardUiConfig: { hideTitle: true, hideChartControls: false, filters: { expanded: false } },
        }).then(() => {
          const iframe = mountPoint.querySelector("iframe");
          if (iframe) {
            iframe.style.width = "100%";
            iframe.style.height = "100%";
            iframe.style.border = "0";
          }
          if (!cancelled) setState({ loading: false, error: null });
        });
      })
      .catch((error) => !cancelled && setState({ loading: false, error }));
    return () => {
      cancelled = true;
      if (mountPoint) mountPoint.innerHTML = "";
    };
  }, [dashboardKey]);

  return (
    <div>
      {state.loading && <Spinner label="Đang tải dashboard..." />}
      {state.error && (
        <Alert kind="error" title="Không hiển thị được dashboard">
          {state.error.message}
        </Alert>
      )}
      <div ref={mount} style={{ height, display: state.error ? "none" : "block" }} data-testid="superset-mount" />
    </div>
  );
}
