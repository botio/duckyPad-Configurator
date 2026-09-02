"""Headless smoke test for the herdr integration dialog.

duckypad_config.py calls root.mainloop() at import time, so the module import
never returns. This driver:
  1. monkeypatches Tk.mainloop BEFORE the import so the app's own
     `root.mainloop()` call returns immediately to the driver code,
  2. imports the app (which builds the full window and "runs" a no-op mainloop),
  3. drives the real event loop manually and invokes the herdr button,
  4. asserts the dialog rendered the diagnostics, then exits 0.

Run:  xvfb-run -a .venv/bin/python -u smoke_herdr.py
"""
import os
import sys
import time

import tkinter as tk
import tkinter.messagebox as mb
import tkinter.filedialog as fd

# Neutralize popups the boot path may raise (HID errors etc.).
mb.showinfo = lambda *a, **k: None
mb.showerror = lambda *a, **k: None
mb.askokcancel = lambda *a, **k: True
fd.askopenfilename = lambda *a, **k: ""

# Make the app's `root.mainloop()` a no-op so the import returns to us.
orig_mainloop = tk.Tk.mainloop

def noop_mainloop(self, n=0):
    self.update()
    return None

tk.Tk.mainloop = noop_mainloop

import duckypad_config as app  # builds the full window; mainloop is a no-op

root = app.root

# Settle the initial geometry pass.
root.update()
root.update_idletasks()
print("SMOKE: main window built", flush=True)

btn = app.herdr_button
assert btn.winfo_exists(), "herdr button missing"
assert btn.cget("text") == "herdr Integration\u2026"
print("SMOKE: herdr button found:", repr(btn.cget("text")), flush=True)

# Invoke the button.
btn.invoke()
root.update()
root.update_idletasks()

# Locate the dialog.
dialogs = [w for w in root.winfo_children()
           if isinstance(w, tk.Toplevel) and w.title() == "duckyPad \u00d7 herdr"]
assert dialogs, "herdr dialog did not open"
dialog = dialogs[0]
# ScrolledText packs its inner Text widget inside a Frame, so the dialog's
# direct children are Frames. Walk one level deeper to find the Text widget.
def find_text(widget):
    for child in widget.winfo_children():
        if isinstance(child, (tk.Text, tk.scrolledtext.ScrolledText)):
            return child
        found = find_text(child)
        if found is not None:
            return found
    return None

texts_root = find_text(dialog)
assert texts_root, "no Text widget anywhere in dialog"
content = texts_root.get("1.0", "end")
assert "herdr environment" in content, f"diagnostics missing: {content[:200]!r}"
assert "plugin registered with herdr" in content
print("DIALOG RENDERED OK", flush=True)
print("--- first 12 lines ---", flush=True)
for line in content.splitlines()[:12]:
    print("  " + line, flush=True)

# Drive a few idle iterations to be safe, then exit.
for _ in range(5):
    root.update()
dialog.destroy()
root.destroy()
print("SMOKE PASS", flush=True)
sys.exit(0)
