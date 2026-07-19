# Reproducing the results

There are two different tasks.

## Rerun the compact tutorial

```bash
uv run tsv-tutorial
```

This executes mask construction, etch, liner, barrier, seed, geometric copper
growth, and ideal planarization. The inputs are in
[`config/tutorial.toml`](../config/tutorial.toml). The command writes the
measured result to `tutorial-output/summary.json`.

The dependency revisions are locked in `uv.lock`. Stochastic process steps use
the checked-in seed. The smoke test verifies that all stages execute and return
usable measurements:

```bash
uv run python tests/test_tutorial_smoke.py
```

## Inspect the larger saved studies

The interactive guide uses larger simulation studies that would make the
tutorial repository bulky. Their reviewed JSON, checkpoints, and checksums are
available in the
[research-data release](https://github.com/haomingkoo/ViennaPS-HBM/releases/tag/research-data-2026-07-19).

The release separates three bundles:

- `evidence.tar.gz`: reviewed simulation evidence;
- `site-build-inputs.tar.gz`: the exact inputs used to build the guide;
- `autoresearch-results.tar.gz`: raw research-loop outputs.

Use `SHA256SUMS` from the same release to verify a download. For example:

```bash
sha256sum --check SHA256SUMS
```

On Windows PowerShell, compare `Get-FileHash <file> -Algorithm SHA256` with the
recorded checksum.

## Current boundary

The compact traveler is runnable from a clean clone. The publication bundle is
replayable and traceable. The full historical campaign has not yet been reduced
to one supported public rerun command, so the guide must not claim that every
published chart can already be regenerated from the clean branch alone.

The remaining release gate is a campaign manifest that maps each published
figure to its command, config, random streams, source revision, and expected
artifact hash. Until that exists, the reviewed release is the authoritative
record for those larger studies.
