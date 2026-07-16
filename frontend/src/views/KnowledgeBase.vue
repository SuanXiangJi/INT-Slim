<template>
  <AppLayout>
    <div class="kb-page">
      <div class="kb-header">
        <div class="kb-search">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input v-model="searchQuery" placeholder="搜索知识..." @input="doSearch" />
        </div>
        <div class="kb-cats">
          <button v-for="cat in categories" :key="cat" class="cat-btn" :class="{ active: selectedCat === cat }" @click="selectedCat = cat; loadDocs()">{{ cat }}</button>
        </div>
      </div>
      <div class="kb-content">
        <div v-if="loading" class="loading-state">加载中...</div>
        <div v-else-if="documents.length === 0" class="empty-state">
          <p>暂无知识文档</p>
        </div>
        <div v-else class="doc-grid">
          <div v-for="doc in documents" :key="doc.id" class="doc-card" @click="viewDoc(doc)">
            <h4>{{ doc.title }}</h4>
            <p>{{ doc.description || doc.content?.substring(0, 100) }}</p>
            <span class="doc-tag">{{ doc.category || "通用" }}</span>
          </div>
        </div>
      </div>
      <!-- Doc Detail Modal -->
      <div v-if="selectedDoc" class="modal-overlay" @click.self="selectedDoc = null">
        <div class="modal-content doc-detail">
          <button class="modal-close" @click="selectedDoc = null">&times;</button>
          <h2>{{ selectedDoc.title }}</h2>
          <div class="doc-meta">
            <span class="doc-tag">{{ selectedDoc.category }}</span>
          </div>
          <div class="doc-body">{{ selectedDoc.content }}</div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted } from "vue"
import AppLayout from "../components/AppLayout.vue"
import { apiGet, apiPost } from "../utils/api"

const searchQuery = ref("")
const documents = ref([])
const loading = ref(false)
const selectedCat = ref("全部")
const selectedDoc = ref(null)
const categories = ["全部", "Python", "AI Agent", "机器学习", "深度学习", "PyTorch", "NLP"]

onMounted(() => loadDocs())

async function loadDocs() {
  loading.value = true
  try {
    const docs = await apiGet("/knowledge-base/documents")
    if (docs && docs.length) {
      documents.value = selectedCat.value === "全部" ? docs : docs.filter(d => d.category === selectedCat.value)
    }
  } catch { documents.value = [] }
  loading.value = false
}

async function doSearch() {
  if (!searchQuery.value.trim()) { loadDocs(); return }
  loading.value = true
  try {
    const results = await apiPost("/knowledge-base/search", { query: searchQuery.value, top_k: 20 })
    documents.value = results || []
  } catch { documents.value = [] }
  loading.value = false
}

function viewDoc(doc) { selectedDoc.value = doc }
</script>

<style scoped>
.kb-page { max-width:1200px; margin:0 auto; }
.kb-header { margin-bottom:24px; }
.kb-search {
  display:flex; align-items:center; gap:10px;
  background:var(--bg-secondary); border:1px solid var(--border-color);
  border-radius:var(--radius-lg); padding:10px 16px; margin-bottom:12px;
}
.kb-search input { flex:1; border:none; outline:none; background:transparent; color:var(--text-primary); font-size:14px; }
.kb-cats { display:flex; gap:8px; flex-wrap:wrap; }
.cat-btn {
  padding:6px 14px; border:1px solid var(--border-color); border-radius:20px;
  background:var(--bg-secondary); color:var(--text-secondary); cursor:pointer;
  font-size:13px; transition:all var(--transition-fast);
}
.cat-btn:hover { border-color:var(--accent-primary); color:var(--accent-primary); }
.cat-btn.active { background:var(--accent-primary); color:#fff; border-color:var(--accent-primary); }
.doc-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:16px; }
.doc-card {
  background:var(--bg-secondary); border:1px solid var(--border-color);
  border-radius:var(--radius-lg); padding:20px; cursor:pointer;
  transition:all var(--transition-fast);
}
.doc-card:hover { border-color:var(--accent-primary); transform:translateY(-2px); box-shadow:var(--shadow-md); }
.doc-card h4 { font-size:15px; margin-bottom:8px; }
.doc-card p { font-size:13px; color:var(--text-secondary); line-height:1.5; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
.doc-tag { display:inline-block; padding:2px 8px; background:var(--bg-tertiary); border-radius:var(--radius-sm); font-size:11px; color:var(--text-secondary); margin-top:8px; }
.modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; z-index:1000; }
.modal-content { background:var(--bg-secondary); border-radius:var(--radius-xl); padding:24px; max-width:700px; width:90%; max-height:80vh; overflow-y:auto; position:relative; }
.modal-close { position:absolute; top:12px; right:16px; font-size:24px; border:none; background:transparent; color:var(--text-secondary); cursor:pointer; }
.doc-detail h2 { margin-bottom:8px; }
.doc-meta { margin-bottom:16px; }
.doc-body { font-size:14px; line-height:1.8; color:var(--text-primary); white-space:pre-wrap; }
.loading-state, .empty-state { text-align:center; padding:60px 0; color:var(--text-secondary); }
</style>

