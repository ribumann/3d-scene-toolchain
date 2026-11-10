import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import type { Scene } from "../../../packages/scene/types";

afterEach(() => vi.unstubAllGlobals());
describe("API contract", () => {
  it("reports a revision conflict without substituting a scene", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "revision mismatch" }), { status: 409 })));
    await expect(api.save("P01", { revision: 3 } as Scene)).rejects.toMatchObject({ status: 409, message: "revision mismatch" });
    expect(fetch).toHaveBeenCalledWith("/api/cases/P01/scene", expect.objectContaining({ method: "PUT", body: '{"revision":3}' }));
  });
  it("reports non-JSON HTTP failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("unavailable", { status: 503, statusText: "Unavailable" })));
    await expect(api.scene("I01")).rejects.toBeInstanceOf(ApiError);
    await expect(api.scene("I01")).rejects.toThrow("503 Unavailable");
  });
});
