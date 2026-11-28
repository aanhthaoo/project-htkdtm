import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { tokenStore } from "../api/client.js";
import { AuthProvider } from "../auth/AuthContext.jsx";
import NewsPage from "../pages/tv5/NewsPage.jsx";

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.clear();
});

it("xóa các điều kiện chưa áp dụng mà không tải lại tin", async () => {
  const fetchNews = vi.fn(async () => ({
    ok: true, status: 200, json: async () => ({ items: [], total: 0 }),
  }));
  vi.stubGlobal("fetch", fetchNews);
  const user = userEvent.setup();
  render(<MemoryRouter><AuthProvider><NewsPage /></AuthProvider></MemoryRouter>);
  await screen.findByText("Chưa có tin tức.");
  const callsBeforeEdit = fetchNews.mock.calls.length;
  const symbol = screen.getByLabelText("Mã cổ phiếu");
  const sector = screen.getByLabelText("Ngành");
  const from = screen.getByLabelText("Từ ngày");
  const to = screen.getByLabelText("Đến ngày");
  await user.type(symbol, "FPT");
  await user.selectOptions(sector, "9500");
  await user.type(from, "2026-11-01");
  await user.type(to, "2026-11-28");
  await user.click(screen.getByRole("button", { name: "Xóa bộ lọc" }));

  for (const field of [symbol, sector, from, to]) {
    expect(field).toHaveValue("");
  }
  expect(fetchNews).toHaveBeenCalledTimes(callsBeforeEdit);
});

it("chặn khoảng ngày đảo ngược và cho phép lọc trong cùng một ngày", async () => {
  const fetchNews = vi.fn(async () => ({
    ok: true, status: 200, json: async () => ({ items: [], total: 0 }),
  }));
  vi.stubGlobal("fetch", fetchNews);
  const user = userEvent.setup();
  render(<MemoryRouter><AuthProvider><NewsPage /></AuthProvider></MemoryRouter>);
  await screen.findByText("Chưa có tin tức.");
  const callsBeforeFilter = fetchNews.mock.calls.length;
  const end = screen.getByLabelText("Đến ngày");
  const submit = screen.getByRole("button", { name: "Lọc tin" });

  await user.type(screen.getByLabelText("Từ ngày"), "2026-11-28");
  await user.type(end, "2026-11-27");
  await user.click(submit);
  expect(screen.getByRole("alert")).toHaveTextContent("Đến ngày phải bằng hoặc sau Từ ngày.");
  expect(end).toHaveFocus();
  expect(fetchNews).toHaveBeenCalledTimes(callsBeforeFilter);

  await user.clear(end);
  await user.type(end, "2026-11-28");
  await user.click(submit);
  await screen.findByText("Không tìm thấy tin phù hợp với bộ lọc.");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(fetchNews.mock.lastCall[0].searchParams.get("to")).toBe("2026-11-28");
});

it("lọc theo mã đã chuẩn hóa và khôi phục danh sách khi xóa bộ lọc", async () => {
  const articles = ["FPT", "VNM"].map((symbol) => ({
    title: `Tin về ${symbol}`,
    url: `https://example.com/${symbol}`,
    source: "Bản tin",
    session_date: "2026-11-27",
    symbol,
  }));
  vi.stubGlobal("fetch", vi.fn(async (url) => {
    const symbol = url.searchParams.get("symbol");
    const items = articles.filter((article) => symbol === null || article.symbol === symbol);
    return { ok: true, status: 200, json: async () => ({ items, total: items.length }) };
  }));
  const user = userEvent.setup();
  render(<MemoryRouter><AuthProvider><NewsPage /></AuthProvider></MemoryRouter>);

  expect(await screen.findByRole("link", { name: "Tin về VNM" })).toBeVisible();
  const input = screen.getByRole("textbox", { name: "Mã cổ phiếu" });
  await user.type(input, " fpt {Enter}");
  expect(input).toHaveValue("FPT");
  expect(await screen.findByText("Tổng cộng 1 bài.")).toBeVisible();
  expect(screen.getByRole("link", { name: "Tin về FPT" })).toBeVisible();
  expect(screen.queryByRole("link", { name: "Tin về VNM" })).not.toBeInTheDocument();

  const sector = screen.getByRole("combobox", { name: "Ngành" });
  await user.selectOptions(sector, "0500");
  await user.type(screen.getByLabelText("Từ ngày"), "2026-11-01");
  await user.type(screen.getByLabelText("Đến ngày"), "2026-11-28");
  await user.click(screen.getByRole("button", { name: "Lọc tin" }));
  const query = globalThis.fetch.mock.lastCall[0].searchParams;
  expect(query.get("symbol")).toBe("FPT");
  expect(query.get("sector")).toBe("0500");
  expect(query.get("from")).toBe("2026-11-01");
  expect(query.get("to")).toBe("2026-11-28");

  await user.click(screen.getByRole("button", { name: "Xóa bộ lọc" }));
  expect(sector).toHaveValue("");
  expect(screen.getByLabelText("Từ ngày")).toHaveValue("");
  expect(screen.getByLabelText("Đến ngày")).toHaveValue("");
  expect(globalThis.fetch.mock.lastCall[0].searchParams.has("from")).toBe(false);
  expect(globalThis.fetch.mock.lastCall[0].searchParams.has("to")).toBe(false);
  expect(globalThis.fetch.mock.lastCall[0].searchParams.has("sector")).toBe(false);
  expect(input).toHaveValue("");
  expect(await screen.findByRole("link", { name: "Tin về VNM" })).toBeVisible();
  expect(screen.getByText("Tổng cộng 2 bài.")).toBeVisible();
});

it("quay về trang đầu khi áp dụng bộ lọc và giữ các điều kiện khi chuyển trang", async () => {
  tokenStore.set("test-token");
  vi.stubGlobal("fetch", vi.fn(async (url) => {
    if (url.pathname === "/api/auth/me") {
      return { ok: true, status: 200, json: async () => ({ role: "investor" }) };
    }
    const page = url.searchParams.get("page");
    const symbol = url.searchParams.get("symbol") || "thị trường";
    const items = [{ url: "https://example.com/news", title: `Tin ${symbol} trang ${page}` }];
    return { ok: true, status: 200, json: async () => ({ items, total: 21 }) };
  }));
  const user = userEvent.setup();
  render(<MemoryRouter><AuthProvider><NewsPage /></AuthProvider></MemoryRouter>);

  expect(await screen.findByRole("button", { name: "Trang trước" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Trang sau" }));
  expect(await screen.findByText("Tin thị trường trang 2")).toBeVisible();
  expect(screen.getByRole("button", { name: "Trang sau" })).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("Ngành"), "9500");
  await user.type(screen.getByLabelText("Từ ngày"), "2026-11-01");
  await user.type(screen.getByLabelText("Đến ngày"), "2026-11-28");
  await user.type(screen.getByRole("textbox", { name: "Mã cổ phiếu" }), "fpt{Enter}");
  expect(await screen.findByText("Tin FPT trang 1")).toBeVisible();
  expect(screen.getByRole("button", { name: "Trang trước" })).toBeDisabled();

  const appliedFilters = { symbol: "FPT", sector: "9500", from: "2026-11-01", to: "2026-11-28" };
  // Ngành mới chọn chỉ có hiệu lực sau khi bấm Lọc tin.
  await user.selectOptions(screen.getByLabelText("Ngành"), "0500");
  await user.click(screen.getByRole("button", { name: "Trang sau" }));
  expect(await screen.findByText("Tin FPT trang 2")).toBeVisible();
  expect(Object.fromEntries(globalThis.fetch.mock.lastCall[0].searchParams))
    .toMatchObject({ ...appliedFilters, page: "2" });

  await user.click(screen.getByRole("button", { name: "Trang trước" }));
  expect(await screen.findByText("Tin FPT trang 1")).toBeVisible();
  expect(Object.fromEntries(globalThis.fetch.mock.lastCall[0].searchParams))
    .toMatchObject({ ...appliedFilters, page: "1" });
});
