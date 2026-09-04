# INVALID: no API key, zero sessions completed

This directory is not a measurement and must never be read as one.

On 2026-08-27 I tried to validate that the calibration command line was well-formed by running
it with `OPENROUTER_API_KEY=placeholder`. `scripts/pilot.py` had no `--dry-run`, so instead of
parsing and stopping it executed the full grid. Every session failed to authenticate.

    admitted cells 0, discarded 36 (bare: 36)
    estimated spend: $0.0 (0 tokens)

**This is an operational authentication failure, not a result about any model, task or arm.** No
task's `bare` rate can be inferred from it, in either direction.

Kept rather than deleted so the mistake stays visible, and renamed so nothing picks it up as
`midband-001`. The real calibration, preregistered in
`preregistration/008-midband-task-calibration.md`, must run under that clean id.

The one thing it does establish: the command line resolves correctly. Six tasks times six seeds
gave exactly 36 cells in the `bare` arm alone, which is the grid the preregistration describes.
