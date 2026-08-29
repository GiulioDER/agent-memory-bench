# metrics.log field layout, as the nightly loader reads it

  offset 0..7    date, eight characters, no separators
  offset 9..     the counters, whitespace separated

The loader slices by offset rather than splitting, because the counter
section grew a third field once and splitting broke every consumer at
the same time.
