# Scene Workbench design

The workbench is a light technical drafting desk for preparing digital-twin scenes:
a persistent case library, a large central scene, and a source/evidence inspector.
White panels and cool blue-grey drafting space keep the artifact dominant; blue
denotes selection and primary actions. System typography, thin rules, compact
native controls and explicit status text prioritize operational clarity.

The source and editable scene are peers. Every object remains selectable from
the keyboard-accessible list, with its stable semantic ID and evidence visible.
Routes are illustrative, not live telemetry or a simulation; positions and
dimensions are not engineering-certified. Stable node IDs provide the future
join point for data overlays without claiming a live digital twin today.

At narrower widths the inspector moves below the viewport, then the case
library becomes horizontally scrollable. Reduced-motion preferences pause flow
by default. Empty, missing-source, pipeline failure and rendering failure states
are first-class; no visual substitute claims an unavailable asset succeeded.

Selected-object corrections include editable labels and an explicit review
checkbox; editing never auto-reviews evidence. JSON interchange supports topology
correction without adding a separate drawing mode. Imports validate identity,
references, numeric fields and local asset paths, check the uploaded source hash,
and save with the current revision; source metadata exposes the matching hash.
