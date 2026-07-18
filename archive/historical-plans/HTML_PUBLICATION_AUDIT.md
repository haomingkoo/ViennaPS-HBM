# HTML publication audit

## Decision

The current explainer is visually coherent and unusually candid about earlier
retractions, but it is no longer an accurate front door to the project. It
predates the controlled full-traveler campaign and gives precursor etch studies
more authority than the final gate-first evidence supports.

## Scientific issues to correct

1. The title and opening frame the project as “Bosch etch + Cu fill.” The final
   study covers pattern, Bosch etch, liner, barrier/seed, fill, and CMP.
2. “Adopted as production” overstates an uncalibrated simulation result. The
   page must say “earlier etch reference” and keep the no-fab-calibration limit
   visible.
3. The spec table marks etch as a general success. Only selected replicated
   finalists pass pattern through barrier; the broad space contains many etch
   failures.
4. “All four real knobs” and “the only two real continuous knobs” confuse the
   currently wired wrapper space with the complete ViennaPS API. The audited
   registry contains 17 wired recipe factors plus unwired numerical, structural,
   and model controls.
5. The fill and CMP ceiling language is too broad. The supported conclusion is
   a ceiling of the tested constant-vector fill and isotropic-removal model
   forms, not physical impossibility.
6. The page omits the strongest evidence: shared upstream geometries, hard CMP
   mask gates, 16-seed confirmations, the 3^4 process-window map, p90/worst-case
   ranking, and the final Pareto alternatives.
7. Earlier interactive explorers use precursor grids. They remain useful only
   when labeled as precursor evidence, not the final recipe search.

## Narrative and copy issues

- The current opening explains background before giving the research decision.
- Several headings argue with older versions of the page instead of helping a
  new reader understand the evidence.
- Repeated “not X” constructions and “production” language make the prose feel
  defensive and less precise than the final research record.
- The report needs separate language for observation, interpretation, model
  limitation, and next experiment.

## Visual and interaction issues

- The page has good native typography, contrast-aware themes, keyboard-visible
  range controls, and reduced-motion support.
- The repeated panel treatment flattens the hierarchy. The final decision,
  campaign history, process-window map, and visual failure reads need distinct
  rhythms.
- The amber side-stripe callout is a generic alert treatment and should become
  a full bordered evidence note.
- Interactions should expose exact sampled recipes and seeds. No interpolation
  or decorative animation should be added.
- Every chart and geometry must have a written visual read for readers who
  cannot rely on color or image inspection.

## Rewrite standard

The rebuilt page opens with a concise package overview and a reproducible tour
of the repo, then uses the complete process as a case study. Readers can move
from one simulation into screening, controlled comparisons, replication,
boundary expansion, and nearby-recipe analysis. Public claims are traceable to
the compact publication dataset generated from saved campaign rows.

## Post-rewrite technical audit

| Dimension | Source-level score | Current read |
|---|---:|---|
| Accessibility | 3/4 | Semantic sections, labeled range inputs, keyboard-operable sampled points, 44px controls, focus states, alt text, reduced motion. Rendered contrast and zoom still require browser verification. |
| Performance | 4/4 | One standalone document, no runtime dependencies or network requests, compact embedded campaign data and two evidence images. |
| Responsive design | 3/4 | Single-column fallbacks, scrollable tables, fluid SVGs, and mobile process-flow changes are present. Real viewport QA remains pending. |
| Theming | 3/4 | Tokenized light/dark palettes and system preference support. The embedded white-background evidence images need a rendered dark-mode read. |
| Anti-patterns | 3/4 | The generic eyebrow, side-stripe alert, tiny labels, missing image sources, and stale hero framing were removed. Numbered precursor findings remain intentionally because sequence is evidence. |
| **Total** | **16/20** | **Good at source level; rendered audit still required before publication.** |

The deterministic detector's remaining “em dash” warning comes from required
CLI flags such as `--replicates`, not prose. Its numbered-section advisory is
also accepted: the labels encode research order and retractions. The remaining
flat-type warning is driven mainly by compact SVG chart labels; it cannot be
accepted or rejected without the browser visual pass.

### Corrections made during the audit

- Reframed the page as a repository tutorial, full-traveler case study, and
  simulation-learning report.
- Added exact campaign, process-window, finalist-seed, and geometry evidence.
- Replaced “production” and whole-API claims with scoped model-language.
- Corrected the wired recipe-factor count from 18 to 17 and added a code-derived
  regression guard.
- Added generation hypotheses, designs, results, and next experiments.
- Added accessibility semantics and tests for all interactive controls.

### Plain-language and interaction audit

A reader review exposed three problems that source-level checks missed:

- Internal terms such as “audited wired model space,” “canonical traveler,”
  and “robust miss” obscured simple ideas. They were replaced with physical
  process names and direct explanations.
- The managed-loss history joined scores from different experiments and made a
  deliberate destructive boundary test look like research regression. The
  chart was removed. Nine selectable experiment summaries now show the
  question, simulation count, finding, and next move.
- The precursor explorers were partially synchronized and failed to draw in
  the deployed page. They were removed from the public reading path. The
  81-recipe explorer remains because all four sliders select one saved recipe
  and update one consistent readout.

The CMP failure image now marks its blank panel explicitly: excessive isotropic
removal deleted every visible modeled material, including the mask. The result
and finalist sections explain failure using measured Cu-gap and CMP-recess
ranges rather than abstract score language.

## Interim foundation update, 2026-07-12

### Editorial decision

The public page now leads with the active investigation. The 1,948-run campaign
remains below it as clearly labeled history. Its withdrawn pass labels no
longer control the opening claim or process recommendation.

Each current finding has three separate fields:

- observation: the measured result;
- interpretation: what that result supports and what it does not support;
- process move: the next knob, direction, tradeoff, and validation needed.

This structure removes the earlier failure mode where a result table asked the
reader to infer the analysis.

### Evidence bound into the page

The compact interim dataset contains 328 unique foundation simulations and 336
reviewed logical cells, including eight exact parent reuses. Seven reviewed
summary files are bound by SHA-256. The page now reports:

- the four-seed, cycle-13 Bosch handoff geometry;
- numerical qualification and baseline failures for liner and barrier/seed;
- the failed candidate Cu law and successful prescribed bottom-up control;
- the 168-case coarse Cu transport surface;
- the 128-cell grid, ray-count, and reflection confirmation;
- the next justified lower-sticking boundary;
- the CMP connectivity rule and why its recipe DOE remains blocked.

The Cu explorer uses the exact 42 coarse tier cells. It does not interpolate.
The newer sticking 0.0125 confirmation is shown as a separate result because it
uses a different numerical design and sits outside the plotted range.

### Language audit

The copy now uses physical questions and process actions instead of phrases such
as “audited wired model space,” “canonical traveler,” “compliant traveler,” and
“model-limited miss.” Internal geometry tiers are displayed as the 1.25-deep
target via and the 3.0-deep stress case. “Foundation audit” is defined on the
page as measurement and controlled failure testing before another broad DOE.

### Verification status

- publication data guard: pass;
- Python compilation: pass;
- embedded JavaScript syntax: pass;
- duplicate IDs, form labels, image sources, and alt text: pass;
- locally served HTML byte-for-byte matches the generated file;
- in-app rendered audit: pending because the browser runtime exposed no browser
  instance during this update.

The page must not be described as visually audited until a browser instance is
available for desktop, mobile, light, dark, and keyboard checks.

## Completed screening-traveler update, 2026-07-17

### Editorial decision

The completed screening traveler is now the lead result. The report opens with
the measured outcome, the five saved geometry stages, the acceptance table, and
the limit of the claim. Earlier foundation checks and failed campaigns remain
below it as methods and research history.

### Evidence added

- the exact `aac0e99de49584cc` etched geometry at 500-ray screening fidelity;
- conformal liner and barrier/seed gate decisions;
- zero open or closed Cu voids and 0.17056 minimum overburden;
- field-clear endpoint CMP, a connected plug, a continuous stop, and zero dish;
- SHA-256 provenance for the source etch and final CMP domains;
- the complete five-panel traveler rendered from native ViennaPS checkpoints.

The page calls the downstream stages morphology controls. It does not describe
them as calibrated deposition, plating, or CMP recipes. The 2,000-ray etch
confirmation is recorded as deferred.

### Verification status

- publication data guard: pass;
- Gate-0 publication checkpoint guard: pass;
- Python compilation: pass;
- embedded JavaScript syntax: pass;
- rendered desktop/mobile audit: pending because no browser instance was
  available in this session.
