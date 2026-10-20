# One long-running process owns the schedule

The send time moves every day (30 minutes before the earliest first pitch, Eastern), so a fixed cron entry cannot express it. The Azure version solved this by having the app rewrite its own timer-trigger setting through the Azure management API each morning. The rebuilt app is instead a single long-running container: once a day at a fixed early-morning time (and on every boot) it fetches the schedule, computes the send time, and sleeps until then. Host cron firing a one-shot container every few minutes was rejected because it spreads the scheduling logic across the host and the app and makes "did I already send today?" the app's problem anyway; an at(1)-style two-stage job was rejected because it reproduces the self-scheduling pattern we are trying to remove.

## Consequences

- The container must be restart-safe: on boot it recomputes today's send time and consults the last-sent marker so a restart never double-sends or skips.
- The morning computation must run early enough for international-series games with first pitches before 7:00 AM Eastern.
- There is no HTTP server. Container health is a CLI check against the state file, not an endpoint.
