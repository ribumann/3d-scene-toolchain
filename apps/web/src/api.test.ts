import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, createApi } from "./api";
import type { Scene } from "../../../packages/scene/types";

const sha256 = "0".repeat(64);
const quality = { version: 1, assets: { [sha256]: {
  sha256, status: "accepted", render_bounds: { min: [-1, -1, -1], max: [1, 1, 1] }, reasons: [],
} } };

afterEach(() => vi.unstubAllGlobals());
describe("API contract", () => {
  it("reports a revision conflict without substituting a scene", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "revision mismatch" }), { status: 409 })));
    await expect(api.save("P01", { revision: 3 } as Scene)).rejects.toMatchObject({ status: 409, message: "revision mismatch" });
    expect(fetch).toHaveBeenCalledWith("/api/cases/P01/scene", expect.objectContaining({ method: "PUT", body: '{"revision":3}' }));
  });

  describe("public static demo", () => {
    it("loads the public case catalog and real procedural scene JSON, without using /api", async () => {
      const fetchMock = vi.fn().mockImplementation((path: string) => Promise.resolve(new Response(
        path.endsWith("cases.json") ? "[]" : JSON.stringify({ case_id: path.match(/(P0[1-3])\.json/)?.[1], assets: [] }),
      )));
      vi.stubGlobal("fetch", fetchMock);
      const demo = createApi(true);
      await demo.cases();
      for (const id of ["P01", "P02", "P03"]) await demo.scene(id);
      expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
        "/demo/cases.json", "/demo/P01.json", "/demo/P02.json", "/demo/P03.json",
      ]);
    });
    it("rejects all mutations and unpublished reconstructions without sending requests", async () => {
      vi.stubGlobal("fetch", vi.fn());
      const demo = createApi(true);
      for (const result of [
        demo.save("P01", { revision: 1 } as Scene),
        demo.upload("I01", new File(["image"], "source.png")),
        demo.start("P01", "idol"), demo.cancel("job"), demo.sourceMetadata("I01"),
      ]) await expect(result).rejects.toMatchObject({ status: 403 });
      for (const id of ["I01", "I02", "I03", "I04", "I05", "G01", "G02", "G03", "../P01"]) {
        await expect(demo.scene(id)).rejects.toMatchObject({ status: 409, message: expect.stringContaining("no reconstructed 3D scene is published") });
      }
      await expect(demo.jobs()).resolves.toEqual([]);
      expect(fetch).not.toHaveBeenCalled();
    });
    it("surfaces missing snapshot files rather than substituting an empty scene", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not found", { status: 404 })));
      await expect(createApi(true).scene("P01")).rejects.toMatchObject({ status: 404 });
    });
    it("keeps processing sources reference-only while completed sources remain inspectable", async () => {
      vi.stubGlobal("fetch", vi.fn().mockImplementation((path: string) => Promise.resolve(new Response(JSON.stringify(
        path.endsWith("cases.json") ? [{ id: "I01", status: "ready" }, { id: "I02", status: "awaiting_input" }] :
          path.endsWith("pilots.json") ? [{ case_id: "I02", status: "processing", scene: null, objects: 0 }] :
            { case_id: "I01", assets: [] },
      )))));
      const demo = createApi(true);
      await demo.cases();
      await expect(demo.pilots()).resolves.toEqual([{ case_id: "I02", status: "processing", scene: null, objects: 0 }]);
      await expect(demo.scene("I01")).resolves.toMatchObject({ case_id: "I01" });
      await expect(demo.scene("I02")).rejects.toMatchObject({ status: 409 });
      expect(vi.mocked(fetch).mock.calls.every(([path]) => !String(path).startsWith("/api/"))).toBe(true);
    });
    it("loads only catalog-approved pilot scenes and maps approved PLY paths without /api requests", async () => {
      const fetchMock = vi.fn().mockImplementation((path: string) => Promise.resolve(new Response(JSON.stringify(
        path.endsWith("cases.json") ? [{ id: "I02", status: "ready" }] : path.endsWith("quality.json") ? quality :
          { case_id: "I02", assets: [{ id: "idol-object-000", sha256, uri: "/api/assets/pilot/I02/object-000.ply" }] },
      ))));
      vi.stubGlobal("fetch", fetchMock);
      const demo = createApi(true);
      await demo.cases();
      const scene = await demo.scene("I02");
      expect(scene.assets[0].uri).toBe("/pilot-assets/pilot/I02/object-000.ply");
      expect(scene.assets[0].provenance.geometry_quality).toEqual(quality.assets[sha256]);
      expect(fetchMock.mock.calls.map(call => call[0])).toEqual(["/demo/cases.json", "/demo/I02.json", "/demo/quality.json"]);
      await expect(demo.scene("I03")).rejects.toMatchObject({ status: 409 });
    });
    it("rejects unpublished asset paths rather than loading a backend or external resource", async () => {
      const fetchMock = vi.fn().mockImplementation((path: string) => Promise.resolve(new Response(JSON.stringify(
        path.endsWith("cases.json") ? [{ id: "I02", status: "ready" }] :
          { case_id: "I02", assets: [{ uri: "/api/assets/private/original.png" }] },
      ))));
      vi.stubGlobal("fetch", fetchMock);
      const demo = createApi(true);
      await demo.cases();
      await expect(demo.scene("I02")).rejects.toMatchObject({ status: 422 });
    });
    it("loads only approved trial variants with isolated static appearance paths", async () => {
      vi.stubGlobal("fetch", vi.fn().mockImplementation((path: string) => Promise.resolve(new Response(JSON.stringify(
        path.endsWith("quality.json") ? quality : path.endsWith("cases.json") ? [{ id: "T01-baseline", status: "ready" }, { id: "T01-optimized", status: "awaiting_input" }] :
          path.endsWith("trials.json") ? [{ trial_id: "T01", variant: "optimized", status: "not_run", scene: null }] :
            { case_id: "T01-baseline", assets: [{ sha256, uri: "/api/assets/trials/T01/baseline/object-000.ply" }] },
      )))));
      const demo = createApi(true);
      await demo.cases();
      await expect(demo.scene("T01-baseline")).resolves.toMatchObject({ assets: [{ uri: "/trial-assets/T01/baseline/object-000.ply" }] });
      await expect(demo.scene("T01-optimized")).rejects.toMatchObject({ status: 409 });
      await expect(demo.trials()).resolves.toMatchObject([{ status: "not_run" }]);
      expect(vi.mocked(fetch).mock.calls.every(([path]) => !String(path).startsWith("/api/"))).toBe(true);
    });
    it("loads catalog-approved real-photo splats but rejects cross-case asset substitution", async () => {
      let uri = "/api/assets/trials/R03/optimized/object-001.ply";
      vi.stubGlobal("fetch", vi.fn().mockImplementation((path: string) => Promise.resolve(new Response(JSON.stringify(
        path.endsWith("quality.json") ? quality : path.endsWith("cases.json") ? [{ id: "R03-optimized", status: "ready" }] :
          { case_id: "R03-optimized", assets: [{ sha256, uri }] },
      )))));
      const demo = createApi(true);
      await demo.cases();
      await expect(demo.scene("R03-optimized")).resolves.toMatchObject({ assets: [{ uri: "/trial-assets/R03/optimized/object-001.ply" }] });
      uri = "/api/assets/trials/R01/optimized/object-001.ply";
      await expect(demo.scene("R03-optimized")).rejects.toMatchObject({ status: 422 });
      await expect(demo.scene("R03-baseline")).rejects.toMatchObject({ status: 409 });
    });
    it("refuses an appearance whose content hash has no quality assessment", async () => {
      vi.stubGlobal("fetch", vi.fn().mockImplementation((path: string) => Promise.resolve(new Response(JSON.stringify(
        path.endsWith("cases.json") ? [{ id: "I02", status: "ready" }] :
          path.endsWith("quality.json") ? { version: 1, assets: {} } :
            { case_id: "I02", assets: [{ sha256, uri: "/api/assets/pilot/I02/object-000.ply" }] },
      )))));
      const demo = createApi(true);
      await demo.cases();
      await expect(demo.scene("I02")).rejects.toMatchObject({ status: 422, message: expect.stringContaining("hash-bound") });
    });
  });
  it("reports non-JSON HTTP failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("unavailable", { status: 503, statusText: "Unavailable" })));
    await expect(api.scene("I01")).rejects.toBeInstanceOf(ApiError);
    await expect(api.scene("I01")).rejects.toThrow("503 Unavailable");
  });
});
