import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import MacroPage from "../pages/tv5/MacroPage.jsx";

afterEach(() => vi.unstubAllGlobals());

function mockApi(correlationResponse) {
  vi.stubGlobal("fetch", vi.fn(async (url) => {
    if (url.pathname === "/api/macro/series") {
      return { ok: true, status: 200, json: async () => ({ series: [] }) };
    }
    return correlationResponse(url);
  }));
}

it("hiện hệ số âm, bằng không, thiếu dữ liệu và đổi cửa sổ độc lập với kỳ tháng", async () => {
  mockApi(async (url) => ({ ok: true, status: 200, json: async () => ({
    against: "foreign_net", stub: false,
    items: [
      { code: "DXY", correlation: url.searchParams.get("window") === "120" ? 0.75 : -0.5, window: Number(url.searchParams.get("window")) },
      { code: "GOLD", correlation: 0, window: Number(url.searchParams.get("window")) },
    ],
  }) }));
  const user = userEvent.setup();
  render(<MacroPage />);
  const coefficient = async (code) => {
    const row = await screen.findByRole("rowheader", { name: code });
    return within(row.closest("tr")).getByRole("cell");
  };
  expect(await coefficient("Chỉ số USD (DXY)")).toHaveTextContent("-0,5");
  expect(await coefficient("Vàng (GOLD)")).toHaveTextContent(/^0$/);
  expect(await coefficient("Tỷ giá USD/VND (USDVND)")).toHaveTextContent("Chưa đủ dữ liệu hoặc hệ số không xác định");
  expect(screen.getByText(/Tương quan không thể hiện quan hệ nhân quả/)).toBeVisible();
  const correlationCalls = () => globalThis.fetch.mock.calls.filter(([url]) => url.pathname === "/api/macro/correlation");
  expect(correlationCalls()[0][0].searchParams.get("against")).toBe("foreign_net");
  expect(correlationCalls()[0][0].searchParams.get("window")).toBe("60");
  await user.selectOptions(screen.getByLabelText("Kỳ dữ liệu"), "monthly");
  await user.selectOptions(screen.getByLabelText("Chỉ số"), "CPI_YOY");
  await user.selectOptions(screen.getByLabelText("Cửa sổ tương quan"), "120");
  await waitFor(async () => expect(await coefficient("Chỉ số USD (DXY)")).toHaveTextContent("0,75"));
  expect(correlationCalls().at(-1)[0].searchParams.get("codes")).toBe("USDVND,DXY,SP500,WTI,BRENT,GOLD,US10Y");
  expect(screen.getByText(/Cửa sổ 120 phiên gần nhất/)).toBeVisible();
});

it("hiện trạng thái rỗng khi không có hệ số", async () => {
  mockApi(async () => ({ ok: true, status: 200, json: async () => ({ items: [] }) }));
  render(<MacroPage />);
  expect(await screen.findByText("Chưa đủ dữ liệu để tính tương quan trong cửa sổ đã chọn.")).toBeVisible();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("thử lại riêng tương quan sau lỗi mà vẫn giữ dữ liệu chuỗi", async () => {
  let attempts = 0;
  mockApi(async () => {
    attempts += 1;
    return attempts === 1
      ? { ok: false, status: 503, json: async () => ({}) }
      : { ok: true, status: 200, json: async () => ({ items: [{ code: "DXY", correlation: 1, window: 60 }] }) };
  });
  const user = userEvent.setup();
  render(<MacroPage />);
  await user.click(await screen.findByRole("button", { name: "Thử lại tương quan" }));
  expect(await screen.findByRole("rowheader", { name: "Chỉ số USD (DXY)" })).toBeVisible();
  expect(screen.queryByText("Không tải được tương quan.")).not.toBeInTheDocument();
  expect(globalThis.fetch.mock.calls.filter(([url]) => url.pathname === "/api/macro/series")).toHaveLength(1);
});
