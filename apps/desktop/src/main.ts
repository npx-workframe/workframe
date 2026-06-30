import { app, BrowserView, BrowserWindow, ipcMain, Menu, screen, shell } from 'electron'
import type { IpcMainInvokeEvent } from 'electron'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import Store from 'electron-store'

import { isSafeUrl } from './lib/urlPolicy.js'

const isWin = process.platform === 'win32'

async function win32Api() {
  if (!isWin) return null
  return import('./win32Window.js')
}

const __dirname = dirname(fileURLToPath(import.meta.url))
const isDev = !app.isPackaged

const store = new Store<{
  lastUrl: string
  isFirstRun: boolean
}>({
  defaults: {
    lastUrl: '',
    isFirstRun: true,
  },
})

const DEV_URL = process.env.WORKFRAME_WEB_URL?.trim() || 'http://127.0.0.1:18644'
const DEFAULT_FALLBACK_URL = process.env.WORKFRAME_PRELOAD_URL?.trim() || 'http://127.0.0.1:18644'

interface InviteParams {
  inviteToken: string
  email: string
}

function extractInviteParams(url: URL): InviteParams {
  return {
    inviteToken: url.searchParams.get('invite_token')?.trim() || '',
    email: url.searchParams.get('email')?.trim() || '',
  }
}

function resolveTargetUrl(): { url: string; invite: InviteParams; isFirstRun: boolean } {
  if (isDev) {
    const invite = extractInviteParams(new URL(DEV_URL))
    return { url: DEV_URL, invite, isFirstRun: false }
  }
  const lastUrl = store.get('lastUrl')?.trim()
  const preload = process.env.WORKFRAME_PRELOAD_URL?.trim()
  if (!lastUrl && preload) {
    store.set('lastUrl', preload)
    store.set('isFirstRun', false)
  }
  const targetUrl = store.get('lastUrl')?.trim() || preload || DEFAULT_FALLBACK_URL
  if (!isSafeUrl(targetUrl)) {
    store.set('lastUrl', '')
    const fallback = preload && isSafeUrl(preload) ? preload : DEFAULT_FALLBACK_URL
    const url = new URL(fallback)
    const invite = extractInviteParams(url)
    return { url: url.toString(), invite, isFirstRun: true }
  }
  const url = new URL(targetUrl)
  const invite = extractInviteParams(url)
  return { url: url.toString(), invite, isFirstRun: !lastUrl }
}

function buildUrlWithInvite(baseUrl: string, invite: InviteParams): string {
  const url = new URL(baseUrl)
  if (invite.inviteToken) {
    url.searchParams.set('invite_token', invite.inviteToken)
  }
  if (invite.email) {
    url.searchParams.set('email', invite.email)
  }
  return url.toString()
}

let mainWindow: BrowserWindow | null = null
let currentState: 'connecting' | 'connected' | 'error' = 'connecting'
let browserView: BrowserView | null = null

type WindowChromeState = {
  customMaximized: boolean
  restoreBounds: Electron.Rectangle | null
}

const windowChrome = new WeakMap<BrowserWindow, WindowChromeState>()

function chromeState(win: BrowserWindow): WindowChromeState {
  let state = windowChrome.get(win)
  if (!state) {
    state = { customMaximized: false, restoreBounds: null }
    windowChrome.set(win, state)
  }
  return state
}

function rememberWindowBounds(win: BrowserWindow) {
  const state = chromeState(win)
  if (!state.customMaximized && !win.isMaximized() && !win.isMinimized()) {
    state.restoreBounds = win.getBounds()
  }
}

function isWindowExpanded(win: BrowserWindow) {
  return win.isMaximized() || chromeState(win).customMaximized
}

function restoreWindowBounds(win: BrowserWindow) {
  const state = chromeState(win)
  if (win.isMaximized()) {
    win.unmaximize()
  }
  if (state.restoreBounds) {
    win.setBounds(state.restoreBounds)
  }
  state.customMaximized = false
}

function expandWindow(win: BrowserWindow) {
  const state = chromeState(win)
  state.restoreBounds = win.getBounds()
  win.maximize()
  if (process.platform === 'win32' && !win.isMaximized()) {
    const { workArea } = screen.getDisplayMatching(win.getBounds())
    win.setBounds(workArea)
    state.customMaximized = true
    return
  }
  state.customMaximized = win.isMaximized()
}

function emitConnectionState(state: 'connecting' | 'connected' | 'error') {
  currentState = state
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('connection:state', state)
  }
}

async function loadUrl(targetUrl: string) {
  if (!mainWindow) return
  if (!isSafeUrl(targetUrl)) {
    emitConnectionState('error')
    return
  }
  emitConnectionState('connecting')
  try {
    await mainWindow.loadURL(targetUrl)
    emitConnectionState('connected')
  } catch (err) {
    emitConnectionState('error')
    console.error('[workframe] loadURL failed:', err)
  }
}

function ensureBrowserView() {
  if (!mainWindow) return null
  if (!browserView || browserView.webContents.isDestroyed()) {
    browserView = new BrowserView({
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        javascript: true,
      },
    })
    mainWindow.addBrowserView(browserView)
    browserView.setBounds({ x: 0, y: 0, width: 0, height: 0 })
    browserView.webContents.setWindowOpenHandler(({ url }) => {
      if (isSafeUrl(url)) void shell.openExternal(url)
      return { action: 'deny' }
    })
  }
  return browserView
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'Workframe',
    frame: false,
    thickFrame: isWin,
    minimizable: true,
    maximizable: true,
    closable: true,
    transparent: false,
    backgroundColor: '#0A0A0F',
    show: false,
    webPreferences: {
      preload: join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webviewTag: false,
    },
  })

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.on('resize', () => {
    if (mainWindow) rememberWindowBounds(mainWindow)
  })
  mainWindow.on('move', () => {
    if (mainWindow) rememberWindowBounds(mainWindow)
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isSafeUrl(url)) void shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, _errorDescription, _validatedURL, isMainFrame) => {
    if (!isMainFrame) return
    if (String(errorCode) !== '-3') {
      emitConnectionState('error')
    }
  })

  const { url, invite } = resolveTargetUrl()
  const finalUrl = buildUrlWithInvite(url, invite)
  void loadUrl(finalUrl)
}

// --- IPC handlers ---

ipcMain.handle('app:getVersion', () => app.getVersion())

ipcMain.handle('config:get', () => {
  return {
    lastUrl: store.get('lastUrl'),
    isFirstRun: store.get('isFirstRun'),
  }
})

ipcMain.handle('config:setLastUrl', (_event, url: string) => {
  const trimmed = String(url || '').trim()
  if (!trimmed || !isSafeUrl(trimmed)) {
    throw new Error('invalid url')
  }
  store.set('lastUrl', trimmed)
  store.set('isFirstRun', false)
})

ipcMain.handle('config:clearLastUrl', () => {
  store.set('lastUrl', '')
})

ipcMain.handle('invite:getParams', () => {
  const { invite } = resolveTargetUrl()
  return invite
})

function windowFromEvent(event: IpcMainInvokeEvent) {
  return BrowserWindow.fromWebContents(event.sender)
}

ipcMain.handle('window:minimize', async (event) => {
  const win = windowFromEvent(event)
  if (!win || win.isMinimized()) return

  if (isWin) {
    const w32 = await win32Api()
    if (win.isMaximized()) {
      w32?.win32Restore(win)
    } else if (chromeState(win).customMaximized) {
      restoreWindowBounds(win)
    }
    w32?.win32Minimize(win)
    return
  }

  if (isWindowExpanded(win)) restoreWindowBounds(win)
  win.minimize()
})

ipcMain.handle('window:toggle-maximize', async (event) => {
  const win = windowFromEvent(event)
  if (!win) return { maximized: false }

  if (isWin) {
    const w32 = await win32Api()
    if (win.isMaximized()) {
      w32?.win32Restore(win)
      chromeState(win).customMaximized = false
      return { maximized: false }
    }
    if (chromeState(win).customMaximized) {
      restoreWindowBounds(win)
      return { maximized: false }
    }
    chromeState(win).restoreBounds = win.getBounds()
    w32?.win32Maximize(win)
    return { maximized: win.isMaximized() }
  }

  if (isWindowExpanded(win)) {
    restoreWindowBounds(win)
    return { maximized: false }
  }

  expandWindow(win)
  return { maximized: isWindowExpanded(win) }
})

ipcMain.handle('window:close', (event) => {
  windowFromEvent(event)?.close()
})

ipcMain.handle('browser-view:bounds', (_event, bounds) => {
  const view = ensureBrowserView()
  if (!view || !mainWindow) return
  const width = Math.max(0, Math.round(bounds.width))
  const height = Math.max(0, Math.round(bounds.height))
  if (width === 0 || height === 0) {
    view.setBounds({ x: 0, y: 0, width: 0, height: 0 })
    return
  }
  view.setBounds({
    x: Math.round(bounds.x),
    y: Math.round(bounds.y),
    width,
    height,
  })
  view.setBackgroundColor('#000000')
})

ipcMain.handle('browser-view:url', (_event, url: string) => {
  const view = ensureBrowserView()
  if (!view) return
  const normalized = url.trim()
  if (!normalized || !isSafeUrl(normalized)) return
  void view.webContents.loadURL(normalized)
})

ipcMain.handle('browser-view:clear', () => {
  if (!mainWindow || !browserView) return
  try {
    mainWindow.removeBrowserView(browserView)
  } catch {
    // ignore
  }
  browserView.webContents.close()
  browserView = null
})

// --- App lifecycle ---

app.whenReady().then(() => {
  Menu.setApplicationMenu(null)
  createWindow()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})

// --- Public API for URL navigation (called from menu/protocol) ---

export function navigateTo(url: string) {
  if (!isSafeUrl(url)) return
  if (mainWindow && !mainWindow.isDestroyed()) {
    void loadUrl(url)
  }
}

export function reload() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.reload()
  }
}
