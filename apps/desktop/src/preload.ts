import { contextBridge, ipcRenderer } from 'electron'

import type { DesktopBridge } from './bridgeTypes.js'

const bridge: DesktopBridge = {
  getConfig: () => ipcRenderer.invoke('config:get'),
  setLastUrl: (url: string) => ipcRenderer.invoke('config:setLastUrl', url),
  clearLastUrl: () => ipcRenderer.invoke('config:clearLastUrl'),
  getInviteParams: () => ipcRenderer.invoke('invite:getParams'),
  minimizeWindow: () => ipcRenderer.invoke('window:minimize'),
  toggleMaximizeWindow: () => ipcRenderer.invoke('window:toggle-maximize'),
  closeWindow: () => ipcRenderer.invoke('window:close'),
  setBrowserViewBounds: (bounds) => ipcRenderer.invoke('browser-view:bounds', bounds),
  setBrowserViewUrl: (url) => ipcRenderer.invoke('browser-view:url', url),
  clearBrowserView: () => ipcRenderer.invoke('browser-view:clear'),
  onConnectionChange: (callback) => {
    const listener = (_event: Electron.IpcRendererEvent, state: 'connecting' | 'connected' | 'error') => {
      callback(state)
    }
    ipcRenderer.on('connection:state', listener)
    return () => { ipcRenderer.removeListener('connection:state', listener) }
  },
  getPlatform: () => process.platform,
  getAppVersion: () => ipcRenderer.invoke('app:getVersion'),
}

contextBridge.exposeInMainWorld('workframe', bridge)
