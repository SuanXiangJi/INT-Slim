<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="bg-orb orb-1"></div>
      <div class="bg-orb orb-2"></div>
      <div class="bg-orb orb-3"></div>
      <div class="bg-grid"></div>
    </div>
    <div class="login-container">
      <div class="login-brand">
        <div class="brand-icon">智</div>
        <h1>智训云枢</h1>
        <p class="brand-sub">AI 智能学习平台</p>
      </div>
      <form class="login-form" @submit.prevent="handleLogin">
        <div class="form-group">
          <label>邮箱地址</label>
          <div class="input-wrap">
            <svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
            <input v-model="email" type="email" placeholder="请输入邮箱" required />
          </div>
        </div>
        <div class="form-group">
          <label>密码</label>
          <div class="input-wrap">
            <svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            <input v-model="password" type="password" placeholder="请输入密码" required />
          </div>
        </div>
        <p v-if="error" class="login-error">{{ error }}</p>
        <button type="submit" class="login-btn" :disabled="loading">
          <span v-if="loading" class="btn-loading"></span>
          <span>{{ loading ? "登录中..." : "进入学习平台" }}</span>
        </button>
        <div class="login-footer">
          <span>智训云枢 &copy; 2026 — 让学习更智能</span>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { useRouter } from "vue-router"
import { login, setToken } from "../utils/api"

const router = useRouter()
const email = ref("")
const password = ref("")
const loading = ref(false)
const error = ref("")

async function handleLogin() {
  if (!email.value || !password.value) { error.value = "请填写邮箱和密码"; return }
  loading.value = true; error.value = ""
  try {
    const res = await login(email.value, password.value)
    if (res && res.access_token) { setToken(res.access_token); router.push("/dashboard") }
    else error.value = res?.detail || "登录失败"
  } catch (e) { error.value = "登录失败，请检查网络连接" }
  loading.value = false
}
</script>

<style scoped>
.login-page {
  display:flex; align-items:center; justify-content:center;
  min-height:100vh; background:var(--bg-primary); position:relative; overflow:hidden;
}
.login-bg { position:absolute; inset:0; pointer-events:none; }
.bg-grid {
  position:absolute; inset:0;
  background-image: radial-gradient(circle at 1px 1px, var(--border-color) 1px, transparent 0);
  background-size: 40px 40px; opacity:0.4;
}
.bg-orb { position:absolute; border-radius:50%; filter:blur(100px); opacity:0.12; }
.orb-1 { width:600px; height:600px; background:var(--accent-primary); top:-200px; left:-200px; animation:orbA 25s ease-in-out infinite; }
.orb-2 { width:500px; height:500px; background:var(--warm-accent); bottom:-150px; right:-150px; animation:orbB 30s ease-in-out infinite; }
.orb-3 { width:400px; height:400px; background:var(--accent-secondary); top:40%; left:60%; animation:orbC 20s ease-in-out infinite; }
@keyframes orbA { 0%,100%{transform:translate(0,0)} 50%{transform:translate(120px,80px)} }
@keyframes orbB { 0%,100%{transform:translate(0,0)} 50%{transform:translate(-100px,-60px)} }
@keyframes orbC { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(-60px,40px) scale(1.1)} }
.login-container { position:relative; z-index:1; width:100%; max-width:400px; padding:20px; }
.login-brand { text-align:center; margin-bottom:36px; }
.brand-icon {
  width:64px; height:64px; margin:0 auto 18px;
  background:var(--accent-gradient); border-radius:18px;
  display:flex; align-items:center; justify-content:center;
  color:#fff; font-size:30px; font-weight:bold; box-shadow:var(--accent-glow);
}
.login-brand h1 { font-size:30px; font-weight:700; margin-bottom:4px; background:var(--accent-gradient); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
.brand-sub { font-size:14px; color:var(--text-secondary); }
.login-form {
  background:var(--bg-glass); backdrop-filter:var(--blur-glass);
  border-radius:var(--radius-xl); padding:36px; border:1px solid var(--border-color);
  box-shadow:var(--shadow-lg);
}
.form-group { margin-bottom:20px; }
.form-group label { display:block; font-size:13px; font-weight:500; margin-bottom:6px; color:var(--text-secondary); }
.input-wrap {
  display:flex; align-items:center; gap:10px;
  padding:0 14px; border:1px solid var(--border-color); border-radius:var(--radius-md);
  background:var(--bg-primary); transition:border-color var(--transition-fast);
}
.input-wrap:focus-within { border-color:var(--accent-primary); box-shadow:0 0 0 3px rgba(99,102,241,0.1); }
.input-icon { width:18px; height:18px; color:var(--text-tertiary); flex-shrink:0; }
.input-wrap input {
  flex:1; padding:12px 0; border:none; background:transparent;
  color:var(--text-primary); font-size:14px; outline:none;
}
.login-error { color:var(--error); font-size:13px; margin-bottom:12px; }
.login-btn {
  width:100%; padding:14px; border:none; border-radius:var(--radius-md);
  background:var(--accent-gradient); color:#fff; font-size:15px; font-weight:600;
  cursor:pointer; display:flex; align-items:center; justify-content:center; gap:8px;
  transition:opacity var(--transition-fast), transform var(--transition-fast);
}
.login-btn:hover:not(:disabled) { opacity:0.92; transform:translateY(-1px); }
.login-btn:disabled { opacity:0.5; cursor:not-allowed; }
.btn-loading { width:16px; height:16px; border:2px solid rgba(255,255,255,0.3); border-top-color:#fff; border-radius:50%; animation:spin .6s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
.login-footer { text-align:center; margin-top:20px; font-size:12px; color:var(--text-tertiary); }
</style>
