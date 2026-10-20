# Fetch every source at send time, fall back to the last snapshot

The Azure version pre-fetched Fangraphs leaderboards into blob storage at 6:00 AM and joined them at send time, with blob writes acting as the message bus between functions. The rebuilt app fetches all sources (schedule, yesterday's results, both leaderboards) in one pass at send time, and writes each successful raw response to a mounted volume as a snapshot. If a source fails at send time the digest is built from that source's snapshot and carries a "stale as of" note. A two-phase pre-fetch was rejected because leaderboards change only overnight, so it buys nothing except a second code path to keep in sync.

## Consequences

- One pipeline, one code path, one place to test.
- The volume is required state: snapshots and the last-sent marker live there. Losing it degrades one day's digest at most.
