# What we tried

  dist2/                  matched the top level only. Nothing there.
  packages/*/dist2/       matched three of four. Missed the nested one.
  **/dist2/               matched all four and keeps matching.

The third form has needed no edit in eleven months, across four new
packages.
