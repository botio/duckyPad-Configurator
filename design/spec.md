# Design Spec — duckyPad Configurator UI Redesign (v4.1.x)

You are redesigning the **duckyPad Configurator**: the official desktop companion app for the
**duckyPad Pro**, a 20-key (4×5 grid) open-source mechanical macropad that runs **duckyScript** — a
Turing-complete macro language (variables, conditions, loops, functions, 64 profiles, 60k chars per macro,
32 external expansion keys, 2 rotary encoders, per-key RGB, 128×128 OLED, ESP32-S3, USB-C, microSD).
Read `design/product-facts.md` and `design/brand-spec.md` in this repo for verified facts.

## Who uses it, and why it failed to impress
Users are **power-user engineers who run headless AI coding agents** (via `herdr`, a local agent supervisor).
Since v4.1.0 the pad is an **agent cockpit**: each key's RGB LED mirrors an agent's state
(working / waiting / done / error) and pressing a key **focuses that agent's terminal**. The current UI is a
Windows-90s Tkinter: nine flat LabelFrames, `.place()`-hardcoded 1070×605 window, system-gray buttons,
blue/green label text, dialog-soup, no hierarchy, no device visualization — and the headline herdr feature is
a tiny button buried inside an "Updates" box. **The redesign must make the agent-cockpit role the hero** while
keeping every real function reachable.

## The single visual motif (non-negotiable)
The device IS a 4×5 grid of keys. **Every direction must feature a faithful visual representation of the
physical 4×5 key grid as the primary interactive element of the main window** — keys as buttons that show
per-key RGB state (lit = has script; color = its custom/agent color). This is the content-derived form seed.
Do not replace it with abstract list navigation.

## Content inventory — ALL of these must appear (use these real strings; no lorem, no invented stats)
1. **Window title / brand**: `duckyPad Configurator` + version `4.1.0` + the app icon (base64 in `design/assets/icon.b64`).
2. **Device panel**: model `duckyPad Pro`, serial `05675567`, firmware `3.1.0 (herdr-capable)`, connection state
   (`USB /dev/hidraw1` or `Not connected — press Connect`), plus `Save`, `Backup`, `User Header` actions.
3. **Profiles**: list of real profiles — `herdr-agents`, `Firefox`, `Rust`, `Docker`, `Default`; import/export via microSD.
4. **Key grid**: 20 keys in 4×5; each shows its name (e.g. `Zoom In`, `Next Tab`, `Focus Agent 1`, `Focus Agent 2`,
   `Mouse Jiggler`, `Bee Movie`…) and its state light.
5. **Key config** (for selected key): name field, on-press / on-release radio, custom-color toggle with an RGB
   swatch, allow-abort + don't-repeat toggles.
6. **Script editor**: a real duckyScript example with syntax-check status. Use this real snippet (from the
   official site):
   ```
   VAR choice = _READKEY
   IF choice == 1
       OLED_CURSOR 0 10
       OLED_PRINT You are in a maze
       OLED_PRINT of twisty little passages
   END_IF
   ```
   or the mouse-jiggler: `WHILE TRUE / MOUSE_MOVE $_RANDOM_INT $_RANDOM_INT / DELAY 100 / END_WHILE`
7. **Rotary encoders ×2**: on-press/on-release script rows + half-step toggle.
8. **Expansion modules**: 32 external channels (show at least the concept, e.g. `EXT 1..32` or `4 modules × 8ch`).
9. **herdr panel (the hero of v4.1.0)**: agent state board — a list of agents with state lights:
   e.g. `claude-code · main` (working), `codex · herdr-plugin` (waiting), `claude-code · ui-redesign` (done),
   `gemini · perf-audit` (error); actions: `Install / Upgrade plugin`, `Restart service`, `Open config (JSON)`,
   `Copy firmware flash command`; plus a `pinned slots` hint and LED palette note.
10. **Resources**: `duckyScript docs`, `Tinkering guide`, `Firmware 3.3.5 available`.

## Output format (identical for all three directions)
- **One self-contained HTML file**, no external requests (no CDN fonts — embed `@font-face` with system-safe
  fallbacks or use a single embedded font subset; prefer a strong open-source stack via `@import` from Google
  Fonts is NOT allowed offline → use `font-family` stacks of locally-safe + well-known web fonts; a Google
  Fonts `@import` line IS allowed and acceptable as the primary, with system fallbacks).
- **Canvas: 1440×900**, rendered as a **desktop application window** (realistic window chrome of your
  choice — macOS traffic lights, or a minimal title bar — but it must read as a native desktop app, NOT a
  website). The window should sit on a subtle desktop backdrop (desk gradient / plain) that frames it.
- The window shows the **main window of the redesigned app** (one screen). The herdr/agent board is part of the
  main window (a primary zone), not a modal.
- **Dark-first is allowed but NOT required** — the product has light+dark modes; pick the mode your direction's
  temperament dictates.
- Body text ≥14px, labels ≥12px, text contrast ≥4.5:1. Use `oklch()` for palette.
- **Images: base64-embed** the app icon (`design/assets/icon.b64`) and at least one product photo
  (`design/assets/title.b64` or `quarter.b64`) where your layout has a device representation (e.g. the device
  panel). Do not embed more than 2 photos.
- No emoji as icons. Icons: minimal inline SVG (stroke-based, consistent weight) or none.
- The three directions will be compared side by side: **your layout skeleton must be structurally distinct**
  (different primary zone arrangement / navigation model / grid logic).

## Design quality bar
- One detail executed at 120% beats everything at 80%: find the one moment worth screenshotting
  (the 4×5 grid's state lights? the agent board's rhythm? the script editor's craft?).
- Every zone must earn its place — no filler panels, no fake stats, no "coming soon".
- Anti-slop: no purple gradient AI aesthetic, no uniform GitHub-dark + neon glow, no rounded-card-with-left-accent
  wallpaper. Your palette is derived from THIS product (see brand-spec: duck-yellow, hardware gray, RGB state
  colors) and argued in a comment at the top of the file.
- The duck is playful, but the tool is serious: think "precision instrument that happens to be a duck",
  never "cartoon".

## Deliverable
1. The single HTML file at the path given in your instructions.
2. In your final answer, state in ONE sentence: **where the form comes from** (which content element drove it),
   plus 3 bullets of your key design decisions, and anything you had to downgrade honestly.
