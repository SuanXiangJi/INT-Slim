<template>
  <AppLayout>
    <div class="review-page">
      <h3>内容审核</h3>
      <div v-if="contents.length === 0" class="empty-state">
        <p>还没有待审核的内容</p>
      </div>
      <div v-else class="review-list">
        <div v-for="c in contents" :key="c.id" class="review-card">
          <div class="review-header">
            <h4>{{ c.title }}</h4>
            <span class="review-status" :class="c.status">{{ c.status || "待审核" }}</span>
          </div>
          <p>{{ c.content?.substring(0, 150) }}</p>
          <div class="review-actions">
            <button class="action-btn approve" @click="approve(c)">通过</button>
            <button class="action-btn reject" @click="reject(c)">驳回</button>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted } from "vue"
import AppLayout from "../components/AppLayout.vue"
import { apiGet, apiPost } from "../utils/api"

const contents = ref([])

onMounted(async () => {
  try {
    const c = await apiGet("/learning/contents")
    if (c) contents.value = c.filter(x => x.status !== "approved")
  } catch {}
})

async function approve(item) {
  await apiPost("/learning/reviews", { content_id: item.id, status: "approved", defects: [] })
  contents.value = contents.value.filter(c => c.id !== item.id)
}
async function reject(item) {
  await apiPost("/learning/reviews", { content_id: item.id, status: "rejected", defects: [{ description: "需要修改" }] })
  contents.value = contents.value.filter(c => c.id !== item.id)
}
</script>

<style scoped>
.review-page { max-width:800px; margin:0 auto; }
.review-page h3 { font-size:18px; margin-bottom:20px; }
.review-card { background:var(--bg-secondary); border:1px solid var(--border-color); border-radius:var(--radius-lg); padding:20px; margin-bottom:12px; }
.review-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
.review-header h4 { font-size:15px; }
.review-status { padding:2px 8px; border-radius:var(--radius-sm); font-size:11px; font-weight:500; }
.review-status.pending { background:rgba(245,158,11,0.12); color:var(--warm-accent); }
.review-status.approved { background:rgba(16,185,129,0.12); color:var(--success); }
.review-status.rejected { background:rgba(239,68,68,0.12); color:var(--error); }
.review-card p { font-size:13px; color:var(--text-secondary); line-height:1.5; margin-bottom:12px; }
.review-actions { display:flex; gap:8px; }
.action-btn { padding:6px 16px; border:none; border-radius:var(--radius-sm); cursor:pointer; font-size:13px; font-weight:500; transition:all var(--transition-fast); }
.action-btn.approve { background:var(--success); color:#fff; }
.action-btn.approve:hover { opacity:0.85; }
.action-btn.reject { background:var(--error); color:#fff; }
.action-btn.reject:hover { opacity:0.85; }
.empty-state { text-align:center; padding:60px 0; color:var(--text-secondary); }
</style>

