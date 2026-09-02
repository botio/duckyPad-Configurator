# duckyPad Configurator · Brand Spec (corrected 2026-09-02)

## Primary identity
- **Default product:** `duckyPad`, a **3 columns × 5 rows (3×5) / 15-key** mechanical macropad.
- **Configurator role:** desktop setup tool for profiles, duckyScript, key LEDs, save/backup, and (v4.1.0) herdr agent focus/state mapping.
- **Temperament:** hacker-friendly and playful-but-competent: a precision instrument with a quiet duck soul, never a generic AI dashboard.
- **2026 identity:** a 15-key agent cockpit—RGB state on the physical keys and a key press that focuses an agent terminal.

> The earlier statement that the primary product is duckyPad Pro / 4×5 / 20 keys is superseded by the user’s correction. Pro-specific hardware is optional compatibility UI only.

## Visual form
- The non-negotiable silhouette is **3 columns × 5 rows (3×5) = 15 thick keycaps**.
- A selected key receives the one orange focus accent; RGB light seams are reserved for agent/key states.
- Rotary encoders and expansion modules must live in an `Extensions when present` area, not the default composition.

## Assets
| Asset | File | Use |
|---|---|---|
| App icon (old reference) | `assets/duckypad_icon_128.png` | Current icon only; replaced by D3 icon source before packaging |
| D3 source of truth | `demos/direction-3-teenage-eng.html` | Selected direction; primary device is **3 columns × 5 rows**, not the superseded 4×5 draft |
| Existing UI reference | `assets/current_ui.jpg` | Functional/spacing reference, not visual target |
| Official Pro photos | `assets/resized_official_title.jpeg`, `assets/resized_official_quarter.jpeg` | **Do not use as primary device imagery**; they depict 4×5 Pro hardware |

## D3 palette tokens
- Surface: warm off-white and hardware gray, not pure white
- Ink / dark instrument: warm near-black
- Action / selection: a single restrained orange
- State-only colors: amber=working, slate-blue=waiting, green=done, red=error
- Typography: condensed sans for controls; monospace for data and duckyScript; silk-screen uppercase labels are readable at 12px minimum

## Red lines
- ❌ Do not render 4×5/20-key geometry in the default UI or icon.
- ❌ Do not use Pro product photos to depict the primary duckyPad device.
- ❌ Do not invent status agents or Pro-only hardware in the default screen.
- ❌ No purple AI gradient, emoji UI iconography, or generic rounded-card dashboard.
