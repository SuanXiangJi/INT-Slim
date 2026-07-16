"""Tests for all new services: rule engine, KG+RAG, cognitive diagnosis, evidence tracker, path planner."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("PYTHONPATH", os.path.join(os.path.dirname(__file__), "..", "backend"))

async def test_rule_engine():
    from app.services.rule_engine import get_rule_engine
    engine = get_rule_engine()
    
    # Test 1: List rules
    rules = engine.list_rules()
    assert len(rules) >= 4, f"Expected >=4 rules, got {len(rules)}"
    print(f"  [PASS] Rule engine: {len(rules)} rules loaded")
    
    # Test 2: Evaluate load rule
    results = await engine.evaluate("load", cognitive_load=0.9, load_threshold=0.8, plan_difficulty=0.5)
    assert len(results) == 1
    load_result = results[0]
    assert not load_result.passed, "High load should fail"
    print(f"  [PASS] Load rule correctly fails: {load_result.message[:50]}")
    
    # Test 3: Evaluate load rule (safe)
    results2 = await engine.evaluate("load", cognitive_load=0.2, load_threshold=0.8, plan_difficulty=0.3)
    assert results2[0].passed
    print(f"  [PASS] Load rule correctly passes for low load")
    
    # Test 4: Evaluate evidence rule
    content_no_evidence = {"title": "Test", "sections": [{"body": "content"}]}
    results3 = await engine.evaluate("quality", content=content_no_evidence)
    evidence_result = results3[0] if results3 else None
    if evidence_result:
        print(f"  [PASS] Evidence rule: {evidence_result.passed} - {evidence_result.message[:50]}")
    
    # Test 5: Evaluate all rules
    all_results = await engine.evaluate_all(
        content={"title": "Test", "evidence_map": [{"claim": "test", "source": "doc", "confidence": "high"}]},
        mastery={}, cognitive_load=0.3, load_threshold=0.8,
    )
    print(f"  [PASS] All rules evaluated: {len(all_results)} results")
    return True

async def test_kg_rag():
    from app.services.kg_rag_service import get_kg_rag_service
    kg = get_kg_rag_service()
    
    # Test: KG graph operations
    kg.graph.add_node("kp1", "Python基础", "编程", "Python basics", 0.3)
    kg.graph.add_node("kp2", "Python进阶", "编程", "Advanced Python", 0.7)
    kg.graph.add_edge("kp1", "kp2", "prerequisite")
    
    prereqs = kg.graph.get_prerequisites("kp2")
    assert "kp1" in prereqs, "kp1 should be prerequisite of kp2"
    print(f"  [PASS] KG: prerequisite relationship works")
    
    path = kg.graph.find_path("kp2")
    assert len(path) >= 2, f"Path should have >=2 nodes, got {len(path)}"
    print(f"  [PASS] KG: find_path returns {path}")
    
    # Test: TF-IDF search (with minimal data)
    kg.tfidf.add_document("d1", "Python programming language tutorial", {"course": "Python"})
    kg.tfidf.build()
    scored = kg.tfidf.search("python", 3)
    print(f"  [PASS] TF-IDF: search returns {len(scored)} results")
    return True

def test_cognitive_diagnosis():
    from app.services.cognitive_diagnosis import get_diagnosis_service
    diag = get_diagnosis_service()
    
    # Test 1: New learner (no history)
    d1 = diag.diagnose("kp1", "Python基础", 0, 0)
    assert 0 < d1.mastery_prob < 1, f"Mastery should be between 0-1, got {d1.mastery_prob}"
    print(f"  [PASS] New learner mastery: {d1.mastery_prob:.3f}")
    
    # Test 2: Good learner
    d2 = diag.diagnose("kp1", "Python基础", 8, 10)
    assert d2.mastery_prob > 0.5, "Good learner should have high mastery"
    print(f"  [PASS] Good learner mastery: {d2.mastery_prob:.3f}")
    
    # Test 3: Poor learner
    d3 = diag.diagnose("kp1", "Python基础", 2, 10)
    assert d3.struggling or d3.mastery_prob < 0.5, "Poor learner should struggle"
    print(f"  [PASS] Poor learner correctly identified as struggling")
    
    # Test 4: Elo rating
    new_rating, new_diff = diag.estimate_elo_change(1500, 1500, True)
    assert new_rating > 1500, "Correct answer should increase rating"
    print(f"  [PASS] Elo rating correctly updates: {new_rating:.0f}")
    
    # Test 5: Forgetting curve
    retained = diag.apply_forgetting_curve(0.8, 30)
    assert retained < 0.8, "Mastery should decay over time"
    print(f"  [PASS] Forgetting curve: mastery {0.8} -> {retained:.3f} after 30 days")
    
    # Test 6: Review schedule
    days = diag.estimate_next_review_days(0.4)
    assert days <= 3, f"Low mastery should recommend soon review, got {days} days"
    print(f"  [PASS] Review schedule: {days} days for mastery 0.4")
    return True

def test_evidence_tracker():
    from app.services.evidence_tracker import get_evidence_tracker
    tracker = get_evidence_tracker()
    
    # Test 1: Track a claim
    tracker.start_tracking("content_1", "Test Content")
    cid = tracker.add_claim("Python is dynamically typed", "kb_document", "doc_1", "Python教程", "high")
    assert cid, "Should return claim_id"
    
    # Test 2: Verify claim
    assert tracker.verify_claim(cid, "manual"), "Should verify successfully"
    
    # Test 3: Generate report
    report = tracker.generate_report("content_1")
    assert report.total_claims == 1
    assert report.verified_claims == 1
    print(f"  [PASS] Evidence report: {report.total_claims} claims, {report.verified_claims} verified")
    
    # Test 4: Track from evidence_map
    report2 = tracker.track_content(
        {"title": "Python", "sections": [{"body": "Dynamic typing [来源:Python教程]"}]},
        [{"claim": "Dynamic typing", "source": "doc_1", "source_name": "Python教程", "confidence": "high", "verified": True}],
        "content_2"
    )
    assert report2.total_claims >= 1
    print(f"  [PASS] Evidence from content: {report2.total_claims} claims, confidence={report2.overall_confidence}")
    return True

def test_path_planner():
    from app.services.path_planner import get_path_planner
    planner = get_path_planner()
    
    # Test data
    kps = [
        {"id": "kp1", "name": "Python基础语法", "difficulty": 0.3},
        {"id": "kp2", "name": "Python数据结构", "difficulty": 0.5},
        {"id": "kp3", "name": "Python面向对象", "difficulty": 0.6},
        {"id": "kp4", "name": "Python高级特性", "difficulty": 0.8},
    ]
    prereq_map = {"kp2": ["kp1"], "kp3": ["kp2"], "kp4": ["kp3", "kp1"]}
    mastery = {"kp1": {"level": 0.8}, "kp2": {"level": 0.3}, "kp3": {"level": 0.1}}
    
    # Test 1: Full path planning
    path = planner.plan(
        goal="掌握Python进阶",
        available_kps=kps,
        prerequisite_map=prereq_map,
        learner_mastery=mastery,
        cognitive_load=0.3,
        focus_areas=["Python"],
    )
    assert len(path.nodes) > 0, "Should have nodes"
    assert path.total_hours > 0, "Should have estimated hours"
    print(f"  [PASS] Path plan: {len(path.nodes)} nodes, {path.total_hours}h total")
    
    # Test 2: Nodes are in correct topological order
    if len(path.nodes) >= 2:
        for i, node in enumerate(path.nodes):
            if node.kp_id in prereq_map:
                for prereq in prereq_map[node.kp_id]:
                    prereq_idx = next((j for j, n in enumerate(path.nodes) if n.kp_id == prereq), -1)
                    if prereq_idx >= 0:
                        assert prereq_idx < i, f"Prereq {prereq} should come before {node.kp_id}"
        print(f"  [PASS] Nodes in correct topological order")
    
    # Test 3: Weekly schedule
    assert path.weekly_schedule, "Should have weekly schedule"
    print(f"  [PASS] Schedule: {path.weekly_schedule[:100]}...")
    
    # Test 4: Topological sort
    sorted_nodes = planner._topological_sort({"kp1", "kp2", "kp3", "kp4"}, prereq_map, {k["id"]: k for k in kps})
    node_order = [n[0] for n in sorted_nodes]
    assert node_order[0] == "kp1", "kp1 should be first"
    print(f"  [PASS] Topo sort order: {' -> '.join(node_order)}")
    return True

async def main():
    print("=" * 50)
    print("SERVICE TESTS")
    print("=" * 50)
    
    tests = [
        ("Rule Engine", test_rule_engine()),
        ("KG + RAG", test_kg_rag()),
        ("Cognitive Diagnosis", asyncio.to_thread(test_cognitive_diagnosis)),
        ("Evidence Tracker", asyncio.to_thread(test_evidence_tracker)),
        ("Path Planner", asyncio.to_thread(test_path_planner)),
    ]
    
    passed = 0
    for name, coro in tests:
        print(f"\n--- {name} ---")
        try:
            if asyncio.iscoroutine(coro):
                result = await coro
            else:
                result = await coro
            if result:
                passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            import traceback; traceback.print_exc()
    
    print(f"\n{'=' * 50}")
    print(f"PASSED: {passed}/{len(tests)}")
    print(f"{'=' * 50}")

if __name__ == "__main__":
    asyncio.run(main())