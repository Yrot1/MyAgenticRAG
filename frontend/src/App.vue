<template>
  <div v-if="!currentUser" class="auth-page tech-bg">
    <div class="auth-card">
      <div class="auth-brand">
        <div class="logo-ring">
          <el-avatar :size="42" :src="assistantAvatar" class="logo-avatar" />
        </div>
        <div>
          <h1>知识库助手</h1>
          <p>登录后使用个人会话和知识库</p>
        </div>
      </div>
      <el-form class="auth-form" @submit.prevent>
        <el-form-item>
          <el-input v-model="authForm.username" placeholder="用户名或邮箱" size="large" />
        </el-form-item>
        <el-form-item v-if="authMode === 'register'">
          <el-input v-model="authForm.email" placeholder="邮箱" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="authForm.password" type="password" show-password placeholder="密码" size="large" />
        </el-form-item>
        <el-button type="primary" class="auth-submit" :loading="authLoading" @click="submitAuth">
          {{ authMode === 'login' ? '登录' : '注册并登录' }}
        </el-button>
      </el-form>
      <button class="auth-switch" @click="authMode = authMode === 'login' ? 'register' : 'login'">
        {{ authMode === 'login' ? '没有账号？去注册' : '已有账号？去登录' }}
      </button>
    </div>
  </div>

  <div v-else class="app-container tech-bg">
    <!-- 统一顶部导航栏 -->
    <div class="top-bar glass-bar">
      <div class="top-bar-content">
        <div class="left-section">
          <el-button 
            v-if="sidebarCollapsed"
            type="link" 
            @click="sidebarCollapsed = false"
            class="menu-btn"
          >
            <el-icon><Expand /></el-icon>
          </el-button>
          <div class="logo-ring">
            <el-avatar :size="34" :src="assistantAvatar" class="logo-avatar" />
          </div>
          <div class="brand-text">
            <span class="app-name">知识库助手</span>
            <span class="app-tag">Agentic RAG</span>
          </div>
        </div>
        <div class="right-section">
          <span class="user-chip">{{ currentUser.username }}</span>
          <el-button 
            type="link" 
            class="action-btn kb-trigger"
            @click="openDrawer"
            title="知识库"
          >
            <el-icon><Folder /></el-icon>
            <span class="kb-trigger-label">知识库</span>
          </el-button>
          <el-button type="link" class="action-btn logout-btn" @click="logout">
            退出
          </el-button>
        </div>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="content-wrapper">
      <!-- 左侧边栏 -->
      <div class="sidebar glass-sidebar" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
        <div class="sidebar-content" v-if="!sidebarCollapsed">
          <div class="sidebar-toolbar">
            <span class="sidebar-label">会话</span>
            <el-button type="link" class="sidebar-fold" @click="sidebarCollapsed = true" title="收起侧栏">
              <el-icon><Fold /></el-icon>
            </el-button>
          </div>
          <!-- 新建对话按钮 -->
          <el-button type="primary" @click="createNewConversation" class="new-chat-btn" block>
            <el-icon><Plus /></el-icon>
            新建对话
          </el-button>
          
          <!-- 对话列表标题 -->
          <div class="history-title">历史对话</div>
          
          <!-- 对话列表 -->
          <div class="conversation-list">
            <div
              v-for="conv in conversations"
              :key="conv.id"
              :class="['conversation-item', { active: currentConversationId === conv.id }]"
              @click="switchConversation(conv.id)"
            >
              <el-icon class="chat-icon"><ChatDotRound /></el-icon>
              <span class="conversation-name">{{ conv.name }}</span>
              <div class="conversation-actions">
                <el-button 
                  type="link" 
                  size="small"
                  @click.stop="renameConversation(conv)"
                >
                  <el-icon><Edit /></el-icon>
                </el-button>
                <el-button 
                  type="link" 
                  size="small"
                  @click.stop="deleteConversation(conv.id)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 主聊天区 -->
      <div class="main-chat-area">
        <ChatBox 
          :currentConversationId="currentConversationId"
          @conversation-change="handleConversationChange"
        />
      </div>
    </div>

    <!-- 右侧抽屉 - 知识库 -->
    <el-drawer
      v-model="drawerVisible"
      direction="rtl"
      size="480px"
      :before-close="handleClose"
      :show-close="true"
      class="knowledge-drawer tech-drawer-panel"
      @opened="onKnowledgeDrawerOpened"
    >
      <template #header>
        <div class="kb-drawer-head">
          <div class="kb-drawer-icon-box">
            <el-icon :size="22"><FolderOpened /></el-icon>
          </div>
          <div class="kb-drawer-text">
            <span class="kb-drawer-title">知识库</span>
            <span class="kb-drawer-sub">向量索引 · 对话检索共用数据源</span>
          </div>
        </div>
      </template>
      <FileUploader ref="fileUploaderRef" />
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import ChatBox from './components/ChatBox.vue'
import FileUploader from './components/FileUploader.vue'
import { Folder, FolderOpened, Plus, Fold, Expand, Edit, Delete, ChatDotRound } from '@element-plus/icons-vue'
import { conversationStore } from './utils/conversationStore'
import { authStore } from './utils/authStore'
import { ElMessage, ElMessageBox } from 'element-plus'

const ACTIVE_CONVERSATION_KEY = 'rag_active_conversation_id'

// 头像 URL
const assistantAvatar = 'https://ts1.tc.mm.bing.net/th/id/OIP-C.9sP0jV5JcinOj8ZOgxXGHAHaHa?rs=1&pid=ImgDetMain&o=7&rm=3'

const drawerVisible = ref(false)
const sidebarCollapsed = ref(false)
const conversations = ref([])
const currentConversationId = ref(null)
const fileUploaderRef = ref(null)
const currentUser = ref(authStore.getUser())
const authMode = ref('login')
const authLoading = ref(false)
const authForm = ref({
  username: '',
  email: '',
  password: ''
})

const submitAuth = async () => {
  if (!authForm.value.username.trim() || !authForm.value.password.trim()) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  if (authMode.value === 'register' && !authForm.value.email.trim()) {
    ElMessage.warning('请输入邮箱')
    return
  }
  authLoading.value = true
  try {
    const user = authMode.value === 'login'
      ? await authStore.login({
        username: authForm.value.username,
        password: authForm.value.password
      })
      : await authStore.register({
        username: authForm.value.username,
        email: authForm.value.email,
        password: authForm.value.password
      })
    currentUser.value = user
    await initializeConversations()
    ElMessage.success('登录成功')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    authLoading.value = false
  }
}

const logout = () => {
  authStore.clearSession()
  currentUser.value = null
  conversations.value = []
  currentConversationId.value = null
  localStorage.removeItem(ACTIVE_CONVERSATION_KEY)
}

const openDrawer = () => {
  drawerVisible.value = true
}

const onKnowledgeDrawerOpened = () => {
  fileUploaderRef.value?.refreshFiles?.()
}

const handleClose = (done) => {
  done()
}

const getConversationTitleFromMessages = (messages = []) => {
  const firstUserMessage = messages.find((message) => message.role === 'user')
  return firstUserMessage?.content?.trim().replace(/\s+/g, ' ') || ''
}

// 加载对话列表
const loadConversations = async () => {
  conversations.value = await conversationStore.getAllConversations()
  console.log('加载到的对话列表:', conversations.value)
  const preferredId = localStorage.getItem(ACTIVE_CONVERSATION_KEY)
  if (preferredId && conversations.value.some((c) => c.id === preferredId)) {
    currentConversationId.value = preferredId
    console.log('恢复上次选中对话 ID:', currentConversationId.value)
  } else if (conversations.value.length > 0 && !currentConversationId.value) {
    currentConversationId.value = conversations.value[0].id
    console.log('选中对话 ID:', currentConversationId.value)
  }
}

watch(currentConversationId, (id) => {
  if (id) localStorage.setItem(ACTIVE_CONVERSATION_KEY, id)
  else localStorage.removeItem(ACTIVE_CONVERSATION_KEY)
})

// 新建对话
const createNewConversation = async () => {
  const newConv = await conversationStore.createConversation('新对话')
  await loadConversations()
  currentConversationId.value = newConv.id
  ElMessage.success('新建对话成功')
}

// 切换对话
const switchConversation = (id) => {
  currentConversationId.value = id
}

// 重命名对话
const renameConversation = async (conv) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入新名称', '重命名对话', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: conv.name,
      inputPattern: /.+/,
      inputErrorMessage: '名称不能为空'
    })
    await conversationStore.renameConversation(conv.id, value)
    await loadConversations()
    ElMessage.success('重命名成功')
  } catch {
    // 取消操作
  }
}

// 删除对话
const deleteConversation = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await conversationStore.deleteConversation(id)
    await loadConversations()
    if (currentConversationId.value === id) {
      currentConversationId.value = conversations.value.length > 0 ? conversations.value[0].id : null
    }
    ElMessage.success('删除成功')
  } catch {
    // 取消操作
  }
}

// 处理对话变化
const handleConversationChange = async (data) => {
  const { conversationId, messages } = data
  const currentConversation = conversations.value.find((conversation) => conversation.id === conversationId)
  const updates = { messages }

  if (currentConversation?.name === '新对话') {
    const hadUserMessage = currentConversation.messages?.some((message) => message.role === 'user')
    const firstQuestionTitle = getConversationTitleFromMessages(messages)
    if (!hadUserMessage && firstQuestionTitle) {
      updates.name = firstQuestionTitle
    }
  }

  const updatedConversation = await conversationStore.updateConversation(conversationId, updates)
  if (updatedConversation) {
    conversations.value = conversations.value.map((conversation) =>
      conversation.id === conversationId ? updatedConversation : conversation
    )
  }
}

const initializeConversations = async () => {
  await loadConversations()
  // 确保至少有一个对话
  if (conversations.value.length === 0) {
    const newConv = await conversationStore.createConversation('新对话')
    // 不添加初始欢迎消息到 messages，让快捷按钮显示
    await loadConversations()
    currentConversationId.value = newConv.id
    ElMessage.success('欢迎使用个人知识库助手')
  } else {
    // 如果没有选中对话，选中第一个
    if (!currentConversationId.value && conversations.value.length > 0) {
      currentConversationId.value = conversations.value[0].id
    }
  }
}

window.addEventListener('auth-expired', () => {
  logout()
  ElMessage.warning('登录已过期，请重新登录')
})

onMounted(async () => {
  if (!authStore.getToken()) {
    currentUser.value = null
    return
  }
  try {
    currentUser.value = await authStore.fetchMe()
    await initializeConversations()
  } catch {
    logout()
  }
})
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.auth-card {
  width: min(420px, 100%);
  padding: 30px;
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), transparent 42%),
    rgba(15, 23, 42, 0.78);
  border: 1px solid rgba(148, 163, 184, 0.16);
  box-shadow:
    0 28px 72px rgba(0, 0, 0, 0.48),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(18px);
}

.auth-brand {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
}

.auth-brand h1 {
  margin: 0;
  font-size: 22px;
  color: var(--tech-text);
}

.auth-brand p {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--tech-muted);
}

.auth-form {
  margin-bottom: 16px;
}

.auth-submit {
  width: 100%;
  height: 44px;
  border: none;
  border-radius: 12px;
  font-weight: 700;
  background: linear-gradient(135deg, #0891b2 0%, #6366f1 100%) !important;
}

.auth-switch {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--tech-accent);
  cursor: pointer;
  font-size: 13px;
}

.app-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.glass-bar {
  backdrop-filter: blur(16px);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent),
    rgba(15, 23, 42, 0.78) !important;
  border-bottom: 1px solid var(--tech-border);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.top-bar {
  height: 64px;
  flex-shrink: 0;
  width: 100%;
}

.top-bar-content {
  height: 100%;
  padding: 0 26px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.left-section {
  display: flex;
  align-items: center;
  gap: 14px;
}

.menu-btn {
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  color: var(--tech-muted);
  transition: color 0.2s, background 0.2s, box-shadow 0.2s;
}

.menu-btn:hover {
  color: var(--tech-accent);
  background: var(--tech-accent-soft);
  box-shadow: 0 0 20px rgba(34, 211, 238, 0.15);
}

.logo-ring {
  padding: 2px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.85), rgba(167, 139, 250, 0.85));
  box-shadow:
    0 0 22px rgba(34, 211, 238, 0.28),
    0 0 48px rgba(167, 139, 250, 0.1);
}

.logo-avatar {
  flex-shrink: 0;
  border: 2px solid rgba(15, 23, 42, 0.95);
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.app-name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--tech-text);
  white-space: nowrap;
  line-height: 1.2;
}

.app-tag {
  font-family: var(--tech-font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--tech-accent);
  opacity: 0.95;
}

.right-section {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-chip {
  max-width: 160px;
  padding: 7px 10px;
  border-radius: 999px;
  color: var(--tech-text);
  background: rgba(30, 41, 59, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.14);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.logout-btn {
  color: var(--tech-muted);
  font-size: 13px;
}

.action-btn.kb-trigger {
  width: auto;
  height: 38px;
  padding: 0 14px;
  border-radius: 10px;
  color: var(--tech-muted);
  font-size: 16px;
  gap: 8px;
  border: 1px solid transparent;
  transition: color 0.2s, border-color 0.2s, background 0.2s, box-shadow 0.2s;
}

.kb-trigger-label {
  font-size: 13px;
  font-weight: 600;
}

.action-btn.kb-trigger:hover {
  color: var(--tech-accent);
  background: var(--tech-accent-soft);
  border-color: rgba(34, 211, 238, 0.28);
  box-shadow: 0 0 24px rgba(34, 211, 238, 0.12);
}

.content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
  min-height: 0;
}

.glass-sidebar {
  backdrop-filter: blur(12px);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.025), transparent 35%),
    rgba(15, 23, 42, 0.68) !important;
  border-right: 1px solid var(--tech-border);
  box-shadow: 4px 0 32px rgba(0, 0, 0, 0.2);
}

.sidebar {
  width: 292px;
  display: flex;
  flex-direction: column;
  transition: width 0.28s ease, opacity 0.2s ease;
  overflow: hidden;
  flex-shrink: 0;
}

.sidebar-collapsed {
  width: 0;
  border: none;
  opacity: 0;
}

.sidebar-content {
  flex: 1;
  padding: 18px 16px 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.sidebar-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.sidebar-label {
  font-family: var(--tech-font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--tech-muted);
  text-transform: uppercase;
}

.sidebar-fold {
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: 8px;
  color: var(--tech-muted);
}

.sidebar-fold:hover {
  color: var(--tech-accent);
  background: var(--tech-accent-soft);
}

.new-chat-btn {
  margin-bottom: 18px;
  border-radius: 12px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-weight: 600;
  letter-spacing: 0.02em;
  border: none;
  background: linear-gradient(135deg, #0891b2 0%, #6366f1 100%) !important;
  box-shadow: 0 4px 20px rgba(6, 182, 212, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.15);
  transition: transform 0.2s, box-shadow 0.2s;
}

.new-chat-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 28px rgba(99, 102, 241, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.history-title {
  font-size: 11px;
  font-family: var(--tech-font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--tech-muted);
  margin-bottom: 12px;
  padding-left: 6px;
  font-weight: 600;
}

.conversation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.conversation-item {
  display: flex;
  align-items: center;
  padding: 12px 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s, box-shadow 0.2s, transform 0.2s;
  background: rgba(30, 41, 59, 0.42);
  border: 1px solid rgba(148, 163, 184, 0.08);
  gap: 10px;
  position: relative;
  overflow: hidden;
}

.conversation-item:hover {
  background: rgba(51, 65, 85, 0.45);
  border-color: rgba(34, 211, 238, 0.15);
  transform: translateX(2px);
}

.conversation-item.active {
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.15), rgba(167, 139, 250, 0.12));
  border-color: rgba(34, 211, 238, 0.35);
  box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.12), 0 8px 24px rgba(0, 0, 0, 0.25);
}

.conversation-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 999px;
  background: linear-gradient(180deg, var(--tech-accent), var(--tech-violet));
  box-shadow: 0 0 14px rgba(34, 211, 238, 0.55);
}

.chat-icon {
  color: var(--tech-muted);
  font-size: 16px;
  flex-shrink: 0;
}

.conversation-item.active .chat-icon {
  color: var(--tech-accent);
}

.conversation-name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--tech-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conversation-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.2s ease;
  flex-shrink: 0;
}

.conversation-item:hover .conversation-actions {
  opacity: 1;
}

.conversation-actions .el-button {
  padding: 4px;
  color: var(--tech-muted);
}

.conversation-actions .el-button:hover {
  color: var(--tech-accent);
}

.main-chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
  position: relative;
  background:
    radial-gradient(circle at 50% 0%, rgba(34, 211, 238, 0.08), transparent 34%),
    rgba(7, 11, 18, 0.32);
  backdrop-filter: blur(8px);
}

.main-chat-area::before {
  content: '';
  pointer-events: none;
  position: absolute;
  inset: 18px 18px 0;
  border: 1px solid rgba(148, 163, 184, 0.08);
  border-bottom: 0;
  border-radius: 24px 24px 0 0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.018), transparent 38%);
}

.main-chat-area > * {
  position: relative;
  z-index: 1;
}

.kb-drawer-head {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-right: 8px;
}

.kb-drawer-icon-box {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.2), rgba(167, 139, 250, 0.18));
  border: 1px solid rgba(34, 211, 238, 0.28);
  color: var(--tech-accent);
  box-shadow: 0 0 28px rgba(34, 211, 238, 0.12);
}

.kb-drawer-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.kb-drawer-title {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--tech-text);
  line-height: 1.2;
}

.kb-drawer-sub {
  font-size: 12px;
  color: var(--tech-muted);
  font-family: var(--tech-font-mono);
  letter-spacing: 0.04em;
}

.tech-drawer-panel :deep(.el-drawer__header) {
  margin-bottom: 0;
  padding: 18px 20px 16px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  align-items: flex-start;
}

.tech-drawer-panel :deep(.el-drawer__body) {
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.tech-drawer-panel :deep(.el-drawer) {
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, rgba(17, 24, 39, 0.98) 0%, rgba(10, 15, 26, 0.99) 100%);
  border-left: 1px solid rgba(34, 211, 238, 0.12);
  box-shadow: -12px 0 48px rgba(0, 0, 0, 0.55);
}

.tech-drawer-panel :deep(.el-drawer__close-btn) {
  margin-top: 4px;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  color: var(--tech-muted);
}

.tech-drawer-panel :deep(.el-drawer__close-btn:hover) {
  color: var(--tech-accent);
  background: rgba(34, 211, 238, 0.1);
}

@media (max-width: 900px) {
  .top-bar-content {
    padding: 0 14px;
  }

  .sidebar {
    width: 248px;
  }

  .main-chat-area::before {
    inset: 8px 8px 0;
    border-radius: 18px 18px 0 0;
  }
}
</style>
