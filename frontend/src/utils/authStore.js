import { apiRequest, getAuthToken, setAuthToken } from './api'

const USER_KEY = 'rag_auth_user'

export const authStore = {
  getToken() {
    return getAuthToken()
  },

  getUser() {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  },

  setSession(token, user) {
    setAuthToken(token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  },

  clearSession() {
    setAuthToken('')
    localStorage.removeItem(USER_KEY)
  },

  async register(payload) {
    const data = await apiRequest('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    this.setSession(data.access_token, data.user)
    return data.user
  },

  async login(payload) {
    const data = await apiRequest('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    this.setSession(data.access_token, data.user)
    return data.user
  },

  async fetchMe() {
    const user = await apiRequest('/api/auth/me')
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    return user
  }
}
