"""Render an illustrative coarse-grid 3D via."""
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import viennaps as ps
import viennals as ls

ps.setDimension(3)
ps.Logger.setLogLevel(ps.LogLevel.ERROR)

geometry = ps.Domain(gridDelta=0.03, xExtent=0.8, yExtent=0.8)
ps.MakeHole(domain=geometry, holeRadius=0.15, holeDepth=0.0, maskHeight=0.3,
            holeShape=ps.HoleShape.FULL).apply()

ION_SOURCE_EXPONENT = 200
NEUTRAL_STICKING_PROBABILITY = 0.2
ETCH_TIME = 0.5
DEPOSITION_THICKNESS = 0.01

depo_model = ps.SingleParticleProcess(rate=DEPOSITION_THICKNESS, stickingProbability=0.01)
depo_removal = ps.SingleParticleProcess(rate=-DEPOSITION_THICKNESS, stickingProbability=1.0,
                                          sourceExponent=ION_SOURCE_EXPONENT, maskMaterial=ps.Material.Mask)
etch_model = ps.MultiParticleProcess()
etch_model.addNeutralParticle(NEUTRAL_STICKING_PROBABILITY)
etch_model.addIonParticle(sourcePower=ION_SOURCE_EXPONENT, thetaRMin=60.0)


def rate_fn(fluxes, material):
    if material == ps.Material.Mask:
        return 0.0
    rate = fluxes[1] * -0.1
    if material == ps.Material.Si:
        rate += fluxes[0] * -0.2
    return rate


etch_model.setRateFunction(rate_fn)

# Open the mask before the first passivation cycle.
ps.Process(geometry, etch_model, min(0.3, ETCH_TIME)).apply()
for _ in range(5):
    geometry.duplicateTopLevelSet(ps.Material.Polymer)
    ps.Process(geometry, depo_model, 1.0).apply()
    ps.Process(geometry, depo_removal, 1.0).apply()
    ps.Process(geometry, etch_model, ETCH_TIME).apply()
    geometry.removeTopLevelSet()
    geometry.removeStrayPoints()

# Render silicon alone because the merged mesh includes the mask plane.
mat_map = geometry.getMaterialMap()
si_idx = next(i for i, _ in enumerate(geometry.getLevelSets())
              if mat_map.getMaterialAtIdx(i) == ps.Material.Si)
mesh = ls.Mesh()
ls.ToSurfaceMesh(geometry.getLevelSets()[si_idx], mesh).apply()
nodes = np.array(mesh.getNodes())
triangles = np.array(mesh.getTriangles())
print(f"3D mesh (Si only): {len(nodes)} nodes, {len(triangles)} triangles")

fig = plt.figure(figsize=(6, 6), facecolor="white")
ax = fig.add_subplot(projection="3d")
poly = Poly3DCollection(nodes[triangles], facecolors="#b8763f", edgecolor="none",
                          alpha=1.0, shade=True, lightsource=plt.matplotlib.colors.LightSource(azdeg=200, altdeg=45))
ax.add_collection3d(poly)
ax.set_xlim(nodes[:, 0].min(), nodes[:, 0].max())
ax.set_ylim(nodes[:, 1].min(), nodes[:, 1].max())
ax.set_zlim(nodes[:, 2].min(), nodes[:, 2].max())
ax.view_init(elev=25, azim=-55)
ax.set_axis_off()
ax.set_title("HBM4 TSV -- tuned Bosch etch profile (3D)")
plt.tight_layout()
plt.savefig("fig_3d_via.png", dpi=150, facecolor="white")
print("saved fig_3d_via.png")
