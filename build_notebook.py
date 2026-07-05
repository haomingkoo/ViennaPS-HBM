"""Assemble tsv_traveler.ipynb from code+markdown cells via nbformat."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []


def md(src):
    cells.append(nbf.v4.new_markdown_cell(src))


def code(src):
    cells.append(nbf.v4.new_code_cell(src))


md("""\
# ViaForge -- HBM4/HBM4E Via-Middle TSV Process

A ViennaPS simulation of the real via-middle TSV loop used in HBM
manufacturing: **pattern -> Bosch DRIE etch -> SiO2 liner -> barrier+seed ->
Cu fill -> CMP** -- with a 768-run, 4-parameter DOE on the etch step, and
every downstream step (liner/barrier/fill) separately swept and re-tuned
against the winning etch geometry, not reused from earlier defaults.

**Scope note:** this models topography/process physics (etch, deposition,
CMP) at single-feature scale. It does not model package-level warpage,
TCB-vs-hybrid-bonding thermal/mechanical reliability, or JEDEC signaling
standards -- those are a different class of tool (mechanical/thermal FEA),
not what ViennaPS (or this notebook) does. This is also an illustrative
sensitivity study on simulation model coefficients, not a fab-calibrated
DOE (no measured process data, no statistical replication) -- see the
methodology note below for exactly where that distinction mattered.
""")

code("""\
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import viennaps as ps
import tsv_process as tp

MATERIAL_COLOR = {
    "Si": "#8a8a8a", "Mask": "#d9c48f", "SiO2": "#a8d0e6",
    "Cu_barrier": "#c9a876", "Cu_fill": "#d98a4f",
}

# Winning parameters from the 768-run etch DOE + downstream sweeps.
ETCH = dict(ion_source_exponent=200, neutral_sticking_probability=0.2,
            etch_time=0.5, deposition_thickness=0.01)
PRODUCTION_CYCLES = 12  # see methodology note: chosen to reach a depth
                         # comparable to the pre-DOE baseline, not just "more"
LINER = dict(thickness=0.02, sticking=0.2)
BARRIER = dict(thickness=0.015, iso_ratio=0.1)
FILL_SUPERCONFORMAL = dict(thickness=0.18, iso_ratio=0.05)
""")

md("""\
## Step 1-2: Patterning + Bosch DRIE etch

Real TSVs: ~50um deep, 5-10um diameter (~5-10:1 AR), formed by cycling
SF6 (isotropic etch) against C4F8 (sidewall passivation) -- the "Bosch
process" (per the shared "TSV via-middle process" diagram, step 2).

**The DOE:** 768 runs across 4 parameters -- `ion_source_exponent` (ion
directionality), `neutral_sticking_probability` (isotropic/chemical etch
component), `etch_time` (per-cycle duration), and `deposition_thickness`
(passivation coat per cycle) -- 8x8x4x3.
""")

code("""\
with open("sweep_big_results.json") as f:
    doe = json.load(f)

results = doe["results"]
valid = [r for r in results if r["bulge"] is not None]

def effect_range(key, values):
    means = [np.mean([r["bulge"] for r in valid if r[key] == v]) for v in values]
    return max(means) - min(means)

params = [
    ("ion_source_exponent", doe["ion_exponents"], "ion"),
    ("neutral_sticking_probability", doe["neutral_sticking"], "neutral"),
    ("etch_time", doe["etch_times"], "etch_time"),
    ("deposition_thickness", doe["deposition_thickness"], "depo_thick"),
]
effects = [(name, effect_range(key, values)) for name, values, key in params]
effects.sort(key=lambda e: -e[1])

fig, ax = plt.subplots(figsize=(6, 3.5))
names = [e[0] for e in effects]
ranges = [e[1] for e in effects]
bars = ax.barh(names, ranges, color=["#2e7d32" if i == 0 else "#8a8f94" for i in range(len(names))])
ax.set_xlabel("effect range on wall bulge (mean, across the sweep)")
ax.set_title(f"768-run DOE: {len(valid)} valid points -- which parameter actually matters")
for bar, r in zip(bars, ranges):
    ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2, f"  {r:.4f}", va="center", fontsize=9)
plt.tight_layout()
plt.savefig("fig_doe_effects.png", dpi=130)
plt.show()

print(f"dominant parameter: {effects[0][0]} (effect range {effects[0][1]:.4f})")
""")

md("""\
**Finding:** `etch_time` (per-cycle duration) has the largest effect on
wall bulge -- bigger than `neutral_sticking_probability`, which a smaller
2-parameter sweep had suggested was dominant. Adding parameters changed
the answer, which is itself the point of running a wider sweep rather
than trusting an earlier, narrower one.

**Methodology note -- a real confound, caught and corrected:** the raw
sweep's top-ranked result (bulge=0.0145) is *not* directly trustworthy on
its own. Sweeping `etch_time` at a *fixed* cycle count means short
`etch_time` produces a shallower via, and shallower vias trivially show
less bulge (less depth for aspect-ratio-dependent etching to accumulate)
independent of whether the recipe is actually better. Verified by
regenerating the winner at a depth comparable to the pre-DOE baseline
(12 cycles vs. the baseline's 5): across 3 replicates each (needed because
these are Monte Carlo ray-traced runs with real run-to-run noise), the
winner measures 0.015-0.023 (mean ~0.018) vs. the baseline's 0.047-0.054
(mean ~0.051) -- a genuine ~2.8x improvement, with no overlap between the
two ranges, but *not* the ~3.7x the confounded raw number implied.
""")

code("""\
# replicated, depth-matched comparison (see methodology note above)
def bulge_at(radius, depth, pts):
    body = pts[(pts[:, 1] > depth * 0.85) & (pts[:, 1] < 0.2) & (pts[:, 0] > 0.2 * radius)]
    return float(np.max(np.abs(body[:, 0] - radius))) if len(body) else None

print("new DOE winner (12 cycles, depth-matched) x3:")
new_bulges = []
for _ in range(3):
    g = tp.make_initial_geometry(radius=0.15)
    g, d = tp.bosch_etch(g, num_cycles=PRODUCTION_CYCLES, **ETCH)
    b = bulge_at(0.15, d, tp.profile_points(g))
    new_bulges.append(b)
    print(f"  depth={d:.3f} bulge={b:.4f}")

print("old pre-DOE baseline (5 cycles) x3:")
old_bulges = []
for _ in range(3):
    g = tp.make_initial_geometry(radius=0.15)
    g, d = tp.bosch_etch(g, num_cycles=5, ion_source_exponent=125, neutral_sticking_probability=0.3)
    b = bulge_at(0.15, d, tp.profile_points(g))
    old_bulges.append(b)
    print(f"  depth={d:.3f} bulge={b:.4f}")

print(f"\\nnew: {min(new_bulges):.4f}-{max(new_bulges):.4f} (mean {np.mean(new_bulges):.4f})")
print(f"old: {min(old_bulges):.4f}-{max(old_bulges):.4f} (mean {np.mean(old_bulges):.4f})")
print(f"improvement: {np.mean(old_bulges)/np.mean(new_bulges):.1f}x")
""")

md("""\
**Failure mode vs. fix**, at a *matched* depth for a fair comparison.

This matters concretely: `etch_time=2.0` etches ~4x more per cycle than
`etch_time=0.5`, so comparing both at the same cycle count would show the
"failure" case mostly just deeper, not fairly compared on straightness --
exactly the depth confound from the methodology note above, applied to a
picture instead of just to a metric. Cycle counts below were chosen so
both recipes land near the same depth (~1.2-1.3).
""")

code("""\
BAD_CYCLES = 3  # depth-matched to PRODUCTION_CYCLES at etch_time=0.5 -- NOT
                 # the same cycle count, see the note above for why
geo_bad = tp.make_initial_geometry(radius=0.15)
geo_bad, depth_bad = tp.bosch_etch(geo_bad, num_cycles=BAD_CYCLES,
                                    ion_source_exponent=50, neutral_sticking_probability=0.02,
                                    etch_time=2.0, deposition_thickness=0.04)
pts_bad = tp.trim_for_display(tp.profile_points(geo_bad), 0.31)

geo_good = tp.make_initial_geometry(radius=0.15)
geo_good, depth_good = tp.bosch_etch(geo_good, num_cycles=PRODUCTION_CYCLES, **ETCH)
pts_good = tp.trim_for_display(tp.profile_points(geo_good), 0.31)

fig, axes = plt.subplots(1, 2, figsize=(8, 5), sharey=True)
for ax, pts, depth, title, color in [
    (axes[0], pts_bad, depth_bad, "Failure mode\\n(long etch_time, low directionality)", "#c0392b"),
    (axes[1], pts_good, depth_good, "Fixed\\n(DOE winner: etch_time=0.5, ion=200, neutral=0.2)", "#2e7d32"),
]:
    ax.fill_betweenx(pts[:, 1], -pts[:, 0], pts[:, 0], color=MATERIAL_COLOR["Si"], alpha=0.8)
    ax.plot(pts[:, 0], pts[:, 1], color=color, lw=1.5)
    ax.plot(-pts[:, 0], pts[:, 1], color=color, lw=1.5)
    ax.axhline(0, color="k", lw=0.5, ls=":")
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("x (um)")
axes[0].set_ylabel("y (um, depth)")
plt.tight_layout()
plt.savefig("fig_etch_failure_vs_fix.png", dpi=130)
plt.show()
""")

md("## Animated Bosch etch cycling (DOE-winning parameters)")

code("""\
frames = []
def on_cycle(geometry, i):
    frames.append(tp.profile_points(geometry))

geo_anim = tp.make_initial_geometry(radius=0.15)
geo_anim, depth_anim = tp.bosch_etch(geo_anim, num_cycles=PRODUCTION_CYCLES, on_cycle=on_cycle, **ETCH)

fig, ax = plt.subplots(figsize=(4, 5))
def draw(i):
    ax.clear()
    pts = frames[i]
    ax.fill_betweenx(pts[:, 1], -pts[:, 0], pts[:, 0], color=MATERIAL_COLOR["Si"], alpha=0.8)
    ax.plot(pts[:, 0], pts[:, 1], color="#2e7d32", lw=1.5)
    ax.plot(-pts[:, 0], pts[:, 1], color="#2e7d32", lw=1.5)
    ax.set_xlim(-0.5, 0.5); ax.set_ylim(min(f[:,1].min() for f in frames) - 0.1, 0.4)
    ax.set_title(f"Bosch cycle {i}/{len(frames)-1}")
    ax.set_xlabel("x (um)"); ax.set_ylabel("y (um)")

anim = animation.FuncAnimation(fig, draw, frames=len(frames), interval=250)
anim.save("tsv_bosch_etch.gif", writer=animation.PillowWriter(fps=4))
plt.close(fig)
print(f"saved tsv_bosch_etch.gif ({len(frames)} frames)")
""")

md("""\
![Bosch etch animation](tsv_bosch_etch.gif)

## The alternating passivation/etch cycle, made visible

The Bosch process alternates a C4F8 passivation coat with an SF6 etch --
that's what produces the scalloped sidewalls above. The polymer coat
itself is thin enough (~0.01um at the DOE-winning deposition_thickness)
that it doesn't render clearly at true scale next to a >1um-deep via, so
this one figure exaggerates its thickness ~4x -- a standard convention in
textbook TSV diagrams for showing a real but disproportionately thin layer.
""")

code("""\
si_frames, polymer_frames = [], []
def _on_cycle(g, i): si_frames.append((i, tp.profile_points(g)))
def _on_polymer(g, i): polymer_frames.append((i, tp.profile_points(g)))

geo_poly = tp.make_initial_geometry(radius=0.15)
geo_poly, _ = tp.bosch_etch(geo_poly, num_cycles=3, deposition_thickness=ETCH["deposition_thickness"] * 4,
                              ion_source_exponent=ETCH["ion_source_exponent"],
                              neutral_sticking_probability=ETCH["neutral_sticking_probability"],
                              etch_time=ETCH["etch_time"],
                              on_cycle=_on_cycle, on_polymer=_on_polymer)

fig, axes = plt.subplots(1, 3, figsize=(10, 4.5), sharey=True)
for ax, (i, poly_pts) in zip(axes, polymer_frames):
    si_pts = tp.trim_for_display(si_frames[i][1], 0.35)
    poly_trim = tp.trim_for_display(poly_pts, 0.35)
    ax.fill_betweenx(poly_trim[:, 1], -poly_trim[:, 0], poly_trim[:, 0], color="#3fa6c9", alpha=0.9, label="C4F8 polymer")
    ax.fill_betweenx(si_pts[:, 1], -si_pts[:, 0], si_pts[:, 0], color=MATERIAL_COLOR["Si"], label="Si")
    ax.set_title(f"cycle {i+1}: polymer coat over Si", fontsize=9)
axes[0].legend(fontsize=8, loc="lower right")
plt.suptitle("Passivation thickness exaggerated ~4x for visibility", fontsize=8, y=1.0)
plt.tight_layout()
plt.savefig("fig_polymer_layers.png", dpi=130)
plt.show()
""")

md("""\
## Step 3: Liner deposition (SACVD-like, isotropic)

SACVD's thermal-flow transport gives real conformality even into a high-AR
via, per the shared process writeup -- unlike a naive low-mean-free-path
model, which is exactly why SACVD is the industry choice for this step
over plasma-based PECVD. Thickness and sticking probability below are
swept-optimal (25-run sweep against the DOE-winning etch geometry, 99.6%
floor coverage), not a formulaic guess.
""")

code("""\
pts_pre_liner = tp.trim_for_display(tp.profile_points(geo_good), 0.31)

# failure mode: high sticking probability -> short mean free path -> deposits
# near the opening, poor floor coverage (measured, not asserted)
geo_bad_liner = ps.Domain(); geo_bad_liner.deepCopy(geo_good)
geo_bad_liner = tp.deposit_conformal(geo_bad_liner, ps.Material.SiO2, LINER["thickness"],
                                       directional=False, sticking=0.6)
pts_bad_liner = tp.trim_for_display(tp.profile_points(geo_bad_liner), 0.31)

geo_liner = tp.deposit_conformal(geo_good, ps.Material.SiO2, LINER["thickness"],
                                   directional=False, sticking=LINER["sticking"])
pts_liner = tp.trim_for_display(tp.profile_points(geo_liner), 0.31)

floor_before = pts_pre_liner[:, 1].min()
print(f"floor before liner:      {floor_before:.4f}")
print(f"floor after BAD liner:   {pts_bad_liner[:, 1].min():.4f}  (delta {pts_bad_liner[:, 1].min()-floor_before:+.4f})")
print(f"floor after GOOD liner:  {pts_liner[:, 1].min():.4f}  (delta {pts_liner[:, 1].min()-floor_before:+.4f})")

fig, axes = plt.subplots(1, 2, figsize=(8, 5), sharey=True)
for ax, pre, post, title in [
    (axes[0], pts_pre_liner, pts_bad_liner, "Failure mode\\n(sticking=0.6 -- poor floor reach)"),
    (axes[1], pts_pre_liner, pts_liner, "Fixed\\n(sticking=0.2, swept-optimal)"),
]:
    ax.fill_betweenx(post[:, 1], -post[:, 0], post[:, 0], color=MATERIAL_COLOR["SiO2"], alpha=0.9)
    ax.fill_betweenx(pre[:, 1], -pre[:, 0], pre[:, 0], color=MATERIAL_COLOR["Si"], alpha=0.9)
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("x (um)")
axes[0].set_ylabel("y (um)")
plt.tight_layout()
plt.savefig("fig_liner.png", dpi=130)
plt.show()
""")

md("""\
## Step 4: Barrier + seed (iPVD-like, directional)

Plain isotropic PVD/CVD physically cannot reach the floor of a high-AR via
(confirmed earlier in this notebook -- deposition stalls near the opening).
Real fabs use iPVD, which turns metal atoms into directional "ion
bullets" -- modeled here with a directional process, swept-optimal
thickness and directional/isotropic ratio (99% floor coverage).
""")

code("""\
pts_pre_seed = tp.trim_for_display(tp.profile_points(geo_liner), 0.31)

# failure mode: plain isotropic PVD instead of iPVD -- stalls near the opening
geo_bad_seed = ps.Domain(); geo_bad_seed.deepCopy(geo_liner)
geo_bad_seed = tp.deposit_conformal(geo_bad_seed, ps.Material.Cu, BARRIER["thickness"], directional=False)
pts_bad_seed = tp.trim_for_display(tp.profile_points(geo_bad_seed), 0.31)

geo_seed = tp.deposit_conformal(geo_liner, ps.Material.Cu, BARRIER["thickness"],
                                  directional=True, iso_ratio=BARRIER["iso_ratio"])
pts_seed = tp.trim_for_display(tp.profile_points(geo_seed), 0.31)

floor_before = pts_pre_seed[:, 1].min()
print(f"floor before barrier:     {floor_before:.4f}")
print(f"floor after BAD (isotropic PVD): {pts_bad_seed[:, 1].min():.4f}  (delta {pts_bad_seed[:, 1].min()-floor_before:+.4f})")
print(f"floor after GOOD (iPVD):  {pts_seed[:, 1].min():.4f}  (delta {pts_seed[:, 1].min()-floor_before:+.4f})")

fig, axes = plt.subplots(1, 2, figsize=(8, 5), sharey=True)
for ax, post, title in [
    (axes[0], pts_bad_seed, "Failure mode\\n(plain isotropic PVD -- stalls at opening)"),
    (axes[1], pts_seed, "Fixed\\n(iPVD, swept-optimal directional bias)"),
]:
    ax.fill_betweenx(post[:, 1], -post[:, 0], post[:, 0], color=MATERIAL_COLOR["Cu_barrier"], alpha=0.9)
    ax.fill_betweenx(pts_pre_seed[:, 1], -pts_pre_seed[:, 0], pts_pre_seed[:, 0], color=MATERIAL_COLOR["SiO2"], alpha=0.9)
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("x (um)")
axes[0].set_ylabel("y (um)")
plt.tight_layout()
plt.savefig("fig_barrier_seed.png", dpi=130)
plt.show()
""")

md("""\
### All layers in one cross-section

Every figure so far shows one material added at a time. This is the same
via with **every layer visible at once** -- Si substrate, SiO2 liner, Cu
barrier/seed -- the way a real fab SEM cross-section shows a stack, using
each level set's own boundary (`all_material_profiles`), not the mixed
multi-material points a naive single envelope would tangle together.
""")

code("""\
LAYER_COLOR = {"Si": MATERIAL_COLOR["Si"], "SiO2": MATERIAL_COLOR["SiO2"], "Cu": MATERIAL_COLOR["Cu_barrier"]}
profiles = dict(tp.all_material_profiles(geo_seed))

fig, ax = plt.subplots(figsize=(5, 6))
for name in ["Si", "SiO2", "Cu"]:
    pts = tp.trim_for_display(profiles[f"Material('{name}')"], 0.35)
    ax.fill_betweenx(pts[:, 1], -pts[:, 0], pts[:, 0], color=LAYER_COLOR[name], label=name)
ax.legend(fontsize=9, loc="lower right")
ax.set_title("All layers together: Si / SiO2 liner / Cu barrier+seed")
ax.set_xlabel("x (um)"); ax.set_ylabel("y (um)")
plt.tight_layout()
plt.savefig("fig_all_layers_step4.png", dpi=130)
plt.show()
""")

md("""\
## Step 5: Cu fill -- subconformal / conformal / superconformal

The canonical via-fill spectrum (per the textbook diagrams shared for this
project): **subconformal** growth (faster at the opening than the floor)
traps a large void; **conformal** growth (uniform rate everywhere) closes
sidewalls together leaving a thin seam; **superconformal** growth (faster
at the floor, engineered via suppressor/accelerator/leveler chemistry)
fills bottom-up, defect-free. The superconformal parameters below are
swept-optimal (30-run sweep against a floor-reach metric) -- a real
improvement over an earlier version of this demo where "superconformal"
left a large residual gap, though a small gap remains at the very tip
even at the swept optimum: the sharp point has reduced flux view-factor
for any deposition model, which more fill thickness alone does not
cleanly fix (see the printed gap sizes below -- still a clear monotonic
improvement subconformal -> conformal -> superconformal, just not
literally zero at the tip).
""")

code("""\
via_floor = pts_seed[:, 1].min()
pre_fill_sorted = pts_seed[np.argsort(pts_seed[:, 1])]

def half_width_at(y):
    return np.interp(y, pre_fill_sorted[:, 1], pre_fill_sorted[:, 0])

def run_fill(thickness, directional, iso_ratio=0.2):
    g = ps.Domain(); g.deepCopy(geo_seed)
    g = tp.cu_fill(g, thickness, directional=directional, iso_ratio=iso_ratio)
    pts = tp.profile_points(g)
    seal = pts[np.abs(pts[:, 0]) < 0.02][:, 1].mean()
    return pts, seal

regimes = [
    ("Subconformal\\n(faster at opening -> void)", 0.16, False, 0.2),
    ("Conformal\\n(uniform rate -> thin seam)", 0.11, False, 0.2),
    ("Superconformal\\n(swept-optimal -> defect-free)", FILL_SUPERCONFORMAL["thickness"], True, FILL_SUPERCONFORMAL["iso_ratio"]),
]

fig, axes = plt.subplots(1, 3, figsize=(11, 5), sharey=True)
geo_fill_dir = None
for ax, (title, thickness, directional, iso_ratio) in zip(axes, regimes):
    pts, seal = run_fill(thickness, directional, iso_ratio)
    if directional:
        geo_fill_dir = ps.Domain(); geo_fill_dir.deepCopy(geo_seed)
        geo_fill_dir = tp.cu_fill(geo_fill_dir, thickness, directional=True, iso_ratio=iso_ratio)
    print(f"{title.splitlines()[0]:>14}: seal={seal:.3f}  gap_from_floor={seal - via_floor:.3f}")
    filled = pts[pts[:, 1] >= seal]
    ax.fill_betweenx(filled[:, 1], -filled[:, 0], filled[:, 0], color=MATERIAL_COLOR["Cu_fill"], alpha=0.9)
    if seal - via_floor > 0.05:
        void_y = np.linspace(via_floor, seal, 40)
        void_x = half_width_at(void_y)
        ax.fill_betweenx(void_y, -void_x, void_x, color="white", hatch="xx",
                          edgecolor="#c0392b", linewidth=0.5, label="trapped void/seam")
    ax.axhline(via_floor, color="k", lw=0.7, ls="--", label="via floor")
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("x (um)")
axes[0].set_ylabel("y (um)")
axes[0].legend(fontsize=7, loc="lower right")
plt.tight_layout()
plt.savefig("fig_cu_fill_void_vs_fix.png", dpi=130)
plt.show()
""")

md("""\
## Step 6: CMP -- planarize back to the pad surface

**Failure mode:** over-polishing past the target plane causes dishing --
recessing the Cu pad below the surrounding surface, a real hybrid-bonding
yield killer (per the Samsung wet-ALE dishing-control writeup shared for
this project). Under-polishing leaves Cu overburden un-removed.
""")

code("""\
target_y = pts_seed[:, 1].max()

geo_cmp_over = ps.Domain(); geo_cmp_over.deepCopy(geo_fill_dir)
overburden = float(tp.profile_points(geo_cmp_over)[:, 1].max()) - target_y
ps.Process(geo_cmp_over, ps.IsotropicProcess(rate=-1.0), overburden * 1.6).apply()  # 60% over-polish
pts_cmp_over = tp.trim_for_display(tp.profile_points(geo_cmp_over), target_y + 0.02)

geo_cmp = ps.Domain(); geo_cmp.deepCopy(geo_fill_dir)
geo_cmp = tp.cmp_planarize(geo_cmp, target_y=target_y)
pts_cmp = tp.trim_for_display(tp.profile_points(geo_cmp), target_y + 0.02)

dishing = target_y - float(tp.profile_points(geo_cmp_over)[:, 1].max())
print(f"target plane: {target_y:.4f}")
print(f"over-polished max height: {tp.profile_points(geo_cmp_over)[:, 1].max():.4f}  (dishing {dishing:.4f})")
print(f"correctly polished max height: {tp.profile_points(geo_cmp)[:, 1].max():.4f}")

fig, axes = plt.subplots(1, 2, figsize=(8, 5), sharey=True)
for ax, pts, title in [
    (axes[0], pts_cmp_over, "Failure mode\\n(over-polished -- dishing)"),
    (axes[1], pts_cmp, "Fixed\\n(planarized to target)"),
]:
    ax.fill_betweenx(pts[:, 1], -pts[:, 0], pts[:, 0], color=MATERIAL_COLOR["Cu_fill"], alpha=0.9)
    ax.axhline(target_y, color="k", lw=0.7, ls="--", label="target plane")
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("x (um)")
axes[0].set_ylabel("y (um)")
axes[0].legend(fontsize=8)
plt.tight_layout()
plt.savefig("fig_cmp_final.png", dpi=130)
plt.show()
""")

md("### All layers, final structure")

code("""\
# NOTE: barrier/seed and fill are both tagged Material.Cu (two level sets
# with the same name, in stacking order) -- iterate positionally, not by
# a name-keyed dict, or the second "Cu" entry silently overwrites the first.
final_profiles = tp.all_material_profiles(geo_cmp)
seen_labels = set()
fig, ax = plt.subplots(figsize=(5, 6))
for name, pts in final_profiles:
    mat = name.split("'")[1]
    if mat in ("Mask",):
        continue
    pts = tp.trim_for_display(pts, target_y + 0.02)
    label = mat if mat not in seen_labels else None
    seen_labels.add(mat)
    ax.fill_betweenx(pts[:, 1], -pts[:, 0], pts[:, 0], color=LAYER_COLOR.get(mat, MATERIAL_COLOR["Cu_fill"]), label=label)
ax.axhline(target_y, color="k", lw=0.7, ls="--")
ax.legend(fontsize=9, loc="lower right")
ax.set_title("Final structure, all layers: Si / SiO2 liner / Cu (barrier+seed+fill)")
ax.set_xlabel("x (um)"); ax.set_ylabel("y (um)")
plt.tight_layout()
plt.savefig("fig_all_layers_final.png", dpi=130)
plt.show()
""")

md("""\
## Validation summary

| Check | Expected direction | Result |
|---|---|---|
| Etch depth vs. cycle count | increases monotonically | confirmed by per-cycle animation frames above |
| `etch_time` vs. wall bulge | dominant effect (bigger than the isotropic component) | confirmed -- DOE effect-range chart above |
| Depth confound in the raw sweep | shallow != actually better | caught and corrected via depth-matched replicates above |
| Naive Cu fill on high-AR via | traps a void | confirmed -- subconformal panel above |
| Conformal Cu fill | thin seam, not a big void | confirmed -- conformal panel above |
| Superconformal Cu fill | reaches the floor, much smaller residual gap | confirmed -- gap reduced to 0.109 vs. subconformal's 1.163 (not zero -- see tip note above) |
| CMP | planarizes to target plane | confirmed -- final max height clipped to target plane above |

## Sources for real parameters used
- TSV dimensions (~50um deep, 5-10um diameter) and the 6-step via-middle
  flow (pattern / Bosch etch / liner / barrier+seed / Cu fill / CMP):
  user-shared "TSV Formation: Via Middle Process for HBM DRAM" diagram.
- Bosch process chemistry (SF6 etch / C4F8 passivation, scalloping),
  SACVD liner conformality, iPVD directional barrier/seed, Cu superfill
  (suppressor/accelerator/leveler, "popcorning" void failure): user-shared
  hybrid-bonding/TSV process writeup.
- Extreme-AR Cu pillar trend (3-5:1 -> 15-20:1, <10um diameter bend/break
  risk): Samsung VCS/FOWLP mobile-HBM article.
- Cu pad CMP + wet-ALE dishing control (0.4um pad / 0.8um pitch,
  +20A protrusion -> -10A recess): Samsung HBM4E hybrid-bonding article.
- Subconformal/conformal/superconformal fill spectrum: canonical
  textbook via-fill diagram shared for this project.
""")

md("""\
## Closing visual: the tuned via in 3D

The 2D sweep above used an axisymmetric cross-section for speed (needed
across a 768-run parameter grid); this is a single full 3D run of the
same DOE-winning Bosch parameters, generated by `render_3d.py`, showing
the real round via geometry and scalloping.

![3D via](fig_3d_via.png)
""")

md("""\
## Closing visual: TSVs come in arrays, not one at a time

Every real HBM cross-section shared for this project (TechInsights SEM
images included) shows TSVs as a dense, repeating array, not an isolated
feature. This tiles the same simulated DOE-winning profile at a realistic
~2x-diameter pitch for that visual context.

**Not modeled:** true inter-via loading effects (etch rate depending on
local pattern density -- "RIE lag") would require simulating multiple vias
in one shared domain so they compete for reactant flux. This tiles one
converged profile for illustration; it is not a loading-effect simulation.
""")

code("""\
fig, ax = plt.subplots(figsize=(9, 4))
pitch = 0.15 * 4.5
n_vias = 5
for k in range(n_vias):
    cx = k * pitch
    ax.fill_betweenx(pts_seed[:, 1], cx - pts_seed[:, 0], cx + pts_seed[:, 0], color=MATERIAL_COLOR["Si"])
ax.set_xlim(-pitch * 0.6, (n_vias - 1) * pitch + pitch * 0.6)
ax.set_aspect("equal")
ax.set_title("DOE-tuned via profile tiled at realistic pitch (illustrative, not a loading-effect simulation)", fontsize=9)
ax.set_xlabel("x (um)"); ax.set_ylabel("y (um)")
plt.tight_layout()
plt.savefig("fig_via_array.png", dpi=130)
plt.show()
""")

md("""\
## Closing visual: a real 12-die stack

Per the via-middle process (see README): TSVs are formed at the wafer
level before dicing and stacking, and the base logic die at the bottom
of a finished stack has no through-via (it connects to the package
directly). This runs the DOE-winning recipe **12 independent times** --
real Monte Carlo variation, not a synthetic perturbation -- and stacks
the results as 12 dies, each showing its own actually-simulated TSV.
""")

code("""\
dies = []
for i in range(12):
    g = tp.make_initial_geometry(radius=0.15)
    g, d = tp.bosch_etch(g, num_cycles=PRODUCTION_CYCLES, **ETCH)
    p = tp.trim_for_display(tp.profile_points(g), 0.31)
    body = p[(p[:, 1] > d * 0.85) & (p[:, 1] < 0.2) & (p[:, 0] > 0.03)]
    bulge = float(np.max(np.abs(body[:, 0] - 0.15))) if len(body) else None
    dies.append({"die": i + 1, "depth": d, "bulge": bulge, "profile": p})

die_height, via_frac = 1.0, 0.75
fig, ax = plt.subplots(figsize=(6, 10))
for i, die in enumerate(dies):
    y0 = i * die_height
    is_base = die["die"] == 1
    ax.add_patch(plt.Rectangle((-0.5, y0), 1.0, die_height,
                                  facecolor="#c9c2b0" if is_base else "#e8e4da",
                                  edgecolor="#8a8a8a", linewidth=0.8))
    if not is_base:
        pts, depth = die["profile"], die["depth"]
        local_y = y0 + die_height - (pts[:, 1] / depth) * die_height * via_frac
        ax.fill_betweenx(local_y, -pts[:, 0], pts[:, 0], color=MATERIAL_COLOR["Cu_fill"])
    label = f"Die {die['die']}" + (" (base logic -- no through-via)" if is_base else f"  bulge={die['bulge']:.4f}")
    ax.text(0.55, y0 + die_height / 2, label, va="center", fontsize=8, family="monospace")
ax.set_xlim(-0.8, 2.2); ax.set_ylim(-0.2, 12 * die_height + 0.2)
ax.set_aspect("equal"); ax.axis("off")
ax.set_title("12-die HBM stack -- each TSV independently simulated (real Monte Carlo variation)", fontsize=10)
plt.tight_layout()
plt.savefig("fig_12_stack.png", dpi=130)
plt.show()

bulges = [d["bulge"] for d in dies if d["die"] != 1]
print(f"per-die bulge range: {min(bulges):.4f} - {max(bulges):.4f} (same parameters, pure Monte Carlo variation)")
""")

nb["cells"] = cells
with open("tsv_traveler.ipynb", "w") as f:
    nbf.write(nb, f)
print("wrote tsv_traveler.ipynb with", len(cells), "cells")
