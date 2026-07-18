# Model-factor range research

Status: factor meanings and API domains researched; transferable recipe ranges
are not established.

## Main finding

The active repository uses normalized model controls. ViennaPS documentation
and primary papers explain what many controls mean, but they do not provide
low/nominal/high values that can be transferred into this geometry as a fab
recipe. Existing repository ranges remain internal model-space history until a
new range-finding study verifies their response and numerical stability.

The queries, access dates, applicable geometry, evidence status, and unresolved
searches are recorded in [`range-research-log.json`](range-research-log.json).

## Bosch etch

The official simplified ViennaPS Bosch example provides example points—not a
qualified range—for etch duration, neutral and ion coefficients, sticking,
passivation amount, ion directionality, and reflection angle. The
`MultiParticleProcess` documentation supplies mathematical domains: sticking is
a probability, and the ion exponent describes a power-cosine arrival
distribution. A primary Bosch simulation paper uses physical fluxes, yields,
and cycle times as one coupled model. Those values cannot be substituted for
this wrapper's normalized coefficients.

- [ViennaPS Bosch example configuration](https://github.com/ViennaTools/ViennaPS/blob/master/examples/boschProcess/config.txt)
- [ViennaPS multi-particle model](https://viennatools.github.io/ViennaPS/models/prebuilt/multiParticle.html)
- [Ertl and Selberherr, three-dimensional level-set Bosch simulation](https://www.iue.tuwien.ac.at/pdf/ib_2009/hashed_links/ep4PPErIJjnr4Y_us.pdf)

Defensible bounds and anchors:

- neutral and passivation sticking: mathematical domain 0–1; practical range unknown;
- ion reflection threshold: API angle domain 0–90°; practical range unknown;
- ion source exponent: positive model domain; 1, 200, and 1,000 are documented
  interpretations/examples, not process bounds;
- etch time, initial time, neutral/ion coefficients, passivation amount, and
  mask erosion: transferable range unknown.

Tool-level etch/passivation seconds remain physical context only because they
change jointly with flow, pressure, power, temperature, mask, and geometry.

### Candidate bracket for the first Bosch range study

These are starting model-space values. They come from checked-in examples and
saved V3 trajectories. They are not approved ranges or machine settings. The
study must keep failures, find quiet or saturated edges, and expand an edge only
once when the model remains valid.

| Implemented control | Low | Reference | High | Basis before the new study |
|---|---:|---:|---:|---|
| Opening radius | 0.12 | 0.15 | 0.18 | Saved ideal-mask geometries |
| Mask taper | -4° | 2° | 6° | Prior full-width geometry screen |
| Completed cycles | 4 | 10 | 16 | Saved target-depth checkpoints span 4–30 cycles; 10 is the wrapper default |
| Etch time per cycle | 0.20 | 0.50 | 2.00 | Prior model-space Bosch screen |
| Initial etch time | 0.10 | 0.30 | 0.50 | Prior model-space Bosch screen |
| Neutral removal coefficient | -0.20 | -0.08 | -0.03 | Prior model-space Bosch screen |
| Neutral sticking | 0.02 | 0.08 | 0.30 | Probability domain plus prior model-space screen |
| Polymer amount per cycle | 0.003 | 0.005 | 0.040 | Prior model-space Bosch screen |
| Polymer sticking | 0.001 | 0.010 | 0.030 | Probability domain plus prior model-space screen |
| Ion arrival exponent | 50 | 400 | 1,000 | Documented meanings plus prior model-space screen |
| Ion reflection threshold | 25° | 45° | 90° | API angle domain plus prior model-space screen |
| Ion removal coefficient | -0.22 | -0.10 | -0.04 | Prior model-space Bosch screen |

The first fixed-cycle study measures its final cycle. It does not select a
checkpoint by target depth. The 16-cycle high value is an initial cost-bounded
edge. A shallow high-edge result may trigger one expansion toward the saved
30-cycle horizon.

The raw controls are coupled. Cycle count multiplies every per-cycle exposure.
Etch time multiplies the neutral and ion coefficients. Polymer amount also sets
equal-magnitude directional polymer removal in the current wrapper. The design
must save both raw controls and derived exposure coordinates. It must not call a
coupled result a pure chemical or equipment effect.

## Liner

The active tutorial uses `SingleParticleProcess`, not the available TEOS
reaction model. Its amount is a model growth scale; sticking controls deposition
versus diffuse reflection. The code domain is amount greater than zero and
sticking in (0,1]. The current 0.02/0.04/0.06 amount grid and
0.02/0.05/0.20 sticking grid are internal teaching values.

- [ViennaPS single-particle model](https://viennatools.github.io/ViennaPS/models/prebuilt/singleParticle.html)
- [Experimental TSV liner/barrier/seed study](https://imapsource.org/article/56125-oxide-liner-barrier-and-seed-layers-and-cu-plating-of-blind-through-silicon-vias-tsvs-on-300mm-wafers-for-3d-ic-integration)

The sources support the transport mechanism, not a conversion from precursor
settings to model amount or sticking.

## Barrier and seed

The repository mixes a downward directional component with an isotropic normal
component. Amount must be positive and the mixture fraction is bounded 0–1 by
construction. The mixture is a repository surrogate, not a sputter-tool knob
or measured angular distribution. Existing 0.01/0.02/0.03 amounts and
0/0.30/0.80 fractions are model-space teaching values.

- [ViennaPS directional model](https://viennatools.github.io/ViennaPS/models/prebuilt/directional.html)
- [PVD step-coverage study](https://kjmm.org/kjmm/XmlViewer/f445943)

No source establishes a physical range for the synthetic fraction or maps it
to pressure, target power, bias, or collimation. Seed electrical continuity is
not measured.

## Copper candidate

The candidate extension contains seven controls: suppressor sticking, source
exponent, mean-free-path mode/value, adsorption strength, deactivation rate,
active growth rate, and suppressed growth rate. Literature supports suppressor
adsorption/deactivation and a passive-to-active bottom-up transition. It does
not calibrate these coefficients.

- [NIST chloride/suppressor TSV study](https://www.nist.gov/publications/effect-chloride-concentration-copper-deposition-through-silicon-vias)
- [Bottom-up TSV copper study](https://pmc.ncbi.nlm.nih.gov/articles/PMC7543049/)

The existing sticking/source-power grid is a coupled transport sensitivity
study: adsorption strength changes with sticking. It is not a full independent
factor screen or an electroplating window. All seven ranges require model-space
range finding after the mechanism gate.

## CMP surrogate

The teaching path applies uniform material-selective isotropic removal. Its
duration is a model removal amount, and its material values are relative rates.
It does not implement pad contact, pressure, speed, slurry chemistry, pattern
density, or endpoint sensing.

- [ViennaPS isotropic model](https://viennatools.github.io/ViennaPS/models/prebuilt/isotropic.html)
- [ViennaPS geometric planarization control](https://viennatools.github.io/ViennaPS/misc/planarize.html)
- [CMP dishing and overpolish study](https://doi.org/10.1016/S0167-9317(99)00308-1)
- [CMP pressure, speed, and chemistry study](https://doi.org/10.1016/S0040-6090(98)00896-7)

The current removal amounts and relative rates have no physical calibration.
CMP range finding remains blocked until material-loss limits and valid incoming
copper shapes are declared.

## Consequence for the DOE

1. Use published sources for factor meaning, mathematical bounds, and model
   limitations.
2. Treat current repository values only as prior model-space samples.
3. Run low/reference/high range finding with measured responses and numerical
   controls fixed.
4. Freeze the screening matrix only after valid response brackets exist.
5. Never translate a model coefficient into a tool setting without calibration
   data from that equipment and process stack.
