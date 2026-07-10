# Dry Etch Autoresearch Log

## Generation 1

Input best:

```json
{
  "best_mean_bulge": 0.012303270972788752,
  "best_mean_depth": 1.282514235751915,
  "best_name": "etch_broad_0052",
  "best_p90_dry_etch_score": 1.6795719929600583,
  "best_recipe": {
    "deposition_sticking_probability": 0.005,
    "deposition_thickness": 0.005,
    "etch_time": 0.5,
    "initial_etch_time": 0.2,
    "ion_source_exponent": 600,
    "mask_taper": 4.0,
    "name": "etch_broad_0052",
    "neutral_rate": -0.08,
    "neutral_sticking_probability": 0.05,
    "num_cycles": 15,
    "recipe_hash": "6831a9629ef8",
    "recipe_id": 54,
    "theta_r_min": 75.0
  },
  "best_target_pass_rate": 1.0,
  "boundary_notes": [],
  "recipes": 96,
  "replicates": 3,
  "rows": 288,
  "top_effect_ranges": [
    [
      "deposition_thickness",
      5.027467556648416
    ],
    [
      "neutral_rate",
      2.9402475676333255
    ],
    [
      "num_cycles",
      2.8659879299242497
    ],
    [
      "etch_time",
      2.0799914773047457
    ],
    [
      "neutral_sticking_probability",
      1.8706882132299705
    ]
  ]
}
```

Plan:

```json
{
  "anchors": [
    {
      "deposition_sticking_probability": 0.005,
      "deposition_thickness": 0.005,
      "etch_time": 0.5,
      "initial_etch_time": 0.2,
      "ion_source_exponent": 600,
      "mask_taper": 4.0,
      "name": "carry_00_etch_broad_0052",
      "neutral_rate": -0.08,
      "neutral_sticking_probability": 0.05,
      "num_cycles": 15,
      "theta_r_min": 75.0
    },
    {
      "deposition_sticking_probability": 0.01,
      "deposition_thickness": 0.005,
      "etch_time": 0.5,
      "initial_etch_time": 0.3,
      "ion_source_exponent": 400,
      "mask_taper": 2.0,
      "name": "carry_01_etch_focus_0023",
      "neutral_rate": -0.08,
      "neutral_sticking_probability": 0.08,
      "num_cycles": 14,
      "theta_r_min": 45.0
    },
    {
      "deposition_sticking_probability": 0.01,
      "deposition_thickness": 0.01,
      "etch_time": 0.5,
      "initial_etch_time": 0.2,
      "ion_source_exponent": 100,
      "mask_taper": 2.0,
      "name": "carry_02_etch_broad_0016",
      "neutral_rate": -0.12,
      "neutral_sticking_probability": 0.12,
      "num_cycles": 13,
      "theta_r_min": 45.0
    },
    {
      "deposition_sticking_probability": 0.01,
      "deposition_thickness": 0.01,
      "etch_time": 0.5,
      "initial_etch_time": 0.3,
      "ion_source_exponent": 200,
      "mask_taper": 0.0,
      "name": "carry_03_target_score_candidate",
      "neutral_rate": -0.12,
      "neutral_sticking_probability": 0.05,
      "num_cycles": 14,
      "theta_r_min": 60.0
    },
    {
      "deposition_sticking_probability": 0.02,
      "deposition_thickness": 0.01,
      "etch_time": 0.45,
      "initial_etch_time": 0.3,
      "ion_source_exponent": 400,
      "mask_taper": 0.0,
      "name": "carry_04_etch_focus_0009",
      "neutral_rate": -0.15,
      "neutral_sticking_probability": 0.05,
      "num_cycles": 12,
      "theta_r_min": 45.0
    },
    {
      "deposition_sticking_probability": 0.005,
      "deposition_thickness": 0.01,
      "etch_time": 0.55,
      "initial_etch_time": 0.2,
      "ion_source_exponent": 200,
      "mask_taper": 2.0,
      "name": "carry_05_etch_broad_0049",
      "neutral_rate": -0.15,
      "neutral_sticking_probability": 0.05,
      "num_cycles": 10,
      "theta_r_min": 45.0
    },
    {
      "deposition_sticking_probability": 0.01,
      "deposition_thickness": 0.01,
      "etch_time": 0.5,
      "initial_etch_time": 0.3,
      "ion_source_exponent": 200,
      "mask_taper": 0.0,
      "name": "carry_06_current_production",
      "neutral_rate": -0.1,
      "neutral_sticking_probability": 0.05,
      "num_cycles": 14,
      "theta_r_min": 60.0
    },
    {
      "deposition_sticking_probability": 0.005,
      "deposition_thickness": 0.005,
      "etch_time": 0.4,
      "initial_etch_time": 0.3,
      "ion_source_exponent": 600,
      "mask_taper": 2.0,
      "name": "carry_07_etch_focus_0024",
      "neutral_rate": -0.12,
      "neutral_sticking_probability": 0.05,
      "num_cycles": 16,
      "theta_r_min": 75.0
    }
  ],
  "decision_notes": [
    "mask_taper: focused around top values [0.0, 2.0, 4.0] -> [0.0, 2.0, 4.0, 6.0]",
    "num_cycles: focused around top values [10, 12, 13, 14, 15, 16] -> [8, 10, 11, 12, 13, 14, 15, 16, 18]",
    "etch_time: focused around top values [0.4, 0.45, 0.5, 0.55] -> [0.35, 0.4, 0.45, 0.5, 0.55, 0.6]",
    "neutral_rate: focused around top values [-0.15, -0.12, -0.1, -0.08] -> [-0.06, -0.08, -0.1, -0.12, -0.15, -0.18]",
    "neutral_sticking_probability: focused around top values [0.05, 0.08, 0.12] -> [0.03, 0.05, 0.08, 0.12, 0.16]",
    "initial_etch_time: focused around top values [0.2, 0.3] -> [0.15, 0.2, 0.3, 0.45]",
    "deposition_thickness: focused around top values [0.005, 0.01] -> [0.003, 0.005, 0.01, 0.015]",
    "deposition_sticking_probability: focused around top values [0.005, 0.01, 0.02] -> [0.003, 0.005, 0.01, 0.02, 0.04]",
    "ion_source_exponent: focused around top values [100, 200, 400, 600] -> [50, 100, 200, 400, 600, 800]",
    "theta_r_min: focused around top values [45.0, 60.0, 75.0] -> [30.0, 45.0, 60.0, 75.0, 90.0]"
  ],
  "focus_space": {
    "deposition_sticking_probability": [
      0.003,
      0.005,
      0.01,
      0.02,
      0.04
    ],
    "deposition_thickness": [
      0.003,
      0.005,
      0.01,
      0.015
    ],
    "etch_time": [
      0.35,
      0.4,
      0.45,
      0.5,
      0.55,
      0.6
    ],
    "initial_etch_time": [
      0.15,
      0.2,
      0.3,
      0.45
    ],
    "ion_source_exponent": [
      50,
      100,
      200,
      400,
      600,
      800
    ],
    "mask_taper": [
      0.0,
      2.0,
      4.0,
      6.0
    ],
    "neutral_rate": [
      -0.06,
      -0.08,
      -0.1,
      -0.12,
      -0.15,
      -0.18
    ],
    "neutral_sticking_probability": [
      0.03,
      0.05,
      0.08,
      0.12,
      0.16
    ],
    "num_cycles": [
      8,
      10,
      11,
      12,
      13,
      14,
      15,
      16,
      18
    ],
    "theta_r_min": [
      30.0,
      45.0,
      60.0,
      75.0,
      90.0
    ]
  },
  "generation": 1,
  "space": {
    "deposition_sticking_probability": [
      0.003,
      0.005,
      0.01,
      0.02,
      0.04
    ],
    "deposition_thickness": [
      0.003,
      0.005,
      0.01,
      0.015
    ],
    "etch_time": [
      0.35,
      0.4,
      0.45,
      0.5,
      0.55,
      0.6
    ],
    "initial_etch_time": [
      0.15,
      0.2,
      0.3,
      0.45
    ],
    "ion_source_exponent": [
      50,
      100,
      200,
      400,
      600,
      800
    ],
    "mask_taper": [
      0.0,
      2.0,
      4.0,
      6.0
    ],
    "neutral_rate": [
      -0.06,
      -0.08,
      -0.1,
      -0.12,
      -0.15,
      -0.18
    ],
    "neutral_sticking_probability": [
      0.03,
      0.05,
      0.08,
      0.12,
      0.16
    ],
    "num_cycles": [
      8,
      10,
      11,
      12,
      13,
      14,
      15,
      16,
      18
    ],
    "theta_r_min": [
      30.0,
      45.0,
      60.0,
      75.0,
      90.0
    ]
  },
  "top_n": 8
}
```

Output best:

```json
{
  "best_mean_bulge": 0.0024514378957487537,
  "best_mean_depth": 1.2370744415942632,
  "best_name": "carry_01_etch_focus_0023",
  "best_p90_dry_etch_score": 1.2922347350069492,
  "best_recipe": {
    "deposition_sticking_probability": 0.01,
    "deposition_thickness": 0.005,
    "etch_time": 0.5,
    "initial_etch_time": 0.3,
    "ion_source_exponent": 400,
    "mask_taper": 2.0,
    "name": "carry_01_etch_focus_0023",
    "neutral_rate": -0.08,
    "neutral_sticking_probability": 0.08,
    "num_cycles": 14,
    "recipe_hash": "1efede9c77d2",
    "recipe_id": 1,
    "theta_r_min": 45.0
  },
  "best_target_pass_rate": 1.0,
  "boundary_notes": [],
  "recipes": 96,
  "replicates": 4,
  "rows": 384,
  "top_effect_ranges": [
    [
      "num_cycles",
      8.213888076018582
    ],
    [
      "theta_r_min",
      2.985650072424387
    ],
    [
      "neutral_rate",
      2.9501647093334467
    ],
    [
      "mask_taper",
      2.7262499668195623
    ],
    [
      "neutral_sticking_probability",
      2.550093430534366
    ]
  ]
}
```

## Generation 2

Input best:

```json
{
  "best_mean_bulge": 0.0024514378957487537,
  "best_mean_depth": 1.2370744415942632,
  "best_name": "carry_01_etch_focus_0023",
  "best_p90_dry_etch_score": 1.2922347350069492,
  "best_recipe": {
    "deposition_sticking_probability": 0.01,
    "deposition_thickness": 0.005,
    "etch_time": 0.5,
    "initial_etch_time": 0.3,
    "ion_source_exponent": 400,
    "mask_taper": 2.0,
    "name": "carry_01_etch_focus_0023",
    "neutral_rate": -0.08,
    "neutral_sticking_probability": 0.08,
    "num_cycles": 14,
    "recipe_hash": "1efede9c77d2",
    "recipe_id": 1,
    "theta_r_min": 45.0
  },
  "best_target_pass_rate": 1.0,
  "boundary_notes": [],
  "recipes": 96,
  "replicates": 4,
  "rows": 384,
  "top_effect_ranges": [
    [
      "num_cycles",
      8.213888076018582
    ],
    [
      "theta_r_min",
      2.985650072424387
    ],
    [
      "neutral_rate",
      2.9501647093334467
    ],
    [
      "mask_taper",
      2.7262499668195623
    ],
    [
      "neutral_sticking_probability",
      2.550093430534366
    ]
  ]
}
```

Plan:

```json
{
  "anchors": [
    {
      "deposition_sticking_probability": 0.01,
      "deposition_thickness": 0.005,
      "etch_time": 0.5,
      "initial_etch_time": 0.3,
      "ion_source_exponent": 400,
      "mask_taper": 2.0,
      "name": "carry_00_carry_01_etch_focus_0023",
      "neutral_rate": -0.08,
      "neutral_sticking_probability": 0.08,
      "num_cycles": 14,
      "theta_r_min": 45.0
    },
    {
      "deposition_sticking_probability": 0.04,
      "deposition_thickness": 0.015,
      "etch_time": 0.55,
      "initial_etch_time": 0.15,
      "ion_source_exponent": 50,
      "mask_taper": 2.0,
      "name": "carry_01_etch_focus_0026",
      "neutral_rate": -0.15,
      "neutral_sticking_probability": 0.16,
      "num_cycles": 12,
      "theta_r_min": 45.0
    },
    {
      "deposition_sticking_probability": 0.005,
      "deposition_thickness": 0.003,
      "etch_time": 0.6,
      "initial_etch_time": 0.2,
      "ion_source_exponent": 600,
      "mask_taper": 2.0,
      "name": "carry_02_etch_focus_0014",
      "neutral_rate": -0.06,
      "neutral_sticking_probability": 0.12,
      "num_cycles": 14,
      "theta_r_min": 45.0
    },
    {
      "deposition_sticking_probability": 0.005,
      "deposition_thickness": 0.005,
      "etch_time": 0.5,
      "initial_etch_time": 0.2,
      "ion_source_exponent": 600,
      "mask_taper": 4.0,
      "name": "carry_03_carry_00_etch_broad_0052",
      "neutral_rate": -0.08,
      "neutral_sticking_probability": 0.05,
      "num_cycles": 15,
      "theta_r_min": 75.0
    }
  ],
  "decision_notes": [
    "mask_taper: focused around top values [2.0, 4.0] -> [0.0, 2.0, 4.0, 6.0]",
    "num_cycles: focused around top values [12, 14, 15] -> [11, 12, 13, 14, 15, 16]",
    "etch_time: focused around top values [0.5, 0.55, 0.6] -> [0.45, 0.5, 0.55, 0.6, 0.7]",
    "neutral_rate: focused around top values [-0.15, -0.08, -0.06] -> [-0.04, -0.06, -0.08, -0.1, -0.12, -0.15, -0.18]",
    "neutral_sticking_probability: focused around top values [0.05, 0.08, 0.12, 0.16] -> [0.03, 0.05, 0.08, 0.12, 0.16, 0.2]",
    "initial_etch_time: focused around top values [0.15, 0.2, 0.3] -> [0.1, 0.15, 0.2, 0.3, 0.45]",
    "deposition_thickness: focused around top values [0.003, 0.005, 0.015] -> [0.001, 0.003, 0.005, 0.01, 0.015, 0.02]",
    "deposition_sticking_probability: focused around top values [0.005, 0.01, 0.04] -> [0.003, 0.005, 0.01, 0.02, 0.04, 0.06]",
    "ion_source_exponent: focused around top values [50, 400, 600] -> [25, 50, 100, 200, 400, 600, 800]",
    "theta_r_min: focused around top values [45.0, 75.0] -> [30.0, 45.0, 60.0, 75.0, 90.0]"
  ],
  "focus_space": {
    "deposition_sticking_probability": [
      0.003,
      0.005,
      0.01,
      0.02,
      0.04,
      0.06
    ],
    "deposition_thickness": [
      0.001,
      0.003,
      0.005,
      0.01,
      0.015,
      0.02
    ],
    "etch_time": [
      0.45,
      0.5,
      0.55,
      0.6,
      0.7
    ],
    "initial_etch_time": [
      0.1,
      0.15,
      0.2,
      0.3,
      0.45
    ],
    "ion_source_exponent": [
      25,
      50,
      100,
      200,
      400,
      600,
      800
    ],
    "mask_taper": [
      0.0,
      2.0,
      4.0,
      6.0
    ],
    "neutral_rate": [
      -0.04,
      -0.06,
      -0.08,
      -0.1,
      -0.12,
      -0.15,
      -0.18
    ],
    "neutral_sticking_probability": [
      0.03,
      0.05,
      0.08,
      0.12,
      0.16,
      0.2
    ],
    "num_cycles": [
      11,
      12,
      13,
      14,
      15,
      16
    ],
    "theta_r_min": [
      30.0,
      45.0,
      60.0,
      75.0,
      90.0
    ]
  },
  "generation": 2,
  "space": {
    "deposition_sticking_probability": [
      0.003,
      0.005,
      0.01,
      0.02,
      0.04,
      0.06
    ],
    "deposition_thickness": [
      0.001,
      0.003,
      0.005,
      0.01,
      0.015,
      0.02
    ],
    "etch_time": [
      0.45,
      0.5,
      0.55,
      0.6,
      0.7
    ],
    "initial_etch_time": [
      0.1,
      0.15,
      0.2,
      0.3,
      0.45
    ],
    "ion_source_exponent": [
      25,
      50,
      100,
      200,
      400,
      600,
      800
    ],
    "mask_taper": [
      0.0,
      2.0,
      4.0,
      6.0
    ],
    "neutral_rate": [
      -0.04,
      -0.06,
      -0.08,
      -0.1,
      -0.12,
      -0.15,
      -0.18
    ],
    "neutral_sticking_probability": [
      0.03,
      0.05,
      0.08,
      0.12,
      0.16,
      0.2
    ],
    "num_cycles": [
      11,
      12,
      13,
      14,
      15,
      16
    ],
    "theta_r_min": [
      30.0,
      45.0,
      60.0,
      75.0,
      90.0
    ]
  },
  "top_n": 4
}
```

Output best:

```json
{
  "best_mean_bulge": 0.00268150414537717,
  "best_mean_depth": 1.1627996662859488,
  "best_name": "etch_focus_0006",
  "best_p90_dry_etch_score": 1.1721525819920824,
  "best_recipe": {
    "deposition_sticking_probability": 0.003,
    "deposition_thickness": 0.005,
    "etch_time": 0.6,
    "initial_etch_time": 0.3,
    "ion_source_exponent": 600,
    "mask_taper": 2.0,
    "name": "etch_focus_0006",
    "neutral_rate": -0.08,
    "neutral_sticking_probability": 0.2,
    "num_cycles": 12,
    "recipe_hash": "15252a63cb7c",
    "recipe_id": 10,
    "theta_r_min": 45.0
  },
  "best_target_pass_rate": 1.0,
  "boundary_notes": [],
  "recipes": 64,
  "replicates": 4,
  "rows": 256,
  "top_effect_ranges": [
    [
      "etch_time",
      4.121692118755663
    ],
    [
      "neutral_sticking_probability",
      3.963852550589025
    ],
    [
      "ion_source_exponent",
      3.668656714201003
    ],
    [
      "deposition_thickness",
      3.423997865125111
    ],
    [
      "theta_r_min",
      2.8708460120266235
    ]
  ]
}
```

