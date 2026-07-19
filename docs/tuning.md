# Tuning the example

Use the measurements as feedback. Do not rank a shape from appearance alone.

## Recommended order

1. **Set the mask opening.** Choose the starting CD, height, and taper.
2. **Tune the etch.** Reach the intended depth while keeping top, middle, and
   bottom CD close enough for the next layers.
3. **Check the liner.** Confirm deep coverage and an open aperture.
4. **Check barrier and seed.** Confirm the lower wall remains accessible.
5. **Inspect copper topology.** Look for an open seam, a closed void, or early
   mouth closure.
6. **Set the planarization endpoint.** Clear surface copper without cutting too
   far into the plug.

## Etch controls

| Config key | Model meaning | Useful feedback |
|---|---|---|
| `cycles` | Number of protection-and-etch cycles | Depth and scallop count |
| `time_per_cycle` | Etch duration in each cycle | Depth and CD change |
| `wall_protection` | Protective material added per cycle | Taper, bow, and access |
| `ion_source_exponent` | How narrowly ions arrive | Wall angle and floor access |
| `ion_rate` | Directional silicon removal strength | Depth and bottom CD |
| `neutral_rate` | All-angle silicon removal strength | Bow and lateral widening |
| `neutral_sticking` | Chance that a neutral reacts on contact | Depth distribution and wall attack |
| `wall_protection_sticking` | Chance that protection sticks on contact | Deep protection and taper |
| `minimum_reflection_angle` | Ion reflection rule at the wall | Lower-wall and floor shape |
| `rays_per_point` | Sampled particle paths per surface point | Runtime and repeat spread |

These are model controls. Gas timing, flow, pressure, source power, bias, and
temperature can influence the same physical mechanisms, but they are not
one-to-one equivalents. Use measured wafer profiles and the optional
calibration workflow before converting fitted coefficients into equipment
settings.

## What to do next

For a real study, run a small multi-factor screen rather than changing one
slider until the profile looks good. Measure depth, top/middle/bottom CD, bow,
liner coverage, seed coverage, void topology, and endpoint loss. Repeat promoted
cases with new random streams before narrowing the range.
