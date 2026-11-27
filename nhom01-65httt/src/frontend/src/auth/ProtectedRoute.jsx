import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";
import Spinner from "../components/Spinner.jsx";
import Alert from "../components/Alert.jsx";

// Bảo vệ route theo vai trò: chưa đăng nhập -> trang đăng nhập; đã đăng nhập nhưng thiếu quyền -> thông báo.
export default function ProtectedRoute({ minRole = "investor", children }) {
  const { user, loading, can } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (minRole !== "guest" && !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (!can(minRole)) {
    return (
      <div className="mx-auto max-w-xl p-6">
        <Alert kind="error" title="Không đủ quyền">
          Tài khoản của bạn không được phép xem trang này.
        </Alert>
      </div>
    );
  }
  return children;
}
