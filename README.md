# duckyPad Configurator

Desktop configurator for [duckyPad Macropads](https://duckypad.com).

## Downloads

Download the platform package from the [latest release](https://github.com/botio/duckyPad-Configurator/releases/latest):

* **Linux:** `duckyPad-Configurator-*-linux-x86_64.AppImage`
* **macOS:** Apple Silicon `.dmg`
* **Windows:** x64 NSIS installer

Version 5 uses an Electron desktop shell with a bundled Python device core. It works without a system Python installation and retains duckyPad 2020 HID, duckyPad Pro storage, compiler, profile, backup, import/export, update, and herdr integrations.

Open **Connect → Open Backup Folder** to edit a local duckyPad profile folder without attaching hardware. On Linux, a physical duckyPad requires permission to access its HID device; install the repository's udev rule or run with the device access your distribution requires.

Full device instructions: [duckyPad documentation](https://dekunukem.github.io/duckyPad-Pro/doc/getting_started.html).
### Feedbacks

* [Open an issue](https://github.com/duckyPad/duckyPad-Configurator/issues)
* Ask in [official duckyPad discord](https://discord.gg/4sJCBx5)
* Email dekuNukem`@`gmail.com!

## herdr Integration

The Configurator can drive the [duckyPad × herdr plugin](https://github.com/duckyPad/duckyPad/tree/master/herdr-ducky-pad) so each of the 15 NeoPixel keys lights one herdr agent (colored by state) and pressing a key focuses that agent's pane.

### What it does

* **Agent-state LEDs** — each lit key shows one agent; color follows the agent's `agent_status` (working / blocked / done / idle / unknown).
* **Key → focus** — press a lit key to bring that agent's pane to the front (one-shot `agent.focus` over herdr's Unix socket).
* **User-service supervision** — the daemon runs as a Linux `systemd --user` service (`ducky-pad-bridge`) or a macOS `launchd` job (`com.botio.ducky-pad-bridge`), not as a herdr `[[startup]]` hook (which is one-shot).

### Using it

1. Launch the Configurator and use the **HERDR** panel in the right sidebar.
2. The panel exposes its current DFU and installation readiness. Use **↻** to refresh it after changing your herdr environment.
3. Click **INSTALL** to run the plugin installer. Click **FLASH** for the herdr firmware or **STOCK** to restore the stock image; both require an explicit confirmation.
4. Edit `herdr.json` at the path below when you need palette or slot overrides.

### Config file

`herdr.json` lives at:

* `~/.config/duckyPad/herdr.json` (Linux / XDG)
* `~/Library/Application Support/duckyPad/herdr.json` (macOS)

Schema (v1):

```json
{
  "schema_version": 1,
  "colors": {
    "working": [0, 255, 0],
    "blocked": [255, 0, 0]
  },
  "pinned_slots": {
    "1": "pane-abc"
  }
}
```

* `colors` — optional `state -> [r, g, b]` overrides. Only the keys you list are replaced; missing keys keep the built-in palette (blocked=red, working=green, done=blue, unknown=amber, idle=dim-gray).
* `pinned_slots` — optional `slot (1..15) -> pane_id` pin. When a pane_id is pinned, that agent stays on that slot, overriding the sticky "lowest free slot" rule. Unpinned agents still use the sticky rule.

The daemon re-reads the file on every ~2-second `agent.list` poll, so edits apply without a restart.

### Firmware

The herdr mode was added in `duckypad_v3.1.0-herdr.dfu`; the stock `duckypad_v3.0.4.dfu` image does **not** include it. The dialog's **Copy Firmware Flash Cmd** button gives you the verified command:

```
dfu-util --device=0483:df11 -a 0 -D <path-to>/duckypad_v3.1.0-herdr.dfu
```

Put the pad in DFU mode (hold the DFU button while plugging it in) and run it. Roll back to the stock image with the `duckypad_v3.0.4.dfu` command the dialog also offers.