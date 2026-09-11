import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createTestQueryClient, withQueryClient } from "@/test/query";

const get = vi.fn();
const getWithTotal = vi.fn();
vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: (...args: unknown[]) => get(...args),
    getWithTotal: (...args: unknown[]) => getWithTotal(...args),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const { MappingStep } =
  await import("@/features/imports/components/MappingStep");

const MAPPING = {
  id: 3,
  data_source_id: 2,
  name: "tracelab-jsonl",
  version: 1,
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  source_format: "jsonl",
  entities: [],
};

function routeGet(mappings: () => Promise<unknown>) {
  // Since #192 the data sources come with their total (`getWithTotal`); the
  // mappings list is an envelope read with `get`.
  getWithTotal.mockImplementation((url: string) => {
    if (url.startsWith("/data-sources"))
      return Promise.resolve({
        data: [{ id: 2, name: "TraceLab", slug: "tracelab" }],
        total: 1,
      });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  get.mockImplementation((url: string) => {
    if (url.startsWith("/data-sources"))
      return Promise.resolve([{ id: 2, name: "TraceLab", slug: "tracelab" }]);
    if (url.startsWith("/mappings?")) return mappings();
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

function renderStep() {
  render(
    <MappingStep
      fileId={null}
      dataSourceId={2}
      mappingId={null}
      onDataSourceChange={vi.fn()}
      onMappingChange={vi.fn()}
    />,
    { wrapper: withQueryClient(createTestQueryClient()) },
  );
}

beforeEach(() => {
  get.mockReset();
  getWithTotal.mockReset();
});

describe("MappingStep load errors", () => {
  it("offers Retry, not a free-text mapping id, when the mappings fail to load", async () => {
    // The bug this pins: any error — a transient 500 — swapped the select for a
    // "Mapping id" input, a fallback meant for backends older than #52.
    let calls = 0;
    routeGet(() =>
      ++calls === 1
        ? Promise.reject(new Error("Internal Server Error"))
        : Promise.resolve({
            items: [MAPPING],
            total: 1,
            limit: 200,
            offset: 0,
          }),
    );
    renderStep();

    const retry = await screen.findByRole("button", { name: "Retry" });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Internal Server Error",
    );
    expect(screen.queryByLabelText(/mapping id/i)).toBeNull();
    expect(screen.getByLabelText("Mapping")).toBeDisabled();

    fireEvent.click(retry);

    expect(
      await screen.findByRole("option", { name: /tracelab-jsonl · v1/ }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.getByLabelText("Mapping")).toBeEnabled();
  });

  it("shows a message even when the error has none", async () => {
    routeGet(() => Promise.reject(new Error("")));
    renderStep();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to load mappings.",
    );
  });
});
