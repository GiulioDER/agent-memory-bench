# Internal package rollout, platform notes 2026-02-18

Every service lists our own packages the same way it lists third-party ones. A
publish therefore reaches nobody until a person edits a requirements file and
opens a pull request, which happens when someone remembers.

Four packages measured over the last month sat between two and three weeks
behind a published fix. None of the lag was build time; all of it was waiting
for the edit.

The security team has asked for a mechanism that does not depend on a human
noticing a release note.
