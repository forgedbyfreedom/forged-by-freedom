#!/usr/bin/env python3
"""
Coach Bryan Testing Dashboard
-----------------------------
Tests the Coach Bryan API with sample questions and analyzes:
- Response quality
- Source citations
- ThinkBig appearance rate
- Response time

Usage:
    python test_coach_bryan.py                    # Run all tests
    python test_coach_bryan.py --question "..."   # Test single question
    python test_coach_bryan.py --report           # Generate report only
"""

import json
import time
import argparse
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess
    subprocess.run(["pip3", "install", "requests"], capture_output=True)
    import requests

API_URL = "http://localhost:5051/ask"
RESULTS_DIR = Path(__file__).parent / "test_results"

# Test questions covering different topics
TEST_QUESTIONS = [
    # PED/Cycle questions (should hit ThinkBig)
    {"q": "What is the best PCT protocol after a testosterone cycle?", "expect_thinkbig": True},
    {"q": "How should I dose anavar for my first cycle?", "expect_thinkbig": True},
    {"q": "What do experts say about using HGH for bodybuilding?", "expect_thinkbig": True},
    {"q": "Is trenbolone safe to use?", "expect_thinkbig": True},
    {"q": "What's a good beginner steroid cycle?", "expect_thinkbig": True},

    # Female-specific (should hit female priority sources)
    {"q": "What should women know about anavar?", "expect_female": True},
    {"q": "How does the menstrual cycle affect training?", "expect_female": True},
    {"q": "What are the best supplements for women over 40?", "expect_female": True},

    # Nutrition/Training (general)
    {"q": "How much protein should I eat to build muscle?", "expect_thinkbig": False},
    {"q": "What's the best training split for hypertrophy?", "expect_thinkbig": False},

    # Peptides (Coach Bryan specialty)
    {"q": "What are the benefits of BPC-157?", "expect_peptide": True},
    {"q": "How does retatrutide work for weight loss?", "expect_peptide": True},

    # Research/Medical
    {"q": "What does the research say about creatine?", "expect_research": True},
]

# ThinkBig channels and hosts
THINKBIG_INDICATORS = [
    "@ThinkBIGBodybuilding", "@rxmuscle", "@anabolicbodybuilding",
    "Scott McNally", "Dave Crosland", "Skipp Hill",
    "Blood Sweat", "Drugs N Stuff", "RXMuscle"
]

FEMALE_INDICATORS = [
    "Dr. Gabrielle Lyon", "John Jewett", "Holly Baxter",
    "@DrGabrielleLyon", "@johnjewett3", "@HollyBaxter"
]


def check_server():
    """Check if Coach Bryan server is running."""
    try:
        r = requests.get("http://localhost:5051/health", timeout=5)
        return r.status_code == 200
    except:
        return False


def test_question(question: str, mode: str = "synthesized") -> dict:
    """Test a single question and return results."""
    start = time.time()

    try:
        r = requests.post(API_URL, json={"question": question, "mode": mode}, timeout=120)
        elapsed = time.time() - start

        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}", "elapsed": elapsed}

        data = r.json()

        # Analyze response
        sources = data.get("sources", [])
        answer = data.get("answer", "")

        # Check for ThinkBig
        thinkbig_count = 0
        for src in sources:
            channel = src.get("channel", "")
            speaker = src.get("speaker", "")
            if any(ind.lower() in channel.lower() or ind.lower() in speaker.lower()
                   for ind in THINKBIG_INDICATORS):
                thinkbig_count += 1

        # Check for female sources
        female_count = 0
        for src in sources:
            channel = src.get("channel", "")
            speaker = src.get("speaker", "")
            if any(ind.lower() in channel.lower() or ind.lower() in speaker.lower()
                   for ind in FEMALE_INDICATORS):
                female_count += 1

        # Check answer quality
        has_forged_plug = "forgedbyfreedom" in answer.lower() or "forged by freedom" in answer.lower()
        has_coach_bryan = "coach bryan" in answer.lower()
        has_citations = any(name in answer for name in ["Scott", "Dave", "Skipp", "According to"])

        return {
            "question": question,
            "status": data.get("status", "UNKNOWN"),
            "elapsed": round(elapsed, 2),
            "source_count": len(sources),
            "thinkbig_count": thinkbig_count,
            "thinkbig_first": sources[0].get("channel", "") in ["@ThinkBIGBodybuilding", "@rxmuscle", "@anabolicbodybuilding"] if sources else False,
            "female_count": female_count,
            "has_forged_plug": has_forged_plug,
            "has_coach_bryan": has_coach_bryan,
            "has_citations": has_citations,
            "answer_length": len(answer),
            "sources": sources[:5],  # First 5 sources
            "answer_preview": answer[:500] if answer else ""
        }

    except Exception as e:
        return {"error": str(e), "elapsed": time.time() - start}


def run_all_tests():
    """Run all test questions and collect results."""
    print("\n" + "=" * 60)
    print("  COACH BRYAN TESTING DASHBOARD")
    print("=" * 60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  API: {API_URL}")
    print(f"  Tests: {len(TEST_QUESTIONS)}")
    print("=" * 60 + "\n")

    if not check_server():
        print("❌ Server not running at localhost:5051")
        print("   Start with: cd forged-by-freedom && node index.js")
        return []

    results = []

    for i, test in enumerate(TEST_QUESTIONS, 1):
        q = test["q"]
        print(f"[{i}/{len(TEST_QUESTIONS)}] {q[:50]}...")

        result = test_question(q)
        result["expected"] = test
        results.append(result)

        if "error" in result:
            print(f"  ❌ Error: {result['error']}")
        else:
            status_icon = "✅" if result["status"] == "OK" else "⚠️"
            thinkbig_icon = "🎯" if result["thinkbig_count"] > 0 else "  "
            print(f"  {status_icon} {result['elapsed']}s | {result['source_count']} sources | {thinkbig_icon} ThinkBig: {result['thinkbig_count']}")

    return results


def generate_report(results: list):
    """Generate summary report."""
    print("\n" + "=" * 60)
    print("  TEST RESULTS SUMMARY")
    print("=" * 60)

    if not results:
        print("No results to report")
        return

    # Calculate metrics
    total = len(results)
    successful = sum(1 for r in results if r.get("status") == "OK")
    errors = sum(1 for r in results if "error" in r)

    thinkbig_hits = sum(1 for r in results if r.get("thinkbig_count", 0) > 0)
    thinkbig_first = sum(1 for r in results if r.get("thinkbig_first", False))

    avg_sources = sum(r.get("source_count", 0) for r in results) / max(total, 1)
    avg_time = sum(r.get("elapsed", 0) for r in results) / max(total, 1)

    forged_plugs = sum(1 for r in results if r.get("has_forged_plug", False))
    coach_bryan = sum(1 for r in results if r.get("has_coach_bryan", False))

    print(f"""
  📊 METRICS
  ────────────────────────────────────
  Total Tests:     {total}
  Successful:      {successful} ({successful*100//total}%)
  Errors:          {errors}

  ⏱️  PERFORMANCE
  ────────────────────────────────────
  Avg Response:    {avg_time:.2f}s
  Avg Sources:     {avg_sources:.1f}

  🎯 THINKBIG PRIORITY
  ────────────────────────────────────
  ThinkBig Hits:   {thinkbig_hits}/{total} ({thinkbig_hits*100//total}%)
  ThinkBig First:  {thinkbig_first}/{total} ({thinkbig_first*100//total}%)

  📝 RESPONSE QUALITY
  ────────────────────────────────────
  FBF Plug:        {forged_plugs}/{total} ({forged_plugs*100//total}%)
  Coach Bryan:     {coach_bryan}/{total} ({coach_bryan*100//total}%)
""")

    # Check expected results
    print("  🔍 EXPECTATION CHECKS")
    print("  ────────────────────────────────────")

    for r in results:
        if "error" in r:
            continue

        expected = r.get("expected", {})
        q_short = r["question"][:40]

        if expected.get("expect_thinkbig") and r.get("thinkbig_count", 0) == 0:
            print(f"  ⚠️  Missing ThinkBig: {q_short}...")

        if expected.get("expect_female") and r.get("female_count", 0) == 0:
            print(f"  ⚠️  Missing Female source: {q_short}...")

    print("=" * 60)

    # Save results
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"test_results_{timestamp}.json"

    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n  📁 Results saved: {results_file}")


def main():
    parser = argparse.ArgumentParser(description="Coach Bryan Testing Dashboard")
    parser.add_argument("--question", "-q", help="Test a single question")
    parser.add_argument("--report", action="store_true", help="Load and report last results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full answers")
    args = parser.parse_args()

    if args.question:
        if not check_server():
            print("❌ Server not running")
            return

        result = test_question(args.question)
        print(json.dumps(result, indent=2))

    elif args.report:
        # Load most recent results
        results_files = sorted(RESULTS_DIR.glob("test_results_*.json"))
        if results_files:
            with open(results_files[-1]) as f:
                results = json.load(f)
            generate_report(results)
        else:
            print("No previous results found")

    else:
        results = run_all_tests()
        generate_report(results)


if __name__ == "__main__":
    main()
