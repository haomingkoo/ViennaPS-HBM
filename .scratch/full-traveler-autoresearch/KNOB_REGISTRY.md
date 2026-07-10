# TSV Traveler Knob Registry

Status is based on direct wrapper/call-site inspection and ViennaPS 2-D API `help()` output on 2026-07-10. “Untested” means the long campaign must screen or explicitly classify the control before ruling it out.

| Step | Owner/API | Knob | Default / current range | Class | Mechanism and evidence status |
|---|---|---|---|---|---|
| Pattern | `make_initial_geometry` / `MakeHole` | `radius` | 0.15 | product specification | Sets target width; held fixed. |
| Pattern | `make_initial_geometry` / `MakeHole` | `mask_height` | 0.30 | product specification | Mask budget; held fixed. |
| Pattern | `MakeHole.maskTaperAngle` | `taper` | 0.0; screened 0--8 deg | recipe knob | Changes mouth geometry and etch ray tracing; effect plausible but depth-matched conclusion is unconfirmed. |
| Pattern | `MakeHole.holeTaperAngle` | hole taper | 0.0, currently not wired | recipe knob | API-exposed opening taper; small historical screen only; must be wired/screened. |
| Pattern | `Domain` | `gridDelta`, extents, hole shape, materials | 0.01 / fixed | numerical or structural | Numerical resolution and geometry representation, not recipe optimization. |
| Etch | `bosch_etch` | `num_cycles` | 10; 9--18 planned | recipe knob | Bosch granularity/depth interaction; confirmed non-monotonic. |
| Etch | `bosch_etch` | `etch_time` | 1.5; 0.40--0.80 planned | recipe knob | Per-cycle etch dose; dominant, must depth-match. |
| Etch | `bosch_etch` | `initial_etch_time` | 0.3; 0.10--0.60 planned | recipe knob | Initial unpassivated seed etch; screened/combined DOE relevant. |
| Etch | `MultiParticleProcess.addNeutralParticle` | neutral sticking | 0.1; 0.03--0.30 planned | recipe knob | Chemical/isotropic flux and sidewall undercut. |
| Etch | rate function | `neutral_rate`, `ion_rate` | -0.2, -0.1 | recipe knob | Material removal response to neutral/ion flux; neutral rate confirmed important, ion rate is exposed but unconfirmed. |
| Etch | `SingleParticleProcess` | deposition thickness, deposition sticking, deposition source exponent | 0.02, 0.01, 1.0 | recipe knob | Passivation thickness/conformality/removal; source exponent is currently implicit and untested for the polymer step. |
| Etch | `MultiParticleProcess.addIonParticle` | source power / `ion_source_exponent`, `thetaRMin` | 200, 60 | recipe knob | Ion directionality and angular window; screened. |
| Etch | `MultiParticleProcess.addIonParticle` | `thetaRMax`, `minAngle`, `B_sp`, mean/sigma/threshold energy, inflect angle, `n` | API defaults | recipe knob or model control | API-exposed angular/energy distribution controls, presently unwired and untested; registry screening decides whether they are physical knobs in this model. |
| Etch | `addNeutralParticle` overload | material-specific neutral sticking | default uniform | structural/recipe candidate | API permits material mapping; currently uniform. Screen only if simple uniform model is inadequate. |
| Liner | `deposit_conformal` / `SingleParticleProcess` | thickness, sticking | 0.02, 0.05 | recipe knob | Functional thickness gate then floor coverage. |
| Liner | `SingleParticleProcess` | source exponent, material rates, mask material | 1.0 / defaults | numerical or structural | Source exponent historically no effect; material rate mapping is a model variant, not a first-line recipe knob. |
| Barrier/seed | `DirectionalProcess` | thickness, isotropic ratio | 0.014, 0.1 | recipe knob | iPVD directional/isotropic balance; thickness gate then floor coverage. |
| Barrier/seed | `DirectionalProcess` | direction vector/angle, visibility | vertical, true | recipe candidate/model control | Angle had no validated benefit when upstream geometry was controlled; visibility historically no effect in single-via domain. |
| Fill | `cu_fill` / `DirectionalProcess` | thickness, isotropic ratio | 0.15, 0.01 | recipe knob | Must satisfy thickness; centerline tip gap is the gate. |
| Fill | `DirectionalProcess` | direction vector/angle, visibility, material rates | vertical, true/default | model control | Constant-vector process cannot represent CEAC curvature chemistry; do not claim zero gap as tunable. |
| CMP | `cmp_planarize` / `IsotropicProcess` | target height / overburden multiplier | target field height, multiplier | recipe knob | Changes removal duration; mask survival is a hard gate. |
| CMP | `IsotropicProcess` | global rate | -1.0 | numerical control | Rescales duration for a fixed removal target, not an outcome knob. |
| CMP | `IsotropicProcess.materialRates` | material-selective rates | API default uniform | model control | Unscreened; may rescale removal but cannot introduce topography-sensitive CMP physics. |

## Required evidence labels

Each registry item must end as `screened`, `replicated`, `confirmed`, `rejected`, `boundary-limited`, or `structurally-unresolvable`, with experiment IDs and confidence. Downstream conclusions additionally require shared upstream geometry IDs.
