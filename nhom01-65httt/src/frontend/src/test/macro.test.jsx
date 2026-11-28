import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import MacroPage from "../pages/tv5/MacroPage.jsx";

afterEach(() => vi.unstubAllGlobals());

it("đổi từ chuỗi ngày sang tháng và hiển thị đúng ngày công bố", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url) => {
    const monthly = url.searchParams.get("frequency") === "monthly";
    return {
      ok: true, status: 200,
      json: async () => ({
        series: [{
          code: monthly ? "CPI_YOY" : "DXY",
          name_vi: monthly ? "Lạm phát CPI" : "Chỉ số DXY",
          unit: "%",
          points: [{
            date: "2026-10-31", value: 3.1, pct_change_prev: null,
            ...(monthly ? { published_date: "2026-11-05" } : {}),
          }],
        }],
      }),
    };
  }));
  const user = userEvent.setup();
  render(<MacroPage />);
  expect(await screen.findByRole("heading", { name: "Chỉ số DXY (DXY)" })).toBeVisible();
  expect(screen.queryByRole("columnheader", { name: "Ngày công bố" })).not.toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Chỉ số"), "DXY");
  await waitFor(() => expect(globalThis.fetch.mock.lastCall[0].searchParams.get("codes")).toBe("DXY"));
  await user.selectOptions(screen.getByLabelText("Kỳ dữ liệu"), "monthly");
  expect(await screen.findByRole("heading", { name: "Lạm phát CPI (CPI_YOY)" })).toBeVisible();
  expect(screen.getByText("2026-11-05")).toHaveAttribute("datetime", "2026-11-05");
  expect(screen.getByRole("columnheader", { name: "Ngày cuối kỳ" })).toBeVisible();
  expect(globalThis.fetch.mock.lastCall[0].searchParams.get("codes"))
    .toBe("CPI_YOY,IIP_YOY,EXPORT_USD_BN,IMPORT_USD_BN");
  expect(screen.getByLabelText("Chỉ số")).toHaveValue("");
  expect(screen.queryByRole("option", { name: "Chỉ số USD (DXY)" })).not.toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Chỉ số"), "CPI_YOY");
  await waitFor(() => expect(globalThis.fetch.mock.lastCall[0].searchParams.get("codes")).toBe("CPI_YOY"));
  await user.selectOptions(screen.getByLabelText("Kỳ dữ liệu"), "daily");
  expect(await screen.findByRole("heading", { name: "Chỉ số DXY (DXY)" })).toBeVisible();
  expect(screen.queryByText("2026-11-05")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Chỉ số")).toHaveValue("");
  expect(globalThis.fetch.mock.lastCall[0].searchParams.get("codes")).toBe("USDVND,DXY,SP500,WTI,BRENT,GOLD,US10Y");
});
