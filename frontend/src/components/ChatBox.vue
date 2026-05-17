<template>
  <div class="chat-wrapper">
    <div class="chat-container" ref="chatContainer">
      <div v-if="messages.length === 0 && !loading" class="chat-empty">
        <div class="empty-visual">
          <div class="empty-orbit" />
          <div class="empty-core" />
        </div>
        <p class="empty-kicker">星河科技 · Nova X1</p>
        <h2 class="empty-title">售后知识助手</h2>
        <p class="empty-desc">请先在知识库面板「导入演示语料」或上传手册/政策文档。可尝试：红灯闪三下、进水保修、七天无理由退换。</p>
        <div class="empty-examples">
          <el-button
            v-for="q in sampleQuestions"
            :key="q"
            size="small"
            round
            class="sample-q-btn"
            @click="askSample(q)"
          >{{ q }}</el-button>
        </div>
      </div>
      <!-- 消息列表 -->
      <div
        v-for="(message, index) in messages"
        :key="index"
        :class="['message', message.role]"
      >
        <!-- 用户消息 -->
        <template v-if="message.role === 'user'">
          <div class="message-content user-content">
            <div class="message-text">{{ message.content }}</div>
          </div>
          <div class="message-avatar">
            <el-avatar :src="userAvatar" class="bubble-avatar" />
          </div>
        </template>
        
        <!-- AI 消息 -->
        <template v-else>
          <div class="message-avatar">
            <el-avatar :src="assistantAvatar" class="bubble-avatar" />
          </div>
          <div class="message-content assistant-content">
            <!-- Agent 模式思考过程 -->
            <div v-if="message.thinking_process && message.thinking_process.length > 0" class="thinking-section">
              <el-button 
                type="link" 
                size="small"
                @click="message.showThinking = !message.showThinking"
                class="toggle-thinking-btn"
              >
                <el-icon>
                  <ArrowDown v-if="!message.showThinking" />
                  <ArrowUp v-else />
                </el-icon>
                {{ message.showThinking ? '收起思考过程' : '查看思考过程 (' + message.thinking_process.length + '步)' }}
              </el-button>
              
              <el-collapse-transition>
                <div v-show="message.showThinking" class="thinking-process">
                  <div v-for="(step, stepIndex) in message.thinking_process" :key="stepIndex" 
                       :class="['thinking-step', step.status]">
                    <div class="thinking-step-content">
                      <div class="thinking-message">{{ step.message }}</div>
                      <div v-if="step.details" class="thinking-details">
                        <ul v-if="Array.isArray(step.details)">
                          <li v-for="(detail, dIndex) in step.details" :key="dIndex">{{ detail }}</li>
                        </ul>
                        <pre v-else>{{ JSON.stringify(step.details, null, 2) }}</pre>
                      </div>
                    </div>
                  </div>
                  
                  <!-- 工具调用日志 -->
                  <div v-if="message.tools_called && message.tools_called.length > 0" class="tools-section">
                    <div class="tools-title"><span class="tools-badge">TOOLS</span> 工具调用记录</div>
                    <div v-for="(tool, tIndex) in message.tools_called" :key="tIndex" class="tool-item">
                      <div class="tool-header">
                        <el-tag size="small" type="primary">{{ tool.tool }}</el-tag>
                        <span class="tool-action">{{ tool.action }}</span>
                      </div>
                      <div class="tool-details">
                        <div class="tool-row">
                          <span class="label">输入:</span>
                          <span class="value">{{ tool.input }}</span>
                        </div>
                        <div class="tool-row">
                          <span class="label">输出:</span>
                          <span class="value">{{ tool.output }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </el-collapse-transition>
            </div>
            
            <div class="message-text">{{ message.content }}</div>
            
            <!-- 显示检索到的上下文 -->
            <div v-if="getUsedContexts(message).length > 0" class="contexts-section">
              <el-button 
                type="link" 
                size="small"
                @click="message.showContexts = !message.showContexts"
                class="toggle-contexts-btn"
              >
                <el-icon>
                  <ArrowDown v-if="!message.showContexts" />
                  <ArrowUp v-else />
                </el-icon>
                {{ message.showContexts ? '收起参考资料' : '查看参考资料 (' + getUsedContexts(message).length + '条)' }}
              </el-button>
              
              <el-collapse-transition>
                <div v-show="message.showContexts" class="contexts-list">
                  <div v-for="(context, ctxIndex) in getUsedContexts(message)" :key="ctxIndex" class="context-item">
                    <div class="context-header">
                      <el-tag size="small" type="info">资料 {{ ctxIndex + 1 }}</el-tag>
                    </div>
                    <div class="context-content">{{ context }}</div>
                  </div>
                </div>
              </el-collapse-transition>
            </div>
            
            <!-- 操作按钮 -->
            <div class="message-actions">
              <el-button 
                class="action-btn copy-btn"
                @click="copyMessage(message.content)"
                :title="'复制'"
              >
                <el-icon><CopyDocument /></el-icon>
              </el-button>
              <el-button 
                class="action-btn regenerate-btn"
                @click="regenerateResponse(index)"
                :disabled="loading"
                :title="'重新生成'"
              >
                <el-icon><Refresh /></el-icon>
              </el-button>
              <el-button 
                class="action-btn evaluate-btn"
                @click="evaluateMessage(index)"
                :loading="message.evaluating"
                :title="'评估质量'"
              >
                <el-icon><DataAnalysis /></el-icon>
              </el-button>
              <el-button 
                type="link" 
                size="small"
                :class="{ 'action-active': message.feedback === 'like' }"
                @click="toggleFeedback(index, 'like')"
                :title="'点赞'"
              >
                <el-icon><CircleCheck /></el-icon>
              </el-button>
              <el-button 
                type="link" 
                size="small"
                :class="{ 'action-active': message.feedback === 'dislike' }"
                @click="toggleFeedback(index, 'dislike')"
                :title="'点踩'"
              >
                <el-icon><CircleClose /></el-icon>
              </el-button>
            </div>
            <div
              v-if="message.thinkingTimeMs != null"
              class="thinking-time-footer"
            >
              思考用时 {{ formatThinkingDuration(message.thinkingTimeMs) }}
            </div>
          </div>
        </template>
      </div>
      
      <!-- 加载中消息 -->
      <div v-if="loading" class="message assistant">
        <div class="message-avatar">
          <el-avatar :src="assistantAvatar" class="bubble-avatar" />
        </div>
        <div class="message-content assistant-content assistant-loading">
          <div v-if="streamThinking.length" class="stream-thinking">
            <div v-for="(step, si) in streamThinking.slice(-3)" :key="si" class="stream-thinking-step">{{ step.message }}</div>
          </div>
          <div v-if="streamingContent" class="message-text stream-preview">{{ streamingContent }}</div>
          <template v-else>
            <div class="thinking-animation">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
            <div class="thinking-text">{{ useAgentMode ? 'Agent 多路检索与生成中…' : '正在检索并生成…' }}</div>
          </template>
          <div class="thinking-time-active">
            思考中 · {{ formatThinkingDuration(thinkingElapsedMs) }}
          </div>
        </div>
      </div>
    </div>
    
    <!-- 输入区域（贴底栏，与消息区同一列布局） -->
    <div class="input-container">
      <div class="composer-inner">
      <!-- Agent 模式切换开关 -->
      <div class="mode-switch">
        <span class="mode-label">推理模式</span>
        <el-switch
          v-model="useAgentMode"
          inline-prompt
          active-text="Agent"
          inactive-text="快速"
          size="default"
          class="tech-switch"
        />
        <el-tooltip placement="top">
          <template #content>
            Agent：并行多路检索（可关评估加速）<br/>
            快速：检索后流式回答
          </template>
          <el-icon class="help-icon"><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
      
      <el-input
        v-model="inputMessage"
        class="composer-input"
        placeholder="输入问题，Enter 发送..."
        @keyup.enter="sendMessage"
        :disabled="loading"
        size="large"
      >
        <template #append>
          <el-button type="primary" class="send-btn" @click="sendMessage" :loading="loading">
            <el-icon><Promotion /></el-icon>
          </el-button>
        </template>
      </el-input>
      </div>
    </div>
    
    <!-- 评估对话框 -->
    <el-dialog
      v-model="evaluationDialogVisible"
      title="回答质量评估"
      width="560px"
      class="tech-dialog"
      :close-on-click-modal="false"
      align-center
    >
      <div v-if="evaluationResult" class="evaluation-content">
        <div class="evaluation-score">
          <div class="score-item" v-for="(score, key) in evaluationResult.scores" :key="key">
            <div class="score-label">{{ getMetricName(key) }}</div>
            <div class="score-value">
              <el-progress
                :percentage="score * 100"
                :color="getScoreColor(score)"
                :format="formatScore"
              />
            </div>
          </div>
        </div>
        <div class="evaluation-interpretation">
          <h4>评估解读</h4>
          <p>{{ evaluationResult.interpretation }}</p>
        </div>
      </div>
      <template #footer>
        <el-button @click="evaluationDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox, ElDialog } from 'element-plus'
import { User, ChatDotRound, Promotion, Delete, CopyDocument, Refresh, CircleCheck, CircleClose, DataAnalysis, ArrowUp, ArrowDown, QuestionFilled } from '@element-plus/icons-vue'
import { conversationStore } from '../utils/conversationStore'
import { apiRequest, authFetch } from '../utils/api'

// 头像 URL
const assistantAvatar = 'https://ts1.tc.mm.bing.net/th/id/OIP-C.9sP0jV5JcinOj8ZOgxXGHAHaHa?rs=1&pid=ImgDetMain&o=7&rm=3'
const userAvatar = 'https://ts1.tc.mm.bing.net/th/id/OIP-C.i7QRzxQrXkZ5uAXLbZ1XTwHaHa?rs=1&pid=ImgDetMain&o=7&rm=3'

const props = defineProps({
  currentConversationId: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['conversation-change'])

const messages = ref([])
const inputMessage = ref('')
const loading = ref(false)
const streamingContent = ref('')
const streamThinking = ref([])
const sampleQuestions = [
  '红灯闪三下是什么意思？',
  '耳机进水了还能保修吗？',
  '七天无理由退换需要什么条件？'
]
const chatContainer = ref(null)
const lastUserMessage = ref('')
const useAgentMode = ref(false)  // Agent 模式开关

const thinkingElapsedMs = ref(0)
let thinkingTimerId = null
let thinkingStartedAt = 0

const formatThinkingDuration = (ms) => {
  const n = Number(ms) || 0
  if (n < 1000) return `${(n / 1000).toFixed(2)}s`
  const sec = n / 1000
  if (sec < 60) return `${sec.toFixed(2)}s`
  const m = Math.floor(sec / 60)
  const s = (sec % 60).toFixed(1)
  return `${m}分${s}秒`
}

const startThinkingTimer = () => {
  clearThinkingTimer()
  thinkingStartedAt = performance.now()
  thinkingElapsedMs.value = 0
  thinkingTimerId = setInterval(() => {
    thinkingElapsedMs.value = Math.floor(performance.now() - thinkingStartedAt)
  }, 50)
}

const captureThinkingTimeMs = () => {
  if (thinkingTimerId) {
    clearInterval(thinkingTimerId)
    thinkingTimerId = null
  }
  if (thinkingStartedAt) {
    thinkingElapsedMs.value = Math.floor(performance.now() - thinkingStartedAt)
  }
  return thinkingElapsedMs.value
}

const clearThinkingTimer = () => {
  if (thinkingTimerId) {
    clearInterval(thinkingTimerId)
    thinkingTimerId = null
  }
  thinkingStartedAt = 0
  thinkingElapsedMs.value = 0
}

const buildAssistantMessage = (streamState, thinkingTimeMs) => ({
  role: 'assistant',
  content: streamState.fullContent,
  timestamp: new Date().toISOString(),
  metadata: {
    contexts: streamState.contexts,
    ...streamState.metadata
  },
  thinking_process: streamState.thinkingProcess,
  tools_called: streamState.toolsCalled,
  thinkingTimeMs,
  showThinking: false,
  showContexts: false
})

onUnmounted(() => {
  clearThinkingTimer()
})

const hydrateMessages = async () => {
  const id = props.currentConversationId
  if (!id) {
    messages.value = []
    return
  }
  const conv = await conversationStore.getConversation(id)
  if (props.currentConversationId !== id) return
  const raw = conv?.messages
  messages.value = Array.isArray(raw) && raw.length
    ? JSON.parse(JSON.stringify(raw))
    : []
  nextTick(() => scrollToBottom())
}

watch(
  () => props.currentConversationId,
  () => hydrateMessages(),
  { immediate: true }
)

// 评估相关
const evaluationDialogVisible = ref(false)
const evaluationResult = ref(null)
const currentEvaluatedMessage = ref(null)

const scrollToBottom = async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

const getTextFeatures = (text = '') => {
  const normalized = text.toLowerCase()
  const features = new Set()
  const words = normalized.match(/[a-z0-9_\u4e00-\u9fa5]{2,}/g) || []

  words.forEach((word) => {
    if (/^[\u4e00-\u9fa5]+$/.test(word)) {
      for (let i = 0; i < word.length - 1; i += 1) {
        features.add(word.slice(i, i + 2))
      }
      return
    }
    features.add(word)
  })

  return features
}

const getUsedContexts = (message) => {
  const contexts = message.metadata?.contexts || []
  const answerFeatures = getTextFeatures(message.content)

  if (!contexts.length || answerFeatures.size === 0) return []

  return contexts.filter((context) => {
    const contextFeatures = getTextFeatures(context)
    if (contextFeatures.size === 0) return false

    let matched = 0
    contextFeatures.forEach((feature) => {
      if (answerFeatures.has(feature)) matched += 1
    })

    const overlapRatio = matched / Math.min(contextFeatures.size, answerFeatures.size)
    return matched >= 6 || overlapRatio >= 0.08
  })
}

// 评估消息质量
const evaluateMessage = async (index) => {
  const message = messages.value[index]
  message.evaluating = true
  currentEvaluatedMessage.value = message
  
  try {
    const contexts = message.metadata?.contexts || []
    
    if (contexts.length === 0) {
      ElMessage.warning('未找到检索的上下文，无法评估')
      message.evaluating = false
      return
    }
    
    const response = await apiRequest('/api/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
      question: lastUserMessage.value || '未知问题',
      answer: message.content,
      contexts: contexts
      })
    })
    
    evaluationResult.value = response
    evaluationDialogVisible.value = true
    ElMessage.success('评估完成')
  } catch (error) {
    console.error('评估失败:', error)
    ElMessage.error('评估失败：' + (error.response?.data?.detail || error.message))
  } finally {
    message.evaluating = false
  }
}

// 获取指标名称
const getMetricName = (key) => {
  const names = {
    'faithfulness': '忠实度',
    'answer_relevancy': '答案相关性',
    'overall_score': '综合评分'
  }
  return names[key] || key
}

// 获取分数颜色
const getScoreColor = (score) => {
  if (score >= 0.8) return '#67C23A'
  if (score >= 0.6) return '#E6A23C'
  return '#F56C6C'
}

// 格式化分数显示
const formatScore = (percentage) => {
  return (percentage / 100).toFixed(2)
}

const applySsePayload = (parsed, streamState) => {
  if (parsed.content_replace != null) {
    streamState.fullContent = parsed.content_replace
    streamingContent.value = streamState.fullContent
  } else if (parsed.content) {
    streamState.fullContent += parsed.content
    streamingContent.value = streamState.fullContent
  }
  if (parsed.contexts) {
    streamState.contexts = parsed.contexts
  }
  if (parsed.thinking_process) {
    streamState.thinkingProcess = parsed.thinking_process
    streamThinking.value = parsed.thinking_process
  }
  if (parsed.tools_called) {
    streamState.toolsCalled = parsed.tools_called
  }
  if (parsed.metadata) {
    streamState.metadata = parsed.metadata
  }
  if (parsed.evaluation) {
    streamState.metadata = { ...streamState.metadata, evaluation: parsed.evaluation }
  }
  if (parsed.error) {
    throw new Error(parsed.error)
  }
}

const askSample = (q) => {
  inputMessage.value = q
  sendMessage()
}

const sendMessage = async () => {
  if (!inputMessage.value.trim()) return

  const userMessage = inputMessage.value.trim()
  lastUserMessage.value = userMessage
  
  messages.value.push({ 
    role: 'user', 
    content: userMessage,
    timestamp: new Date().toISOString()
  })
  emit('conversation-change', {
    conversationId: props.currentConversationId,
    messages: messages.value
  })
  inputMessage.value = ''
  loading.value = true
  streamingContent.value = ''
  streamThinking.value = []
  startThinkingTimer()
  await scrollToBottom()

  try {
    // 构建对话历史（最近 20 轮）
    const conversationHistory = messages.value
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .slice(-20)
      .map(m => ({
        role: m.role,
        content: m.content
      }))

    const response = await authFetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: userMessage,
        session_id: props.currentConversationId || 'default',
        use_agent: useAgentMode.value,
        history: conversationHistory
      })
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || '请求失败')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    const streamState = {
      fullContent: '',
      contexts: [],
      thinkingProcess: [],
      toolsCalled: [],
      metadata: {}
    }
    let isDone = false

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      const lines = chunk.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') {
            isDone = true
            const thinkingTimeMs = captureThinkingTimeMs()
            messages.value.push(buildAssistantMessage(streamState, thinkingTimeMs))
            emit('conversation-change', {
              conversationId: props.currentConversationId,
              messages: messages.value
            })
          } else {
            try {
              const parsed = JSON.parse(data)
              applySsePayload(parsed, streamState)
            } catch (e) {
              if (e.message && !String(e.message).includes('JSON')) {
                throw e
              }
              console.error('解析数据失败:', e)
            }
          }
        }
      }
    }
    
    if (!isDone && streamState.fullContent) {
      const thinkingTimeMs = captureThinkingTimeMs()
      messages.value.push(buildAssistantMessage(streamState, thinkingTimeMs))
      emit('conversation-change', {
        conversationId: props.currentConversationId,
        messages: messages.value
      })
    }
  } catch (error) {
    ElMessage.error('发送消息失败：' + error.message)
    messages.value.push({
      role: 'assistant',
      content: '抱歉，处理您的请求时出现错误。',
      timestamp: new Date().toISOString()
    })
    emit('conversation-change', {
      conversationId: props.currentConversationId,
      messages: messages.value
    })
  } finally {
    loading.value = false
    streamingContent.value = ''
    streamThinking.value = []
    clearThinkingTimer()
    await scrollToBottom()
  }
}

// 重新生成回复
const regenerateResponse = async (index) => {
  if (loading.value) return
  
  const message = messages.value[index]
  if (!message || message.role !== 'assistant') return
  
  // 获取上一个用户消息
  let userMessageIndex = -1
  for (let i = index - 1; i >= 0; i--) {
    if (messages.value[i].role === 'user') {
      userMessageIndex = i
      break
    }
  }
  
  if (userMessageIndex === -1) {
    ElMessage.warning('未找到对应的问题')
    return
  }
  
  const userMessage = messages.value[userMessageIndex].content
  lastUserMessage.value = userMessage
  
  // 移除当前的 assistant 消息
  messages.value.splice(index, 1)
  emit('conversation-change', {
    conversationId: props.currentConversationId,
    messages: messages.value
  })

  loading.value = true
  streamingContent.value = ''
  streamThinking.value = []
  startThinkingTimer()
  await scrollToBottom()

  try {
    const conversationHistory = messages.value
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .slice(-20)
      .map(m => ({
        role: m.role,
        content: m.content
      }))

    const response = await authFetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: userMessage,
        session_id: props.currentConversationId || 'default',
        use_agent: useAgentMode.value,
        history: conversationHistory
      })
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || '请求失败')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    const streamState = {
      fullContent: '',
      contexts: [],
      thinkingProcess: [],
      toolsCalled: [],
      metadata: {}
    }
    let isDone = false

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      const lines = chunk.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') {
            isDone = true
            const thinkingTimeMs = captureThinkingTimeMs()
            messages.value.push(buildAssistantMessage(streamState, thinkingTimeMs))
            emit('conversation-change', {
              conversationId: props.currentConversationId,
              messages: messages.value
            })
          } else {
            try {
              const parsed = JSON.parse(data)
              applySsePayload(parsed, streamState)
            } catch (e) {
              if (e.message && !String(e.message).includes('JSON')) {
                throw e
              }
              console.error('解析数据失败:', e)
            }
          }
        }
      }
    }
  } catch (error) {
    ElMessage.error('重新生成失败：' + error.message)
    emit('conversation-change', {
      conversationId: props.currentConversationId,
      messages: messages.value
    })
  } finally {
    loading.value = false
    streamingContent.value = ''
    streamThinking.value = []
    clearThinkingTimer()
    await scrollToBottom()
  }
}

// 复制消息
const copyMessage = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('复制成功')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

// 切换反馈
const toggleFeedback = (messageIndex, type) => {
  const message = messages.value[messageIndex]
  if (message.feedback === type) {
    message.feedback = null
  } else {
    message.feedback = type
  }
  emit('conversation-change', {
    conversationId: props.currentConversationId,
    messages: messages.value
  })
}
</script>

<style scoped>
.chat-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  position: relative;
}

.chat-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  width: min(100%, 1060px);
  margin: 0 auto;
  padding: 34px 34px 22px;
  scroll-behavior: smooth;
}

/* 空状态 */
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  min-height: min(420px, 52vh);
  padding: 32px 20px;
  margin-bottom: 8px;
}

.empty-visual {
  position: relative;
  width: 120px;
  height: 120px;
  margin-bottom: 28px;
}

.empty-orbit {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1px dashed rgba(34, 211, 238, 0.35);
  animation: orbit-spin 14s linear infinite;
}

.empty-orbit::after {
  content: '';
  position: absolute;
  top: -4px;
  left: 50%;
  width: 8px;
  height: 8px;
  margin-left: -4px;
  border-radius: 50%;
  background: var(--tech-accent);
  box-shadow: 0 0 12px rgba(34, 211, 238, 0.8);
}

.empty-core {
  position: absolute;
  inset: 28px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, rgba(34, 211, 238, 0.35), rgba(167, 139, 250, 0.15) 55%, transparent 70%);
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow:
    inset 0 0 40px rgba(34, 211, 238, 0.08),
    0 0 48px rgba(167, 139, 250, 0.12);
}

@keyframes orbit-spin {
  to {
    transform: rotate(360deg);
  }
}

.empty-kicker {
  margin: 0 0 10px;
  font-family: var(--tech-font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.28em;
  color: var(--tech-accent);
}

.empty-title {
  margin: 0 0 12px;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--tech-text);
}

.empty-desc {
  margin: 0;
  max-width: 400px;
  font-size: 14px;
  line-height: 1.65;
  color: var(--tech-muted);
}

.message {
  display: flex;
  margin-bottom: 26px;
  align-items: flex-start;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
  margin: 0 14px;
}

:deep(.bubble-avatar) {
  border: 2px solid rgba(148, 163, 184, 0.25);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
}

.message.user :deep(.bubble-avatar) {
  border-color: rgba(34, 211, 238, 0.45);
  box-shadow: 0 0 20px rgba(34, 211, 238, 0.15);
}

.message-content {
  max-width: min(78%, 820px);
  padding: 17px 20px;
  border-radius: 18px;
  position: relative;
}

.user-content {
  background: linear-gradient(135deg, #0e7490 0%, #4f46e5 100%);
  color: #f8fafc;
  max-width: min(62%, 680px);
  border-top-right-radius: 6px;
  box-shadow:
    0 8px 28px rgba(14, 116, 144, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.assistant-content {
  min-width: min(560px, 100%);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent 42%),
    rgba(30, 41, 59, 0.76);
  backdrop-filter: blur(14px);
  color: var(--tech-text);
  border-top-left-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow:
    0 18px 46px rgba(0, 0, 0, 0.38),
    inset 0 1px 0 rgba(255, 255, 255, 0.07);
}

.message-text {
  line-height: 1.78;
  word-wrap: break-word;
  white-space: pre-wrap;
  font-size: 14.5px;
  letter-spacing: 0.01em;
}

.thinking-section {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.2);
}

.toggle-thinking-btn,
.toggle-contexts-btn {
  font-size: 12px;
  color: var(--tech-accent) !important;
  padding: 4px 8px;
  margin-bottom: 8px;
}

.thinking-process {
  background: rgba(15, 23, 42, 0.65);
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
  border: 1px solid rgba(34, 211, 238, 0.12);
}

.thinking-step {
  padding: 10px 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  border-left: 3px solid;
  background: rgba(51, 65, 85, 0.45);
}

.thinking-step:last-child {
  margin-bottom: 0;
}

.thinking-step.running {
  border-left-color: var(--tech-accent);
}

.thinking-step.completed,
.thinking-step.success {
  border-left-color: #34d399;
}

.thinking-step.warning {
  border-left-color: #fbbf24;
}

.thinking-step.error {
  border-left-color: #f87171;
}

.thinking-message {
  font-size: 13px;
  color: var(--tech-text);
  font-weight: 500;
  margin-bottom: 4px;
}

.thinking-details {
  margin-top: 6px;
  padding: 8px 10px;
  background: rgba(15, 23, 42, 0.55);
  border-radius: 6px;
  font-size: 12px;
  color: var(--tech-muted);
  font-family: var(--tech-font-mono);
}

.thinking-details ul {
  margin: 0;
  padding-left: 18px;
}

.thinking-details li {
  margin-bottom: 3px;
}

.thinking-details pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--tech-font-mono);
  font-size: 11px;
}

.tools-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed rgba(148, 163, 184, 0.2);
}

.tools-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--tech-muted);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tools-badge {
  font-family: var(--tech-font-mono);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.12em;
  padding: 3px 8px;
  border-radius: 4px;
  background: rgba(34, 211, 238, 0.15);
  color: var(--tech-accent);
  border: 1px solid rgba(34, 211, 238, 0.25);
}

.tool-item {
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
}

.tool-item:last-child {
  margin-bottom: 0;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.tool-action {
  font-size: 12px;
  color: var(--tech-muted);
  font-weight: 500;
}

.tool-details {
  font-size: 12px;
  color: var(--tech-muted);
}

.tool-row {
  display: flex;
  gap: 6px;
  margin-bottom: 3px;
}

.tool-row:last-child {
  margin-bottom: 0;
}

.tool-row .label {
  font-weight: 600;
  color: var(--tech-accent);
  min-width: 36px;
}

.tool-row .value {
  color: var(--tech-text);
  flex: 1;
  word-break: break-word;
}

.contexts-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed rgba(148, 163, 184, 0.2);
}

.contexts-list {
  background: rgba(15, 23, 42, 0.5);
  border-radius: 10px;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.context-item {
  margin-bottom: 8px;
  padding: 10px;
  background: rgba(30, 41, 59, 0.55);
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.context-item:last-child {
  margin-bottom: 0;
}

.context-header {
  margin-bottom: 6px;
}

.context-content {
  font-size: 12px;
  color: var(--tech-muted);
  line-height: 1.55;
  max-height: 150px;
  overflow-y: auto;
}

.message-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  opacity: 0.78;
  transition: opacity 0.2s;
}

.assistant-content:hover .message-actions {
  opacity: 1;
}

.action-btn {
  padding: 7px 10px;
  font-size: 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid rgba(148, 163, 184, 0.15);
  color: var(--tech-muted);
}

.action-btn:hover {
  color: var(--tech-accent);
  border-color: rgba(34, 211, 238, 0.35);
}

.action-active {
  color: var(--tech-accent) !important;
}

.thinking-animation {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 8px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--tech-accent);
  box-shadow: 0 0 10px rgba(34, 211, 238, 0.6);
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) {
  animation-delay: -0.32s;
}

.dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.thinking-text {
  font-size: 13px;
  color: var(--tech-muted);
  font-style: italic;
}

.empty-examples {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 16px;
  max-width: 520px;
}

.sample-q-btn {
  border-color: rgba(56, 189, 248, 0.35) !important;
  color: #7dd3fc !important;
}

.stream-thinking {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.15);
}

.stream-thinking-step {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
}

.stream-preview {
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.assistant-loading {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.thinking-time-active {
  align-self: flex-start;
  margin-top: 2px;
  font-family: var(--tech-font-mono);
  font-size: 11px;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.thinking-time-footer {
  align-self: flex-start;
  margin-top: 8px;
  font-family: var(--tech-font-mono);
  font-size: 11px;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.input-container {
  flex-shrink: 0;
  padding: 10px 24px 24px;
  background:
    linear-gradient(180deg, rgba(7, 11, 18, 0), rgba(7, 11, 18, 0.92) 32%),
    rgba(10, 15, 26, 0.78);
  backdrop-filter: blur(20px);
  border-top: 1px solid rgba(148, 163, 184, 0.08);
  box-shadow: 0 -18px 50px rgba(0, 0, 0, 0.42);
}

.composer-inner {
  position: relative;
  max-width: 960px;
  margin: 0 auto;
  width: 100%;
  padding: 14px;
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0.015)),
    rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow:
    0 18px 48px rgba(0, 0, 0, 0.36),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.mode-switch {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 0 4px;
}

.mode-label {
  font-family: var(--tech-font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--tech-muted);
}

.help-icon {
  color: var(--tech-muted);
  cursor: pointer;
  transition: color 0.2s;
}

.help-icon:hover {
  color: var(--tech-accent);
}

:deep(.tech-switch.el-switch) {
  --el-switch-on-color: #0891b2;
  --el-switch-off-color: #475569;
}

:deep(.tech-switch .el-switch__core) {
  border: 1px solid rgba(148, 163, 184, 0.25);
}

:deep(.composer-input .el-input__wrapper) {
  min-height: 48px;
  background: rgba(2, 6, 23, 0.72);
  border-radius: 14px;
  box-shadow:
    0 0 0 1px rgba(148, 163, 184, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
  transition: box-shadow 0.2s;
}

:deep(.composer-input .el-input__wrapper:hover) {
  box-shadow:
    0 0 0 1px rgba(34, 211, 238, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

:deep(.composer-input .el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1px rgba(34, 211, 238, 0.45),
    0 0 24px rgba(34, 211, 238, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

:deep(.composer-input .el-input__inner) {
  color: var(--tech-text);
  font-size: 14px;
}

:deep(.composer-input .el-input__inner::placeholder) {
  color: var(--tech-muted);
}

:deep(.composer-input .el-input-group__append) {
  background: transparent;
  border: none;
  padding-left: 10px;
}

:deep(.composer-input .el-input-group__append .el-button) {
  min-width: 58px;
  height: 42px;
  border-radius: 12px;
  padding: 10px 18px;
  border: none;
  background: linear-gradient(135deg, #0891b2 0%, #6366f1 100%);
  box-shadow:
    0 8px 24px rgba(6, 182, 212, 0.32),
    inset 0 1px 0 rgba(255, 255, 255, 0.16);
}

:deep(.composer-input .el-input-group__append .el-button:hover) {
  filter: brightness(1.08);
}

@media (max-width: 900px) {
  .chat-container {
    padding: 24px 16px 16px;
  }

  .message-avatar {
    margin: 0 8px;
  }

  .message-content,
  .assistant-content,
  .user-content {
    min-width: 0;
    max-width: calc(100% - 58px);
  }

  .input-container {
    padding: 8px 12px 14px;
  }

  .composer-inner {
    padding: 10px;
    border-radius: 16px;
  }
}
</style>
