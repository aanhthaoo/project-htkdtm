// Danh sách trang của hệ thống. MỖI NGƯỜI CHỈ THÊM DÒNG CỦA MÌNH (không sửa lõi):
//   { path, element, minRole: "guest" | "investor" | "admin", label (nếu muốn hiện ở thanh menu) }
// Trang mẫu của từng thành viên nằm ở src/pages/tvN/.
import Home from "./pages/Home.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Account from "./pages/Account.jsx";
import Admin from "./pages/Admin.jsx";
import StocksPage from "./pages/tv2/StocksPage.jsx";
import StockDetailPage from "./pages/tv2/StockDetailPage.jsx";
import SectorsPage from "./pages/tv3/SectorsPage.jsx";
import ForecastPage from "./pages/tv4/ForecastPage.jsx";
import NewsPage from "./pages/tv5/NewsPage.jsx";

export const ROUTES = [
  // Lõi (TV1)
  { path: "/", element: <Home />, minRole: "guest", label: "Tổng quan" },
  { path: "/login", element: <Login />, minRole: "guest" },
  { path: "/register", element: <Register />, minRole: "guest" },
  { path: "/dashboard", element: <Dashboard />, minRole: "investor", label: "Luân chuyển ngành" },
  { path: "/admin", element: <Admin />, minRole: "admin", label: "Quản trị" },
  // TV2: mã cổ phiếu, theo dõi, cảnh báo
  { path: "/stocks", element: <StocksPage />, minRole: "investor", label: "Cổ phiếu" },
  { path: "/stocks/:symbol", element: <StockDetailPage />, minRole: "investor" },
  // TV3: thị trường và ngành
  { path: "/sectors", element: <SectorsPage />, minRole: "investor", label: "Phân tích ngành" },
  // TV4: dự báo, tài khoản
  { path: "/forecast", element: <ForecastPage />, minRole: "investor", label: "Dự báo" },
  { path: "/account", element: <Account />, minRole: "investor", label: "Tài khoản" },
  // TV5: tin tức, vĩ mô
  { path: "/news", element: <NewsPage />, minRole: "guest", label: "Tin tức" },
];

export const NAV_ITEMS = ROUTES.filter((r) => r.label);
