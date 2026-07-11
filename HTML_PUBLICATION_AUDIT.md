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

The rebuilt page will open with a concise package overview and a reproducible
tour of the repo, then use the full traveler as a case study. Readers can move
from one canonical run into screening, controlled interactions, replication,
boundary expansion, and process-window analysis. The final gate-first decision
then anchors interactive campaign stages, local process-window points,
finalist seeds, and real fill/CMP geometry. The precursor etch/fill explorers
remain as clearly labeled research history. All public claims must be traceable
to the compact publication dataset generated from checkpointed campaign rows.

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
