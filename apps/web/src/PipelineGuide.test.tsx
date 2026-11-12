import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import PipelineGuide from "./PipelineGuide";

it("offers an unobtrusive semantic pipeline with actual optimization limits", () => {
  const html = renderToStaticMarkup(createElement(PipelineGuide));
  expect(html).toContain("<summary>");
  expect(html).not.toContain("<details open");
  expect(html.match(/<li>/g)).toHaveLength(6);
  for (const text of ["SAM2", "Grounding DINO", "Idol", "seed 42", "exact crop-and-settings", "human supervision", "Appearance is not layout", "unreviewed region proposals", "generated photographs", "scale reference", "no inference"]) {
    expect(html).toContain(text);
  }
});
