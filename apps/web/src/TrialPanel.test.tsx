import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import TrialPanel from "./TrialPanel";
import type { TrialStatus } from "./api";

const pending: TrialStatus = {
  trial_id: "T01", variant: "optimized", status: "processing", scene: null, report: null,
  definition: {
    title: "Pump room", source: { kind: "generated-photographic-scene", generator: "Model/version not exposed", prompt: "Generated test scene", sha256: "a".repeat(64) },
    expected_inventory: [{ identity: "pump-a", category: "pump", count: 1 }],
    layout_kind: "manual-relative-not-metric",
  },
};

describe("trial evidence panel", () => {
  it("credits real photographs and adaptations without synthetic-input or MIT claims", () => {
    const real: TrialStatus = { ...pending, trial_id: "R01", definition: {
      ...pending.definition,
      source: {
        kind: "licensed-real-photograph", creator: "Test photographer",
        source_page: "https://commons.wikimedia.org/wiki/File:Example.jpg",
        sha256: "a".repeat(64), original_sha256: "b".repeat(64),
        license: "CC-BY-SA-4.0", license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
        derivative_license: "CC-BY-SA-4.0", changes: "Whole-frame resize",
        derivative_changes: "Segmentation and generated geometry, no endorsement.",
        limitations: "Pipework partially occludes the pump.",
      },
    } };
    const html = renderToStaticMarkup(createElement(TrialPanel, { trial: real, onVariant: () => {} }));
    for (const text of ["Test photographer", "CC-BY-SA-4.0", "not the software MIT license", "Whole-frame resize", "partially occludes"]) {
      expect(html).toContain(text);
    }
    expect(html).toContain('href="https://creativecommons.org/licenses/by-sa/4.0/"');
    expect(html).not.toContain("Synthetic photographic input");
  });
  it("labels pending photographic inputs and supervised variants without claiming results", () => {
    const html = renderToStaticMarkup(createElement(TrialPanel, { trial: pending, onVariant: () => {} }));
    expect(html).toContain("processing at snapshot");
    expect(html).toContain("No in-progress objects are published");
    expect(html).toContain("not a real-site photograph");
    expect(html).toContain("supervised workflow comparison");
    expect(html).toContain("Reviewed-box comparison");
    expect(html).not.toContain("Validated / failed");
  });
  it("exposes failures, reuse, measured counts and settings instead of an accuracy score", () => {
    const report: NonNullable<TrialStatus["report"]> = {
      expected_objects: 3, detected_objects: 4, usable_crops: 2, objects_succeeded: 1, objects_failed: 1,
      cache_hits: 1, cache_misses: 1, resumed: 0, independent_generations: 0, seconds_this_run: 12.5,
      supervision: "manual-reviewed-boxes", failure_reason: "trial_objects_failed_or_no_usable_crops",
      rejected: [{ node_id: "object-002", reason: "degenerate_or_tiny_crop" }],
      objects: [{ node_id: "object-001", status: "failed", failure_reason: "cuda_out_of_memory_no_quality_fallback", timing: { seconds: 1 } }],
      settings: { count: 32768, steps: 50, seed: 42, model_pins: {}, sdk_revision: "b".repeat(40) },
    };
    const html = renderToStaticMarkup(createElement(TrialPanel, { trial: { ...pending, status: "partial", report }, onVariant: () => {} }));
    for (const text of ["12.5s", "degenerate_or_tiny_crop", "cuda_out_of_memory_no_quality_fallback", "Counts are not an accuracy score", "seed 42", "not independent reconstructions"]) {
      expect(html).toContain(text);
    }
  });
});
