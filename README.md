# duckyPad Configurator

Desktop configurator for [duckyPad Macropads](https://duckypad.com).

## Downloads

Download the platform package from the [latest release](https://github.com/botio/duckyPad-Configurator/releases/latest):

* **Linux:** `duckyPad-Configurator-*-linux-x86_64.AppImage`
* **macOS:** Apple Silicon `.dmg`
* **Windows:** x64 NSIS installer

Version 5 uses an Electron desktop shell with a bundled Python device core. It works without a system Python installation and retains duckyPad 2020 HID, duckyPad Pro storage, compiler, profile, backup, import/export, update, and herdr integrations.

Open **Connect → Open Backup Folder** to edit a local duckyPad profile folder without attaching hardware. On Linux, a physical duckyPad requires permission to access its HID device; install the repository's udev rule or run with the device access your distribution requires.

The macOS package is ad-hoc signed, not notarized. On its first launch, Control-click the app in Finder, choose **Open**, then confirm **Open**. This is the supported Gatekeeper override for an unsigned app and is available without an Apple Developer membership.

Full device instructions: [duckyPad documentation](https://dekunukem.github.io/duckyPad-Pro/doc/getting_started.html).

### duckyPad 2020 profile reads

Version 5.0.24 fixes `HID read file returned invalid chunk size: 61`. A 64-byte file-read report has a 3-byte header and up to 61 bytes of file data; earlier versions incorrectly rejected full-size chunks. This parser fix requires only a Configurator update, not an SD format or firmware flash.

Version 5.0.26 stores each DP20 connection's mirror in its own operating-system temporary directory instead of reusing `Application Support/duckypad_config/hid_dump`. Unwritable legacy cache files are left untouched. Disconnecting or switching sessions releases the temporary mirror; saved backups remain in their existing location. Local mirror failures are reported separately from device reads and are not retried as HID failures.

### Feedbacks

* [Open an issue](https://github.com/duckyPad/duckyPad-Configurator/issues)
* Ask in [official duckyPad discord](https://discord.gg/4sJCBx5)
* Email dekuNukem`@`gmail.com!

## herdr Integration

The Configurator configures the [duckyPad × Herdr Bridge](https://github.com/botio/duckyPad-herdr/tree/master/herdr-ducky-pad). In a selected Herdr profile, keys 1–14 show agent state and focus the corresponding pane; key 15 remains a local F9 key.

### What it does

* **Agent-state LEDs** — each lit key shows one agent; color follows the agent's `agent_status` (working / blocked / done / idle / unknown).
* **Key → focus** — press a lit key to bring that agent's pane to the front (one-shot `agent.focus` over herdr's Unix socket).
* **User-service supervision** — the daemon runs as a Linux `systemd --user` service (`ducky-pad-bridge`) or a macOS `launchd` job (`com.botio.ducky-pad-bridge`), not as a herdr `[[startup]]` hook (which is one-shot).

### Using it

1. Use **Configurator 5.0.27+** with **firmware 3.1.15+** on the original duckyPad. The **HERDR** sidebar is visible even when the Bridge is not installed.
2. Click **ADD HERDR PROFILE**, choose a name, then click the bottom **SAVE** button to write it to the pad.
3. On the physical pad, use **+ / −** to select that profile. Starting the Bridge no longer takes over ordinary profiles. Switching away restores normal macro behavior.
4. Change **Working, Blocked, Done, Idle, Unknown** in **STATUS COLORS**, then click **SAVE COLORS**. These colors are host-wide and reload automatically in the running Bridge; they are separate from the pad's profile SAVE operation.
5. Use **INSTALL** to install the Bridge when its dependencies are available. **FLASH** uses a locally available, checksum-verified image; **STOCK** restores the stock image. Both require confirmation. **↻** refreshes diagnostics without discarding unsaved color edits.

The SD marker is `HERDR_PROFILE 1` in that profile's `config.txt`. A profile's name does not enable Herdr. Copy, rename, save, backup, ZIP export/import, and reopening preserve its type. A microSD card containing the profile is required.

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
* `pinned_slots` — optional `slot (1..14) -> pane_id` pin. When a pane_id is pinned, that agent stays on that slot, overriding the sticky "lowest free slot" rule. Unpinned agents still use the sticky rule. The color editor preserves existing pins.

The daemon re-reads the file on every ~2-second `agent.list` poll, so edits apply without a restart.

On macOS, the App now uses the same `Library/Application Support` path as the Rust Bridge, irrespective of `XDG_CONFIG_HOME`. If only the older XDG/`~/.config` file exists, it is validated and copied to the canonical path. An existing canonical file always wins.

### Firmware

Profile-based ownership requires `duckypad_v3.1.15-herdr.dfu` or newer. Older Herdr firmware can still auto-take over the pad, regardless of the profile you created. Stock `duckypad_v3.0.4.dfu` has no Herdr support.

```
dfu-util --device=0483:df11 -a 0 -D <path-to>/duckypad_v3.1.15-herdr.dfu
```

Put the pad in DFU mode (hold the DFU button while plugging it in) and run the command. Keep the stock `duckypad_v3.0.4.dfu` image for rollback.