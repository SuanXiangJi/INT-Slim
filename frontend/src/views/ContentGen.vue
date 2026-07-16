<template>
  <AppLayout>
    <div class="content-page">
      <h3>内容生成</h3>
      <div class="gen-form">
        <div class="form-group">
          <label>内容主题</label>
          <input v-model="topic" placeholder="输入内容主题，如：Python装饰器" />
        </div>
        <div class="form-group">
          <label>内容类型</label>
          <select v-model="contentType">
            <option value="lecture">讲义</option>
            <option value="exercise">练习题</option>
          </select>
        </div>
        <button class="action-btn primary" @click="generate" :disabled="generating">
          {{ generating ? "生成中..." : "开始生成" }}
        </button>
      </div>
      <div v-if="result" class="gen-result">
        <h4>生成结果</h4>
        <div class="result-content">{{ result }}</div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref } from "vue"
import AppLayout from "../components/AppLayout.vue"
import { apiPost } from "../utils/api"

const topic = ref("")
const contentType = ref("lecture")
const generating = ref(false)
const result = ref("")

async function generate() {
  if (!topic.value.trim()) return
  generating.value = true
  try {
    const content = await apiPost("/learning/contents", {
      title: topic.value, content_type: contentType.value,
      content: "暂存"
    })
    result.value = content?.content || "生成成功！"
  } catch { result.value = "生成失败，请重试" }
  generating.value = false
}
</script>

<style scoped>
.content-page { max-width:800px; margin:0 auto; }
.content-page h3 { font-size:18px; margin-bottom:20px; }
.gen-form { background:var(--bg-secondary); border:1px solid var(--border-color); border-radius:var(--radius-lg); padding:20px; margin-bottom:20px; }
.form-group { margin-bottom:14px; }
.form-group label { display:block; font-size:13px; font-weight:500; margin-bottom:4px; color:var(--text-secondary); }
.form-group input,.form-group select { width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-md); background:var(--bg-primary); color:var(--text-primary); font-size:14px; outline:none; }
.form-group input:focus,.form-group select:focus { border-color:var(--accent-primary); }
.action-btn { padding:10px 24px; border:none; border-radius:var(--radius-md); cursor:pointer; font-size:14px; font-weight:500; transition:all var(--transition-fast); }
.action-btn.primary { background:var(--accent-primary); color:#fff; }
.action-btn.primary:hover:not(:disabled) { opacity:0.9; }
.action-btn:disabled { opacity:0.5; cursor:not-allowed; }
.gen-result { background:var(--bg-secondary); border:1px solid var(--border-color); border-radius:var(--radius-lg); padding:20px; }
.gen-result h4 { font-size:15px; margin-bottom:12px; }
.result-content { font-size:14px; line-height:1.7; white-space:pre-wrap; }
</style>

