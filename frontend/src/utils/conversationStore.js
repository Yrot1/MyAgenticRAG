import { apiRequest } from './api'

export const conversationStore = {
  async getAllConversations() {
    const data = await apiRequest('/api/conversations')
    return data.conversations || []
  },

  async createConversation(name = '新对话') {
    return apiRequest('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    })
  },

  async getConversation(id) {
    return apiRequest(`/api/conversations/${id}`)
  },

  async updateConversation(id, updates) {
    return apiRequest(`/api/conversations/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    })
  },

  async addMessage(conversationId, message) {
    const conv = await this.getConversation(conversationId)
    return this.updateConversation(conversationId, {
      messages: [...(conv.messages || []), message]
    })
  },

  async deleteConversation(id) {
    await apiRequest(`/api/conversations/${id}`, { method: 'DELETE' })
  },

  async renameConversation(id, newName) {
    return this.updateConversation(id, { name: newName })
  },

  async clearMessages(id) {
    return this.updateConversation(id, { messages: [] })
  }
}
