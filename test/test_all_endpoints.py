"""Comprehensive API endpoint test"""
import httpx, json, sys, asyncio

BASE = "http://localhost:8000/api/v1"
TOKEN = None
passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ✅ {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        failed += 1

# ── Auth ──
def test_auth():
    global TOKEN
    r = httpx.post(f"{BASE}/auth/login/json", json={"email": "demo@example.com", "password": "change-me"})
    assert r.status_code == 200, f"Login failed: {r.text[:200]}"
    data = r.json()
    TOKEN = data["access_token"]
    assert len(TOKEN) > 20

    r = httpx.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert r.json().get("email") == "demo@example.com"

    r = httpx.get(f"{BASE}/auth/tokens", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200

test("Auth: login + me + tokens", test_auth)

headers = {"Authorization": f"Bearer {TOKEN}"}

# ── Models ──
def test_models():
    r = httpx.get(f"{BASE}/models/available", headers=headers)
    assert r.status_code == 200
    data = r.json()
    models = data.get("models") or data.get("available_models", [])
    assert len(models) >= 2

test("Models: list", test_models)

# ── Agent ──
def test_agent():
    r = httpx.get(f"{BASE}/agent/config", headers=headers)
    assert r.status_code == 200
    r = httpx.get(f"{BASE}/agent/tools", headers=headers)
    assert r.status_code == 200
    r = httpx.get(f"{BASE}/agent/tools/enabled", headers=headers)
    assert r.status_code == 200
    r = httpx.post(f"{BASE}/agent/sandbox/init", headers=headers)
    assert r.status_code == 200

test("Agent: config+tools+sandbox", test_agent)

# ── Profile ──
def test_profile():
    r = httpx.get(f"{BASE}/user/profile", headers=headers)
    assert r.status_code == 200
    r = httpx.get(f"{BASE}/user/profile/context", headers=headers)
    assert r.status_code == 200

test("Profile: get+context", test_profile)

# ── KB ──
def test_kb():
    r = httpx.get("http://localhost:8000/api/knowledge/index.json")
    assert r.status_code == 200
    data = r.json()
    assert "topics" in data
    assert len(data["topics"]) >= 10

    r = httpx.post(f"{BASE}/knowledge-base/search", headers=headers, json={"query": "python", "top_k": 3})
    assert r.status_code == 200

    r = httpx.get(f"{BASE}/knowledge-base/documents", headers=headers)
    assert r.status_code == 200

test("KB: index+search+docs", test_kb)

# ── Learners ──
def test_learners():
    r = httpx.get(f"{BASE}/learning/learners", headers=headers)
    assert r.status_code == 200
    learners = r.json()
    if learners:
        lid = learners[0]["id"]
        r = httpx.get(f"{BASE}/learning/learners/{lid}", headers=headers)
        assert r.status_code == 200
    r = httpx.get(f"{BASE}/learning/knowledge-points", headers=headers)
    assert r.status_code == 200

test("Learners: list+get", test_learners)

# ── Conversations ──
async def test_conversations_async():
    async with httpx.AsyncClient(timeout=30) as c:
        # Create
        r = await c.post(f"{BASE}/conversations", headers=headers, json={"title": "test-api"})
        assert r.status_code == 200
        conv = r.json()
        cid = conv["id"]
        assert len(cid) > 10

        # List
        r = await c.get(f"{BASE}/conversations", headers=headers)
        assert r.status_code == 200

        # Get single
        r = await c.get(f"{BASE}/conversations/{cid}", headers=headers)
        assert r.status_code == 200

        # Rename
        r = await c.put(f"{BASE}/conversations/{cid}", headers=headers, json={"title": "renamed"})
        assert r.status_code == 200

        # Delete
        r = await c.delete(f"{BASE}/conversations/{cid}", headers=headers)
        assert r.status_code == 200

asyncio.run(test_conversations_async())

def test_quick_agent():
    """Test quick and agent mode via streaming"""
    import asyncio
    async def _run():
        async with httpx.AsyncClient(timeout=60) as c:
            cr = await c.post(f"{BASE}/conversations", headers=headers, json={"title": "stream-test"})
            cid = cr.json()["id"]

            # Quick mode
            async with c.stream("POST", f"{BASE}/conversations/{cid}/messages",
                headers=headers, json={"content": "hi", "enable_agent": False, "model": "deepseek:deepseek-v4-flash"}) as resp:
                assert resp.status_code == 200

            # Agent mode
            async with c.stream("POST", f"{BASE}/conversations/{cid}/messages",
                headers=headers, json={"content": "现在几点了？", "enable_agent": True, "model": "deepseek:deepseek-v4-flash"}) as resp:
                assert resp.status_code == 200

    asyncio.run(_run())

test("Conversations: CRUD", lambda: None)
test("Quick + Agent streaming", test_quick_agent)

total = passed + failed
print(f"\n{'='*40}")
print(f"   Total: {total}  |  ✅ Passed: {passed}  |  ❌ Failed: {failed}")
print(f"{'='*40}")

