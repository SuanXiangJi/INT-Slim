<template>
  <div class="sidebar" :class="{ collapsed: isCollapsed }">
    <div class="sidebar-header">
      <div class="logo">
        <img src="/Xbots.png" alt="XBots" />
      </div>
      <button class="toggle-sidebar-btn" @click="handleToggle">
        <svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
          <path d="M896 853.333333H128v-85.333333h768v85.333333zM341.76 226.901333L205.994667 362.666667l135.765333 135.765333-60.330667 60.330667L85.333333 362.666667l196.096-196.096L341.76 226.901333zM896 554.666667h-384v-85.333334h384v85.333334z m0-298.666667h-384V170.666667h384v85.333333z"/>
        </svg>
      </button>
    </div>

    <div class="sidebar-content">
      <button class="new-chat-btn" @click="handleNewChat">
        <svg class="new-chat-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
          <path d="M38.469722 1023.999744a38.394212 38.394212 0 0 1-23.906796-68.495274 37.779905 37.779905 0 0 1 2.687595-3.148326l130.540321-134.840472c14.692185-15.357685 26.492006-29.102813 50.142841-3.890614a41.312172 41.312172 0 0 1 5.119228 57.232972l-73.640099 76.276501h395.434788a38.394212 38.394212 0 0 1 0 76.788425z"/>
          <path d="M511.998337 1023.846167a512.613923 512.613923 0 0 1-247.668264-63.836776l247.668264 48.095149v-61.046797a435.134403 435.134403 0 1 0-314.499789-134.482127L148.507534 872.368202a511.922828 511.922828 0 0 1 363.465207 151.529157z"/>
          <path d="M281.633065 486.37839m38.394212 0l358.345979 0q38.394212 0 38.394213 38.394213l0 0q0 38.394212-38.394213 38.394212l-358.345979 0q-38.394212 0-38.394212-38.394212l0 0q0-38.394212 38.394212-38.394213Z"/>
          <path d="M537.594479 307.205401m0 38.394212l0 358.345979q0 38.394212-38.394212 38.394212l0 0q-38.394212 0-38.394212-38.394212l0-358.345979q0-38.394212 38.394212-38.394212l0 0q38.394212 0 38.394212 38.394212Z"/>
        </svg>
        新建会话
      </button>

      <div class="history-section">
        <h3 class="history-title">历史对话</h3>
        <div class="history-list">
          <!-- 今天 -->
          <div v-if="groupedConversations.today.length" class="history-group">
            <div class="history-group-title">今天</div>
            <div
              v-for="chat in groupedConversations.today"
              :key="chat.id"
              :class="['history-item', { active: currentConversationId === chat.id }]"
            >
              <div class="history-item-content" @click="handleSelectChat(chat.id)">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span class="chat-title">{{ chat.title }}</span>
                <span v-if="activeConversations.has(chat.id)" class="streaming-indicator" title="AI 正在回复..."></span>
              </div>
              <el-popover
                :visible="pendingDeleteId === chat.id"
                trigger="manual"
                placement="top-end"
                :width="200"
                popper-class="minimal-delete-popover"
                @update:visible="(v) => { if (!v) pendingDeleteId = null }"
              >
                <template #reference>
                  <button
                    class="delete-btn"
                    @click.stop="pendingDeleteId = chat.id"
                    title="删除对话"
                    aria-label="删除对话"
                  >
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M3 6H5H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M10 11V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M14 11V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </button>
                </template>
                <div class="delete-popover-content">
                  <div class="delete-popover-title">确定删除「{{ chat.title || '未命名对话' }}」吗？</div>
                  <div class="delete-popover-actions">
                    <button class="delete-popover-btn cancel" @click.stop="pendingDeleteId = null">取消</button>
                    <button class="delete-popover-btn confirm" @click.stop="handleDeleteChat(chat.id)">删除</button>
                  </div>
                </div>
              </el-popover>
            </div>
          </div>

          <!-- 昨天 -->
          <div v-if="groupedConversations.yesterday.length" class="history-group">
            <div class="history-group-title">昨天</div>
            <div
              v-for="chat in groupedConversations.yesterday"
              :key="chat.id"
              :class="['history-item', { active: currentConversationId === chat.id }]"
            >
              <div class="history-item-content" @click="handleSelectChat(chat.id)">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span class="chat-title">{{ chat.title }}</span>
                <span v-if="activeConversations.has(chat.id)" class="streaming-indicator" title="AI 正在回复..."></span>
              </div>
              <el-popover
                :visible="pendingDeleteId === chat.id"
                trigger="manual"
                placement="top-end"
                :width="200"
                popper-class="minimal-delete-popover"
                @update:visible="(v) => { if (!v) pendingDeleteId = null }"
              >
                <template #reference>
                  <button
                    class="delete-btn"
                    @click.stop="pendingDeleteId = chat.id"
                    title="删除对话"
                    aria-label="删除对话"
                  >
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M3 6H5H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M10 11V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M14 11V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </button>
                </template>
                <div class="delete-popover-content">
                  <div class="delete-popover-title">确定删除「{{ chat.title || '未命名对话' }}」吗？</div>
                  <div class="delete-popover-actions">
                    <button class="delete-popover-btn cancel" @click.stop="pendingDeleteId = null">取消</button>
                    <button class="delete-popover-btn confirm" @click.stop="handleDeleteChat(chat.id)">删除</button>
                  </div>
                </div>
              </el-popover>
            </div>
          </div>

          <!-- 最近7天 -->
          <div v-if="groupedConversations.last7Days.length" class="history-group">
            <div class="history-group-title">最近7天</div>
            <div
              v-for="chat in groupedConversations.last7Days"
              :key="chat.id"
              :class="['history-item', { active: currentConversationId === chat.id }]"
            >
              <div class="history-item-content" @click="handleSelectChat(chat.id)">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span class="chat-title">{{ chat.title }}</span>
                <span v-if="activeConversations.has(chat.id)" class="streaming-indicator" title="AI 正在回复..."></span>
              </div>
              <el-popover
                :visible="pendingDeleteId === chat.id"
                trigger="manual"
                placement="top-end"
                :width="200"
                popper-class="minimal-delete-popover"
                @update:visible="(v) => { if (!v) pendingDeleteId = null }"
              >
                <template #reference>
                  <button
                    class="delete-btn"
                    @click.stop="pendingDeleteId = chat.id"
                    title="删除对话"
                    aria-label="删除对话"
                  >
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M3 6H5H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M10 11V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M14 11V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </button>
                </template>
                <div class="delete-popover-content">
                  <div class="delete-popover-title">确定删除「{{ chat.title || '未命名对话' }}」吗？</div>
                  <div class="delete-popover-actions">
                    <button class="delete-popover-btn cancel" @click.stop="pendingDeleteId = null">取消</button>
                    <button class="delete-popover-btn confirm" @click.stop="handleDeleteChat(chat.id)">删除</button>
                  </div>
                </div>
              </el-popover>
            </div>
          </div>

          <!-- 更早 -->
          <div v-if="groupedConversations.older.length" class="history-group">
            <div class="history-group-title">更早</div>
            <div
              v-for="chat in groupedConversations.older"
              :key="chat.id"
              :class="['history-item', { active: currentConversationId === chat.id }]"
            >
              <div class="history-item-content" @click="handleSelectChat(chat.id)">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span class="chat-title">{{ chat.title }}</span>
                <span v-if="activeConversations.has(chat.id)" class="streaming-indicator" title="AI 正在回复..."></span>
              </div>
              <el-popover
                :visible="pendingDeleteId === chat.id"
                trigger="manual"
                placement="top-end"
                :width="200"
                popper-class="minimal-delete-popover"
                @update:visible="(v) => { if (!v) pendingDeleteId = null }"
              >
                <template #reference>
                  <button
                    class="delete-btn"
                    @click.stop="pendingDeleteId = chat.id"
                    title="删除对话"
                    aria-label="删除对话"
                  >
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M3 6H5H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M10 11V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M14 11V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </button>
                </template>
                <div class="delete-popover-content">
                  <div class="delete-popover-title">确定删除「{{ chat.title || '未命名对话' }}」吗？</div>
                  <div class="delete-popover-actions">
                    <button class="delete-popover-btn cancel" @click.stop="pendingDeleteId = null">取消</button>
                    <button class="delete-popover-btn confirm" @click.stop="handleDeleteChat(chat.id)">删除</button>
                  </div>
                </div>
              </el-popover>
            </div>
          </div>
        </div>
      </div>

      <div class="user-section">
        <div class="user-info" @click="toggleUserMenu">
          <div class="user-avatar">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="10" fill="#ff7e5f"/>
              <path d="M12 7C10.3431 7 9 8.34315 9 10C9 11.6569 10.3431 13 12 13C13.6569 13 15 11.6569 15 10C15 8.34315 13.6569 7 12 7Z" fill="white"/>
              <path d="M12 15C9.33 15 7 16.34 7 18V19H17V18C17 16.34 14.67 15 12 15Z" fill="white"/>
            </svg>
          </div>
          <div class="user-details">
            <span class="user-nickname">{{ userInfo.nickname }}</span>
            <span class="user-email">{{ userInfo.email }}</span>
          </div>
          <svg class="dropdown-icon" :class="{ open: showUserMenu }" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M6 9L12 15L18 9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>

        <div v-if="showUserMenu" class="user-menu">
          <div class="menu-item" @click="handleProfile">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M20 21V19C20 17.9391 19.5786 16.9217 18.8284 16.1716C18.0783 15.4214 17.0609 15 16 15H8C6.93913 15 5.92172 15.4214 5.17157 16.1716C4.42143 16.9217 4 17.9391 4 19V21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            个人资料
          </div>
          <div class="menu-item" @click="handleSettings">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M19.4 15C19.2669 15.3016 19.2272 15.6362 19.286 15.96C19.3448 16.2839 19.4995 16.5816 19.73 16.81L19.79 16.87C19.976 17.0557 20.1237 17.2762 20.2241 17.5191C20.3246 17.762 20.3756 18.0227 20.3756 18.2857C20.3756 18.5488 20.3246 18.8094 20.2241 19.0524C20.1237 19.2952 19.976 19.5158 19.79 19.7014C19.6042 19.8872 19.3838 20.0349 19.1409 20.1353C18.898 20.2358 18.6373 20.2868 18.3743 20.2868C18.1112 20.2868 17.8506 20.2358 17.6076 20.1353C17.3648 20.0349 17.1442 19.8872 16.9586 19.7014L16.8986 19.6414C16.6701 19.411 16.3725 19.2563 16.0486 19.1975C15.7247 19.1387 15.39 19.1784 15.0886 19.3114C14.7934 19.4384 14.5408 19.6472 14.3613 19.9135C14.1818 20.1797 14.0827 20.4923 14.0757 20.813V21C14.0757 21.5304 13.865 22.0391 13.4899 22.4142C13.1148 22.7893 12.6061 23 12.0757 23C11.5453 23 11.0366 22.7893 10.6615 22.4142C10.2864 22.0391 10.0757 21.5304 10.0757 21V20.91C10.0618 20.579 9.95315 20.258 9.76216 19.9887C9.57118 19.7195 9.30562 19.5143 9 19.4C8.69861 19.267 8.36391 19.2273 8.04002 19.2861C7.71612 19.3449 7.41848 19.4996 7.19 19.73L7.13 19.79C6.94425 19.976 6.72372 20.1237 6.48083 20.2241C6.23794 20.3246 5.97727 20.3756 5.71429 20.3756C5.4513 20.3756 5.19064 20.3246 4.94775 20.2241C4.70486 20.1237 4.48433 19.976 4.29857 19.79C4.1128 19.6042 3.96509 19.3838 3.86463 19.1409C3.76418 18.898 3.7132 18.6373 3.7132 18.3743C3.7132 18.1112 3.76418 17.8506 3.86463 17.6076C3.96509 17.3648 4.1128 17.1442 4.29857 16.9586L4.35857 16.8986C4.58902 16.6701 4.74368 16.3725 4.80251 16.0486C4.86134 15.7247 4.82164 15.39 4.68857 15.0886C4.56157 14.7934 4.35277 14.5408 4.08652 14.3613C3.82027 14.1818 3.50768 14.0827 3.187 14.0757H3C2.46957 14.0757 1.96086 13.865 1.58579 13.4899C1.21071 13.1148 1 12.6061 1 12.0757C1 11.5453 1.21071 11.0366 1.58579 10.6615C1.96086 10.2864 2.46957 10.0757 3 10.0757H3.09C3.42097 10.0618 3.74202 9.95315 4.01126 9.76216C4.2805 9.57118 4.48568 9.30562 4.6 9C4.733 8.69861 4.7727 8.36391 4.71387 8.04002C4.65504 7.71612 4.50038 7.41848 4.27 7.19L4.21 7.13C4.02423 6.94425 3.87652 6.72372 3.77606 6.48083C3.67561 6.23794 3.62463 5.97727 3.62463 5.71429C3.62463 5.4513 3.67561 5.19064 3.77606 4.94775C3.87652 4.70486 4.02423 4.48433 4.21 4.29857C4.39575 4.1128 4.61628 3.96509 4.85917 3.86463C5.10206 3.76418 5.36273 3.7132 5.62571 3.7132C5.8887 3.7132 6.14937 3.76418 6.39226 3.86463C6.63515 3.96509 6.85568 4.1128 7.04143 4.29857L7.10143 4.35857C7.32991 4.58902 7.62754 4.74368 7.95143 4.80251C8.27532 4.86134 8.61 4.82164 8.91143 4.68857H9C9.29523 4.56157 9.54783 4.35277 9.72733 4.08652C9.90683 3.82027 10.0059 3.50768 10.013 3.187V3C10.013 2.46957 10.2237 1.96086 10.5988 1.58579C10.9739 1.21071 11.4826 1 12.013 1C12.5434 1 13.0521 1.21071 13.4272 1.58579C13.8023 1.96086 14.013 2.46957 14.013 3V3.09C14.02 3.41068 14.1191 3.72327 14.2986 3.98952C14.4781 4.25577 14.7307 4.46457 15.026 4.59157C15.3274 4.72464 15.6621 4.76434 15.986 4.70551C16.3099 4.64668 16.6075 4.49202 16.836 4.26157L16.896 4.20157C17.0817 4.0158 17.3023 3.86809 17.5452 3.76763C17.7881 3.66718 18.0487 3.6162 18.3117 3.6162C18.5747 3.6162 18.8354 3.66718 19.0782 3.76763C19.3211 3.86809 19.5417 4.0158 19.7274 4.20157C19.9132 4.38733 20.0609 4.60786 20.1614 4.85075C20.2618 5.09364 20.3128 5.3543 20.3128 5.61729C20.3128 5.88027 20.2618 6.14094 20.1614 6.38383C20.0609 6.62672 19.9132 6.84725 19.7274 7.033L19.6674 7.093C19.437 7.32148 19.2823 7.61912 19.2235 7.943C19.1647 8.26689 19.2044 8.60157 19.3374 8.903V9C19.4644 9.29523 19.6732 9.54783 19.9395 9.72733C20.2057 9.90683 20.5183 10.0059 20.839 10.013H21C21.5304 10.013 22.0391 10.2237 22.4142 10.5988C22.7893 10.9739 23 11.4826 23 12.013C23 12.5434 22.7893 13.0521 22.4142 13.4272C22.0391 13.8023 21.5304 14.013 21 14.013H20.91C20.5893 14.02 20.2767 14.1191 20.0105 14.2986C19.7442 14.4781 19.5354 14.7307 19.4084 15.026V15Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            设置
          </div>
          <div class="menu-divider"></div>
          <div class="menu-item logout" @click="handleLogout">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M9 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M16 17L21 12L16 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M21 12H9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            退出登录
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import { removeToken, logout } from '@/utils/api'

const props = defineProps({
  collapsed: {
    type: Boolean,
    default: false
  },
  currentChatTitle: {
    type: String,
    default: ''
  },
  conversations: {
    type: Array,
    default: () => []
  },
  currentConversationId: {
    type: String,
    default: null
  },
  activeConversations: {
    type: Object,
    default: () => new Set()
  }
})

const emit = defineEmits(['toggle', 'new-chat', 'select-chat', 'delete-chat'])

const router = useRouter()
const { isDark } = useTheme()
const showUserMenu = ref(false)

const savedUserInfo = localStorage.getItem('userInfo')
const userInfo = reactive(savedUserInfo ? JSON.parse(savedUserInfo) : {
  nickname: '用户昵称',
  email: 'user@example.com'
})

const isCollapsed = computed(() => props.collapsed)

// Group conversations by date
const groupedConversations = computed(() => {
  const groups = {
    today: [],
    yesterday: [],
    last7Days: [],
    older: []
  }

  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const last7Days = new Date(today)
  last7Days.setDate(last7Days.getDate() - 7)

  props.conversations.forEach(chat => {
    const chatDate = new Date(chat.created_at || chat.updated_at || Date.now())
    const chatDay = new Date(chatDate.getFullYear(), chatDate.getMonth(), chatDate.getDate())

    if (chatDay.getTime() === today.getTime()) {
      groups.today.push(chat)
    } else if (chatDay.getTime() === yesterday.getTime()) {
      groups.yesterday.push(chat)
    } else if (chatDay.getTime() > last7Days.getTime()) {
      groups.last7Days.push(chat)
    } else {
      groups.older.push(chat)
    }
  })

  return groups
})

watch(() => props.currentChatTitle, (newTitle) => {
  if (newTitle && props.currentConversationId) {
    const chat = props.conversations.find(c => c.id === props.currentConversationId)
    if (chat) {
      chat.title = newTitle
    }
  }
})

function handleToggle() {
  emit('toggle')
}

function handleNewChat() {
  emit('new-chat')
}

function handleSelectChat(chatId) {
  emit('select-chat', chatId)
}

const pendingDeleteId = ref(null)

function handleDeleteChat(chatId) {
  pendingDeleteId.value = null
  emit('delete-chat', chatId)
}

function toggleUserMenu() {
  showUserMenu.value = !showUserMenu.value
}

function handleProfile() {
  alert('个人资料功能待开发')
  showUserMenu.value = false
}

function handleSettings() {
  alert('设置功能待开发')
  showUserMenu.value = false
}

async function handleLogout() {
  if (confirm('确定要退出登录吗？')) {
    try {
      await logout()
    } catch (error) {
      console.error('退出登录失败:', error)
    } finally {
      removeToken()
      router.push('/')
    }
  }
}
</script>

<style scoped>
/* History group styling */
.history-group {
  margin-bottom: 16px;
}

.history-group-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 0 12px 8px;
  opacity: 0.8;
}

/* Enhanced history item */
.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-bottom: 2px;
  position: relative;
}
.history-item:hover {
  background: var(--bg-hover);
}
.history-item.active {
  background: rgba(255, 107, 107, 0.08);
  border-left: 3px solid var(--accent-primary);
  padding-left: 9px;
}

.history-item:hover {
  background: rgba(102, 126, 234, 0.08);
  border-color: rgba(102, 126, 234, 0.15);
  transform: translateX(2px);
}

.history-item.active {
  background: linear-gradient(135deg, rgba(255, 154, 86, 0.15) 0%, rgba(255, 107, 53, 0.15) 100%);
  border-color: rgba(255, 154, 86, 0.3);
  box-shadow: 0 2px 8px rgba(255, 154, 86, 0.15);
}

.dark .history-item.active {
  background: linear-gradient(135deg, rgba(255, 126, 95, 0.2) 0%, rgba(255, 107, 53, 0.2) 100%);
  border-color: rgba(255, 126, 95, 0.4);
  box-shadow: 0 2px 8px rgba(255, 126, 95, 0.2);
}

.history-item.active .chat-title {
  color: var(--text-primary);
  font-weight: 600;
}

.history-item.active svg {
  color: #ff9a56;
}

.dark .history-item.active svg {
  color: #ff7e5f;
}

/* Minimal delete button */
.delete-btn {
  opacity: 0.35;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s ease;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.delete-btn svg {
  width: 15px;
  height: 15px;
}

.history-item:hover .delete-btn {
  opacity: 0.7;
}

.delete-btn:hover {
  opacity: 1 !important;
  background: transparent;
  color: #f44336;
  transform: scale(1.05);
}

.dark .delete-btn:hover {
  color: #ff6b6b;
}

/* Streaming indicator enhancement */
.streaming-indicator {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ff6b9d, #4ecdc4);
  margin-left: 8px;
  animation: streaming-pulse 1.5s ease-in-out infinite;
  flex-shrink: 0;
  box-shadow: 0 0 6px rgba(255, 107, 157, 0.4);
}

@keyframes streaming-pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(0.8);
  }
}

.dark .streaming-indicator {
  background: linear-gradient(135deg, #ff8fab, #7fdbda);
  box-shadow: 0 0 6px rgba(255, 143, 171, 0.4);
}

.sidebar {
  width: 260px;
  height: 100vh;
  background: var(--bg-glass);
  backdrop-filter: var(--blur-glass);
  -webkit-backdrop-filter: var(--blur-glass);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: width var(--transition-base);
  position: relative;
  z-index: 10;
  flex-shrink: 0;
}

.sidebar.collapsed {
  width: 0;
  overflow: hidden;
  border-right: none;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
  min-height: 60px;
}

.logo img {
  height: 36px;
  width: auto;
  object-fit: contain;
}

.toggle-sidebar-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 8px;
  border-radius: 6px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.toggle-sidebar-btn:hover {
  background: var(--bg-hover);
}

.toggle-sidebar-btn svg {
  width: 20px;
  height: 20px;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 12px 16px;
  background: var(--accent-gradient);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all var(--transition-fast);
  box-shadow: var(--shadow-xs);
  margin-bottom: 16px;
}
.new-chat-btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md), var(--accent-glow);
}
.new-chat-btn:active { transform: translateY(0); }

.new-chat-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(255, 126, 95, 0.3);
}

.new-chat-icon {
  width: 18px;
  height: 18px;
}

.history-section {
  flex: 1;
  overflow-y: auto;
  margin-top: 8px;
}

.history-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
  padding: 8px 12px 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.history-list {
  display: flex;
  flex-direction: column;
}

.history-item-content {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.history-item-content svg {
  width: 16px;
  height: 16;
  flex-shrink: 0;
  color: var(--text-tertiary);
}

.chat-title {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

/* User section */
.user-section {
  border-top: 1px solid var(--border-color);
  padding: 12px 8px;
  position: relative;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s;
}

.user-info:hover {
  background: var(--bg-hover);
}

.user-avatar svg {
  width: 36px;
  height: 36px;
}

.user-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.user-nickname {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-email {
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-icon {
  width: 16px;
  height: 16px;
  color: var(--text-tertiary);
  transition: transform 0.2s;
  flex-shrink: 0;
}

.dropdown-icon.open {
  transform: rotate(180deg);
}

/* User menu */
.user-menu {
  position: absolute;
  bottom: 100%;
  left: 8px;
  right: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  margin-bottom: 8px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.15s;
  font-size: 14px;
  color: var(--text-primary);
}

.menu-item:hover {
  background: var(--bg-hover);
}

.menu-item svg {
  width: 18px;
  height: 18px;
  color: var(--text-secondary);
}

.menu-divider {
  height: 1px;
  background: var(--border-color);
  margin: 4px 0;
}

.menu-item.logout {
  color: #f44336;
}

.menu-item.logout svg {
  color: #f44336;
}

</style>

<style>
/* Minimal delete popover (unscoped because Element Plus appends it to body) */
.el-popover.el-popper.minimal-delete-popover {
  padding: 0 !important;
  background: var(--bg-secondary) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: 10px !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08) !important;
  min-width: 170px;
}

.dark .el-popover.el-popper.minimal-delete-popover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25) !important;
}

.el-popover.el-popper.minimal-delete-popover .el-popper__arrow::before {
  background: var(--bg-secondary) !important;
  border-color: var(--border-color) !important;
}

.delete-popover-content {
  padding: 10px 12px;
}

.delete-popover-title {
  font-size: 13px;
  line-height: 1.4;
  color: var(--text-primary);
  margin-bottom: 10px;
  word-break: break-word;
}

.delete-popover-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.delete-popover-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  color: var(--text-secondary);
  transition: all 0.15s ease;
}

.delete-popover-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.delete-popover-btn.confirm {
  color: #f44336;
}

.delete-popover-btn.confirm:hover {
  color: #d32f2f;
  background: rgba(244, 67, 54, 0.08);
}

.dark .delete-popover-btn.confirm {
  color: #ff6b6b;
}

.dark .delete-popover-btn.confirm:hover {
  color: #ff5252;
  background: rgba(244, 67, 54, 0.12);
}

/* Minimal theme-adaptive sidebar scrollbar (unscoped for wider compatibility) */
.sidebar ::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}

.sidebar ::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar ::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.12);
  border-radius: 2px;
}

.sidebar ::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.22);
}

.dark .sidebar ::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
}

.dark .sidebar ::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.22);
}

.sidebar ::-webkit-scrollbar-button {
  display: none;
}

.sidebar ::-webkit-scrollbar-corner {
  background: transparent;
}

.sidebar-content,
.history-section {
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 0, 0, 0.12) transparent;
}

.dark .sidebar-content,
.dark .history-section {
  scrollbar-color: rgba(255, 255, 255, 0.12) transparent;
}
</style>
