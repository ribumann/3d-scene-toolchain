import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, createApi } from "./api";
import type { Scene } from "../../../packages/scene/types";

afterEach(() => vi.unstubAllGlobals());
describe("API contract", () => {
  it("reports a revision conflict without substituting a scene", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "revision mismatch" }), { status: 409 })));
    await expect(api.save("P01", { revision: 3 } as Scene)).rejects.toMatchObject({ status: 409, message: "revision mismatch" });
    expect(fetch).toHaveBeenCalledWith("/api/cases/P01/scene", expect.objectContaining({ method: "PUT", body: '{"revision":3}' }));
  });

  describe("public static demo", () => {
    it("loads the public case catalog and real procedural scene JSON, without using /api", async () => {
      const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response("{}")));
      vi.stubGlobal("fetch", fetchMock);
      const demo = createApi(true);
      await demo.cases();
      for (const id of ["P01", "P02", "P03"]) await demo.scene(id);
      expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
        "/demo/cases.json", "/demo/P01.json", "/demo/P02.json", "/demo/P03.json",
      ]);
    });
    it("rejects all mutations and unavailable references without sending requests", async () => {
      vi.stubGlobal("fetch", vi.fn());
      const demo = createApi(true);
      for (const result of [
        demo.save("P01", { revision: 1 } as Scene),
        demo.upload("I01", new File(["image"], "source.png")),
        demo.start("P01", "idol"), demo.cancel("job"), demo.sourceMetadata("I01"),
      ]) await expect(result).rejects.toMatchObject({ status: 403 });
      for (const id of ["I01", "I02", "I03", "I04", "I05", "G01", "G02", "G03", "../P01"]) {
        await expect(demo.scene(id)).rejects.toMatchObject({ status: 409 });
      }
      await expect(demo.jobs()).resolves.toEqual([]);
      expect(fetch).not.toHaveBeenCalled();
    });
    it("surfaces missing snapshot files rather than substituting an empty scene", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not found", { status: 404 })));
      await expect(createApi(true).scene("P01")).rejects.toMatchObject({ status: 404 });
    });
  });
  it("reports non-JSON HTTP failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("unavailable", { status: 503, statusText: "Unavailable" })));
    await expect(api.scene("I01")).rejects.toBeInstanceOf(ApiError);
    await expect(api.scene("I01")).rejects.toThrow("503 Unavailable");
  });
});
