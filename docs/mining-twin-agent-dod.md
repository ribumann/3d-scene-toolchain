# Mining twin: agent execution contract and Definition of Done

Extend [ribumann/fabrictritwin](https://github.com/ribumann/fabrictritwin), not a
new application estate. Deliver a hosted, Fabric-connected D01 diamond recovery
twin using the existing capacity, hosting and identity foundations. This document
defines future implementation acceptance; it does not claim that work is done.

Use the [D01 functional specification](diamond-plant-demo.md) for all 56 sensor
definitions, generation formulas, scenarios, calculations, thresholds and query
contracts, and the [plant handoff](diamond-plant.md) for geometry and provenance.
Use the [two-mode integration contract](digital-twin-integration.md#d01-two-visual-modes-one-twin)
for clean and photo-reconstructed appearances of the same operational twin.
Keep that specification as the single detailed domain reference; do not copy it
into another large design document.

## Agent operating instructions

1. Read target-repository instructions and current source before editing.
   The reviewed reference is `fabrictritwin` main at
   `580bac50eb6203eddca07ec11b96cb7e330c7a62`; reconcile later changes.
2. Discover the authorized existing deployment read-only. Source files and
   historical release notes are not a current cloud inventory. Resolve exact
   tenant/subscription, capacity/workspace/items, serving apps/revisions,
   identities, connection boundaries and release environments privately.
3. Implement the smallest vertical slice: catalog -> bounded simulator ->
   existing Eventstream -> Eventhouse -> existing backend -> Cockpit. Then add
   scenarios, incidents and the grounded assistant. Test locally without cloud
   credentials before approved live writes. Keep overlapping changes together.
4. Automate repeatable setup, deployment, verification and demo start/stop.
   Use supported APIs/scripts and existing protected workflows. Human consent,
   environment approvals and target authorization remain human gates, not things
   to bypass. A required unavailable permission is `BLOCKED`, not a new account,
   replacement resource or simulated success.
5. Continue until every required gate below passes. Record `PASS`, `FAIL`,
   `BLOCKED` or `NOT_RUN` with evidence for each; never equate a merged PR,
   successful send or healthy HTTP endpoint with a working digital twin.

## Non-negotiable reuse and change budget

| Surface | Required approach |
| --- | --- |
| Capacity and workspace | Reuse the selected existing Fabric capacity and workspace. Do not buy, resize or create another capacity, trial or workspace. Coordinate any approved active window; never pause shared capacity to stop this demo. |
| Hosting | Extend `apps/cockpit`, `apps/streaming-backend`, `apps/simulator` and, where needed, `apps/mcp-tools`. Reuse Container Apps environment, ACR, domains/TLS, logging and simulator runtime. No second UI host, backend estate, registry or resource group. Leave the existing deployed legacy Console alone. |
| Fabric data path | Extend the existing Eventstream custom endpoint and Eventhouse/KQL database with namespaced mining routing, tables and functions. Preserve triathlon routes and schemas. The custom endpoint's backing hub is Fabric-managed: do not provision Azure Event Hubs or IoT Hub. |
| Identity and secrets | Preserve Entra gates, workload identities, native Container Apps secret references and least privilege. Current runtime secrets are not assumed to be read from Key Vault merely because a vault exists. Do not introduce a secret manager, API keys, broad roles or browser credentials. |
| AI and presentation | Reuse existing Foundry/model/MCP and Fabric data-agent foundations where authorized. Extend instructions/tools with explicit domain scope. Reuse an existing appropriate dashboard/queryset, or add at most one justified mining dashboard. No new AI project/model hosting, agent fleet, Power BI stack or mandatory embedding path. |
| State and extras | Prefer existing runtime/storage capabilities. No Redis, new storage account, Lakehouse copy, notebook/Spark pipeline, warehouse or new twin service just for this demo. Do not introduce a general framework to support one domain extension. |

Maintain a small **change ledger**: logical target, reused/modified/new, reason,
automation entry point, permission/cost impact and rollback. Tables, stream
nodes, functions and an unavoidable Fabric item count as additions, even when
they reuse a capacity. Any departure from the budget needs explicit approval
before creation; do not silently substitute a different endpoint or tenant.

The target repository's `scripts/provision/provision-all.ps1` is not an
existing-environment deployment shortcut. Prefer additive, exact-target
reconciliation with dry-run/plan and idempotent re-execution. Do not enable
quarantined workflows. Existing image-update scripts preserve non-image settings;
new routes/configuration require a separately scoped overlay, not a reprovision.

## Required acceptance gates

### G1. Existing deployment is identified and preserved

- [ ] Record the exact private resource manifest and a redacted before/after
  change ledger. Confirm capacity/workspace assignment and actual serving
  revisions; resolve authorization and feature prerequisites before writes.
- [ ] Baseline triathlon session/race, analyses/alerts, Cockpit and applicable
  assistant behavior. After deployment, prove these paths still work without
  mining rows leaking into athlete queries or athlete data entering mining views.
- [ ] No unapproved infrastructure addition, identity change, schedule,
  ingress/auth relaxation, custom-domain change or tenant-setting change.
  Preserve unrelated workloads, secret references and existing data/retention.

### G2. One versioned, joinable plant contract

- [ ] Import the D01 catalog with exactly 24 modules, 64 equipment children,
  50 directed streams and 56 numeric tags. Preserve stable IDs, units,
  coordinates, sizes, ports and parent relationships; reject dangling references.
  Pin source asset/catalog revisions and hashes, including redistribution terms.
- [ ] Package both the authored GLBs/site plan and the approved reconstructed
  Gaussian assets with their exact receipts and quality report. Do not import
  the reconstruction GPU toolchain or generate assets in the operational app.
  Identify clean meshes as authored and reconstructed appearance as single-image
  approximation; dimensions remain demo assumptions in both modes.
- [ ] Implement and validate the version-2 numeric envelope, state events and
  ingestion mappings. Explicitly migrate/version the strict version-1 contract;
  test old consumers and the Eventstream `entityType` discriminator separately.
  Prefix mining tables/functions if necessary rather than renaming athlete data.

### G3. A bounded, correlated simulator, not random dashboards

- [ ] Implement the referenced fixed-seed, 5-second internal model and 30/60-second
  publication profile. In an uninterrupted 20-minute measurement window require
  **2,020 numeric events + 80 state heartbeats**, plus separately counted sparse
  transitions. Batch every 30 seconds; default duration 20 minutes, hard stop 30.
  No one-second publishing, accelerated future timestamps or always-on schedule.
- [ ] Prove load/flow delays, shared-water bookkeeping, inventory constraints,
  power and cumulative product counter behave as specified. Invalid/non-finite
  readings fail explicitly; normal bands must not clamp away faults.
  Fixed seeds and start time reproduce values; retries preserve event IDs.
- [ ] Provide repeatable start, status, cancel/reset and scenario selection with
  a run ID. Reject a concurrent run for the same plant; reject unbounded durations.
  Account for the actual replica/revision/job topology and restart/rollout.
  Existing locks are process-local and the live backend permits three replicas:
  a single-process unit test is not environment-wide admission proof.
- [ ] Choose one existing execution surface and prove one authoritative sender.
  Reuse an available durable coordination mechanism, or obtain approval for a
  scoped single-executor/drain arrangement. Do not add a coordination service
  by default or alter shared backend scaling without review. Uncertain start/
  delivery outcomes are reconciled by run/event ID, never blindly retried.

### G4. Actual Eventstream-to-Eventhouse ingestion

- [ ] Add mining filters/derived streams and JSON mappings without replacing
  `SessionMetric` or `RaceSplit`. Observe source, default, mining derived nodes
  and destinations in the actual topology. The current resume helper recognizes
  only the original two derived streams: extend its validation/tests narrowly
  if used; never bypass unexpected-topology failures.
- [ ] Query the intended Eventhouse for the same generated run. Report generated,
  accepted, ingested and deduplicated counts, all 56 tag IDs, missing/bad/rejected
  counts, event-time range and fresh ingestion times. In a no-gap run, all expected
  logical events must be queryable within 120 seconds of the final batch; report
  lag and fail this gate if missing, rather than hide loss behind HTTP success.
- [ ] Prove duplicate retries do not duplicate logical samples/totals and invalid
  events are rejected/quarantined with reasons. A SAS send acknowledgment,
  WebSocket frame, aggregate `asOf`, direct Kusto backfill or a synthetic local
  response is not ingestion evidence.
- [ ] Apply raw 7-day / alert 30-day retention only to owned mining tables.
  No full database retention changes or unnecessary permanent raw archive.

### G5. Correct analytics and incident lifecycle

- [ ] Install/test the five bounded query contracts in the functional spec:
  `PlantLatest`, `PlantSummary`, `AssetTrend`, `ActiveIncidents`, `CompareLines`.
  Cover all six specified insight families, with catalog-first unknown readings,
  explicit state, UTC windows, units, coverage and source timestamps.
- [ ] Verify units/integrals with deterministic fixtures: nominal 120 t/h for
  10 completed minutes gives 20 t; 234 m3/h gives 39 m3; 203 kW gives 33.833 kWh.
  Gross process-water and energy intensities are 1.95 m3/t and about 1.692 kWh/t
  for that common interval. Do not double-count the hopper or claim fresh-water
  use, per-line metered energy, ore grade, recovery efficiency or OEE.
- [ ] Test gaps, bad quality, startup, stopped/planned state, duplicate/out-of-order
  arrivals and counter resets. Ratios require at least 90% common coverage and
  return unknown below 10 t/h. Screen excitation never triggers crusher limits.
- [ ] Implement all five incident rules with specified holds, hysteresis,
  startup suppression, deduplication, escalation, raise/clear and separate ack.
  Missing data leaves a process incident unverified, not cleared.
  Stateful transitions must survive evaluation retries; no row/email per poll.
- [ ] Run B bearing, C DMS, shared water and the communication-gap scenario.
  Assert each expected affected asset, transition and delayed impact, including
  reset/recovery. The gap yields unknown/stale, not a fabricated process stop.
  Validate the water scenario's roughly 7.4-minute drawdown, not an impossible
  instantaneous tank loss. Use one approved notification route; prove repeat
  evaluation does not spam. Keep scenario truth out of measurement/AI evidence.

### G6. Hosted Cockpit works as the mining twin

- [ ] Add a mining entry/view in the existing Cockpit, preserving triathlon and
  exact `DEMO_PROFILE` semantics. Generated data travelling through Fabric is
  live-connected simulation, not the in-memory `synthetic` bypass.
- [ ] Deliver the specified four KPIs, 3D/top plant view, line/utility visibility,
  top-three incident rail, equipment drawer and two focused comparison charts.
  Clicking an incident selects the correct module, evidence and time series.
  Include readable list/keyboard/mobile access and non-color status labels.
- [ ] Offer **Visual model: Clean / Reconstructed**, defaulting to Clean, using
  one catalog and operational state. Render all 24 clean modules; the current
  reconstructed publication has ten accepted concepts across twenty placements,
  with the three DMS placements and hopper hidden by exact-hash screening.
  Keep all 24 semantic modules and their data selectable. Review-only visibility
  never accepts exclusions or bypasses invalid bounds; no silent mesh/proxy
  replacement for excluded or failed splats.
- [ ] Verify scale/orientation, grounded aspect-preserving Gaussian fit and shared
  source instancing against the integration contract. Retain module selection,
  incident focus, camera target, line/utility filters, run and time window when
  switching mode. Mode changes must not restart simulation, duplicate queries
  or leak inactive renderer resources. Prove explicit load-error handling and
  keyboard/mobile/list access in both modes.
- [ ] Show measured
  status, units, sample time and quality; no fabricated tags or flow animations
  claiming measurements where no meter exists. Missing/bad/stale is never green.
- [ ] Query real Fabric through the existing authenticated service boundary.
  Enforce plant/run authorization separately from athlete mappings, parameterized
  allowlisted queries, 24-hour/1,000-row/1 MB/10-second limits and explicit errors.
  Retain private backend/MCP boundaries; no unrestricted public KQL endpoint.
- [ ] Demonstrate consolidated 30-second latest / 60-second chart/alert refresh,
  15-second request reuse, hidden-tab pause and replay without live polling.
  A public demo view must not expose private athlete data or unrestricted
  start/admin controls. Apply bounded authorized admission, not anonymous cost.

### G7. One grounded, read-only assistant

- [ ] Extend existing assistant/tool/data-agent paths with mining-scoped catalog,
  curated queries and incident evidence. Verify current feature availability,
  permissions and any human delegated consent; old anonymous MCP evidence does
  not prove native Fabric Data Agent access.
- [ ] Exercise the four reference questions against the actual run. Answers
  include window, IDs, units, supporting values, coverage and inspectable query
  evidence; distinguish correlation from cause. Test missing-data, foreign-plant
  and attempted-control requests: no inventions, data leakage or plant writes.
- [ ] Where native Fabric agent chat cannot be embedded through a supported API,
  provide a working authenticated native-agent link and retain the existing
  grounded MCP/assistant path if available. Do not create a replacement AI
  estate. If no approved grounded path works, mark this required gate `BLOCKED`;
  the dashboard can be delivered, but the complete twin is not done.

### G8. Automated release, live proof and safe stop

- [ ] Run the target repository's applicable build, Vitest, ESLint, formatting,
  Pester and image checks; compile changed Bicep only if applicable. Use existing
  CI, focused regression tests and dependency locks, not a new testing platform.
- [ ] Provide idempotent plan/apply/verify for mining-owned Fabric/configuration
  changes; a second apply produces no duplicate items, rules or permissions.
  Apply only under the exact authorized scope and supported protection gates.
- [ ] Publish immutable app digests and deploy through the existing main-only,
  protected `azure-build` / `azure-deploy` lanes. Record source SHA, publication
  run/digest and actual traffic-serving revision for every changed workload.
  Image publication, deployment and live acceptance are separate gates.
- [ ] Execute a real hosted normal run plus the four scenario checks above.
  Correlate run ID across sender, Eventhouse, API, incidents, UI and assistant.
  Include a hosted screenshot/browser result and redacted query aggregates.
  Mock/local screenshots or historical release evidence cannot replace this.
- [ ] Stop/cancel and verify no new mining events after one in-flight 30-second
  batch, no orphan sender and no mining-owned background evaluation/polling.
  Reopening a view must not restart a run. Do not stop triathlon services or pause
  shared capacity; coordinate any shared evaluator/capacity ownership explicitly.
- [ ] Verify the scoped rollback: previous approved images/config plus removal
  or disabling of only mining-owned routes/rules. No estate-wide teardown,
  destructive data reset or blind retry after an uncertain deployment write.

## Small, auditable handoff

Keep only these durable implementation outputs in `fabrictritwin`, following its
existing layout:

- Code, schemas, KQL and automated setup/deploy/verify commands with focused tests.
- One short mining runbook: entry URL, prerequisites, start/scenario/stop,
  error recovery and rollback. Add links to existing README/operations docs,
  rather than another architecture/manual per service.
- One redacted acceptance record and machine-readable result manifest containing
  each gate's status, source/assets/digests, workflow references, run IDs,
  count/lag/coverage assertions, evidence locations and known blockers. Keep
  exact cloud IDs, raw private responses and secrets in approved private storage.

**Completion predicate:** G1-G8 pass with reproducible evidence, the code is
merged, and the actual hosted app demonstrates simulator -> Eventstream ->
Eventhouse -> queried insights/incidents -> plant UI and grounded assistant on
the existing foundations. Report the working entry point, what was reused/
added and how to stop it. Human UAT/consent remains explicitly human-owned;
never mark it passed on someone's behalf. A platform or approval blocker must
name the failed gate, precise missing prerequisite and safe next action.

## Repository learnings to retain

Read these current target-repository sources, rather than inferring the deployed
estate from templates:
[release architecture](https://github.com/ribumann/fabrictritwin/blob/580bac50eb6203eddca07ec11b96cb7e330c7a62/docs/release-architecture.md),
[runtime operations](https://github.com/ribumann/fabrictritwin/blob/580bac50eb6203eddca07ec11b96cb7e330c7a62/docs/live-runtime-operations.md),
[hosted profiles](https://github.com/ribumann/fabrictritwin/blob/580bac50eb6203eddca07ec11b96cb7e330c7a62/docs/hosted-runtime-profiles.md),
[release automation](https://github.com/ribumann/fabrictritwin/blob/580bac50eb6203eddca07ec11b96cb7e330c7a62/scripts/deploy/README.md)
and [Eventstream recovery](https://github.com/ribumann/fabrictritwin/blob/580bac50eb6203eddca07ec11b96cb7e330c7a62/scripts/fabric/README.md).
Some older inventory/contributor prose predates active CI/OIDC release lanes:
check current workflows and real environment protections instead of treating
either dated documentation or an environment name as authorization.
