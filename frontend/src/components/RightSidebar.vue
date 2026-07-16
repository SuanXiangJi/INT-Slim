<template>
  <div 
    class="right-sidebar" 
    :class="{ expanded: isExpanded }"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <div class="sidebar-handle" @mouseenter="handleMouseEnter"></div>
    
    <div class="sidebar-content" @mouseenter="handleContentMouseEnter" @mouseleave="handleContentMouseLeave">
 
      
      <div class="chat-list-wrapper">
        <div class="chat-list-container">
          <div class="chat-sections">
            <div 
              v-for="(section, index) in chatSections" 
              :key="index"
              class="section-item"
              :class="`role-${section.type}`"
              @click="scrollToSection(section.id)"
            >
              <div class="section-icon" @click.stop="handleFavor(section.id)">
                <svg v-if="isMessageFavored(section.id)" class="favor-icon" viewBox="0 0 1025 1024" xmlns="http://www.w3.org/2000/svg">
                  <path d="M1024 384a103.04 103.04 0 0 0-72.32-64l-215.68-58.24L590.72 49.92A101.12 101.12 0 0 0 512 0a92.8 92.8 0 0 0-78.72 51.84l-120.32 192-161.28 49.28L72.96 320a97.28 97.28 0 0 0-68.48 56.96 115.2 115.2 0 0 0 19.84 97.28l140.8 178.56-7.68 256a117.76 117.76 0 0 0 17.92 88.96 64 64 0 0 0 49.92 21.12 181.76 181.76 0 0 0 60.8-13.44l208-84.48 236.16 87.68a141.44 141.44 0 0 0 42.88 7.68c29.44 0 78.72-13.44 82.56-103.68l-12.8-230.4 152.96-205.44A106.88 106.88 0 0 0 1024 384" fill="#f6ef37"/>
                </svg>
                <svg v-else class="favor-icon" viewBox="0 0 1054 1024" xmlns="http://www.w3.org/2000/svg">
                  <path d="M498.665413 824.614245a60.112101 60.112101 0 0 1 56.739078 0l259.783056 139.076995-49.842448-295.952713a60.353031 60.353031 0 0 1 16.985584-52.854076L993.837338 404.973958l-291.495503-43.156633a60.20245 60.20245 0 0 1-45.325006-33.308609L527.034952 60.323216l-130.011994 268.1855a60.20245 60.20245 0 0 1-45.355122 33.308609l-291.495503 43.126517 211.566888 209.940609c13.913723 13.823374 20.238142 33.519423 16.985584 52.854076L238.822124 963.69124l259.813173-139.076995z m28.369539 53.185356l-259.813173 139.046878a60.142217 60.142217 0 0 1-87.698616-63.183961l49.842448-295.952713-211.536771-209.910492a60.353031 60.353031 0 0 1 33.549539-102.485711l291.525619-43.126518 129.981877-268.185499a60.142217 60.142217 0 0 1 108.298154 0l129.981877 268.185499 291.525619 43.126518a60.262682 60.262682 0 0 1 33.549539 102.455594l-211.536771 209.940609 49.842448 295.952713a60.262682 60.262682 0 0 1-87.728732 63.183961L527.034952 877.799601z" fill="#7F7F7F"/>
                </svg>
              </div>
              <div class="section-content">
                <div class="section-title">{{ section.title }}</div>
                <div class="section-info">
                  <span class="section-role">{{ section.type }}</span>
                  <span class="section-time">{{ section.time }}</span>
                </div>
              </div>
              <button 
                class="delete-btn" 
                @click.stop="handleDelete(section.id)"
                title="删除消息"
              >
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M3 6H5H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M10 11V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M14 11V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { updateMessageFavor, deleteMessage } from '@/utils/api'
import { ElMessage } from 'element-plus'

const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['scroll-to-message', 'message-deleted', 'message-favored'])

const isExpanded = ref(false)
let expandTimeout = null

// 根据消息数据生成对话记录目录
const chatSections = computed(() => {
  return props.messages.map((message, index) => {
    // 只显示前20个字符，超过则用省略号
    let previewText = message.content
    if (previewText.length > 20) {
      previewText = previewText.substring(0, 20) + '...'
    }
    
    // 格式化时间
    const time = formatMessageTime(message.created_at)
    
    return {
      id: message.id,
      type: message.role,
      title: previewText,
      time: time,
      messageIndex: index,
      isFavored: message.is_favored || false
    }
  })
})

function formatMessageTime(timestamp) {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function isMessageFavored(messageId) {
  const message = props.messages.find(msg => msg.id === messageId)
  return message ? message.is_favored : false
}

async function handleFavor(messageId) {
  try {
    const message = props.messages.find(msg => msg.id === messageId)
    if (message) {
      const newFavorStatus = !message.is_favored
      const response = await updateMessageFavor(messageId, newFavorStatus)

      // 更新本地消息状态
      message.is_favored = newFavorStatus
      
      // 更新chatSections中的状态
      const section = chatSections.value.find(s => s.id === messageId)
      if (section) {
        section.isFavored = newFavorStatus
      }
      
      ElMessage.success(newFavorStatus ? '已收藏' : '已取消收藏')
    }
  } catch (error) {
    console.error('Favor update error:', error)
    ElMessage.error(`操作失败：${error.message}`)
  }
}

async function handleDelete(messageId) {
  if (confirm('确定要删除这条消息吗？')) {
    try {
      await deleteMessage(messageId)
      
      // 触发删除事件，让父组件更新消息列表
      emit('message-deleted', messageId)
      
      ElMessage.success('消息已删除')
    } catch (error) {
      ElMessage.error(`删除失败：${error.message}`)
    }
  }
}

function handleMouseEnter() {
  if (expandTimeout) {
    clearTimeout(expandTimeout)
    expandTimeout = null
  }
  isExpanded.value = true
}

function handleMouseLeave() {
  expandTimeout = setTimeout(() => {
    isExpanded.value = false
  }, 100)
}

function handleContentMouseEnter() {
  if (expandTimeout) {
    clearTimeout(expandTimeout)
    expandTimeout = null
  }
  isExpanded.value = true
}

function handleContentMouseLeave() {
  expandTimeout = setTimeout(() => {
    isExpanded.value = false
  }, 300)
}

function scrollToSection(sectionId) {
  // 触发滚动到对应消息的事件
  emit('scroll-to-message', sectionId)
}
</script>

<style scoped>
.right-sidebar {
  position: fixed;
  top: 88px;
  right: 0;
  bottom: 150px;
  background: transparent;
  border-left: none;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  transition: width 0.3s ease;
  z-index: 100;
  width: 20px;
  overflow: hidden;
}

.right-sidebar.expanded {
  width: 280px;
}

.sidebar-handle {
  position: absolute;
  left: 0;
  top: 0;
  width: 40px;
  height: 100%;
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  box-shadow: none;
  transition: all 0.2s;
  z-index: 101;
}

.sidebar-handle:hover {
  background: transparent;
}

.sidebar-content {
  width: 280px;
  height: 100%;
  display: flex;
  flex-direction: column;
  margin-left: 12px;
}

.chat-list-wrapper {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.chat-list-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0 16px 16px 16px;
  -webkit-overflow-scrolling: touch;
}
 

.sidebar-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.section-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  position: relative;
}

.section-item:hover {
  background: var(--bg-hover);
  border-color: var(--accent-color);
  transform: translateX(-4px);
}

.section-item:hover .delete-btn {
  opacity: 1;
}

.section-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
  cursor: pointer;
  transition: all 0.2s;
  background: transparent;
}

/* user角色：收藏图标后面保持为空（无背景） */
.section-item.role-user .section-icon {
  background: transparent;
}

/* 其他角色（如assistant）：收藏图标后面加圆形背景 */
.section-item:not(.role-user) .section-icon {
  background: var(--bg-tertiary);
}

.section-icon:hover {
  transform: scale(1.1);
}

.favor-icon {
  width: 18px;
  height: 18px;
  object-fit: contain;
}



.section-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.section-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.section-role {
  font-size: 11px;
  color: var(--text-tertiary);
}

.section-time {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-left: auto;
}

.delete-btn {
  width: 24px;
  height: 24px;
  padding: 4px;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
  opacity: 0;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.section-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background: rgba(244, 67, 54, 0.1);
  color: #f44336;
}

.delete-btn svg {
  width: 16px;
  height: 16px;
}

/* 滚动条样式 */
.chat-list-container::-webkit-scrollbar {
  width: 6px;
}

.chat-list-container::-webkit-scrollbar-track {
  background: transparent;
}

.chat-list-container::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.chat-list-container::-webkit-scrollbar-thumb:hover {
  background: var(--text-tertiary);
}
</style>