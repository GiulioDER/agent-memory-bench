# How deploy events join to traces

The span carries `deploy.at` as an RFC 3339 instant. The join is exact:
we match the deploy line's stamp against it with no tolerance window,
because two deploys inside the same minute are routine on release days.

A date alone loses that entirely. It also loses every deploy that
straddles midnight UTC, which is when the EU release window sits.
