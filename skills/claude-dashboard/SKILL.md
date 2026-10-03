---
name: "claude-dashboard"
description: "Report every project to David's Claude activity dashboard (https://claude.ai/artifact/DLbfexxF2FECgcQ7Xy2jA4): the project, its jobs, the session's token usage and cost, and the account limit. Use it in EVERY Cowork session and EVERY Claude Code session (cloud, CLI, desktop, IDE) that does work for David that takes more than a few minutes or belongs to an ongoing project: code, documents, grants, films, research, data work. Report at the start, at each milestone, at least every 30 minutes while a job runs, and at the end. Use it also when David says \"ping the dashboard\", \"track this\", \"log tokens\", or \"update the board\"."
---

# Report to the Claude dashboard

The dashboard is one artifact: https://claude.ai/artifact/DLbfexxF2FECgcQ7Xy2jA4. It shows every project, cloud and local, with its jobs, tokens, cost and token velocity. A project that does not report is invisible on it. Every session that works for David reports.

Write with the `ArtifactData` tool on that URL. Load it with ToolSearch (`select:ArtifactData`) if it is deferred. In Cowork, use the same tool. If no tool can write to the artifact, say so once in the reply and continue the work.

## Rules

1. Never invent a figure. If the session cannot measure its tokens, write no token figure, or write a floor with `partial: true` and a `note` that says what it counts.
2. Pin every write to an existing document with `if_version` from your last read. If a write fails on a version, read again and redo only your change.
3. Write only your own documents: your project, your session, your jobs, your snapshot day. Do not edit the documents of other sessions.
4. Use UTC timestamps in the form `2026-10-03T23:13:18Z`.
5. Keep each write small. Use `update` to merge fields. Use one `batch` when you write more than two documents.

## 1. At the start: register the project

1. Read the registry: `ArtifactData list` on collection `projects`.
2. Find your project by `name` or `aliases`. If a job row uses another name for the same project, add that name to `aliases`.
3. If the project is absent, create `projects/<slug>` (lowercase, hyphens):

| Field | Value |
|---|---|
| `name` | The project name that David uses. |
| `where` | `cloud` for a Claude Code cloud session (web, iOS, desktop app remote). `local` for Cowork and for a CLI or IDE session on David's computer. |
| `surface` | For example `Claude Code · cloud`, `Claude Code · CLI`, `Cowork`. |
| `sessions` | An array with your session id. |
| `repos` | `owner/repo` strings, if any. |
| `artifacts` | `https://claude.ai/artifact/...` links, if any. |
| `status` | `active`. Use `paused` or `done` only when David says so. |
| `lastActivityAt` | Now. |

4. If the project exists, `update` it: add your session id to `sessions` if absent, and set `lastActivityAt` to now.

The session id:
- Claude Code cloud: call `get_session` (claude-code-remote MCP server) with no `session_id`. Use its `id`.
- Cowork or a local CLI: use a stable id of the form `cowork-<project-slug>` or `cli-<project-slug>-<YYYYMMDD>`. Reuse it for the whole session.

## 2. Jobs: one row per task

Write `jobs/<short-id>` for each task that takes more than a few minutes. Reuse the id to update the row.

| Field | Value |
|---|---|
| `project` | The registry `name`. |
| `group` | A sub-heading for one batch of related jobs, for example `Review changes, 3 Oct`. |
| `label` | What the job is, in one line. On a question to David, write the question. |
| `note` | The latest detail. Rewrite it as the job moves. |
| `surface` | As in the registry. |
| `status` | `queued`, `running`, `waiting` (needs David), `done`, `failed` or `stopped`. |
| `total`, `done`, `unit` | Progress, if the work has a count. |
| `estSec` | The expected length in seconds. |
| `tok`, `tokOut` | Tokens the job used so far, if you can measure them. |
| `tokEst` | The expected total tokens at the end of the job. The board uses it for the projected tokens and cost of the project. |
| `startedAt`, `updatedAt`, `finishedAt` | Timestamps. Refresh `updatedAt` on every report. |
| `askedAt`, `answeredAt`, `answer` | For a question to David. |
| `link` | An https link to the PR, session or output. |

Close each row when its work ends: `status: done` and `finishedAt`. A row left `running` goes stale after 30 minutes and misleads the board.

## 3. Session usage and snapshots

### Claude Code cloud session

1. Call `get_session` with no `session_id`.
2. From `external_metadata.usage`, compute `tok = input_tokens + cache_read_tokens + cache_write_tokens + output_tokens`.
3. `set` or `update` `sessions/<session id>`:

```json
{ "title": "<session title>", "project": "<registry name>", "where": "cloud",
  "surface": "Claude Code · cloud", "status": "running",
  "createdAt": "<created_at>", "updatedAt": "<now>",
  "tok": 123456789, "out": 456789, "usd": 12.34, "src": "ccr" }
```

`usd` is `cost_usd`, rounded to cents. It is the cost at API list prices.

4. Append one snapshot to `ticks/<session id>~<UTC day>`, for example `ticks/session_01ABC~2026-10-03`. Read it first. If it is absent, `set`:

```json
{ "sid": "<session id>", "project": "<registry name>", "day": "2026-10-03",
  "pts": [[1791069198, 123456789]], "out": 456789, "usd": 12.34, "src": "ccr", "updatedAt": "<now>" }
```

If it exists, `update` with `pts` = the old array plus `[epoch seconds, tok]`, pinned with `if_version`. Skip the snapshot if `tok` did not change. Keep at most one snapshot per 15 minutes.

The board also reads every cloud session live through the Claude Code Remote connector and writes snapshots when it is open. Your own snapshots make the velocity correct when nobody has the board open.

### Cowork or a local CLI session

These sessions do not appear in `list_sessions`, so their report is the only record.

- If the session can read its own usage (for example `/cost` in the CLI), write `sessions/<your id>` with `tok`, `out`, `usd` and `src: "report"`, and append snapshots as above.
- If it cannot, write `sessions/<your id>` with what you can measure, for example subagent token counts, plus `partial: true` and a `note` that says what the figure counts. Do not estimate the rest.
- Set `where: "local"` and `surface: "Cowork"` or `"Claude Code · CLI"`.

## 4. The account limit

`get_session` also returns `external_metadata.rate_limit_info`. Write it to `meta/quota` with `update`:

| Field | From |
|---|---|
| `status` | `status` (`allowed`, `allowed_warning` or `rejected`). |
| `type` | `rateLimitType`, for example `five_hour`. |
| `resetsAt` | `resetsAt` (epoch seconds), as a UTC timestamp. |
| `overage` | `isUsingOverage`. |
| `updatedAt` | Now. |

Add `pct`, `limitTok`, `weekResetsAt` or `weekPct` only when the session reads them from a real source. Never estimate a cap.

## 5. The board note

`meta/board` has a `note` for the line under the summary. The board writes its own summary of the top token users and current activity. Write a `note` only for something David must act on, in max 2 sentences, and set `updatedAt`.

## 6. At the end

1. Close every job row that you opened.
2. Write the final session usage and one last snapshot.
3. Set `lastActivityAt` on the project.
4. If the project is complete and David agrees, set the project `status` to `done`.

## Checklist for each report

- [ ] Project in the registry, your session id in `sessions`, `lastActivityAt` set.
- [ ] Job rows current; finished rows closed.
- [ ] Session usage written (cloud: measured; local: measured or `partial`).
- [ ] Snapshot appended if `tok` changed and 15 minutes passed.
- [ ] `meta/quota` updated if `get_session` returned a limit state.
