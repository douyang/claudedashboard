# Dashboard data

The artifact database holds the collections below. All timestamps are UTC.

## Data planes and access

| Plane | Where | Who reads and writes |
|---|---|---|
| The board owner | `jobs`, `projects`, `sessions`, `syncs`, `ticks`, `meta` at the top level | The board owner only. |
| A person | `data/users/<id>/profile/<collection>` with the same collection names, and the document `data/users/<id>/profile` | That person and the board owner. |
| The person registry | `join/<id>` | That person and the board owner. |

`<id>` is the person's user id on the board. In `ArtifactData`, write `data/users/me/...` and the platform resolves `me` to the writer. The page declares the rules that enforce this (see the README). The page never trusts an `owner` field in a document. A document's owner is the plane it was read from.

The collections below have the same fields on every plane.

## `projects/<slug>`

The registry. One document per project.

| Field | Meaning |
|---|---|
| `name` | The project name on the board. |
| `aliases` | Other names that job rows use for this project. |
| `where` | `cloud` or `local`. When absent, the board derives it from the sessions and job surfaces. |
| `surface` | For example `Claude Code · cloud` or `Cowork`. |
| `sessions` | Session ids that belong to the project. |
| `repos`, `artifacts` | Links shown on the project card. |
| `status` | `active`, `paused` or `done`. `paused` and `done` make the project inactive. |
| `pinned` | `true` keeps the project active. |
| `color` | A fixed colour slot, 1 to 8. A project without one draws in grey as Other. Eight is the most colours a chart can keep apart for readers with colour-vision deficiency. |
| `lastActivityAt` | Set by a reporting session. A registry edit does not set it. |

A session that no project lists is grouped by its first repository. Without a repository it forms a project named by its title.

## `sessions/<session id>`

One document per session. `tok` counts input, cache reads, cache writes and output. `usd` is the cost at API list prices. `partial: true` marks a floor. When the Claude Code Remote connector answers, the live figures replace the stored ones for the board owner's cloud sessions.

## `syncs/<epoch seconds>`

One document per hourly sync. A scheduled routine calls `list_sessions`, runs `scripts/ccr_sync_doc.py`, and writes the result. Fields: `at`, `src`, `sessions` (id, title, status, bucket, model, createdAt, updatedAt, tok, out, usd, repos), and `quota` (the limit state of the most recently updated session). The page reads the last 8 days. The newest sync of each person supplies that person's cloud sessions when the page cannot read Claude Code Remote itself, for example when the connector answers `blocked_by_policy`. The sync stores no message text and no task summaries.

`bucket` is Claude Code's own state: `working`, `blocked` (waits on a person), `review_ready`, `completed` or `failed`.

## `daily/<UTC day>`

The ledger. One entry per UTC day, written by the sync at the day's first reading and never replaced: the board keeps the first one. Fields: `day`, `at`, `src`, `cols` (id, title, status, tok, out, usd, createdAt, repo), and `rows`, one array per session with the totals at that reading. An entry is about 4 KB for 22 sessions. The page reads every entry, so the ledger never leaves the window.

A completed day that has hourly readings but no entry gets one from the page, made from the day's first reading. `scripts/ccr_sync_doc.py --from-sync SYNC.json DAILY.json` makes the same entry.

The ledger keeps three things that the hourly readings cannot:
- Usage per day for the 30 d, 90 d and All ranges, after the hourly readings leave the 8-day window.
- A session that Claude Code no longer lists. The board counts its last known totals and marks it "No longer listed".
- A durable copy for the CSV export.

## `ticks/<session id>~<UTC day>`

Usage snapshots. `pts` is an array of `[epoch seconds, cumulative tokens]`. One document per session per day keeps the database far below its 25,000-document limit.

## `jobs/<id>`

One row per task. The dashboard's "Posting from another Claude session" panel lists the fields.

## `meta/board`, `meta/quota`

`meta/board` holds a note. `meta/quota` holds the board owner's account limit as Claude Code reports it. Everyone else stores the same fields as the object `quota` in the document `data/users/<id>/profile`.

## `join/<id>`

Written by a person when they open the board: `name`, `joinedAt`, `seenAt`. The board owner adds `label`, the name that the board shows. The board lists a person under People from this document.

## How the page computes its figures

- **Points.** For each session, the page builds a series of `[time, cumulative tokens]`: zero at `createdAt` for a cloud session, every sync and snapshot, and the current total at `updatedAt` (or at the live read time for a running session). The series never decreases.
- **Measured tokens.** Between two consecutive points at most 3 hours apart, the page spreads the growth evenly over the time between them. Growth across a longer gap is **unplaced**: the tokens are in the totals and in no hour. Equal totals at both ends count as measured zero, whatever the gap.
- **Windows.** The last hour, 24 hours and 7 days end at the newest reading. Each says how long the readings cover inside it. A rate divides the measured tokens by that covered time.
- **Days.** Last 30 days and the 30 d, 90 d and All ranges accept readings at most 26 hours apart. Hourly readings keep their own time. A pair of ledger readings places its tokens in the UTC day of the earlier reading. A gap longer than 26 hours places nothing.
- **Sessions that left.** A session that appears in the hourly readings or the ledger but not in the newest listing keeps its last known totals, marked "No longer listed". Its tokens stay in All tokens and cost.
- **Last token use.** The end of the last interval in which a session's total grew. A project takes the latest of its sessions.
- **Cost.** At API list prices, as Claude Code reports it, in whole dollars. A project with tokens but no reported cost (a Cowork session) gets the account's dollars per token, marked with ≈.
- **At the end of the open jobs.** Each running or queued job adds its `tokEst` less its `tok`. A job with a time estimate and no `tokEst` adds the project's measured rate times its time left. A job with neither adds nothing, and the board says so. Cost uses the project's own dollars per token.
- **Working now.** A running session, or a running job that reported in the last 30 minutes.
- **Active.** Working now, an open job, or any activity in the last 72 hours. `status` and `pinned` override this.
- **Cloud or local.** The registry `where` first. Else Claude Code cloud sessions and `Claude Code · web` rows count as cloud, and `Cowork` and `CLI` rows count as local.
- **Colours.** Each project draws in its registry slot in the chart, the table, and on its card. The bars stack in slot order.
