# duckyPad Configurator · Product Facts (corrected 2026-09-02)

## Source-of-truth correction
The user corrected the earlier design assumption: **this Configurator primarily supports the original duckyPad, a 3 columns × 5 rows (3×5) mechanical macropad with 15 onboard keys — NOT duckyPad Pro’s 4×5 / 20-key layout.**

This statement is the design and implementation source of truth. The earlier 4×5/20-key research and visual drafts are archival exploration only. Do not repeat them in the primary UI, app icon, herdr board, documentation, or packaged app.

## Primary device model
- **Product name in the default UI:** `duckyPad`
- **Onboard hardware representation:** `15 onboard keys · 3 columns × 5 rows (3×5)`
- **Core work:** profiles, one duckyScript per key, per-key RGB/selection, save/backup/import/export, and herdr mapping to the physical keys.
- **herdr mapping:** the default visual board and pinned-slot model maps to **15 slots**.
- **Primary visual form:** a 3 columns × 5 rows mechanical key grid at left. The OLED sits in the lower-right of the physical faceplate, directly above its two `−` / `+` profile-switch buttons. This narrow/tall product silhouette, not a 5 columns × 3 rows grid, is the UI’s source form.

## Variant support
The source base contains device-type-aware UI such as rotary encoders and expansion modules. These are **conditional extensions**: show them only after a detected device reports them. They are not a primary visual zone, and no default screen may imply every duckyPad has Pro hardware.

## Existing Configurator behavior to preserve
- Device dashboard: Connect, connection/root path, Save, Backups, User Header
- Profiles: select, create/delete, import/export through microSD
- Key selection: 15 default onboard key actions; name, script, custom RGB, allow-abort, don’t-repeat, on-press/on-release
- Script editor: duckyScript syntax feedback
- Resources and firmware/update links
- Optional device-specific controls only when present

## herdr integration (v4.1.0)
- herdr turns the 15-key pad into an agent-state board: each physical key’s RGB represents the associated agent’s live state; pressing it focuses that agent terminal.
- Existing real actions remain: install/upgrade plugin, stop/uninstall or restart service, open JSON config, copy firmware flash command.
- Four UI sample agent rows are presentation content only; a production UI must show only actual status returned by the existing integration, otherwise a truthful service/config state.

## Historical note
The official `duckyPad-Pro` site documents a separate 20-key 4×5 Pro model. Its product photos and hardware facts must not be used to represent this app’s default device. They may be retained only as secondary compatibility references when a Pro is actually detected.
