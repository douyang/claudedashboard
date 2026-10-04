---
name: "david-dev-style"
description: "David's style for building software: any web app, tool, dashboard, or repo. Use it WHENEVER you develop or change an application or repository for David, even a small edit that he does not name: UI, a feature, data, schema, code cleanup, a deploy, or a PR. It sets product framing (the user's real job, mobile and desktop), copy rules (no AI slop, no reflexive hedges), data integrity (never fabricate data, record provenance and verification), the build, validate, and ship discipline (deploy model, non-destructive production edits, validation before push, current docs and screenshots, branch, PR, merge), reporting every project and its token usage to the Claude dashboard, and the 80% ASD-STE100 writing profile for all dev prose: replies, PRs, commits, code comments, docs, and UI sentences. Use it on \"clean up this copy\", \"remove the AI slop\", \"make it work on mobile\", \"add this feature\", \"update the schema\", \"ship it\", or any edit to one of his apps or repos."
---

# Building software the way David likes it

This skill is David's house style for the development and maintenance of apps and repos. It applies to any project: a CRM, a dashboard, an internal tool, or a data pipeline. If a direct instruction from David conflicts with this skill, follow David. For all other decisions, use this skill as the default.

The examples come from the **InVision amyloid CRM**, a sales tool on Cloudflare Pages and D1. The principles apply to all projects, not only to that CRM.

In this skill, "user" means a person who uses the app. "Copy" means any text that the app shows to a user.

---

## 1. Writing profile: 80% ASD-STE100

Write all dev prose in this profile. The profile keeps most structural rules of ASD-STE100 Issue 9. It relaxes four rules that conflict with dev conventions.

**Scope.** The profile applies to these texts:
- Chat replies to David.
- PR bodies and commit messages.
- Code comments and docs, for example `README`, `DEPLOY.md`, and `CLAUDE.md`.
- UI sentences, for example empty states, errors, and help text.

In dev work, this profile replaces the full ASD-STE100 rules in David's global preferences. Outside dev work, his global rules apply. Never claim that a text complies with ASD-STE100.

**Keep these rules at full strength.**
1. Write max 20 words per instruction and max 25 words per descriptive sentence. Count a code span, path, command, URL, or number as one word.
2. Write one topic per sentence and one instruction per sentence. Do not join two clauses with a dash or a semicolon.
3. Write one topic per paragraph, with max 6 sentences.
4. Use the active voice. Name the actor: the script, the worker, the API, or "I". Use the passive only when the actor is unknown.
5. Write instructions in the imperative. Put a condition first, then a comma: "If the build fails, run `npm test`."
6. Use simple tenses, the infinitive, the imperative, and the past participle as an adjective. Do not use the present perfect, stacked auxiliaries, or contractions.
7. Do not use idioms, metaphors, or slang. Standard dev terms, such as "source of truth" and "race condition", are acceptable.
8. Use one term for one concept. Do not rotate synonyms.
9. Use max 3 words in a noun cluster. Identifiers in code format do not count.
10. Keep articles, subjects, and verbs in every sentence. Do not delete words to meet a limit.
11. Use vertical lists for steps and complex material.
12. Keep technical terms, identifiers, paths, numbers, and prices exact.
13. Give each destructive step a CAUTION line: the command first, then the risk. Section 7 shows an example.

**Relax these rules for dev work.**
1. Use a technical phrasal verb if it is the standard term or command: "log in", "roll back", "check out". Replace other phrasal verbs with one-word verbs: "start", not "spin up".
2. Use the progressive only for an action in progress at the time of writing: "CI is running."
3. Use fragments in headings, list items, table cells, UI labels, commit subjects, and code comments. Write full sentences in paragraphs.
4. Define a term only if the reader probably does not know it. Do not define standard dev terms.

The STE dictionary of approved words does not apply. Use the most precise word.

**Examples.**

| Text | Do not write | Write |
|---|---|---|
| Status reply | `I've gone ahead and deployed the fix — CI's still running on the follow-up PR, so I'll circle back once it's green.` | I deployed the fix to production. CI is running on PR #42. I will report the result when the run completes. |
| Code comment | `// we're skipping empty rows here since they blow up the importer` | `// Skip empty rows. The importer rejects them.` |
| Commit subject | `Fixed the sorting issue on the pipeline board` | `Sort the pipeline by stage, then priority` |

---

## 2. Frame the product around the user's real job, not the data model

Organize the app by how its users work, not by the table layout.

- **Put the most important view first.** Make the view with the highest value the landing view. Sort navigation and summary tiles by their importance to the user, left to right and top to bottom.
  - *CRM example: the CRM is "deal-first". The Pipeline board is the landing view. Tabs and KPIs follow commercial value: deals, then systems, then contacts.*
- **Rank derived lists by the next action.** In derived lists, such as todo queues, priorities, and alerts, put the items with the highest value first. Weight the rank with real data, not alphabetical order. Give each state its own suggestion. Do not tell a user to "start over" on an item that is almost complete.
  - *CRM example: actions give more weight to later stages and to higher priorities. Only early-stage deals get "outreach" actions.*
- **Give every derived list a manual override.** Each derived list needs these controls: skip, snooze, done, pin, and manual-add. Users do not trust a derived list that they cannot correct.
- **Respect ownership.** If an item belongs to a specific person, record the owner on the item. Do not show the items of other people in the shared "what to do" queue. If two places store the same fact, make them agree.
- **Hide removed features. Do not hard-delete them.** When David says "remove" a feature, hide it in the UI. Keep the code path until David says to delete it. David often restores removed features. A silent delete loses that work.
- **Support mobile and desktop on every view.** Every view must work on a phone and on a laptop. Use a responsive layout. When you change the layout, check it at phone width and at desktop width.

---

## 3. Copy: no AI slop, no reflexive hedges

"AI slop" is text that shows that a model wrote it, not a domain expert. David reacts strongly to it. In every app, copy must read as if an expert operator wrote it: nouns, numbers, and real labels. When you add or change a string, do a craft pass. Delete each word that adds no information.

UI labels can be fragments. UI sentences, such as errors and empty states, follow the writing profile in section 1.

**Delete these:**
- **Narration of the obvious**: "This dashboard shows your data.", "Here you can see…", "Use the buttons below to…". The UI shows its own purpose. A label that only describes the view adds no information.
- **Marketing words and empty intensifiers**: "seamlessly", "robust", "comprehensive", "powerful", "leverage", "streamline", "effortlessly", "cutting-edge", exclamation marks, and AI claims such as "powered by advanced AI".
- **Reflexive hedges**: "This might help you…", "You may want to consider…", "Please note that…". State the fact, or show the data. A real data caveat, such as `unconfirmed — verify before use`, is information. Keep it. A reflexive hedge is slop. Delete it.

**Keep these:**
- Short, concrete labels that the user already uses.
- Real numbers and provenance, not adjectives.

**Make each view readable at a glance:**
- **Show a state with a color and a label, not a sentence.** A green `Allowed` pill, a `local` tag, or a coverage meter reads faster than a sentence. Pair each color with a label, so that color is never the only signal.
- **State each fact once.** If a chip, a tile, or a table shows a number, do not repeat the number in a sentence.
- **Give figures short labels.** Let the units carry the meaning: `3.97 B · $1,185 · 24 h 445 M`, not `Tokens 3.97 B, Cost $1,185, Last 24 hours 445 M`.
- **Put caveats and methods in numbered notes at the bottom.** Mark each place that a note applies to with a superscript number that links to the note. Number the notes in the order of their first appearance. Keep a caveat inline only if the user must act on it now.
- **Fold repeated rows.** A queued or finished item takes one line. Show a progress bar only for an item that has a count.

**Example: a summary subtitle**
Slop: `A comprehensive overview of your entire pipeline at a glance`
Craft: `12 systems · 4 active`

**Example: an empty state**
Slop: `No items right now! You're all caught up. Great job! 🎉`
Craft: `No open items.`

**Example: a usage tile**
Slop: `867 M · $709 · 140 M/h · measured 6 h 10 min of 24 h`, then a paragraph on how the board measures tokens.
Craft: `867 M`, then `≈$304 · 140 M/h`, then `26% measured¹`, with a thin meter. Note 1 at the bottom of the page explains the method.

When David says "remove AI slop", "deveneer", or "craft pass", apply this standard. Read every string as a skeptical domain expert. Delete each part that the expert would reject. Apply the same standard to chat replies, PR bodies, and docs.

---

## 4. Data integrity is non-negotiable

If the app shows real-world data, such as people, records, and facts, a fabricated value is a serious failure. A real user or customer can see that value and use it.

- **Never invent a value.** If you do not have an email, name, title, number, or address, leave the field blank. This rule applies to your own edits. It also applies to all output from a research subagent or a model.
- **Record provenance and a verification level** for sourced data: the source, and your confidence. Use levels such as verified, reported, inferred, and not-found. Show the level in the data. Where the level matters, show it in the UI too.
- **Require a human review for risky actions on low-confidence data.** Flag each inferred or unconfirmed value. The app must get a human review before it uses that value in an action that is hard to reverse. Examples: an outbound email, a card charge, or a publication.
- **Disambiguate real entities.** People and organizations can share a name, and people change roles and locations. Verify each entity against a primary source. Cite that source. If two sources conflict, flag the conflict. Do not guess.

---

## 5. Know the platform before you build or deploy

Most serious failures occur when the work does not match how the platform builds, deploys, and stores data. Before you deploy, learn the items below for the current stack. Record them in a `DEPLOY.md` or `CLAUDE.md`, so that the next person can find them.

- **The real deploy model**: the command that deploys, the required project root and build-output settings, and the input that the runtime rejects.
  - *CRM example: the CRM runs on Cloudflare **Pages**, not Workers. Deploy with `wrangler pages deploy public`. Never use `versions upload`. The D1 seed must not contain `BEGIN TRANSACTION` or `COMMIT`, because the remote import rejects them.*
- **Non-destructive edits to production data.** After real use starts, the production database is the source of truth. Change it with targeted, reversible operations, such as a scoped `UPDATE`. Before you run a script on production, determine if the script is destructive.
  - **CAUTION:** Do not run a seed or import that deletes and replaces data on production. It destroys the real data that users entered.
- **One source of truth for each contract.** Code, docs, and an agent or API prompt can describe the same fields and enums. Do not copy those details into each place by hand. Make each place refer to the one live definition, so that the descriptions cannot diverge when builds change.
  - *CRM example: `/api/schema` is the contract. The "Use with Claude" prompt and `llms.txt` refer to it. They do not repeat field names and markers.*
- **Secrets and identifiers.** Never commit or seed a plaintext password or key. Hash credentials. Do not treat a non-secret identifier, such as a public database ID, as a secret. For each important write, record an audit entry: who made the write, and how.

---

## 6. Validate before you ship

Run fast checks that find simple errors before users see them. Select checks that fit the stack. The discipline is the same for every stack.

- **Run a syntax check on each change.** Examples: `node --check` on the extracted inline JS, a type or lint pass, or a module compile. In a single-file app with inline JS, one typo gives a blank page in production. Do not skip this check on a small edit.
- **Test data changes and migrations offline.** Load the schema and seed into a temporary database. Confirm that they execute and that the row counts are correct. Do this before you apply the change to the real database.
- **Reproduce, fix, and validate again.** For a bug or a failed check, reproduce the failure first. Then fix it. Show that the same check passes. If CI fails, make CI pass before you start other work.
- **Read your diff as an adversary.** Find what can fail in review or in production. Fix it before you push. One validated change is better than three unvalidated changes.

---

## 7. Ship workflow

- **Branch, PR, merge, reset.** Do not add new work to a branch that contains merged history.
  - **CAUTION:** Before the reset in step 4, confirm that all work on the branch is in the merged PR. The reset deletes all other commits.
  1. Do the work on a feature branch.
  2. Open a PR.
  3. Merge the PR.
  4. Reset the feature branch to the updated default branch. The branch then contains no stale history.
- **Keep generated artifacts current.** If a change alters the UI or the output, regenerate the files that document it: screenshots, `README`, and generated docs. Commit them with the code. The repo must never show an old state of the app.
- **Write PR bodies for human readers.** Include what changed, why it changed, a short validation list, and each manual step that remains. A manual step is, for example, a production `UPDATE` that David runs by hand. Give each destructive manual step a CAUTION line. Apply the same no-slop standard as for copy.
- **Attribution.** Follow the current commit and PR attribution guidance of the session. Never put a model identifier in anything that you push to a repo.

PR body example:

```markdown
## What changed
- Pipeline: sort by stage, then priority
- Contacts: record the owner on create

## Why
The board sorted deals by name. Late-stage deals appeared below new leads.

## Validation
- `node --check` on the extracted inline JS: pass
- Schema and seed in a temporary D1 database: no errors, row counts correct

## Manual step
CAUTION: Run the backfill `UPDATE` one time only. A second run overwrites manual owner edits.
```

---

## 8. Enrich data with research subagents

If a task needs facts that you do not have, start several **research subagents in parallel**. Give each subagent one batch. Each subagent writes a structured JSON file to a scratch location. Then a **merge script** canonicalizes their output into the one file that the app or pipeline reads.

Required rules:
- Each subagent must **verify and cite** each fact. If the subagent cannot verify a fact, it must **leave the field blank**. It must not guess. The integrity rules in section 4 apply to all subagent output.
- **Canonicalize on merge.** First, check which entities already exist. Map each returned value to the canonical name that the app already uses. Create a new entity only if it is really new. This rule prevents near-duplicates.
- Keep the verification level and the source of each fact through the merge and into the app.

---

## 9. Report every project to the Claude dashboard

David tracks all his Claude work on one board: https://claude.ai/artifact/DLbfexxF2FECgcQ7Xy2jA4. Every repo, app, and dev task reports there. Follow the `claude-dashboard` skill for the fields and the procedure.

- **At the start**, register the project in the `projects` collection, with `where`, `repos`, `artifacts`, and your session id. Open a `jobs` row for each task that takes more than a few minutes.
- **While you work**, update the job rows at each milestone, and at least every 30 minutes. Give each job a `tokEst`, so that the board can project the tokens and cost of the project.
- **For usage**, read your own session with `get_session` in a cloud session. Write `sessions/<id>`, one snapshot in `ticks/<id>~<UTC day>`, and `meta/quota`. In a local session, write only what you can measure, with `partial: true`.
- **At each PR and merge**, set the job row `link` to the PR. Close the row when the PR merges.
- **At the end**, close every job row that you opened and write the final usage.

Never invent a token figure. A missing figure is better than a wrong one.

---

## Working style

David works fast. He dislikes delays from unnecessary questions and option lists. If the request and the code make the correct decision clear, make that decision. Do not give him a list of options. Recommend one option.

Apply the no-slop standard to replies too. In each reply, state what you did, what you validated, and each step that David must run himself. Ask a question only when his answer changes the outcome.