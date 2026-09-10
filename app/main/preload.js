const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('core', {
  call: async (method, params = {}) => {
    const response = await ipcRenderer.invoke('core:call', { method, params });
    if (!response || !response.ok) {
      throw response?.error || { code: -32000, message: 'Core request failed', data: {} };
    }
    return response.result;
  },
  on: (method, callback) => {
    const listener = (_event, payload) => {
      if (payload.method === method) callback(payload.params || {});
    };
    ipcRenderer.on('core:event', listener);
    return () => ipcRenderer.removeListener('core:event', listener);
  },
  pickExportDir: () => ipcRenderer.invoke('core:pickExportDir'),
  pickImportFile: () => ipcRenderer.invoke('core:pickImportFile'),
  pickFolder: () => ipcRenderer.invoke('core:pickFolder'),
  openPath: (target) => ipcRenderer.invoke('core:openPath', target),
  openExternal: (target) => ipcRenderer.invoke('core:openExternal', target),
});
