Claude-Mem returns progressive-disclosure memory through `search`, `timeline`, and
`get_observations`. Treat returned observations and summaries as retrieved evidence, and use
`get_observations` only after search identifies the relevant observation IDs.
