<template>
  <div class="kb-panel-root">
    <section class="kb-files-panel">
      <div class="section-head">
        <div class="section-head-text">
          <span class="section-badge">INDEX</span>
          <span class="section-title">已入库文件</span>
        </div>
        <el-button
          type="success"
          plain
          size="small"
          :loading="samplesLoading"
          @click="loadSamples"
        >
          导入演示语料
        </el-button>
        <el-button
          type="primary"
          plain
          size="small"
          class="refresh-btn"
          :loading="filesLoading"
          @click="refreshFiles"
        >
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
      <p v-if="stats.total_files > 0" class="stats-line">
        {{ stats.total_files }} 个文件 · {{ stats.total_chunks }} 条向量切片
      </p>
      <div class="file-scroll">
        <el-skeleton v-if="filesLoading && files.length === 0" :rows="4" animated />
        <template v-else-if="files.length === 0">
          <el-empty :image-size="72">
            <template #description>
              <span class="empty-hint">星河科技 Nova X1 售后演示库<br />点击「导入演示语料」一键载入手册/政策/FAQ，或自行上传文档</span>
            </template>
          </el-empty>
        </template>
        <ul v-else class="file-list">
          <li v-for="row in files" :key="row.id || row.filename" class="file-row">
            <el-icon class="file-doc-icon"><Document /></el-icon>
            <div class="file-meta">
              <span class="file-name" :title="row.filename">{{ row.filename }}</span>
              <span class="file-sub">
                <span class="chunk-tag">{{ row.chunks }} 切片</span>
                <span :class="['status-tag', row.status]">{{ getStatusText(row.status) }}</span>
                <span v-if="row.last_ingested" class="time-str">{{ row.last_ingested }}</span>
              </span>
            </div>
            <el-button
              type="link"
              size="small"
              class="delete-file-btn"
              :loading="deletingFileId === row.id"
              @click="deleteFile(row)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </li>
        </ul>
      </div>
    </section>

    <section class="kb-upload-panel">
      <div class="upload-head">
        <span class="section-badge upload-badge">UPLOAD</span>
        <span class="section-title">追加文档</span>
      </div>
      <el-upload
        ref="uploadRef"
        drag
        :http-request="customUpload"
        :accept="acceptTypes"
        :show-file-list="true"
        :on-success="handleSuccess"
        :on-error="handleError"
        :before-upload="beforeUpload"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            PDF, Word, CSV, XLSX, MD, TXT · 单文件 &lt; 10MB
          </div>
        </template>
      </el-upload>
      <div v-if="uploadResult" class="upload-result">
        <el-alert
          :title="uploadResult.message"
          :type="uploadResult.status === 'success' ? 'success' : 'error'"
          show-icon
          :closable="false"
        />
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Refresh, Document, Delete } from '@element-plus/icons-vue'
import axios from 'axios'
import { apiUrl, authHeaders } from '../utils/api'

const uploadRef = ref(null)
const uploadResult = ref(null)
const files = ref([])
const stats = ref({ total_files: 0, total_chunks: 0 })
const filesLoading = ref(false)
const samplesLoading = ref(false)
const deletingFileId = ref(null)

const acceptTypes = '.pdf,.doc,.docx,.csv,.xlsx,.xls,.md,.txt'

const getStatusText = (status = 'success') => {
  const map = {
    processing: '处理中',
    success: '已入库',
    failed: '失败'
  }
  return map[status] || status
}

const refreshFiles = async () => {
  filesLoading.value = true
  try {
    const { data } = await axios.get(apiUrl('/api/files'), {
      headers: authHeaders()
    })
    files.value = data.files || []
    stats.value = {
      total_files: data.total_files ?? 0,
      total_chunks: data.total_chunks ?? 0
    }
  } catch (error) {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    let msg = typeof detail === 'string' ? detail : '获取知识库列表失败'
    if (status === 404) {
      msg =
        '列表接口 404：请确认后端已更新并重启（需要 GET /api/files）；若直连后端可在 .env 设置 VITE_API_BASE=http://127.0.0.1:8000'
    }
    ElMessage.error(msg)
    files.value = []
    stats.value = { total_files: 0, total_chunks: 0 }
  } finally {
    filesLoading.value = false
  }
}

const loadSamples = async () => {
  samplesLoading.value = true
  try {
    const { data } = await axios.post(apiUrl('/api/knowledge/load-samples'), {}, {
      headers: authHeaders()
    })
    ElMessage.success(data.message || '演示语料导入完成')
    await refreshFiles()
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '导入演示语料失败')
  } finally {
    samplesLoading.value = false
  }
}

defineExpose({ refreshFiles, loadSamples })

onMounted(() => {
  refreshFiles()
})

const customUpload = async (options) => {
  const formData = new FormData()
  formData.append('file', options.file)

  try {
    const response = await axios.post(apiUrl('/api/upload'), formData, {
      headers: {
        ...authHeaders(),
        'Content-Type': 'multipart/form-data'
      }
    })

    uploadResult.value = {
      status: 'success',
      message: response.data.message
    }

    ElMessage.success('文件上传成功！')
    uploadRef.value.clearFiles()
    await refreshFiles()
  } catch (error) {
    uploadResult.value = {
      status: 'error',
      message: error.response?.data?.detail || '上传失败'
    }

    ElMessage.error('文件上传失败')
  }
}

const deleteFile = async (row) => {
  if (!row.id) {
    ElMessage.warning('缺少文件 ID，无法删除')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除「${row.filename}」及其向量索引吗？`,
      '删除知识库文件',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    deletingFileId.value = row.id
    await axios.delete(apiUrl(`/api/files/${row.id}`), {
      headers: authHeaders()
    })
    ElMessage.success('删除成功')
    await refreshFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  } finally {
    deletingFileId.value = null
  }
}

const beforeUpload = (file) => {
  const validTypes = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword',
    'text/csv',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
    'text/markdown',
    'text/plain'
  ]

  const fileExtension = file.name.split('.').pop().toLowerCase()
  const validExtensions = ['pdf', 'doc', 'docx', 'csv', 'xlsx', 'xls', 'md', 'txt']

  const isTypeValid = validTypes.includes(file.type) || validExtensions.includes(fileExtension)

  if (!isTypeValid) {
    ElMessage.error('不支持的文件类型！')
    return false
  }

  const isLt10M = file.size / 1024 / 1024 < 10
  if (!isLt10M) {
    ElMessage.error('文件大小不能超过 10MB!')
    return false
  }

  uploadResult.value = null
  return true
}

const handleSuccess = (response) => {
  console.log('上传成功:', response)
}

const handleError = (error) => {
  console.error('上传错误:', error)
}
</script>

<style scoped>
.kb-panel-root {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.kb-files-panel {
  flex: 1;
  min-height: 140px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 18px 20px 14px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-head-text {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.section-badge {
  font-family: var(--tech-font-mono);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.14em;
  padding: 4px 8px;
  border-radius: 4px;
  background: rgba(34, 211, 238, 0.12);
  color: var(--tech-accent);
  border: 1px solid rgba(34, 211, 238, 0.22);
  flex-shrink: 0;
}

.upload-badge {
  background: rgba(167, 139, 250, 0.12);
  color: var(--tech-violet);
  border-color: rgba(167, 139, 250, 0.28);
}

.section-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--tech-text);
}

.refresh-btn {
  flex-shrink: 0;
  border-radius: 8px !important;
}

.stats-line {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--tech-muted);
  font-family: var(--tech-font-mono);
}

.file-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin-top: 12px;
  padding-right: 4px;
}

.file-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(30, 41, 59, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.1);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.file-row:hover {
  border-color: rgba(34, 211, 238, 0.22);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}

.file-doc-icon {
  font-size: 20px;
  color: var(--tech-accent);
  flex-shrink: 0;
  margin-top: 2px;
}

.file-meta {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--tech-text);
  word-break: break-all;
  line-height: 1.4;
}

.file-sub {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--tech-muted);
  font-family: var(--tech-font-mono);
}

.chunk-tag {
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(34, 211, 238, 0.1);
  color: var(--tech-accent);
  border: 1px solid rgba(34, 211, 238, 0.2);
}

.status-tag {
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  color: var(--tech-muted);
  background: rgba(148, 163, 184, 0.08);
}

.status-tag.success {
  color: #34d399;
  border-color: rgba(52, 211, 153, 0.24);
  background: rgba(52, 211, 153, 0.1);
}

.status-tag.processing {
  color: #fbbf24;
  border-color: rgba(251, 191, 36, 0.24);
  background: rgba(251, 191, 36, 0.1);
}

.status-tag.failed {
  color: #f87171;
  border-color: rgba(248, 113, 113, 0.24);
  background: rgba(248, 113, 113, 0.1);
}

.delete-file-btn {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  margin-top: -3px;
  border-radius: 8px;
  color: var(--tech-muted);
}

.delete-file-btn:hover {
  color: #f87171;
  background: rgba(248, 113, 113, 0.1);
}

.time-str {
  opacity: 0.85;
}

.empty-hint {
  font-size: 12px;
  color: var(--tech-muted);
  line-height: 1.55;
}

.kb-upload-panel {
  flex-shrink: 0;
  padding: 18px 20px 28px;
}

.upload-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.el-upload {
  width: 100%;
}

:deep(.el-upload-dragger) {
  width: 100%;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 32px 20px;
  border: 1px dashed rgba(34, 211, 238, 0.35);
  border-radius: 14px;
  background: rgba(30, 41, 59, 0.35);
  transition: border-color 0.25s, box-shadow 0.25s, background 0.25s;
}

:deep(.el-upload-dragger:hover) {
  border-color: rgba(167, 139, 250, 0.55);
  background: rgba(167, 139, 250, 0.06);
  box-shadow:
    0 0 0 1px rgba(34, 211, 238, 0.1),
    0 12px 36px rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

:deep(.el-icon--upload) {
  font-size: 48px;
  color: var(--tech-muted);
  margin-bottom: 14px;
  transition: color 0.25s, transform 0.25s, filter 0.25s;
}

:deep(.el-upload-dragger:hover .el-icon--upload) {
  color: var(--tech-violet);
  transform: scale(1.06);
  filter: drop-shadow(0 0 14px rgba(167, 139, 250, 0.45));
}

:deep(.el-upload__text) {
  font-size: 14px;
  color: var(--tech-muted);
  text-align: center;
  line-height: 1.55;
}

:deep(.el-upload__text em) {
  color: var(--tech-accent);
  font-style: normal;
  font-weight: 600;
  cursor: pointer;
}

:deep(.el-upload__tip) {
  margin-top: 12px;
  font-size: 11px;
  color: var(--tech-muted);
  text-align: center;
  font-family: var(--tech-font-mono);
  opacity: 0.9;
}

.upload-result {
  margin-top: 14px;
}

:deep(.upload-result .el-alert) {
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(30, 41, 59, 0.55);
}

:deep(.el-upload-list) {
  width: 100%;
  padding: 10px 0 0;
}

:deep(.el-upload-list__item) {
  border-radius: 10px;
  margin-bottom: 8px;
  background: rgba(30, 41, 59, 0.35);
  border: 1px solid rgba(148, 163, 184, 0.08);
}

:deep(.el-upload-list__item:hover) {
  border-color: rgba(34, 211, 238, 0.2);
}

:deep(.el-upload-list__item-name) {
  color: var(--tech-text);
  font-size: 13px;
}

:deep(.el-empty__description) {
  margin-top: 12px;
}

:deep(.el-skeleton) {
  padding: 8px 0;
}
</style>
