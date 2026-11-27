import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import Alert from "../components/Alert.jsx";
import Button from "../components/Button.jsx";
import Card from "../components/Card.jsx";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(form.email, form.password, form.full_name);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const detail = err.details?.map((d) => `${d.field}: ${d.message}`).join("; ");
      setError(detail ? `${err.message} (${detail})` : err.message);
    } finally {
      setBusy(false);
    }
  }

  const input = "mt-1 w-full rounded-md border border-slate-300 px-3 py-2";
  return (
    <div className="mx-auto max-w-md">
      <Card title="Đăng ký tài khoản nhà đầu tư">
        <form onSubmit={submit} className="space-y-3">
          {error && <Alert kind="error">{error}</Alert>}
          <label className="block text-sm">
            Họ tên
            <input
              className={input}
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            Email
            <input
              type="email"
              required
              autoComplete="email"
              className={input}
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            Mật khẩu (tối thiểu 8 ký tự)
            <input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              className={input}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </label>
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Đang tạo tài khoản..." : "Đăng ký"}
          </Button>
          <p className="text-center text-sm text-slate-500">
            Đã có tài khoản?{" "}
            <Link to="/login" className="text-brand-600 hover:underline">
              Đăng nhập
            </Link>
          </p>
        </form>
      </Card>
    </div>
  );
}
