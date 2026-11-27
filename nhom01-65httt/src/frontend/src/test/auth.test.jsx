import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, tokenStore } from "../api/client.js";
import { AuthProvider } from "../auth/AuthContext.jsx";
import ProtectedRoute from "../auth/ProtectedRoute.jsx";
import { hasRole } from "../auth/roles.js";

function mockFetch(status, body) {
  globalThis.fetch = vi.fn(async () => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }));
}

function renderAt(path, minRole) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<p>trang dang nhap</p>} />
          <Route
            path="/secret"
            element={
              <ProtectedRoute minRole={minRole}>
                <p>noi dung bao ve</p>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("hasRole", () => {
  it("xếp hạng khách < nhà đầu tư < quản trị", () => {
    expect(hasRole(null, "guest")).toBe(true);
    expect(hasRole(null, "investor")).toBe(false);
    expect(hasRole({ role: "investor" }, "investor")).toBe(true);
    expect(hasRole({ role: "investor" }, "admin")).toBe(false);
    expect(hasRole({ role: "admin" }, "investor")).toBe(true);
  });
});

describe("ProtectedRoute", () => {
  it("khách chưa đăng nhập bị chuyển tới trang đăng nhập", async () => {
    renderAt("/secret", "investor");
    expect(await screen.findByText("trang dang nhap")).toBeInTheDocument();
  });

  it("nhà đầu tư vào trang quản trị thấy thông báo không đủ quyền", async () => {
    tokenStore.set("token-hop-le");
    mockFetch(200, { id: 1, email: "a@b.com", full_name: "A", role: "investor" });
    renderAt("/secret", "admin");
    expect(await screen.findByText("Không đủ quyền")).toBeInTheDocument();
    expect(screen.queryByText("noi dung bao ve")).not.toBeInTheDocument();
  });

  it("quản trị vào được trang quản trị", async () => {
    tokenStore.set("token-hop-le");
    mockFetch(200, { id: 2, email: "ad@b.com", full_name: "Ad", role: "admin" });
    renderAt("/secret", "admin");
    expect(await screen.findByText("noi dung bao ve")).toBeInTheDocument();
  });

  it("token không còn hợp lệ: bị đưa về đăng nhập và xóa token", async () => {
    tokenStore.set("token-het-han");
    mockFetch(401, { error: { code: "token_expired", message: "hết hạn" } });
    renderAt("/secret", "investor");
    expect(await screen.findByText("trang dang nhap")).toBeInTheDocument();
    await waitFor(() => expect(tokenStore.get()).toBeNull());
  });
});

describe("api client", () => {
  it("gửi Bearer token và chuyển lỗi thành ApiError theo định dạng contract", async () => {
    tokenStore.set("abc");
    mockFetch(403, { error: { code: "forbidden", message: "Không đủ quyền" } });
    await expect(api("/api/admin/users")).rejects.toMatchObject({ status: 403, code: "forbidden" });
    const [, init] = globalThis.fetch.mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer abc");
  });

  it("không gửi token cho yêu cầu auth: false (đăng nhập)", async () => {
    tokenStore.set("abc");
    mockFetch(200, { ok: true });
    await api("/api/auth/login", { method: "POST", body: { email: "a@b.com" }, auth: false });
    const [, init] = globalThis.fetch.mock.calls[0];
    expect(init.headers.Authorization).toBeUndefined();
    expect(init.headers["Content-Type"]).toBe("application/json");
  });

  it("ApiError mang theo chi tiết kiểm tra dữ liệu", async () => {
    mockFetch(422, {
      error: { code: "validation_error", message: "Sai", details: [{ field: "email", message: "x" }] },
    });
    const err = await api("/api/auth/register", { method: "POST", body: {}, auth: false }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.details[0].field).toBe("email");
  });
});
