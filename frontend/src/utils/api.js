// API璇锋眰宸ュ叿
const API_BASE_URL = 'http://localhost:8000/api/v1';

// ============ 缂撳瓨閰嶇疆 ============
const CACHE_PREFIX = 'xbots_cache_';
const CACHE_EXPIRY = 5 * 60 * 1000; // 5鍒嗛挓缂撳瓨杩囨湡

// 鑾峰彇token
const getToken = () => {
  return localStorage.getItem('token');
};

// 璁剧疆token
const setToken = (token) => {
  localStorage.setItem('token', token);
};

// 绉婚櫎token
const removeToken = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('userInfo');
  currentUserCache = null;
  currentUserCacheAt = 0;
  currentUserRequest = null;
  // 娓呴櫎鎵€鏈夌紦瀛?
  clearAllCache();
};

// 妫€鏌ョ敤鎴锋槸鍚﹀凡鐧诲綍
const isLoggedIn = () => {
  const token = getToken();
  return !!token;
};

// 鑾峰彇褰撳墠鐧诲綍鐢ㄦ埛淇℃伅
const getCurrentUserInfo = () => {
  const userInfo = localStorage.getItem('userInfo');
  return userInfo ? JSON.parse(userInfo) : null;
};

// ============ 缂撳瓨宸ュ叿 ============
const getCache = (key) => {
  const cached = localStorage.getItem(CACHE_PREFIX + key);
  if (!cached) return null;

  try {
    const { data, timestamp } = JSON.parse(cached);
    const now = Date.now();

    // 妫€鏌ユ槸鍚﹁繃鏈?
    if (now - timestamp > CACHE_EXPIRY) {
      localStorage.removeItem(CACHE_PREFIX + key);
      return null;
    }

    return data;
  } catch {
    return null;
  }
};

const setCache = (key, data) => {
  try {
    localStorage.setItem(CACHE_PREFIX + key, JSON.stringify({
      data,
      timestamp: Date.now()
    }));
  } catch (e) {
    console.warn('缂撳瓨鍐欏叆澶辫触:', e);
  }
};

const clearCache = (key) => {
  localStorage.removeItem(CACHE_PREFIX + key);
};

const clearAllCache = () => {
  const keys = Object.keys(localStorage);
  keys.forEach(key => {
    if (key.startsWith(CACHE_PREFIX)) {
      localStorage.removeItem(key);
    }
  });
};

let currentUserCache = null;
let currentUserCacheAt = 0;
let currentUserRequest = null;
const CURRENT_USER_TTL = 2000;

const formatApiError = (detail, fallback = '请求失败') => {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map(item => {
      if (typeof item === 'string') return item;
      const field = Array.isArray(item?.loc) ? item.loc.filter(part => part !== 'body').join('.') : '';
      return [field, item?.msg].filter(Boolean).join('：');
    }).filter(Boolean);
    if (messages.length) return messages.join('；');
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback;
  }
  return fallback;
};

// ============ 鍩虹璇锋眰鍑芥暟 ============
const request = async (url, options = {}) => {
  const token = getToken();

  const config = {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  // 濡傛灉鏈塼oken锛屾坊鍔犲埌璇锋眰澶?
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_BASE_URL}${url}`, config);

    // 瑙ｆ瀽鍝嶅簲鏁版嵁
    const data = await response.json();

    // 澶勭悊閿欒鍝嶅簲
    if (!response.ok) {
      // 濡傛灉鏄?01閿欒涓斾笉鏄埛鏂皌oken璇锋眰锛屽皾璇曞埛鏂皌oken
      if (response.status === 401 && url !== '/auth/refresh-token') {
        // 灏濊瘯鍒锋柊token
        const refreshResponse = await refreshToken();

        // 淇濆瓨鏂皌oken
        setToken(refreshResponse.access_token);

        // 鏇存柊璇锋眰澶翠腑鐨則oken
        config.headers.Authorization = `Bearer ${refreshResponse.access_token}`;

        // 閲嶆柊鍙戦€佸師濮嬭姹?
        const retryResponse = await fetch(`${API_BASE_URL}${url}`, config);
        const retryData = await retryResponse.json();

        if (!retryResponse.ok) {
          throw new Error(formatApiError(retryData.detail));
        }

        return retryData;
      }

      throw new Error(formatApiError(data.detail));
    }

    return data;
  } catch (error) {
    console.error('API璇锋眰閿欒:', error);
    throw error;
  }
};

// 鐧诲綍
const apiGet = (url) => request(url, { method: 'GET' });
const apiPost = (url, data) => request(url, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } });
const apiPut = (url, data) => request(url, { method: 'PUT', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } });
const apiDelete = (url) => request(url, { method: 'DELETE' });

const streamCodeEvaluation = async (assessmentId, code, onEvent) => {
  const response = await fetch(`${API_BASE_URL}/learning/code-practice/${assessmentId}/submit-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ code }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(formatApiError(data.detail, '评测请求失败'));
  }
  if (!response.body) throw new Error('浏览器无法读取评测进度流。');
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let finalResult = null;
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || '';
    for (const block of blocks) {
      const raw = block.split(/\r?\n/).find(line => line.startsWith('data: '))?.slice(6);
      if (!raw) continue;
      const event = JSON.parse(raw);
      onEvent?.(event);
      if (event.type === 'result') finalResult = event;
    }
    if (done) break;
  }
  if (!finalResult) throw new Error('评测已结束，但没有收到评分结果。');
  return finalResult;
};

const login = async (email, password) => {
  const result = await request('/auth/login/json', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  // 鐧诲綍鎴愬姛鍚庢竻闄ゆ棫缂撳瓨
  clearAllCache();
  return result;
};

// 娉ㄥ唽
const register = async (userData) => {
  return request('/auth/register', {
    method: 'POST',
    body: JSON.stringify(userData),
  });
};

// 鍙戦€侀獙璇佺爜
const sendVerificationCode = async (email, purpose = 'register') => {
  return request('/auth/send-code', {
    method: 'POST',
    body: JSON.stringify({ email, purpose }),
  });
};

// 楠岃瘉楠岃瘉鐮?
const verifyVerificationCode = async (email, code, purpose = 'register') => {
  return request('/auth/verify-code', {
    method: 'POST',
    body: JSON.stringify({ email, code, purpose }),
  });
};

// 鑾峰彇褰撳墠鐢ㄦ埛淇℃伅
const getCurrentUser = async () => {
  const now = Date.now();
  if (currentUserCache && now - currentUserCacheAt < CURRENT_USER_TTL) {
    return currentUserCache;
  }
  if (currentUserRequest) return currentUserRequest;
  currentUserRequest = request('/auth/me')
    .then(user => {
      currentUserCache = user;
      currentUserCacheAt = Date.now();
      try { localStorage.setItem('userInfo', JSON.stringify(user)); } catch {}
      return user;
    })
    .finally(() => {
      currentUserRequest = null;
    });
  return currentUserRequest;
};

// 鍒锋柊token
const refreshToken = async () => {
  return request('/auth/refresh-token', {
    method: 'POST',
  });
};

// 閫€鍑虹櫥褰?
const logout = async () => {
  try {
    await request('/auth/logout', {
      method: 'POST',
    });
  } finally {
    removeToken();
  }
};

// 鑾峰彇瀵硅瘽鍒楄〃锛堝甫缂撳瓨锛?
const getConversations = async (useCache = true) => {
  const cacheKey = 'conversations';

  // 灏濊瘯浠庣紦瀛樿幏鍙?
  if (useCache) {
    const cached = getCache(cacheKey);
    if (cached) {
      return cached;
    }
  }

  // 浠庢湇鍔″櫒鑾峰彇
  const data = await request('/conversations');

  // 鏇存柊缂撳瓨
  setCache(cacheKey, data);

  return data;
};

// 鍒涘缓鏂板璇?
const createConversation = async (title = 'New Chat') => {
  const data = await request('/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  });

  // 鏇存柊瀵硅瘽鍒楄〃缂撳瓨
  const cached = getCache('conversations');
  if (cached) {
    setCache('conversations', [data, ...cached]);
  }

  return data;
};

// 鑾峰彇瀵硅瘽娑堟伅锛堝甫缂撳瓨锛?
const getConversationMessages = async (conversationId, useCache = true) => {
  const cacheKey = `messages_${conversationId}`;

  // 灏濊瘯浠庣紦瀛樿幏鍙?
  if (useCache) {
    const cached = getCache(cacheKey);
    if (cached) {
      return cached;
    }
  }

  // 浠庢湇鍔″櫒鑾峰彇
  const data = await request(`/conversations/${conversationId}/messages`);

  // 鏇存柊缂撳瓨
  setCache(cacheKey, data);

  return data;
};

// 鍙戦€佹秷鎭紙娴佸紡锛?
const sendMessage = async (conversationId, content, model, onMessage, onChunk, onComplete, onError, enableAgent = false, options = {}) => {
  const token = getToken();
  const url = `${API_BASE_URL}/conversations/${conversationId}/messages`;

  // Build request body
  const body = { content };
  if (model) {
    body.model = model;
  }
  if (enableAgent) {
    body.enable_agent = true;
  }

  // 娓呴櫎璇ュ璇濈殑娑堟伅缂撳瓨锛堝彂閫佹柊娑堟伅鍚庢棫缂撳瓨澶辨晥锛?
  clearCache(`messages_${conversationId}`);
  // 娓呴櫎瀵硅瘽鍒楄〃缂撳瓨锛堝彲鑳芥湁鏂板璇濓級
  clearCache('conversations');

  // AbortSignal is optional; lets the UI cancel an in-flight stream (e.g. pause button).
  const externalSignal = options && options.signal;
  const controller = new AbortController();
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else externalSignal.addEventListener('abort', () => controller.abort());
  }

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullResponse = '';
    let buffer = '';
    let aborted = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        if (!aborted) onComplete(fullResponse);
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // Process each SSE event
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line in buffer

      for (const line of lines) {
        if (!line || line.startsWith(':')) continue; // Ignore empty lines and comments

        if (line === 'data: [DONE]') {
          onComplete(fullResponse);
          return;
        }

        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const parsedData = JSON.parse(data);

            // Handle different event types
            // assistant_chunk / title_update are kept for legacy (non-agent) flow.
            // The newer agent emits thinking / action / observation / reflection / ask / run_done.
            switch (parsedData.type) {
              case 'assistant_chunk':
                fullResponse += parsedData.content;
                if (onChunk) onChunk(parsedData.content);
                break;

              case 'title_update':
                if (onChunk) onChunk({ type: 'title_update', data: parsedData.data });
                clearCache('conversations');
                break;

              // ---- New autonomous-agent events ----
              case 'thinking':
              case 'action':
              case 'observation':
              case 'reflection':
              case 'ask':
              case 'run_done':
                if (onChunk) onChunk({ type: parsedData.type, data: parsedData.data });
                break;

              // ---- Legacy events (no longer emitted but kept for back-compat) ----
              case 'tool_call':
              case 'tool_result':
              case 'tool_start':
              case 'tool_end':
                if (onChunk) onChunk({ type: parsedData.type, data: parsedData.data });
                break;
            }
          } catch (error) {
            console.error('Error parsing SSE message:', error);
            console.error('Raw message:', data);
          }
        }
      }
    }
  } catch (error) {
    if (error && error.name === 'AbortError') {
      // User pressed pause / stop. Treat as a soft cancel 鈥?don't show an error toast.
      return;
    }
    console.error('Error sending message:', error);
    onError(error);
  }
};

// 鍒犻櫎瀵硅瘽
const deleteConversation = async (conversationId) => {
  await request(`/conversations/${conversationId}`, {
    method: 'DELETE',
  });

  // 娓呴櫎缂撳瓨
  clearCache(`messages_${conversationId}`);
  clearCache('conversations');
};

// 鏇存柊瀵硅瘽鏍囬
const updateConversationTitle = async (conversationId, title) => {
  const data = await request(`/conversations/${conversationId}`, {
    method: 'PUT',
    body: JSON.stringify({ title }),
  });

  // 鏇存柊瀵硅瘽鍒楄〃缂撳瓨
  const cached = getCache('conversations');
  if (cached) {
    const updated = cached.map(conv =>
      conv.id === conversationId ? { ...conv, title } : conv
    );
    setCache('conversations', updated);
  }

  return data;
};

// 鏇存柊娑堟伅鏀惰棌鐘舵€?
const updateMessageFavor = async (messageId, isFavored) => {
  return request(`/messages/${messageId}/favor`, {
    method: 'PUT',
    body: JSON.stringify({ is_favored: isFavored }),
  });
};

// 鍒犻櫎娑堟伅
const deleteMessage = async (messageId) => {
  return request(`/messages/${messageId}`, {
    method: 'DELETE',
  });
};


// ============ User Profile ============
const getMyProfile = async (includeContext = false) => {
  const q = includeContext ? '?include_context=true' : ''
  return request(`/user/profile${q}`)
}

const updateMyProfile = async (patch) => {
  return request('/user/profile', {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

const analyzeMyProfile = async ({ force = false, message_count = 20 } = {}) => {
  return request('/user/profile/analyze', {
    method: 'POST',
    body: JSON.stringify({ force, message_count }),
  })
}

const resetMyProfile = async () => {
  return request('/user/profile', { method: 'DELETE' })
}

const getProfileContext = async () => {
  return request('/user/profile/context')
}

export {
  request,
  login,
  register,
  sendVerificationCode,
  verifyVerificationCode,
  getCurrentUser,
  refreshToken,
  logout,
  getConversations,
  createConversation,
  getConversationMessages,
  sendMessage,
  deleteConversation,
  updateConversationTitle,
  updateMessageFavor,
  deleteMessage,
  getToken,
  setToken,
  removeToken,
  isLoggedIn,
  getCurrentUserInfo,
  clearCache,
  clearAllCache,
  apiGet,
  apiPost,
  apiPut,
  apiDelete,
  streamCodeEvaluation,
  // User profile
  getMyProfile,
  updateMyProfile,
  analyzeMyProfile,
  resetMyProfile,
  getProfileContext,
};

