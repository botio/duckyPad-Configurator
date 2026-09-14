const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function rpc() {
  let now = 0;
  const timers = new Set();
  const writes = [];
  const context = vm.createContext({
    __dirname: path.join(__dirname, '../main'), process, console, Buffer, URL,
    require(name) {
      if (name === 'electron') return {
        app: { isPackaged: false, whenReady: () => new Promise(() => {}), on() {} },
        ipcMain: { handle() {} },
      };
      return require(name);
    },
    setTimeout(callback, delay) {
      const timer = { callback, delay, due: now + delay, refresh() { this.due = now + this.delay; } };
      timers.add(timer);
      return timer;
    },
    clearTimeout(timer) { timers.delete(timer); },
    record(line) { writes.push(JSON.parse(line)); },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../main/main.js'), 'utf8'), context);
  vm.runInContext('sidecar = {stdin: {writable: true, write: record}}', context);
  return {
    start(method = 'profiles/save') {
      const result = vm.runInContext(`request(${JSON.stringify(method)}).then(value => ({value}), error => ({error}))`, context);
      return { result, id: writes.at(-1).id };
    },
    message(payload) { context.handleMessage(JSON.stringify(payload)); },
    advance(ms) {
      const end = now + ms;
      for (;;) {
        const next = [...timers].filter(timer => timer.due <= end).sort((a, b) => a.due - b.due)[0];
        if (!next) break;
        now = next.due;
        timers.delete(next);
        next.callback();
      }
      now = end;
    },
  };
}

test('a slow SD operation can return its precise failure after cleanup', async () => {
  const core = rpc();
  const save = core.start();
  core.advance(10000);
  core.message({ method: 'event/profiles/save', params: { request_id: save.id, phase: 'transfer', path: '/profile_autohotkey' } });
  // SD metadata can occupy 30 seconds; bounded EXIT cleanup follows it.
  core.advance(33000);
  core.message({ id: save.id, error: { code: -32001, message: 'DELETE_DIR: FR_DENIED; backup preserved' } });
  assert.equal((await save.result).error.message, 'DELETE_DIR: FR_DENIED; backup preserved');
});

test('progress keeps only its active SAVE alive, not unrelated or stale requests', async () => {
  const core = rpc();
  const save = core.start();
  const unrelated = core.start('profiles/get');
  core.advance(20000);
  core.message({ method: 'event/profiles/save', params: { request_id: unrelated.id, phase: 'transfer' } });
  core.message({ method: 'event/profiles/save', params: { request_id: save.id, phase: 'transfer' } });
  core.advance(20000);
  assert.equal((await unrelated.result).error.message, 'profiles/get timed out');
  core.message({ method: 'event/profiles/save', params: { request_id: save.id, phase: 'transfer' } });
  core.advance(20000);
  core.message({ id: save.id, result: { ok: true } });
  assert.equal((await save.result).value.ok, true);

  const silent = core.start();
  core.advance(20000);
  core.message({ method: 'event/profiles/save', params: { request_id: save.id, phase: 'transfer' } });
  core.advance(30000);
  assert.equal((await silent.result).error.message, 'profiles/save timed out');
});
