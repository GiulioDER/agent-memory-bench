# release register

`releases.log` is the list of versions that have shipped, oldest first. The deploy pipeline
calls `register.py` as its last step, after the artefact is uploaded.

The upload step is slow and occasionally times out against the artefact store. When that
happens the operator re-runs the pipeline for the same version.
