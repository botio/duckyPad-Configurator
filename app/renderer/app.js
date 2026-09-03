(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const core = window.core;
  const state = { session: null, profile: null, keySlot: null, release: false, devices: [], model: 'dp20', saveTimer: null, checkTimer: null, herdr: null, herdrRoot: null };
  const DP20 = [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16, 17, 18];

  function toast(message, level = 'error') {
    const target = $('toast');
    target.textContent = message;
    target.className = `toast ${level}`;
    clearTimeout(target._timer);
    target._timer = setTimeout(() => target.classList.add('hidden'), 5000);
  }
  async function call(method, params = {}) {
    if (!core) throw { message: 'This UI runs inside the Electron app.' };
    try { return await core.call(method, params); }
    catch (error) { toast(`${error.message || 'Core request failed'}${error.data?.line >= 0 ? ` · line ${error.data.line}` : ''}`); throw error; }
  }
  function show(view) {
    $('boot-view').classList.toggle('hidden', view !== 'boot');
    $('no-device-view').classList.toggle('hidden', view !== 'no-device');
    $('workspace').classList.toggle('hidden', view !== 'workspace');
  }
  function chip(text, cls = '') { const target = $('connection-chip'); target.textContent = text; target.className = `chip ${cls}`; }
  async function refresh() {
    let next = await call('session/state');
    state.session = next;
    if (!next.connected) { state.profile = null; state.keySlot = null; state.herdr = null; state.herdrRoot = null; show('no-device'); chip('NO DEVICE'); return; }
    show('workspace'); chip(`${next.model.toUpperCase()} CONNECTED`, 'connected');
    if (!next.selected_profile && next.profiles.length) {
      next = await call('profiles/select', { name: next.profiles[0].name });
      state.session = next;
    }
    if (next.selected_profile) state.profile = await call('profiles/get', { name: next.selected_profile }); else state.profile = null;
    if (state.herdrRoot !== next.root_path) {
      state.herdrRoot = next.root_path;
      state.herdr = null;
      void refreshHerdr();
    }
    render();
  }
  function render() {
    const session = state.session;
    if (!session?.connected) return;
    $('pad-model').textContent = session.model === 'dp20' ? 'ORIGINAL / 3 × 5' : 'PRO / 4 × 5';
    $('device-info').textContent = `${session.source === 'device' ? 'USB' : 'FOLDER'}\n${session.serial || session.root_path}\nFW ${session.fw_version || 'unknown'}`;
    $('update-status').textContent = `App: ${updateText(session.update.app)}\nFirmware: ${updateText(session.update.firmware)}`;
    renderProfiles(); renderPad(); renderEditor(); renderHerdr();
  }
  function updateText(status) { return status === 0 ? 'up to date' : status === 1 ? 'update available' : 'unknown'; }
  function renderProfiles() {
    const list = $('profile-list'); list.replaceChildren();
    if (!state.session.profiles.length) list.innerHTML = '<p class="dim">NO PROFILES YET</p>';
    for (const profile of state.session.profiles) {
      const button = document.createElement('button'); button.className = `profile ${profile.name === state.session.selected_profile ? 'selected' : ''}`;
      button.textContent = profile.name; button.onclick = () => selectProfile(profile.name); list.append(button);
    }
  }
  function renderPad() {
    const grid = $('key-grid'); const slots = state.session.model === 'dp20' ? DP20 : Array.from({ length: 20 }, (_, i) => i);
    grid.className = `key-grid ${state.session.model === 'dp24' ? 'pro' : ''}`; grid.replaceChildren();
    for (const slot of slots) {
      const key = state.profile?.keylist[slot]; const button = document.createElement('button');
      button.className = `keycap ${key ? '' : 'empty'} ${state.keySlot === slot ? 'selected' : ''}`;
      button.innerHTML = key ? `<span>${escapeHtml(key.name || '')}</span><small>${escapeHtml(key.name_line2 || '')}</small>` : '<span>—</span>';
      button.onclick = () => selectKey(slot); grid.append(button);
    }
    const index = state.session.profiles.findIndex((profile) => profile.name === state.session.selected_profile);
    const name = state.session.selected_profile || 'NO PROFILE';
    $('oled').innerHTML = `<span>P${index >= 0 ? index + 1 : '-'}</span><small>${escapeHtml(name.slice(0, 10))}</small>`;
  }
  function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, (char) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[char])); }
  function setEnabled(enabled) { for (const id of ['key-name','key-name-2','allow-abort','dont-repeat','key-color','script','clear-key']) $(id).disabled = !enabled; }
  function renderEditor() {
    const key = state.keySlot == null ? null : state.profile?.keylist[state.keySlot];
    setEnabled(state.keySlot != null);
    $('key-name').value = key?.name || ''; $('key-name-2').value = key?.name_line2 || '';
    $('allow-abort').checked = Boolean(key?.allow_abort); $('dont-repeat').checked = Boolean(key?.dont_repeat);
    $('key-color').value = colourHex(key?.color || [244, 241, 233]);
    $('script').value = state.release ? (key?.script_on_release || '') : (key?.script || '');
    $('syntax-status').className = 'syntax-status'; $('syntax-status').textContent = state.keySlot == null ? 'Select a key to check its script.' : 'Waiting for edits…';
  }
  function colourHex(rgb) { return `#${rgb.map((value) => Number(value).toString(16).padStart(2, '0')).join('')}`; }
  function hexColour(hex) { const value = hex.replace('#',''); return [0, 2, 4].map((index) => Number.parseInt(value.slice(index, index + 2), 16)); }
  async function selectProfile(name) {
    state.session = await call('profiles/select', { name }); state.profile = await call('profiles/get', { name }); state.keySlot = null; render();
  }
  function selectKey(slot) { state.keySlot = slot; renderPad(); renderEditor(); }
  function mutableKey() {
    if (state.keySlot == null) return null;
    const current = state.profile.keylist[state.keySlot];
    return current || { index: state.keySlot, name: '', name_line2: '', script: '', script_on_release: '', color: null, allow_abort: false, dont_repeat: false, repeat_ms: null };
  }
  function scheduleKeySave() {
    clearTimeout(state.saveTimer); state.saveTimer = setTimeout(saveKey, 300);
    clearTimeout(state.checkTimer); state.checkTimer = setTimeout(checkScript, 400);
  }
  async function saveKey() {
    const key = mutableKey(); if (!key || !state.profile) return;
    key.name = $('key-name').value.trim(); key.name_line2 = $('key-name-2').value.trim(); key.allow_abort = $('allow-abort').checked; key.dont_repeat = $('dont-repeat').checked;
    key.color = hexColour($('key-color').value);
    if (state.release) key.script_on_release = $('script').value; else key.script = $('script').value;
    state.profile.keylist[state.keySlot] = key;
    try { state.session = await call('profiles/update', { name: state.profile.name, patch: { keylist: state.profile.keylist } }); renderPad(); }
    catch (_) { /* call() already showed the error */ }
  }
  async function checkScript() {
    if (state.keySlot == null) return;
    const target = $('syntax-status');
    try { await call('script/check', { script: $('script').value, on_release: state.release ? 1 : 0 }); target.className = 'syntax-status ok'; target.textContent = 'Code seems OK…'; }
    catch (error) { target.className = 'syntax-status error'; target.textContent = `${error.data?.line >= 0 ? `LINE ${error.data.line}: ` : ''}${error.message || 'Syntax error'}`; }
  }
  async function profileAction(method, params = {}) { state.session = await call(method, params); await refresh(); }
  async function cycleProfile(delta) {
    const profiles = state.session.profiles; if (!profiles.length) return;
    const current = Math.max(0, profiles.findIndex((p) => p.name === state.session.selected_profile));
    await selectProfile(profiles[(current + delta + profiles.length) % profiles.length].name);
  }
  function renderHerdr() {
    const status = state.herdr; const panel = $('herdr-panel');
    if (!status || status.unavailable || !status.env) { panel.classList.add('hidden'); return; }
    panel.classList.remove('hidden');
    $('herdr-status').textContent = `DFU: ${status.dfu?.verified === true ? 'verified' : 'not verified'}\nInstall: ${status.env.can_install_plugin ? 'ready' : 'unavailable'}`;
  }
  async function refreshHerdr() {
    try { state.herdr = await call('herdr/status'); }
    catch (_) { state.herdr = null; }
    renderHerdr();
  }
  async function connectScan() {
    const result = await call('device/scan'); state.devices = result.devices || []; const list = $('device-list'); list.replaceChildren();
    if (!state.devices.length) {
      const messages = {
        hid_unavailable: 'The bundled HID runtime could not start.',
        permissions: 'A compatible duckyPad was found, but macOS could not open its HID interface. Reconnect the pad, approve any USB accessory prompt, then retry.',
        unresponsive: 'A compatible duckyPad was found but did not answer its HID probe. Disconnect and reconnect it, then retry.',
        sudo: 'Linux needs permission to read the HID device. Check udev rules or run with the required device access.',
        not_found: 'No compatible duckyPad is visible to macOS. Check USB, cable, and Bluetooth mode.',
      };
      list.textContent = [messages[result.hint] || 'No duckyPad found.', result.detail].filter(Boolean).join('\n');
      return;
    }
    for (const device of state.devices) { const button = document.createElement('button'); button.textContent = `${device.model.toUpperCase()} · ${device.serial} · FW ${device.fw_version}`; button.onclick = async () => { await call('device/connect', { id: device.id }); await refresh(); }; list.append(button); }
  }
  async function connectFolder(model) { const folder = await core.pickFolder(); if (!folder) return; await call('device/connect_folder', { path: folder, model }); await refresh(); }
  function requestProfileName(title, initialValue = '', action = 'CREATE') {
    return new Promise((resolve) => {
      const dialog = $('profile-dialog'); const input = $('profile-dialog-name');
      $('profile-dialog-title').textContent = title; $('profile-dialog-confirm').textContent = action; input.value = initialValue;
      dialog.onclose = () => resolve(dialog.returnValue === 'accept' ? input.value.trim() : null);
      dialog.showModal(); input.focus(); input.select();
    });
  }
  function bind() {
    $('connect-button').onclick = () => { show('no-device'); connectScan(); };
    $('scan-button').onclick = connectScan; $('folder-button').onclick = () => $('model-picker').classList.remove('hidden');
    document.querySelectorAll('[data-model]').forEach((button) => button.onclick = () => connectFolder(button.dataset.model));
    $('new-profile').onclick = async () => { const name = await requestProfileName('New profile'); if (name) await profileAction('profiles/create', { name }); };
    $('profile-rename').onclick = async () => { if (!state.profile) return; const new_name = await requestProfileName('Rename profile', state.profile.name, 'RENAME'); if (new_name) await profileAction('profiles/rename', { name: state.profile.name, new_name }); };
    $('profile-duplicate').onclick = () => state.profile && profileAction('profiles/duplicate', { name: state.profile.name });
    $('profile-delete').onclick = () => state.profile && confirm(`Delete ${state.profile.name}?`) && profileAction('profiles/delete', { name: state.profile.name });
    $('profile-up').onclick = () => state.profile && profileAction('profiles/move', { name: state.profile.name, direction: 'up' });
    $('profile-down').onclick = () => state.profile && profileAction('profiles/move', { name: state.profile.name, direction: 'down' });
    $('previous-profile').onclick = () => cycleProfile(-1); $('next-profile').onclick = () => cycleProfile(1);
    for (const id of ['key-name','key-name-2','allow-abort','dont-repeat','key-color','script']) $(id).addEventListener(id === 'script' ? 'input' : 'change', scheduleKeySave);
    document.querySelectorAll('input[name="script-mode"]').forEach((input) => input.onchange = () => { state.release = input.value === 'release'; renderEditor(); });
    $('clear-key').onclick = async () => { if (state.keySlot == null || !state.profile) return; state.profile.keylist[state.keySlot] = null; state.session = await call('profiles/update', { name: state.profile.name, patch: { keylist: state.profile.keylist } }); renderPad(); renderEditor(); };
    $('save-button').onclick = async () => { await saveKey(); await call('profiles/save', { name: state.profile?.name || null, to: 'device' }); toast('Saved', 'ok'); };
    $('backup-button').onclick = () => call('profiles/save', { name: state.profile?.name || null, to: 'backup' }).then((r) => toast(`Backup: ${r.path}`, 'ok'));
    $('export-button').onclick = async () => { const dir = await core.pickExportDir(); if (dir && state.profile) { const r = await call('profiles/export', { names: [state.profile.name], dir }); toast(`Exported: ${r.path}`, 'ok'); } };
    $('import-button').onclick = async () => { const path = await core.pickImportFile(); if (path) { await call('profiles/import', { path, model: state.session.model }); await refresh(); } };
    $('open-folder').onclick = () => state.session?.root_path && core.openPath(state.session.root_path);
    $('manual-link').onclick = () => core.openExternal('https://dekunukem.github.io/duckyPad-Pro/doc/getting_started.html');
    $('script-docs').onclick = (event) => { event.preventDefault(); core.openExternal('https://dekunukem.github.io/duckyPad-Pro/doc/duckyscript_info.html'); };
    $('refresh-updates').onclick = async () => { state.session.update = await call('update/check'); render(); };
    $('refresh-herdr').onclick = refreshHerdr; $('herdr-install').onclick = () => call('herdr/install').then((r) => toast(r.log || 'herdr installed', 'ok'));
    $('herdr-flash').onclick = () => confirm('Flash herdr firmware?') && call('herdr/flash', { image: 'herdr' }).then(() => toast('Firmware flashed', 'ok'));
    $('herdr-stock').onclick = () => confirm('Restore stock firmware?') && call('herdr/flash', { image: 'stock' }).then(() => toast('Stock firmware flashed', 'ok'));
    if (core) { core.on('event/sidecar-dead', ({ reason }) => { chip('CORE STOPPED', 'failed'); toast(reason); }); core.on('event/herdr/flash', ({ phase, detail }) => toast(`${phase}: ${detail}`, phase === 'error' ? 'error' : 'ok')); }
  }
  async function boot() {
    bind(); if (!core) { show('no-device'); chip('ELECTRON REQUIRED', 'failed'); $('no-device-view').querySelector('.welcome-card').insertAdjacentHTML('afterbegin','<p class="toast">This UI runs inside the Electron app.</p>'); return; }
    try { await call('hello'); await refresh(); await refreshHerdr(); } catch (error) { show('no-device'); chip('CORE ERROR', 'failed'); toast(error.message || 'Cannot start core'); }
  }
  boot();
})();
