import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import NewsHighlights from "../components/NewsHighlights.jsx";

const article = {
  title: "Tin thị trường cuối tuần",
  url: "https://example.com/thi-truong",
  source: "Bản tin",
  session_date: "2026-11-27",
};

function response(status, body) {
  return { ok: status === 200, status, json: async () => body };
}

afterEach(() => vi.unstubAllGlobals());

it("lấy tin nổi bật và hiển thị liên kết gốc, nguồn, ngày", async () => {
  const fetchNews = vi.fn().mockResolvedValue(response(200, { items: [article] }));
  vi.stubGlobal("fetch", fetchNews);
  render(<NewsHighlights />);

  expect(await screen.findByRole("link", { name: article.title })).toHaveAttribute("href", article.url);
  expect(screen.getByText("Bản tin · 2026-11-27")).toBeVisible();
  expect(fetchNews.mock.calls[0][0].pathname).toBe("/api/news/highlights");
});

it("thông báo khi danh sách tin nổi bật trống", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(200, { items: [] })));
  render(<NewsHighlights />);

  expect(await screen.findByText("Chưa có tin nổi bật.")).toBeVisible();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

it("cho phép thử lại sau lỗi máy chủ và hiển thị tin khi tải thành công", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(response(503, {}))
    .mockResolvedValueOnce(response(200, { items: [article] })));
  const user = userEvent.setup();
  render(<NewsHighlights />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Không tải được tin nổi bật.");
  await user.click(screen.getByRole("button", { name: "Thử lại" }));
  expect(await screen.findByRole("link", { name: article.title })).toBeVisible();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
