# Claude activity dashboard

This repository is the source of the board https://claude.ai/artifact/DLbfexxF2FECgcQ7Xy2jA4. The README describes the layout, the publish steps and the access rules.

## The `sync` message

The usage-sync session runs on Haiku 5.5 at low effort and does only the sync. A routine sends the message `sync` to it every hour (UTC minute 26). On `sync`, do only this:

1. Start one sub-agent with the Agent tool:
   - `subagent_type`: "hourly-sync"
   - `run_in_background`: false
   - `description`: "Hourly sync"
   - `prompt`: "Read /home/user/claudedashboard/docs/SYNC_AGENT.md and do what it says. Reply with its one line only."

   `.claude/agents/hourly-sync.md` sets the model (Haiku) and the effort (low). If that agent type is missing, use `subagent_type` "general-purpose" with `model` "haiku".
2. If its reply does not start with "Synced", "Skipped" or "Stopped", start it once more with `model` "sonnet".
3. Reply with the sub-agent's line only.

Make the Agent call alone in its message. If the tool starts the sub-agent in the background, reply "Sync started." and end the turn. When its line arrives, do steps 2 and 3.

If the Agent tool fails, follow `docs/SYNC_AGENT.md` yourself. It is `docs/SYNC.md` in a short form, with the values of this board and with `scripts/sync_agent.py`. A sub-agent keeps the sync cheap: every call of this session reads the whole conversation again.

Do not edit code, open pull requests, publish the artifact, or write other documents during a sync. Do not read task summaries or session events in this session. The sub-agent writes only the count fields of each `get_session` answer to a file for the script, which deletes the file, and its reply holds counts only. From `list_triggers` it copies only the id, the name and the newest run of each scheduled task that starts a fresh session. The script takes only the limit state from the rate-limit events and deletes the pages. The board stores counts, titles and links only.

## Missed syncs

A routine message that arrives while this session works on another turn waits until that turn ends. The sync of 06:26 UTC on 4 Oct arrived at 06:52 this way, so the board had no reading from 05:35 to 06:40.

- At the end of every turn that is not a sync, read the newest `syncs` document. If its `at` is more than 70 minutes old, start the sync before the reply, and give its line when it arrives.
- If a `sync` arrives less than 30 minutes after the newest reading, the sub-agent does not run it again. Its line names that reading.

## Rules for changes

- `docs/INVITE.md`, `docs/SYNC.md`, `scripts/ccr_sync_doc.py`, `skills/token-dashboard/SKILL.md` and `skills/token-dashboard/scripts/local_usage.py` are the source of the text that the page gives to other people. After you edit one, run `python3 scripts/embed_assets.py`.
- Never write a rate from tokens that no two readings at most 3 hours apart place in time. The one exception is a turn that every hourly reading in it saw running. The README explains why.
- The repository is public. Add no real session ids, session titles, transcripts or other people's data. Fixtures are synthetic. `data/projects.json` already lists real project names: treat it as exposed.
- Run `NODE_PATH=$(npm root -g) node tests/check.mjs` before you publish.
