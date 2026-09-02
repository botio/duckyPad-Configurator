# duckyPad Configurator

This is the software that configures [duckyPad Macropads](duckypad.com)!

### How to Use

* [Click me to download the latest version](https://github.com/duckyPad/duckyPad-Configurator/releases/latest)

* [Click me for full instructions](https://dekunukem.github.io/duckyPad-Pro/doc/getting_started.html)

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

1. Launch the Configurator and click **herdr Integration…** in the *Updates* frame (bottom-right).
2. The dialog shows a live diagnostics block:
   * `herdr` / `cargo` / `dfu-util` versions
   * plugin repo path, `herdr plugin list` registration, user-service status
   * the config file location, any palette overrides, and pinned slots
   * the `dfu-util` command to flash the herdr-capable firmware, plus the stock rollback command
3. Click **Install / Upgrade Plugin** to run the repo's `install.sh` (builds the Rust daemon, registers the plugin with herdr, and installs the user service). Click **Stop & Uninstall Service** to remove it.
4. Click **Open Config (JSON)** to edit `herdr.json` in your system editor, or **Copy Firmware Flash Cmd** to copy the `dfu-util` invocation for a guided flash.

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