import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("archive API contract", () => {
  it("requests the existing include_archived list and PATCHes archived=false for restore", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, statusText: "OK", json: async () => [], text: async () => "" });
    vi.stubGlobal("fetch", fetchMock);
    await api.listConversations(true);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/conversations?include_archived=true");
    await api.archiveConversation("c%1", false);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/conversations/c%251");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ archived: false });
  });
});
