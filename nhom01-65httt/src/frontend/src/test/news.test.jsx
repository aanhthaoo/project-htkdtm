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

  await user.click(screen.getByRole("button", { name: "Xóa bộ lọc" }));
  expect(input).toHaveValue("");
  expect(await screen.findByRole("link", { name: "Tin về VNM" })).toBeVisible();
  expect(screen.getByText("Tổng cộng 2 bài.")).toBeVisible();
});

it("cho nhà đầu tư chuyển trang và quay về trang đầu khi lọc theo mã", async () => {
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
  await user.type(screen.getByRole("textbox", { name: "Mã cổ phiếu" }), "fpt{Enter}");
  expect(await screen.findByText("Tin FPT trang 1")).toBeVisible();
  expect(screen.getByRole("button", { name: "Trang trước" })).toBeDisabled();
});
