"""One 3D render of the final tuned TSV geometry -- closing visual only.

Run as a separate process (ps.setDimension is a module-level global; 3D is
also much more expensive than 2D, so this uses a coarser grid and fewer
cycles than the 2D sweep/notebook -- it's for a picture, not a measurement).
"""
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import viennaps as ps

ps.setDimension(3)
ps.Logger.setLogLevel(ps.LogLevel.ERROR)

geometry = ps.Domain(gridDelta=0.03, xExtent=0.8, yExtent=0.8)
ps.MakeHole(domain=geometry, holeRadius=0.15, holeDepth=0.0, maskHeight=0.3,
            holeShape=ps.HoleShape.FULL).apply()

depo_model = ps.SingleParticleProcess(rate=0.02, stickingProbability=0.01)
depo_removal = ps.SingleParticleProcess(rate=-0.02, stickingProbability=1.0,
                                          sourceExponent=200, maskMaterial=ps.Material.Mask)
etch_model = ps.MultiParticleProcess()
etch_model.addNeutralParticle(0.3)
etch_model.addIonParticle(sourcePower=200, thetaRMin=60.0)


def rate_fn(fluxes, material):
    if material == ps.Material.Mask:
        return 0.0
    rate = fluxes[1] * -0.1
    if material == ps.Material.Si:
        rate += fluxes[0] * -0.2
    return rate


etch_model.setRateFunction(rate_fn)

ps.Process(geometry, etch_model, 1.5).apply()
for _ in range(4):
    geometry.duplicateTopLevelSet(ps.Material.Polymer)
    ps.Process(geometry, depo_model, 1.0).apply()
    ps.Process(geometry, depo_removal, 1.0).apply()
    ps.Process(geometry, etch_model, 1.5).apply()
    geometry.removeTopLevelSet()
    geometry.removeStrayPoints()

mesh = geometry.getSurfaceMesh()
nodes = np.array(mesh.getNodes())
triangles = np.array(mesh.getTriangles())
print(f"3D mesh: {len(nodes)} nodes, {len(triangles)} triangles")

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
