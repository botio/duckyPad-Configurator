# D3 Implementation Spec — original duckyPad 3 columns × 5 rows

This is the current implementation source of truth. It supersedes the 4×5/20-key premise in the exploratory `spec.md` and all initial drafts.

## Five form answers
1. **Narrative role** — a working desktop tool’s main screen; the product is a physical 15-key instrument, not a generic settings form.
2. **Viewer distance** — laptop/desktop at roughly one metre; controls and scripts need sustained readability, not showcase-only typography.
3. **Visual temperature** — precise, warm, hardware-like; quiet playfulness from duckyPad’s keycaps and the single orange control accent.
4. **Capacity** — 15 keycaps must remain large enough to read; the main composition therefore uses an explicit **3 columns × 5 rows** matrix, not a compressed compatibility grid.
5. **Visual motif** — the **3 columns × 5 rows** physical switch array, with its OLED at the lower-right above the hardware profile-switch buttons. A selected key has depth and one orange focus edge; RGB seams convey actual key/agent state.

## Native Tkinter layout
- OS titlebar remains native for Windows/macOS/Linux. The internal app uses `grid`, not fixed-coordinate `.place()` composition.
- **Left rail**: 210 logical px; device card, `3 columns × 5 rows` capability label, profiles, save/backup/header, microSD actions, resources.
- **Center**: key deck on top. The deck contains the **3 columns × 5 rows** keycap grid, the physical OLED at lower-right above profile-switch buttons, key inspector, and an optional `Extensions when present` area. Below it is the dark duckyScript editor.
- **Right rail**: dark herdr instrument panel. It exposes existing plugin/service/config/flash actions. It shows live 15-slot mapping only when the existing integration has real state; otherwise it states the actual service/config state.
- Variant-specific encoders/expansion controls do not occupy default space. They appear only after detected capabilities report them.

## Style tokens (Tk-compatible hex)
| Token | Value | Role |
|---|---:|---|
| `surface` | `#E8E4DA` | hardware warm white |
| `panel` | `#F4F1E9` | inset panel / key top |
| `ink` | `#302D27` | primary type, key outline |
| `line` | `#B8B1A3` | seams / silkscreen rule |
| `instrument` | `#292720` | script and herdr panel |
| `orange` | `#F47721` | Save / selected key / intentional action |
| `working` | `#D99A16` | state LED only |
| `waiting` | `#618CA8` | state LED only |
| `done` | `#5DA773` | state LED only |
| `error` | `#C64C43` | state LED only |

## Interaction invariants
- Existing profile, device, script, RGB, save, backup, import/export, firmware and herdr callbacks remain authoritative.
- The view rewrite must not introduce fake data. A 15-key board is rendered from the detected/current key model; a device with fewer/more or extended inputs is surfaced truthfully as an optional capability.
- The new app icon is an SVG source based on the same **3 columns × 5 rows** keycap + orange-focus + state-LED grammar; packaging derives PNG/AppImage and `.icns` from it.
