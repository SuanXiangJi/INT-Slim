<template>
  <div class="markdown-renderer-wrapper">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <div class="markdown-body" ref="rendererContainer" v-html="renderedContent"></div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import katex from 'katex'
// 引入 highlight.js 的样式，你可以换成 'github-dark.css' 或其他喜欢的主题
import 'highlight.js/styles/atom-one-dark.css' 

const props = defineProps({
  content: {
    type: String,
    required: true,
    default: ''
  }
})

const rendererContainer = ref(null)
const renderedContent = ref('')

// 配置 marked
marked.setOptions({
  gfm: true,
  breaks: true,
  headerIds: true, // 开启以便生成锚点
  mangle: false,
  // 关键：集成 highlight.js 实现语法高亮
  highlight: function(code, lang) {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext'
    return hljs.highlight(code, { language }).value
  }
})

const renderMarkdown = () => {
  if (!props.content) {
    renderedContent.value = ''
    return
  }

  // 先渲染数学公式（在 marked 之前）
  let processed = renderMathBeforeMarked(props.content)

  // 再渲染剩余的 markdown
  let html = marked.parse(processed)

  renderedContent.value = html

  nextTick(() => {
    enhanceCodeBlocks()
    enhanceTables()
  })
}

// 在 marked 处理之前渲染数学公式
const renderMathBeforeMarked = (text) => {
  if (!text) return text

  // 先处理块级公式 $$...$$
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (match, math) => {
    try {
      // 将换行符转为 LaTeX 换行命令
      const latexMath = math.replace(/\n/g, '\\\\')
      return `<div class="math-block">${katex.renderToString(latexMath.trim(), { displayMode: true, throwOnError: false })}</div>`
    } catch (e) {
      console.error('KaTeX block error:', e)
      return match
    }
  })

  // 再处理行内公式 $...$
  text = text.replace(/\$([^\$\n]+?)\$/g, (match, math) => {
    try {
      const latexMath = math.replace(/\n/g, '\\\\')
      return katex.renderToString(latexMath.trim(), { displayMode: false, throwOnError: false })
    } catch (e) {
      console.error('KaTeX inline error:', e)
      return match
    }
  })

  return text
}

// 美化代码块并添加复制按钮
const enhanceCodeBlocks = () => {
  const container = rendererContainer.value
  if (!container) return
  
  const pres = container.querySelectorAll('pre')
  
  pres.forEach((pre) => {
    // 1. 如果已经处理过，跳过
    if (pre.classList.contains('enhanced')) return
    pre.classList.add('enhanced')
    
    // 2. 获取语言类型（用于展示）
    const code = pre.querySelector('code')
    const langClass = code?.className.match(/language-(\w+)/)
    const lang = langClass ? langClass[1] : 'text'
    
    // 3. 构建代码块头部
    const header = document.createElement('div')
    header.className = 'code-block-header'
    header.innerHTML = `
      <div class="lang-tag">
        <span class="lang-text">${lang}</span>
      </div>
    `
    
    // 4. 构建复制按钮
    const copyBtn = document.createElement('button')
    copyBtn.className = 'copy-btn'
    copyBtn.innerHTML = `
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
      <span class="text">复制</span>
    `
    copyBtn.onclick = async () => {
      try {
        await navigator.clipboard.writeText(code.innerText)
        copyBtn.classList.add('copied')
        copyBtn.innerHTML = `
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          <span class="text">已复制</span>
        `
        setTimeout(() => {
          copyBtn.classList.remove('copied')
          copyBtn.innerHTML = `
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
            <span class="text">复制</span>
          `
        }, 2000)
      } catch (err) {
        console.error('Copy failed', err)
      }
    }
    
    // 5. 检查代码行数，超过15行则添加折叠功能
    const codeLines = code.textContent.split('\n').length
    const shouldCollapse = codeLines > 15
    
    if (shouldCollapse) {
      pre.classList.add('collapsible')
      pre.classList.add('collapsed')
    }
    
    // 6. 重新组装 DOM 结构
    // 现在的结构是：pre > code
    // 目标结构：pre.enhanced > (header + div.code-wrapper > code + copyBtn + toggleBtn)
    
    // 创建一个包裹层用于滚动，防止滚动条覆盖 Header
    const scrollWrapper = document.createElement('div')
    scrollWrapper.className = 'code-scroll-wrapper'
    
    // 把 code 移入 wrapper
    scrollWrapper.appendChild(code)
    
    // 7. 创建展开/折叠按钮
    const toggleBtn = document.createElement('button')
    toggleBtn.className = 'toggle-btn'
    toggleBtn.innerHTML = `
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
      <span class="text">展开</span>
    `
    
    toggleBtn.onclick = () => {
      const isCollapsed = pre.classList.contains('collapsed')
      if (isCollapsed) {
        pre.classList.remove('collapsed')
        pre.classList.add('expanded')
        toggleBtn.innerHTML = `
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="18 15 12 9 6 15"></polyline>
          </svg>
          <span class="text">收起</span>
        `
      } else {
        pre.classList.remove('expanded')
        pre.classList.add('collapsed')
        toggleBtn.innerHTML = `
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
          <span class="text">展开</span>
        `
      }
    }
    
    // 8. 根据代码行数动态调整拷贝按钮位置
    if (!shouldCollapse) {
      // 代码不超过15行，拷贝按钮在最右侧
      copyBtn.style.right = '12px'
    }
    
    // 9. 清空 pre 并重新添加
    pre.innerHTML = ''
    pre.appendChild(header)
    pre.appendChild(scrollWrapper)
    pre.appendChild(copyBtn)
    if (shouldCollapse) {
      pre.appendChild(toggleBtn)
    }
  })
}

// 美化表格并添加复制按钮
const enhanceTables = () => {
  const container = rendererContainer.value
  if (!container) return
  
  const tables = container.querySelectorAll('table')
  
  tables.forEach((table) => {
    // 1. 如果已经处理过，跳过
    if (table.classList.contains('table-enhanced')) return
    table.classList.add('table-enhanced')
    
    // 2. 创建表格包裹层，用于横向滚动
    const tableWrapper = document.createElement('div')
    tableWrapper.className = 'table-wrapper'
    
    // 3. 将表格移入包裹层
    table.parentNode.insertBefore(tableWrapper, table)
    tableWrapper.appendChild(table)
    
    // 4. 为表格添加复制按钮（在表格右上角）
    const copyBtn = document.createElement('button')
    copyBtn.className = 'table-copy-btn'
    copyBtn.title = '复制整个表格'
    copyBtn.innerHTML = `
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
    `
    
    copyBtn.onclick = async () => {
      try {
        // 获取表格所有内容
        let tableText = ''
        const rows = table.querySelectorAll('tr')
        rows.forEach((row, rowIndex) => {
          const cells = row.querySelectorAll('td, th')
          const rowText = Array.from(cells).map(cell => cell.textContent).join('\t')
          tableText += rowText + '\n'
        })
        
        await navigator.clipboard.writeText(tableText)
        copyBtn.classList.add('copied')
        copyBtn.innerHTML = `
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        `
        setTimeout(() => {
          copyBtn.classList.remove('copied')
          copyBtn.innerHTML = `
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
          `
        }, 2000)
      } catch (err) {
        console.error('Copy failed', err)
      }
    }
    
    table.appendChild(copyBtn)
  })
}

watch(() => props.content, renderMarkdown)
onMounted(renderMarkdown)
</script>

<style scoped>
/* =========================================
   基础变量定义 (方便换肤)
   ========================================= */
.markdown-renderer-wrapper {
  --md-primary-color: #3b82f6;
  --md-text-color: #2c3e50;
  --md-bg-color: #ffffff;
  --md-code-bg: #f8fafc;
  --md-code-text: #1e293b;
  --md-border-color: #e5e7eb;
  --md-table-header-bg: #f8fafc;
  --md-table-row-hover: #f1f5f9;
  --md-font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  --md-quote-bg: #f6f8fa;
  --md-quote-text: #57606a;
  --md-inline-code-bg: rgba(175, 184, 193, 0.2);
  --md-inline-code-text: #24292f;
  --md-table-even-bg: #fbfcfd;
}

/* 深色主题适配 */
.dark .markdown-renderer-wrapper {
  --md-primary-color: #60a5fa;
  --md-text-color: #e5e7eb;
  --md-bg-color: #1a1a1a;
  --md-code-bg: #1e1e1e;
  --md-code-text: #e5e7eb;
  --md-border-color: #2a2f3a;
  --md-table-header-bg: #2a2f3a;
  --md-table-row-hover: #2a3542;
  --md-quote-bg: rgba(255, 255, 255, 0.05);
  --md-quote-text: #9ca3af;
  --md-inline-code-bg: rgba(255, 255, 255, 0.1);
  --md-inline-code-text: #e5e7eb;
  --md-table-even-bg: rgba(255, 255, 255, 0.02);
}

.markdown-body {
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-primary);
  word-break: break-word;
  overflow-wrap: break-word;
}

/* =========================================
   标题与段落
   ========================================= */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin: 20px 0 10px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--text-primary);
}
.markdown-body :deep(h1) { font-size: 1.6em; }
.markdown-body :deep(h2) { font-size: 1.35em; padding-bottom: 6px; border-bottom: 1px solid var(--border-color); }
.markdown-body :deep(h3) { font-size: 1.15em; }

.markdown-body :deep(h1) { font-size: 2em; padding-bottom: 0.3em; border-bottom: 1px solid var(--md-border-color); }
.markdown-body :deep(h2) { font-size: 1.5em; padding-bottom: 0.3em; border-bottom: 1px solid var(--md-border-color); }
.markdown-body :deep(p) { margin-bottom: 1em; }

/* =========================================
   链接与列表
   ========================================= */
.markdown-body :deep(a) {
  color: var(--accent-primary);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: all var(--transition-fast);
}
.markdown-body :deep(a:hover) {
  border-bottom-color: var(--accent-primary);
}
.markdown-body :deep(blockquote p) { margin: 0; }

/* =========================================
   行内代码 (Inline Code)
   ========================================= */
.markdown-body :deep(code):not(pre code) {
  padding: 0.2em 0.4em;
  margin: 0;
  font-size: 85%;
  font-family: var(--md-font-mono);
  background-color: var(--md-inline-code-bg);
  border-radius: 6px;
  color: var(--md-inline-code-text);
}

/* =========================================
   代码块 (Code Blocks) - 核心美化区
   ========================================= */
.markdown-body :deep(pre) {
  position: relative;
  background-color: var(--md-code-bg);
  border-radius: 24px;
  margin: 1.5em 0;
  overflow: hidden;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  border: 1px solid var(--md-border-color);
}

/* 代码块头部 */
.markdown-body :deep(.code-block-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  background: rgba(0, 0, 0, 0.25);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  font-size: 12px;
}

.markdown-body :deep(.lang-tag) {
  display: flex;
  align-items: center;
  gap: 8px;
}

.markdown-body :deep(.lang-icon) {
  width: 16px;
  height: 16px;
  color: var(--md-primary-color);
  opacity: 0.7;
}

.markdown-body :deep(.lang-text) {
  font-size: 12px;
  color: var(--md-primary-color);
  font-family: var(--md-font-mono);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 滚动区域 */
.markdown-body :deep(.code-scroll-wrapper) {
  padding: 16px;
  overflow: auto;
  max-height: calc(100vh - 200px);
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  font-family: var(--md-font-mono);
  font-size: 14px;
  line-height: 1.6;
  color: var(--md-code-text);
}

/* 深色主题下代码文字颜色 */
.dark .markdown-body :deep(pre code) {
  color: #abb2bf;
}

/* 复制按钮 */
.markdown-body :deep(.copy-btn) {
  position: absolute;
  top: 10px;
  right: 88px;
  opacity: 0.89;
  padding: 4px 8px;
  border-radius: 10px;
  background: var(--md-code-bg);
  border: 0px solid var(--md-border-color);
  color: var(--md-code-text);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  z-index: 5;
}

.markdown-body :deep(.copy-btn:hover) {
  background: var(--md-primary-color);
  color: #fff;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}

.markdown-body :deep(.copy-btn svg) {
  width: 14px;
  height: 14px;
}

.markdown-body :deep(.copy-btn .text) {
  font-size: 12px;
  font-weight: 500;
}

.markdown-body :deep(.copy-btn.copied) {
  background: #27c93f;
  color: #fff;
  border-color: #27c93f;
}

/* 深色主题下复制按钮 */
.dark .markdown-body :deep(.copy-btn) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
  color: var(--md-text-color);
}

.dark .markdown-body :deep(.copy-btn:hover) {
  background: var(--md-primary-color);
  color: #fff;
}

.dark .markdown-body :deep(.copy-btn.copied) {
  background: #27c93f;
  color: #fff;
  border-color: #27c93f;
}

/* 展开/折叠按钮 */
.markdown-body :deep(.toggle-btn) {
  position: absolute;
  top: 10px;
  right: 12px;
  padding: 4px 8px;
  border-radius: 10px;
  background: var(--md-code-bg);
  opacity: 0.89;
  border: 0px solid var(--md-border-color);
  color: var(--md-code-text);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  z-index: 5;
}

.markdown-body :deep(.toggle-btn:hover) {
  background: var(--md-primary-color);
  color: #fff;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}

.markdown-body :deep(.toggle-btn svg) {
  width: 14px;
  height: 14px;
  transition: transform 0.2s;
}

.markdown-body :deep(.toggle-btn .text) {
  font-size: 12px;
  font-weight: 500;
}

/* 深色主题下展开/折叠按钮 */
.dark .markdown-body :deep(.toggle-btn) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
  color: var(--md-text-color);
}

.dark .markdown-body :deep(.toggle-btn:hover) {
  background: var(--md-primary-color);
  color: #fff;
}

/* 表格包裹层 */
.markdown-body :deep(.table-wrapper) {
  position: relative;
  display: block;
  overflow-x: auto;
  max-width: 100%;
  margin: 1.5em 0;
  border-radius: 24px;
  border: 1px solid var(--md-border-color);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

/* 表格横向滚动时的阴影效果 */
.markdown-body :deep(.table-wrapper::-webkit-scrollbar) {
  height: 8px;
}

.markdown-body :deep(.table-wrapper::-webkit-scrollbar-thumb) {
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

.markdown-body :deep(.table-wrapper::-webkit-scrollbar-track) {
  background-color: transparent;
}

/* 表格复制按钮 */
.markdown-body :deep(.table-copy-btn) {
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0.89;
  padding: 3px 6px;
  border-radius: 16px;
  background: var(--md-code-bg);
  border: 0px solid var(--md-border-color);
  color: var(--md-code-text);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  font-size: 11px;
  font-weight: 500;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  z-index: 10;
  opacity: 0;
}

.markdown-body :deep(table:hover .table-copy-btn) {
  opacity: 1;
}

.markdown-body :deep(.table-copy-btn:hover) {
  background: var(--md-primary-color);
  color: #fff;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}

.markdown-body :deep(.table-copy-btn svg) {
  width: 12px;
  height: 12px;
}

.markdown-body :deep(.table-copy-btn.copied) {
  background: #27c93f;
  color: #fff;
  border-color: #27c93f;
}

/* 深色主题下表格复制按钮 */
.dark .markdown-body :deep(.table-copy-btn) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
  color: var(--md-text-color);
}

.dark .markdown-body :deep(.table-copy-btn:hover) {
  background: var(--md-primary-color);
  color: #fff;
}

.dark .markdown-body :deep(.table-copy-btn.copied) {
  background: #27c93f;
  color: #fff;
  border-color: #27c93f;
}

/* 自定义滚动条样式 */
.markdown-body :deep(pre ::-webkit-scrollbar) {
  height: 8px;
  width: 8px;
}
.markdown-body :deep(pre ::-webkit-scrollbar-thumb) {
  background-color: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
}
.markdown-body :deep(pre ::-webkit-scrollbar-track) {
  background-color: transparent;
}

/* 代码块折叠功能 */
.markdown-body :deep(pre.collapsed) .code-scroll-wrapper {
  max-height: 240px !important; /* 显示约8行代码的高度，优先级高于默认值 */
  overflow: hidden;
  position: relative;
}

.markdown-body :deep(pre.collapsed) .code-scroll-wrapper::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 60px;
  background: linear-gradient(transparent, var(--md-code-bg));
  pointer-events: none;
}

.markdown-body :deep(pre.expanded) .code-scroll-wrapper {
  max-height: calc(100vh - 200px); /* 使用动态高度，与默认值保持一致 */
}

.markdown-body :deep(pre.expanded) .code-scroll-wrapper::after {
  display: none;
}

/* =========================================
   表格 (Table) - 美化区
   ========================================= */
.markdown-body :deep(table) {
  width: auto !important;
  min-width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin: 0;
  border: none;
  border-radius: 0;
  overflow: visible;
  box-shadow: none;
  position: relative;
  table-layout: auto;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 8px 12px;
  border-bottom: 1px solid var(--md-border-color);
  border-right: 1px solid var(--md-border-color);
  text-align: left;
  font-size: 0.95em;
}

/* 去掉最后一列的竖线 */
.markdown-body :deep(th:last-child),
.markdown-body :deep(td:last-child) {
  border-right: none;
}

/* 表头样式 */
.markdown-body :deep(th) {
  background-color: var(--md-table-header-bg);
  font-weight: 600;
  color: var(--md-text-color);
}

/* 去掉最后一行的下边框 */
.markdown-body :deep(tr:last-child td) {
  border-bottom: none;
}

/* 隔行变色 */
.markdown-body :deep(tr:nth-child(even)) {
  background-color: var(--md-table-even-bg);
}

/* 悬停高亮 */
.markdown-body :deep(tr:hover) {
  background-color: var(--md-table-row-hover);
}

/* 图片 */
.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 8px;
  display: block;
  margin: 1em auto;
}

/* =========================================
   数学公式 (Math Formulas)
   ========================================= */
.math-block {
  display: block;
  text-align: center;
  margin: 1.5em 0;
  overflow-x: auto;
  padding: 1em 0;
}

.markdown-body :deep(.katex-display) {
  margin: 0;
  font-size: 1.1em;
}

.markdown-body :deep(.katex) {
  color: var(--md-text-color);
}

/* 数学公式悬停效果 */
.math-block:hover {
  background: rgba(255, 126, 95, 0.05);
  border-radius: 8px;
}
</style>
