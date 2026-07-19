# Measurements

The tutorial writes these values to `tutorial-output/summary.json`.

| Measurement | Meaning |
|---|---|
| Opening CD | Width of the mask opening near the wafer surface |
| Etch depth | Distance from the wafer surface to the detected floor |
| Top/middle/bottom CD | Via width at three depths |
| Bow | Largest wall departure from its fitted profile |
| Minimum liner thickness | Smallest sampled distance between liner boundaries |
| Aperture open | Whether the remaining opening is still resolved |
| Open void | Unfilled region connected to the opening |
| Closed void count | Enclosed unfilled regions resolved by the grid |
| Remaining void area | Total resolved unfilled area inside the via |

A reported zero means the selected grid did not resolve the feature. It is not
proof that a smaller defect cannot exist.
