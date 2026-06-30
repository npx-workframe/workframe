import type { BrowserWindow } from 'electron'
import koffi from 'koffi'

const user32 = koffi.load('user32.dll')
const showWindow = user32.func('bool __stdcall ShowWindow(void *hWnd, int nCmdShow)')

const SW_MINIMIZE = 6
const SW_MAXIMIZE = 3
const SW_RESTORE = 9

function hwndFor(win: BrowserWindow) {
  // getNativeWindowHandle() returns a Buffer holding the HWND bytes. Passing the
  // Buffer to a void* param would send the buffer's own address, not the handle —
  // decode the pointer value stored inside it instead.
  return koffi.decode(win.getNativeWindowHandle(), 'void *')
}

export function win32Minimize(win: BrowserWindow) {
  showWindow(hwndFor(win), SW_MINIMIZE)
}

export function win32Maximize(win: BrowserWindow) {
  showWindow(hwndFor(win), SW_MAXIMIZE)
}

export function win32Restore(win: BrowserWindow) {
  showWindow(hwndFor(win), SW_RESTORE)
}

if (process.env.WORKFRAME_WIN32_SELF_CHECK === '1') {
  if (typeof showWindow !== 'function') {
    throw new Error('ShowWindow binding failed')
  }
}
