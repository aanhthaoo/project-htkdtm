import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext.jsx";
import NewsPage from "../pages/tv5/NewsPage.jsx";

afterEach(() => vi.unstubAllGlobals());

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
