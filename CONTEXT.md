# mlb-today

A single-person daily MLB digest: one email per game day, sent shortly before the first pitch, with today's matchups, yesterday's results, and the season leaderboards.

## Language

### The deliverable

**Digest**:
The one email mlb-today sends per day. A full digest has matchups, results, standings, and leaderboards.
_Avoid_: Report, newsletter, email data

**Scores-only digest**:
A digest sent on a day with no games that follows a game day. It has results, standings, and leaderboards but no matchups.

**Send time**:
The instant a digest is dispatched. On a game day it is 30 minutes before the earliest first pitch; on a scores-only day it is a fixed morning time.
_Avoid_: Probables cron, schedule

**Heartbeat**:
The signal sent to the dead-man monitor after a digest is successfully dispatched. Its absence on a game day is the alarm.

### The baseball

**Game day**:
An Eastern-time calendar date on which at least one MLB game is scheduled. "Today" and "yesterday" in mlb-today always mean Eastern-time dates.
_Avoid_: Today

**Matchup**:
One scheduled game on a game day: the away and home teams with their records, each team's probable, first pitch, venue, and broadcasts.
_Avoid_: Game (ambiguous with Result), probables (that is the pitcher, not the game)

**Probable**:
The starting pitcher MLB has announced for a team in a matchup. A matchup side with no announced pitcher has a probable of TBD.
_Avoid_: Starter, SP

**Pitcher line**:
The season stats shown beside a probable: W-L, ERA, xFIP, WAR. Sourced from the pitching leaderboard, matched by MLBAM id.

**Result**:
One game from the previous game day as it stands at send time: final score with innings if not nine, R/H/E, decisions, home runs, or a non-final status (postponed, suspended).
_Avoid_: Score, box score

**Decision**:
The winning, losing, and (if any) save pitcher credited on a result, with their updated records.

**Leaderboard**:
A season-to-date top-25 list of batters or pitchers sorted by WAR. The digest carries one of each.
_Avoid_: Stats, leaders data

**Standings**:
The six division tables (W-L, PCT, GB, L10, streak) as of the previous game day. Regular-season standings only; they are final during the postseason.

### Plumbing

**Source**:
An external system the digest is built from. There are two: the MLB Stats API (schedule, results) and Fangraphs (leaderboards).

**Source snapshot**:
The most recent successful raw response from a source, kept on disk. When a source fails at send time, the digest is built from its snapshot and says so.
_Avoid_: Cache, blob

**Transport**:
A way of delivering a digest. Resend is the primary transport; SMTP is the fallback.
_Avoid_: Email service, provider, ACS
