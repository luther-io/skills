---
name: spaceman
description: Use, configure, inspect, or troubleshoot the Spaceman tiling window manager on macOS via the spaceman CLI. Use when the user mentions Spaceman, workspaces, window tiling, window rules, or asks to switch workspaces, move or float windows, adjust layouts or gaps, or inspect display and window state.
runs_on: [local]
---

# Spaceman CLI & Usage

Spaceman is a native macOS tiling window manager. Install and uninstall are always done manually by the user; do not download, install, or delete `/Applications/Spaceman.app`.
If the user tries to invoke the `spaceman` skill, and Spaceman is not installed, the skill will fail with a helpful error message to go download and install it from https://github.com/anomalyco/spaceman/ or https://anoma.ly/spaceman/

## Invoking the CLI

The `spaceman` binary ships inside the app bundle. Use `spaceman` if it is on `PATH` (e.g. `~/.local/bin/spaceman`), or call the bundle binary directly:

```sh
/Applications/Spaceman.app/Contents/MacOS/spaceman <command> [args...]
```

## Live Control (`spaceman ctl`)

`spaceman ctl` talks to the running `spaceman-agent` over `~/Library/Application Support/Spaceman/control.sock`.

### Inspect Live State

```sh
spaceman ctl status     # agent status JSON ("mode":"automatic", "busy":false, "active_workspaces":[...])
spaceman ctl debug      # live displays, tiles, floating windows, focused window, and directional targets JSON
spaceman ctl settings   # agent runtime settings & version JSON
spaceman displays       # connected displays as JSON (id, name, frame, is_main)
spaceman snapshot       # dry-run window observation and reconciliation plan as JSON
spaceman doctor [hours] # summarize recent arrangement journal events, restorations, and anomalies
```

### Workspaces

- Workspaces `1–5` default to `main` display; `6–10` default to `secondary` display.
- Single-letter workspaces `A–Z` are opt-in (enabled when assigned to a monitor or referenced in a rule) and default to `main`.

```sh
spaceman ctl switch <1-10|A-Z>                  # switch to a workspace (repeating active workspace cycles its tiles)
spaceman ctl back-and-forth                     # toggle between current and previous workspace
spaceman ctl move <1-10|A-Z>                    # move the focused window to a workspace
spaceman ctl move-app <bundle-id> <1-10|A-Z>    # move all windows of an app to a workspace
spaceman ctl move-workspace [next|prev|DISPLAY] # move the focused workspace to another display
```

### Windows & Layout

Spaceman tiles windows per workspace in a split layout along a root axis (`horizontal` = side-by-side columns first; `vertical` = stacked rows first).

```sh
spaceman ctl focus <left|down|up|right|next|prev>  # move focus directionally or cycle tiles
spaceman ctl move-direction <left|down|up|right>   # reorder the focused tile
spaceman ctl layout                                # flip root split axis (horizontal <-> vertical)
spaceman ctl fullscreen                            # toggle workspace-wide Fullscreen Layout
spaceman ctl float                                 # toggle per-window floating on the focused window
spaceman ctl resize <shrink|grow>                  # adjust the focused tile's split weight
spaceman ctl balance                               # reset split weights evenly across the workspace
spaceman ctl retile                                # force a fresh observation and retile
```

### Scratchpad (Labs)

Requires `[labs] scratchpad = true` in `config.toml`:

```sh
spaceman ctl scratchpad toggle   # summon the next scratchpad window, or hide the one shown
spaceman ctl scratchpad mark     # send the focused window to the scratchpad, or take it out
```

### Agent Lifecycle & UI

Always run `spaceman ctl pause` before `quit` or `restart` so off-screen parked windows are restored first:

```sh
spaceman ctl pause               # pause tiling and restore all parked windows
spaceman ctl resume              # resume automatic tiling
spaceman ctl restart | quit      # restore parked windows and exit the agent
spaceman ctl open-settings       # open the Spaceman Settings window
spaceman open <target>           # open a Settings pane (general, layout, rules, workspaces, shortcuts)
```

## Configuration (`config.toml`)

Config lives at `~/Library/Application Support/Spaceman/config.toml` (override with `SPACEMAN_CONFIG`). Prefer the atomic CLI subcommands over hand-editing so schema version `1` is validated automatically.

### Settings (`spaceman config`)

```sh
spaceman config path [--json]
spaceman config show [--json]
spaceman config get <key> [--json]
spaceman config set <key> <value> [--json]
spaceman config check [path] [--json]
```

Supported keys for `config get` / `config set`:

- `hud`: `true | false` — show the Workspace HUD overlay (default: `true`)
- `hud_style`: `icons | layouts` — Workspace HUD drawing style (default: `icons`)
- `update_channel`: `stable | dev` — in-app updater channel
- `mouse_follows_focus`: `off | display | window` — move pointer on focus changes
- `single_window_max_width`: `0 | 320-16384` — center a lone window (and Fullscreen Layout) at this width (`0` = off)
- `gaps.inner`: `0-48` — points between tiled windows
- `gaps.top`, `gaps.bottom`, `gaps.left`, `gaps.right`: `0-128` — outer screen edge padding

### Window Rules (`spaceman rules`)

Rules are ordered and first-match. Actions are `route` (requires `--workspace`), `float`, or `ignore`:

```sh
spaceman rules list [--json]
spaceman rules add --app <bundle-id> (--workspace <ws> | --float | --ignore) [--title <title>] [--position <index>] [--json]
spaceman rules remove <index-or-bundle-id> [--json]
spaceman rules remove --app <bundle-id> [--json]
```

### Workspace Monitor Assignments (`spaceman workspaces`)

```sh
spaceman workspaces list [--json]
spaceman workspaces assign <ws> <main|secondary|display-name-or-uuid> [--json]
spaceman workspaces clear <ws> [--json]
```

## Shortcuts

By default, Spaceman uses `Option` (`alt`) as the base modifier, and `Move` shortcuts add `Shift`. The user can override the base modifier or add custom bindings under `[shortcuts]` in `config.toml`:

```toml
[shortcuts]
modifier = "ctrl+alt+cmd" # e.g. Hyper key; default is "alt"

[shortcuts.bindings]
"ctrl+alt+cmd+space" = "float"
"ctrl+alt+cmd+b" = "balance"
```

Built-in bindings (using `<Mod>` = configured `shortcuts.modifier`):

| Keys                              | Action                                                           |
| --------------------------------- | ---------------------------------------------------------------- |
| `<Mod>+1` … `<Mod>+0`             | Switch to workspace 1 … 10                                       |
| `<Mod>+Shift+1` … `<Mod>+Shift+0` | Move focused window to workspace 1 … 10                          |
| `<Mod>+A` … `<Mod>+Z`             | Switch to configured named workspace A … Z                       |
| `<Mod>+Shift+A` … `<Mod>+Shift+Z` | Move focused window to configured named workspace A … Z          |
| `<Mod>+Tab`                       | Toggle between current and previous workspace (`back-and-forth`) |
| `<Mod>+backtick`                  | Focus next window in workspace order (`focus next`)              |
| `<Mod>+H/J/K/L`                   | Focus left / down / up / right                                   |
| `<Mod>+Shift+H/J/K/L`             | Move/reorder focused tile left / down / up / right               |
| `<Mod>+/`                         | Flip root split axis (`layout`)                                  |
| `<Mod>+-`, `<Mod>+=`              | Shrink / grow focused tile (`resize shrink` / `resize grow`)     |
| `<Mod>+Shift+F`                   | Toggle workspace-wide Fullscreen Layout (`fullscreen`)           |

## State & Troubleshooting

Runtime files in `~/Library/Application Support/Spaceman/`:

- `workspace-state.json` — active workspaces, split trees, slots, and per-window floating state
- `window-memory.json` — remembered app/window workspace placements and frames
- `parked-windows.json` — off-screen parked windows waiting to be restored (never delete while windows are parked)
- `journal.jsonl` & `agent.log` — arrangement history and diagnostic logs

Common checks:

- **Window unexpectedly floating without a float rule:** check the `"floating"` array in `spaceman ctl debug` or `workspace-state.json`. A per-window float toggle persists per window; un-float the focused window with `spaceman ctl float`.
- **Two windows not splitting side-by-side:** check `spaceman ctl debug` for `"fullscreen_layout": true` on that display (toggle off with `spaceman ctl fullscreen`) or check if one of the windows is in `"floating"`.
