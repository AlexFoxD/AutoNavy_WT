# AutoNavy_WT v2 — Agent implementation bundle

This bundle contains instructions and a specification for a coding agent. It is **not** an implemented v2 application. Preparing these files did not create a branch, modify the remote repository, run the bot, or measure game performance.

## Recommended: one self-contained prompt

Open the AutoNavy_WT checkout in your coding-agent workspace. Use the coding model already configured in the agent and ensure your installed Superpowers module is available there. Copy the **entire contents** of `ONE_PROMPT_AUTONAVY_V2.txt` into one new agent message.

That file contains the launch instructions and the full specification. No earlier chat, separately attached spec, or second kickoff prompt is required. Read it before submitting: its approval language authorizes local edits, a new branch/worktree, local commits, and project-local test/dependency work. It does not authorize pushing or merging.

## Alternative: attached specification and shorter prompt

Make `AUTONAVY_V2_SPEC.md` available to the agent as an attachment or a readable local file, then send the contents of `START_PROMPT.md` as one message. Ensure the agent can actually read the full attachment. Do not send the short prompt alone without the specification.

Keeping the bundle outside your source checkout avoids creating unrelated untracked files. The agent is instructed to place the authoritative spec and progress records inside the new v2 branch after establishing isolation.

## Files

| File | Purpose |
|---|---|
| `ONE_PROMPT_AUTONAVY_V2.txt` | Complete self-contained launch prompt with embedded specification |
| `AUTONAVY_V2_SPEC.md` | Standalone English specification: scope, architecture, 10 milestones, 39 acceptance rows and source references |
| `START_PROMPT.md` | Shorter English launch prompt for use with the standalone specification |
| `README.md` | This usage guide |
| `SHA256SUMS.txt` | SHA-256 hashes of the text files for integrity checking |

## Selected workflow

The requested branch is `feature/v2-modernization`, based on the current committed checkout. The source branch and unrelated working changes must remain untouched. An isolated worktree is pre-approved; the agent should respect a host-managed workspace when one already exists. A branch-name collision must never lead to overwriting another branch.

Superpowers planning, test-first implementation, review and verification are requested. The launch prompt explicitly approves this design and chooses implementation rather than more brainstorming. The installed module or host can still require a nonwaivable confirmation; this package does not disable those gates or tool permissions. It also cannot prevent context/rate limits or guarantee an uninterrupted agent session. Persistent status and plan files support resumption without re-planning the entire project.

## Deliberate implementation choices

DXcam remains the initial default; OBS Virtual Camera must be implemented as an optional interchangeable source and compared using meaningful measurements. The agent must not infer lower latency from higher reported FPS.

The target remains compatible with the audited Windows x64 / CPython 3.11 native-pathfinder environment. All new development output is English, but game template assets and external protocol strings must not be translated.

The default runtime is non-actuating. Real keyboard/mouse/vJoy output requires an explicit launch opt-in. Agent-driven tests use replay/fake devices and never enter live matchmaking or make purchases. Existing launch scripts must be migrated so this is not merely an unused testing framework.

## What a satisfactory result looks like

A retained local v2 branch with working integrated changes, scoped commits, deterministic offline tests, an optional implemented OBS backend, benchmark tools, updated launch/build/diagnostic scripts, and English operation/migration documentation. The final report must identify the worktree and commits and separate completed implementation from outstanding hardware validation.

A plan alone, an unconnected new package, a placeholder backend, an invented speedup, or a blanket "all tests pass" statement without commands and results does not satisfy the task.

## Evidence and limitations

The specification's source section records the public repository files and Superpowers documentation used as an audit starting point on 2026-09-09. Those URLs follow branches rather than immutable commits. The implementing agent must inspect and record the actual checkout SHA; it must not treat stale findings as unconditional truth.

This bundle was checked for structure and internal consistency. No AutoNavy_WT implementation, Windows build, capture backend, or live-game performance test was executed as part of preparing it.
