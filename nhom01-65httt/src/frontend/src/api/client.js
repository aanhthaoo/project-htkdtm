// Gọi API backend. Token lưu ở localStorage; mọi lỗi được chuyển thành ApiError có status và code (theo contract).
const TOKEN_KEY = "htkdtm_token";

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export async function api(path, { method = "GET", body, auth = true, params } = {}) {
  const url = new URL(path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    });
  }
  const headers = {};
  const token = tokenStore.get();
  if (auth && token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) return null;
  let data = null;
  try {
    data = await response.json();
  } catch {
    // phản hồi không phải JSON
  }
  if (!response.ok) {
    const err = data?.error ?? {};
    const error = new ApiError(
      response.status,
      err.code ?? "error",
      err.message ?? `Lỗi ${response.status}`,
      err.details,
    );
    // Token hết hạn hoặc không hợp lệ: xóa token và báo cho AuthContext đăng xuất
    if (response.status === 401 && ["token_expired", "invalid_token"].includes(error.code)) {
      tokenStore.clear();
      window.dispatchEvent(new Event("auth:expired"));
    }
    throw error;
  }
  return data;
}
