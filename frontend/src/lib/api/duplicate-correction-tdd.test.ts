import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "./client";

/**
 * PI-17 freezes the API-client boundary for the duplicate-correction UI.  The
 * implementation functions intentionally do not exist yet: these tests are
 * expected to be red until PI-05 adds them.  Keeping the test-only cast here
 * lets the contract describe the future client surface without adding a
 * production stub that could accidentally be mistaken for implementation.
 */
type DuplicateCorrectionClient = {
  getDuplicateCorrections: () => Promise<{ items: unknown[] }>;
  createDuplicateCorrection: (payload: {
    canonicalTransactionId: number;
    duplicateTransactionId: number;
  }) => Promise<unknown>;
  reverseDuplicateCorrection: (correctionId: number) => Promise<unknown>;
};

const duplicateClient = client as unknown as DuplicateCorrectionClient;

function mockFetch(payload: unknown) {
  const fetchMock = vi.fn(async () => ({
    ok: true,
    status: 200,
    statusText: "OK",
    json: async () => payload,
  })) as unknown as typeof fetch;
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock as unknown as ReturnType<typeof vi.fn>;
}

afterEach(() => vi.unstubAllGlobals());

describe("PI-17 duplicate-correction API client contract", () => {
  it("lists relationships so Activity can render durable labels and reversal context", async () => {
    const fetchMock = mockFetch({
      items: [
        {
          id: 9001,
          canonical_transaction_id: 101,
          duplicate_transaction_id: 102,
          status: "active",
        },
      ],
    });

    const response = await duplicateClient.getDuplicateCorrections();

    expect(response).toEqual({
      items: [
        {
          id: 9001,
          canonical_transaction_id: 101,
          duplicate_transaction_id: 102,
          status: "active",
        },
      ],
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String((fetchMock.mock.calls[0] as unknown[])[0])).toContain(
      "/duplicate-corrections",
    );
  });

  it("posts the explicit canonical and duplicate IDs, not a local-only selection", async () => {
    const fetchMock = mockFetch({
      id: 9001,
      canonical_transaction_id: 101,
      duplicate_transaction_id: 102,
      status: "active",
    });

    await duplicateClient.createDuplicateCorrection({
      canonicalTransactionId: 101,
      duplicateTransactionId: 102,
    });

    const [input, init] = fetchMock.mock.calls[0] as [RequestInfo | URL, RequestInit];
    expect(new URL(String(input)).pathname).toContain("/duplicate-corrections");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(String(init.body))).toEqual({
      canonical_transaction_id: 101,
      duplicate_transaction_id: 102,
    });
  });

  it("reverses by correction ID through the durable endpoint", async () => {
    const fetchMock = mockFetch({ id: 9001, status: "reversed" });

    await duplicateClient.reverseDuplicateCorrection(9001);

    const [input, init] = fetchMock.mock.calls[0] as [RequestInfo | URL, RequestInit];
    expect(new URL(String(input)).pathname).toContain("/duplicate-corrections/9001");
    expect(init.method).toBe("DELETE");
    expect(init.body).toBeUndefined();
  });
});
