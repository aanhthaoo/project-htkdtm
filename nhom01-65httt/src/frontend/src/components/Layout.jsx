import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { ROLE_LABEL } from "../auth/roles.js";
import { NAV_ITEMS } from "../routes.jsx";
import Button from "./Button.jsx";
import Disclaimer from "./Disclaimer.jsx";

export default function Layout() {
  const { user, logout, can } = useAuth();
  const navigate = useNavigate();
  const items = NAV_ITEMS.filter((item) => can(item.minRole));
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3">
          <Link to="/" className="font-semibold text-brand-700">
            Dòng tiền &amp; Luân chuyển ngành
          </Link>
          <nav className="flex flex-1 flex-wrap gap-4 text-sm">
            {items.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === "/"}
                className={({ isActive }) =>
                  isActive ? "font-semibold text-brand-700" : "text-slate-600 hover:text-slate-900"
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          {user ? (
            <div className="flex items-center gap-3 text-sm">
              <span className="text-slate-600">
                {user.full_name || user.email} · {ROLE_LABEL[user.role]}
              </span>
              <Button
                variant="secondary"
                onClick={() => {
                  logout();
                  navigate("/");
                }}
              >
                Đăng xuất
              </Button>
            </div>
          ) : (
            <div className="flex gap-2 text-sm">
              <Button variant="secondary" onClick={() => navigate("/login")}>
                Đăng nhập
              </Button>
              <Button onClick={() => navigate("/register")}>Đăng ký</Button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <Disclaimer />
    </div>
  );
}
