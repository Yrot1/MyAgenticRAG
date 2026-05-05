/**
 * API 路径拼接：默认相对路径（走 Vite dev/preview 的 /api 代理）。
 * 若刷新列表出现 404，可在 frontend/.env.development 中设置：
 * VITE_API_BASE=http://127.0.0.1:8000
 */
export function apiUrl(path) {
  let p = path.startsWith('/') ? path : `/${path}`
  const raw = import.meta.env.VITE_API_BASE
  const base = typeof raw === 'string' ? raw.trim().replace(/\/$/, '') : ''
  return base ? `${base}${p}` : p
}

export function getAuthToken() {
  return localStorage.getItem('rag_auth_token') || ''
}

export function setAuthToken(token) {
  if (token) localStorage.setItem('rag_auth_token', token)
  else localStorage.removeItem('rag_auth_token')
}

export function authHeaders(extra = {}) {
  const token = getAuthToken()
  return {
    ...extra,
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  }
}

function formatErrorDetail(detail) {
  if (detail == null) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === 'object' && item?.msg ? item.msg : String(item)))
      .filter(Boolean)
      .join('; ')
  }
  if (typeof detail === 'object') return JSON.stringify(detail)
  return String(detail)
}

export async function apiRequest(path, options = {}) {
  let response
  try {
    const headers = authHeaders(options.headers || {})
    response = await fetch(apiUrl(path), {
      ...options,
      headers
    })
  } catch (e) {
    const hint =
      typeof window !== 'undefined' && window.location?.port === '8080'
        ? '（若通过 Docker 的 8080 访问，请先执行 docker compose up -d，确保 api 容器在运行）'
        : ''
    throw new Error((e?.message || '网络异常') + hint)
  }
  if (response.status === 401) {
    setAuthToken('')
    window.dispatchEvent(new CustomEvent('auth-expired'))
  }
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    let msg = ''
    try {
      const data = JSON.parse(text)
      msg = formatErrorDetail(data.detail) || formatErrorDetail(data.message) || ''
    } catch {
      msg = text.trim().slice(0, 200)
    }
    if (!msg) msg = `HTTP ${response.status}`
    if ((response.status === 502 || response.status === 503) && !msg.includes('Docker')) {
      msg +=
        '。若当前地址为 :8080（Nginx），请确认 docker compose 已启动 api 服务，不要只在本机 8000 跑进程。'
    }
    throw new Error(msg)
  }
  if (response.status === 204) return null
  return response.json()
}

export async function authFetch(path, options = {}) {
  return fetch(apiUrl(path), {
    ...options,
    headers: authHeaders(options.headers || {})
  })
}
