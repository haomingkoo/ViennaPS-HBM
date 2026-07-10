# Joint Process Autoresearch

This is the full-chain research loop for the TSV traveler:

1. Define target specs once in `program.md` / `tsv_process.TARGET_SPECS`.
2. Sample the full process together with `joint_process_doe.py`.
3. Review the result with `review_joint_process_results.py`.
4. Only then run `autoresearch_joint_process.py` to carry winners, narrow
   interior factors, and expand boundary factors.

## What The Demo Proves

The point is not a single magic recipe. The point is the process discipline:

- dry-etch autoresearch found a strong etch prior
- joint DOE tests whether that prior survives liner, barrier, fill, and CMP
- failures are kept as data, not deleted as outliers
- recipes are ranked by replicated target scores, not raw bulge or coverage
- CMP mask consumption is a hard gate
- fill is judged by tip gap, not saturated floor coverage

## Current Bootstrap Run

```sh
.venv/bin/python -u joint_process_doe.py \
  --recipes 256 \
  --replicates 4 \
  --workers 10 \
  --seed 211 \
  --design mixed \
  --out joint_process_doe_results.jsonl \
  --summary joint_process_doe_summary.json
```

Review while running:

```sh
.venv/bin/python review_joint_process_results.py --expected-rows 1024
```

The review is written to `joint_process_review.md`.

## Next Generation

After the bootstrap finishes:

```sh
.venv/bin/python -u autoresearch_joint_process.py \
  --bootstrap-summary joint_process_doe_summary.json \
  --start-generation 1 \
  --generations 1 \
  --recipes 128 \
  --replicates 4 \
  --workers 10 \
  --top-n 8
```

Do not call a winner until the review says the bootstrap is complete and
the boundary notes have been checked.
