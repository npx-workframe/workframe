import { authenticatedFetch } from '@/lib/authenticatedFetch'
import { parseApiErrorResponse, WorkframeApiError } from '@/lib/workframeErrors'

async function parseJson<T>(response: Response, method: string, path: string): Promise<T> {
  if (!response.ok) {
    const info = await parseApiErrorResponse(response)
    throw new WorkframeApiError(info, method, path)
  }
  return response.json() as Promise<T>
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await authenticatedFetch(path)
  return parseJson<T>(response, 'GET', path)
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await authenticatedFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return parseJson<T>(response, 'POST', path)
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const response = await authenticatedFetch(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return parseJson<T>(response, 'PATCH', path)
}
