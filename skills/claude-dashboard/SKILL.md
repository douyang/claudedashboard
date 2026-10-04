---
name: "claude-dashboard"
description: "Report every project to the shared Claude activity dashboard (https://claude.ai/artifact/DLbfexxF2FECgcQ7Xy2jA4): the project, its jobs, the session's token usage and cost, and the account limit. Use it in EVERY Cowork session and EVERY Claude Code session (cloud, CLI, desktop, IDE) that does work that takes more than a few minutes or belongs to an ongoing project: code, documents, grants, films, research, data work. Report at the start, at each milestone, at least every 30 minutes while a job runs, and at the end. Use it also when the user says \"ping the dashboard\", \"track this\", \"log tokens\", or \"update the board\"."
---

# Report to the Claude dashboard

The dashboard is one artifact: https://claude.ai/artifact/DLbfexxF2FECgcQ7Xy2jA4. It shows every project of every person on the board, cloud and local, with its jobs, sessions, tokens, cost and token velocity. A project that does not report is invisible on it. Every session that does work reports.

Write with the `ArtifactData` tool on that URL. Load it with ToolSearch (`select:ArtifactData`) if it is deferred. In Cowork, use the same tool. If no tool can write to the artifact, say so once in the reply and continue the work.

## Who reports

<!-- who:start -->
- Person: David C (board owner)
- Collection prefix: none
- Limit document: collection `meta`, doc `quota`
<!-- who:end -->

The board shows each person's usage next to the others. What a person writes stays private to that person and to the board owner. The board owner reads everything.

1. Put the collection prefix in front of every collection name below: `projects`, `sessions`, `jobs`, `ticks` and `syncs`. With the prefix `data/users/me/profile/`, the project `clinic-scheduler` is the document `clinic-scheduler` in the collection `data/users/me/profile/projects`.
2. In that prefix, `me` stands for the person whose Claude account runs this session. The board resolves it. Do not replace it with an id.
3. Write nowhere else. The board rejects a write to another path. If such a write works, stop and tell the person.
4. Never write a document for another person.

## Rules

1. Never invent a figure. If the session cannot measure its tokens, write no token figure, or write a floor with `partial: true` and a `note` that says what it counts.
2. Pin every write to an existing document with `if_version` from your last read. If a write fails on a version, read again and redo only your change.
3. Write only your own documents: your project, your session, your jobs, your snapshot day. Do not edit the documents of other sessions.
4. Use UTC timestamps in the form `2026-10-03T23:13:18Z`.
5. Keep each write small. Use `update` to merge fields. Use one `batch` when you write more than two documents.
6. Never write message text, transcripts, file contents or secrets. Write counts, titles and links.

## 1. At the start: name and register the project

### The project name

The name follows the first rule that applies:

1. The session has a repository: the name is `owner/repo` of its first repository. A cloud session lists it in `session_context.sources` (from `get_session`). A local session reads it with `git remote get-url origin`.
2. The session has no repository, and its work is in a folder (a Cowork project, or a local session outside a repository): the name is the name of that folder, the last part of its path.
3. Neither applies: the name is the project's own name, as the user says it.

Use the same name in `projects.name`, `jobs.project` and `sessions.project`. The board groups by this rule, not by a free label. A session that touched several repositories belongs to its first repository. A project that had another name keeps that name in `aliases`.

### Register

1. Read the registry: `ArtifactData list` on collection `projects`.
2. Find your project by `name` or `aliases`. If a job row uses another name for the same project, add that name to `aliases`.
3. If the project is absent, create `projects/<slug>` (lowercase, hyphens):

| Field | Value |
|---|---|
| `name` | The project name from the rule above. |
| `where` | `cloud` for a Claude Code cloud session (web, iOS, desktop app remote). `local` for Cowork and for a CLI or IDE session on the user's computer. |
| `surface` | For example `Claude Code · cloud`, `Claude Code · CLI`, `Cowork`. |
| `sessions` | An array with your session id. |
| `repos` | `owner/repo` strings, if any. The first one names the project. |
| `folder` | The folder name, when the project has no repository. |
| `artifacts` | `https://claude.ai/artifact/...` links, if any. |
| `status` | `active`. Use `paused` or `done` only when the user says so. |
| `color` | Leave it out. The board owner assigns the colour slots (1 to 8). |
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
| `label` | What the job is, in one line. On a question to a person, write the question. |
| `note` | The latest detail. Rewrite it as the job moves. |
| `surface` | As in the registry. |
| `status` | `queued`, `running`, `waiting` (needs a person), `done`, `failed` or `stopped`. |
| `total`, `done`, `unit` | Progress, if the work has a count. |
| `estSec` | The expected length in seconds. |
| `tok`, `tokOut` | Tokens the job used so far, if you can measure them. |
| `tokEst` | The expected total tokens at the end of the job. The board uses it for the projected tokens and cost of the project. |
| `startedAt`, `updatedAt`, `finishedAt` | Timestamps. Refresh `updatedAt` on every report. |
| `askedAt`, `answeredAt`, `answer` | For a question to a person. |
| `link` | An https link to the PR, session or output. |

Close each row when its work ends: `status: done` and `finishedAt`. A row left `running` goes stale after 30 minutes and misleads the board.

## 3. Session usage and snapshots

### Claude Code cloud session

1. Call `get_session` with no `session_id`.
2. From `external_metadata.usage`, compute `tok = input_tokens + cache_read_tokens + cache_write_tokens + output_tokens`.
3. `set` or `update` `sessions/<session id>`:

```json
{ "title": "<session title>", "project": "<registry name>", "repos": ["owner/repo"], "where": "cloud",
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

An hourly routine also writes the totals of every cloud session of the account to `syncs/<epoch seconds>`, and the first reading of each UTC day to `daily/<UTC day>`. The daily ledger keeps usage for good. Your own snapshots add finer detail between the hourly syncs. Do not run that sync yourself unless the user asks.

### Cowork or a local CLI session

These sessions do not appear in `list_sessions`, so their report is the only record.

- If the session can read its own usage (for example `/cost` in the CLI), write `sessions/<your id>` with `tok`, `out`, `usd` and `src: "report"`, and append snapshots as above.
- If it cannot, write `sessions/<your id>` with what you can measure, for example subagent token counts, plus `partial: true` and a `note` that says what the figure counts. Do not estimate the rest.
- Set `where: "local"` and `surface: "Cowork"` or `"Claude Code · CLI"`.
- Write `repos` when the session has a repository. Write `folder` (the folder name) when it has none.

## 4. The account limit

`get_session` also returns `external_metadata.rate_limit_info`. Write it with `update` to the limit document that "Who reports" names. The board owner writes these fields to `meta/quota`. Every other person writes them as one object in the field `quota` of the limit document.

| Field | From |
|---|---|
| `status` | `status` (`allowed`, `allowed_warning` or `rejected`). |
| `type` | `rateLimitType`, for example `five_hour`. |
| `resetsAt` | `resetsAt` (epoch seconds), as a UTC timestamp. |
| `overage` | `isUsingOverage`. |
| `updatedAt` | Now. |

Add `pct`, `limitTok`, `weekResetsAt` or `weekPct` only when the session reads them from a real source. Never estimate a cap.

## 5. The board note

`meta/board` has a `note` for the line under the summary. The board writes its own summary of the top token users and current activity. Only the board owner writes a `note`, for something that needs a decision, in max 2 sentences, with `updatedAt`.

## 6. At the end

1. Close every job row that you opened.
2. Write the final session usage and one last snapshot.
3. Set `lastActivityAt` on the project.
4. If the project is complete and the user agrees, set the project `status` to `done`.

## Checklist for each report

- [ ] Every collection name starts with the prefix from "Who reports".
- [ ] Project in the registry, your session id in `sessions`, `lastActivityAt` set.
- [ ] Job rows current; finished rows closed.
- [ ] Session usage written (cloud: measured; local: measured or `partial`).
- [ ] Snapshot appended if `tok` changed and 15 minutes passed.
- [ ] Account limit written if `get_session` returned a limit state.
