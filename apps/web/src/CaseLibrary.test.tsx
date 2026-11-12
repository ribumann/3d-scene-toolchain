import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Case } from "../../../packages/scene/types";
import CaseLibrary from "./CaseLibrary";

describe("case library disclosure groups", () => {
  it("separates real and synthetic comparisons from original inputs and opens a deep-linked group", () => {
    const item = (id: string, input_type: Case["input_type"]): Case => ({
      id, input_type, title: id, summary: "", source_filename: null, prompt: "",
      status: "ready", source_url: null,
    });
    const html = renderToStaticMarkup(createElement(CaseLibrary, {
      cases: [item("I02", "photo"), item("R01-optimized", "photo"), item("T01-baseline", "generated"), item("P01-illustrated", "prompt")],
      caseId: "R01-optimized", busy: false, onSelect: () => {}, statusForCase: () => "Published",
    }));
    const groups = html.match(/<details\b[\s\S]*?<\/details>/g) ?? [];
    expect(groups).toHaveLength(4);
    const real = groups.find(group => group.includes("Real-photo reconstructions"))!;
    expect(real).toContain('open=""');
    expect(real).toContain('aria-current="page"');
    expect(real).toContain("R01-optimized");
    expect(real).not.toContain("T01-baseline");
    expect(real).not.toContain(">I02<");
    expect(groups.filter(group => group.includes('open=""'))).toHaveLength(1);
    expect(groups.find(group => group.includes("Synthetic photo comparisons"))).toContain("T01-baseline");
    expect(groups.find(group => group.includes("Original photos"))).toContain(">I02<");
  });
});
