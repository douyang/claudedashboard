<!-- Template. The board page fills {{NAME}}, {{BOARD}}, {{BOARD_OWNER}} and {{SYNC}}. -->
# Report {{NAME}}'s Claude usage to the {{BOARD_OWNER}} activity board

{{NAME}} asks you to run this setup once. After it, an hourly update runs by itself, with no further action.

- Board: {{BOARD}}
- Reporter: {{NAME}}

## Who can read what you write

- You write only to the private path `data/users/me/profile/...`. The board resolves `me` to {{NAME}}'s own id.
- Only {{NAME}} and {{BOARD_OWNER}} can read that path. Other people on the board cannot.
- You cannot write anywhere else on the board. If a write to another path works, stop and report it.

## What the setup sends

- For each Claude Code cloud session of this account: id, title, status, model, start and update times, repositories, token counts, and the cost at API list prices.
- The usage-limit state of the account: status, window and reset time.
- The same totals once a day, as a ledger entry. The ledger keeps usage after a session leaves the listing.
- Nothing else. No messages, no transcripts, no task summaries, no file contents.

## Before you start

- You need the tools ArtifactData and list_sessions (server claude-code-remote). If they are deferred, load them: ToolSearch "select:ArtifactData,mcp__claude-code-remote__list_sessions".
- {{BOARD_OWNER}} must share the board with {{NAME}} with edit access (Contributor). If a write fails with "not found" or "not allowed", stop and tell {{NAME}} to ask {{BOARD_OWNER}} for edit access.
- If ArtifactData says that resolving "me" needs the db and user capabilities, stop. Tell {{NAME}} to ask {{BOARD_OWNER}} to republish the board.
- If a tool is missing, name the tool and the step that needs it. Then stop.

## Step 1. Run the sync once now

Follow "THE SYNC" at the end of this text. It writes the first document to the board.

## Step 2. Check the first document

- Call ArtifactData with action "get", url "{{BOARD}}", collection "data/users/me/profile/syncs", and the doc_id that the script printed.
- Call it again for collection "data/users/me/profile/daily" and the day that the script printed. A day that already has an entry is fine.
- If the sync document is missing or holds no sessions, stop and report the problem.

## Step 3. Make the update hourly

1. Call list_triggers. Look for a routine named "Claude board hourly sync".
2. If the routine exists, call update_trigger on it with the cron and prompt below. Do not create a second routine.
3. If it does not exist, call create_trigger (server claude-code-remote) with these settings:
   - name: "Claude board hourly sync"
   - cron_expression: "0 * * * *"
   - initiation: "human_request"
   - prompt: the full text of "THE SYNC", unchanged.
4. Do not set create_new_session_on_fire or notifications. The routine then wakes this session every hour. A routine that starts a fresh session gets no list_sessions tool, so the sync would fail there.
5. If you have set_session_title, rename this session to "Claude board usage sync". Tell {{NAME}}: "Keep this session. Do not archive or delete it. The hourly update runs in it."
6. If you have no create_trigger tool, tell {{NAME}} to create a scheduled task in the Claude app. The task runs every hour and its prompt is the text of "THE SYNC". Do not skip this silently.
7. Call list_triggers again. Confirm that the routine is enabled. Note its next_run_at.

## Step 4. Show {{NAME}} on the board

Tell {{NAME}}: "Open {{BOARD}} once in your browser." The board then lists {{NAME}} for {{BOARD_OWNER}} and shows {{NAME}} their own usage.

## Step 5. Sessions that list_sessions does not show

- Cowork sessions and local CLI sessions do not appear in list_sessions. They report their own jobs and usage through the claude-dashboard skill.
- Tell {{NAME}}: "Open the board, press Save skill file, and upload the zip in claude.ai under Settings, Capabilities, Skills." The board page builds the file for {{NAME}}.

## Step 6. Report

Reply in max 4 lines:
- The number of sessions and tokens that the first sync wrote.
- The routine id and its next run time.
- Whether {{NAME}} still has to open the board and upload the skill.

## THE SYNC

{{SYNC}}
