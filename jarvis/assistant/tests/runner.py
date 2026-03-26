"""
JARVIS Test Runner — benchmark and regression test framework.

Runs all test suites against the live assistant (requires Ollama running),
stores results as timestamped JSON, and generates an HTML dashboard showing
trends over time.

Usage:
    cd jarvis/assistant
    python tests/runner.py                    # run all test suites
    python tests/runner.py --suite intent     # run only intent classification tests
    python tests/runner.py --suite enrichment # run only enrichment tests
    python tests/runner.py --suite latency    # run only latency benchmarks
    python tests/runner.py --dashboard        # regenerate dashboard from existing results

Results go to tests/results/<timestamp>.json
Dashboard at tests/results/dashboard.html
"""

import sys
import os
import json
import time
import html
import argparse
import platform
from datetime import datetime
from pathlib import Path

# Add assistant/ to path so we can import providers
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import config
from core.logger import get_logger

log = get_logger("tests.runner")


RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def _get_system_info() -> dict:
    """Capture system info for result context."""
    brain_cfg = config.get("brain", {})
    return {
        "platform": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "model": brain_cfg.get("model", "unknown"),
        "endpoint": brain_cfg.get("endpoint", "unknown"),
    }


def _check_ollama() -> bool:
    """Verify Ollama is reachable before running tests."""
    import requests
    endpoint = config.get("brain", {}).get("endpoint", "http://localhost:11434")
    try:
        resp = requests.get(f"{endpoint}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def run_suite(suite_name: str, brain) -> dict:
    """Run a specific test suite and return results."""
    if suite_name == "intent":
        from tests.test_intent import run_intent_tests
        return run_intent_tests(brain)
    elif suite_name == "enrichment":
        from tests.test_enrichment import run_enrichment_tests
        return run_enrichment_tests(brain)
    elif suite_name == "personality":
        from tests.test_personality import run_personality_tests
        return run_personality_tests(brain)
    elif suite_name == "knowledge":
        from tests.test_knowledge import run_knowledge_tests
        return run_knowledge_tests()
    elif suite_name == "latency":
        from tests.test_latency import run_latency_tests
        return run_latency_tests(brain)
    elif suite_name == "prefilter":
        from tests.test_prefilter import run_prefilter_tests
        return run_prefilter_tests()
    elif suite_name == "integration":
        from tests.test_integration import run_integration_tests
        return run_integration_tests()
    else:
        raise ValueError(f"Unknown suite: {suite_name}")


ALL_SUITES = ["prefilter", "intent", "enrichment", "personality", "knowledge", "latency", "integration"]


def run_all(suites: list[str] = None) -> dict:
    """Run test suites, store results, generate dashboard."""
    suites = suites or ALL_SUITES

    print(f"\n{'═' * 60}")
    print(f"  JARVIS Test Runner")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═' * 60}\n")

    # Pre-flight: check Ollama
    if not _check_ollama():
        print("ERROR: Ollama is not running. Start it with: ollama serve")
        sys.exit(1)
    print("✓ Ollama is running\n")

    # Build brain provider (we need it for most tests)
    from core.registry import get_provider
    import providers  # noqa: F401 — trigger auto-discovery

    brain_cfg = config.get("brain", {})
    brain = get_provider(
        "brain",
        brain_cfg.get("provider", "ollama"),
        model=brain_cfg.get("model"),
        endpoint=brain_cfg.get("endpoint"),
    )
    print(f"✓ Brain loaded: {brain.model}")

    # Warm the KV cache by running a throwaway classification.
    # The first classify_intent call is 2-4x slower because Ollama must
    # compile the system prompt's KV cache. Running one dummy call here
    # ensures all timed tests measure steady-state performance.
    print("  Warming KV cache (one throwaway classification)...")
    try:
        brain.classify_intent("hello")
        print("✓ KV cache warm\n")
    except Exception as e:
        print(f"⚠ KV warmup failed: {e} (first test may be slow)\n")

    # Run suites
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {
        "timestamp": datetime.now().isoformat(),
        "system": _get_system_info(),
        "suites": {},
        "summary": {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "score": 0.0,
            "total_latency": 0.0,
        },
    }

    for suite_name in suites:
        print(f"{'─' * 40}")
        print(f"  Running: {suite_name}")
        print(f"{'─' * 40}")

        try:
            suite_result = run_suite(suite_name, brain)
            results["suites"][suite_name] = suite_result

            passed = suite_result.get("passed", 0)
            total = suite_result.get("total", 0)
            score = (passed / total * 100) if total > 0 else 0
            latency = suite_result.get("total_latency", 0)

            results["summary"]["total_tests"] += total
            results["summary"]["passed"] += passed
            results["summary"]["failed"] += total - passed
            results["summary"]["total_latency"] += latency

            status = "✓" if passed == total else "✗"
            print(f"  {status} {suite_name}: {passed}/{total} ({score:.0f}%) — {latency:.2f}s\n")

        except Exception as e:
            print(f"  ✗ {suite_name}: CRASHED — {e}\n")
            results["suites"][suite_name] = {
                "total": 0, "passed": 0, "error": str(e),
                "tests": [], "total_latency": 0,
            }

    # Compute overall score
    total = results["summary"]["total_tests"]
    if total > 0:
        results["summary"]["score"] = results["summary"]["passed"] / total * 100

    # Save results
    result_path = RESULTS_DIR / f"{timestamp}.json"
    with open(result_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"{'═' * 60}")
    print(f"  Results saved: {result_path.name}")

    # Print summary
    s = results["summary"]
    print(f"  Score: {s['passed']}/{s['total_tests']} ({s['score']:.1f}%)")
    print(f"  Total latency: {s['total_latency']:.2f}s")
    print(f"{'═' * 60}\n")

    # Generate dashboard
    generate_dashboard()
    print(f"  Dashboard: tests/results/dashboard.html\n")

    return results


def generate_dashboard():
    """Generate HTML dashboard from all stored results."""
    # Load all result files
    result_files = sorted(RESULTS_DIR.glob("*.json"))
    all_runs = []
    for f in result_files:
        try:
            with open(f) as fh:
                all_runs.append(json.load(fh))
        except json.JSONDecodeError:
            continue

    if not all_runs:
        print("  No results to build dashboard from.")
        return

    # Build dashboard HTML
    html = _build_dashboard_html(all_runs)
    dashboard_path = RESULTS_DIR / "dashboard.html"
    with open(dashboard_path, "w") as f:
        f.write(html)


def _build_dashboard_html(all_runs: list[dict]) -> str:
    """Build the HTML dashboard with charts."""

    # Prepare data for charts
    labels = []
    scores = []
    latencies = []
    suite_data = {}  # suite_name -> list of scores

    for run in all_runs:
        ts = run.get("timestamp", "")[:16]
        labels.append(ts)
        scores.append(run.get("summary", {}).get("score", 0))
        latencies.append(run.get("summary", {}).get("total_latency", 0))

        for suite_name, suite_result in run.get("suites", {}).items():
            if suite_name not in suite_data:
                suite_data[suite_name] = []
            total = suite_result.get("total", 0)
            passed = suite_result.get("passed", 0)
            suite_data[suite_name].append(
                (passed / total * 100) if total > 0 else 0
            )

    # Latest run detail
    latest = all_runs[-1] if all_runs else {}
    latest_suites = latest.get("suites", {})
    latest_summary = latest.get("summary", {})
    latest_system = latest.get("system", {})

    # Build per-suite detail rows for the latest run
    suite_rows_html = ""
    for suite_name, suite_result in latest_suites.items():
        total = suite_result.get("total", 0)
        passed = suite_result.get("passed", 0)
        pct = (passed / total * 100) if total > 0 else 0
        latency = suite_result.get("total_latency", 0)
        color = "#4caf50" if passed == total else ("#ff9800" if pct >= 70 else "#f44336")

        # Individual test results
        test_details = ""
        for test in suite_result.get("tests", []):
            t_status = "✓" if test.get("passed") else "✗"
            t_color = "#4caf50" if test.get("passed") else "#f44336"
            t_name = test.get("name", "?")
            t_latency = test.get("latency", 0)
            t_detail = test.get("detail", "")
            test_details += (
                f'<div style="padding:2px 0;color:{t_color}">'
                f'  {t_status} {t_name} '
                f'  <span style="color:#888">({t_latency:.2f}s)</span>'
            )
            if t_detail and not test.get("passed"):
                safe_detail = html.escape(t_detail[:120])
                test_details += f' <span style="color:#999;font-size:12px">— {safe_detail}</span>'
            test_details += '</div>'

        suite_rows_html += f"""
        <div style="margin:12px 0;padding:12px;background:#1e1e1e;border-radius:6px;border-left:4px solid {color}">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <strong style="font-size:16px">{suite_name}</strong>
                <span>{passed}/{total} ({pct:.0f}%) — {latency:.2f}s</span>
            </div>
            <div style="margin-top:8px;font-family:monospace;font-size:13px">{test_details}</div>
        </div>
        """

    # Chart.js datasets for per-suite scores
    suite_chart_datasets = ""
    colors = ["#4caf50", "#2196f3", "#ff9800", "#e91e63", "#9c27b0", "#00bcd4"]
    for i, (name, scores_list) in enumerate(suite_data.items()):
        color = colors[i % len(colors)]
        padded = [0] * (len(labels) - len(scores_list)) + scores_list
        suite_chart_datasets += f"""{{
            label: '{name}',
            data: {json.dumps(padded)},
            borderColor: '{color}',
            backgroundColor: '{color}33',
            tension: 0.3,
            fill: false,
        }},"""

    # Latency breakdown for latest run
    latency_labels = []
    latency_values = []
    latency_colors = []
    for suite_name, suite_result in latest_suites.items():
        for test in suite_result.get("tests", []):
            if test.get("latency", 0) > 0.01:
                latency_labels.append(f"{suite_name}:{test.get('name', '?')[:20]}")
                latency_values.append(round(test.get("latency", 0), 3))
                is_fast = test.get("latency", 0) < 2.0
                latency_colors.append("#4caf50" if is_fast else "#ff9800")

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>JARVIS Test Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: #121212; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; }}
        .header {{ text-align: center; margin-bottom: 32px; }}
        .header h1 {{ font-size: 28px; color: #fff; }}
        .header p {{ color: #888; margin-top: 4px; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }}
        .card {{ background: #1e1e1e; padding: 20px; border-radius: 8px; text-align: center; }}
        .card .value {{ font-size: 32px; font-weight: 700; color: #fff; }}
        .card .label {{ font-size: 13px; color: #888; margin-top: 4px; }}
        .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}
        .chart-box {{ background: #1e1e1e; padding: 20px; border-radius: 8px; }}
        .chart-box h3 {{ margin-bottom: 12px; font-size: 15px; color: #aaa; }}
        .section {{ margin-bottom: 32px; }}
        .section h2 {{ margin-bottom: 12px; font-size: 18px; color: #fff; }}
        canvas {{ max-height: 280px; }}
        @media (max-width: 768px) {{ .chart-row {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <div class="header">
        <h1>JARVIS Test Dashboard</h1>
        <p>Last run: {latest.get("timestamp", "N/A")[:19]} | Model: {latest_system.get("model", "?")} | Runs: {len(all_runs)}</p>
    </div>

    <div class="cards">
        <div class="card">
            <div class="value" style="color:{('#4caf50' if latest_summary.get('score', 0) >= 90 else '#ff9800' if latest_summary.get('score', 0) >= 70 else '#f44336')}">{latest_summary.get('score', 0):.1f}%</div>
            <div class="label">Overall Score</div>
        </div>
        <div class="card">
            <div class="value">{latest_summary.get('passed', 0)}/{latest_summary.get('total_tests', 0)}</div>
            <div class="label">Tests Passed</div>
        </div>
        <div class="card">
            <div class="value">{latest_summary.get('total_latency', 0):.1f}s</div>
            <div class="label">Total Latency</div>
        </div>
        <div class="card">
            <div class="value">{len(all_runs)}</div>
            <div class="label">Historical Runs</div>
        </div>
    </div>

    <div class="chart-row">
        <div class="chart-box">
            <h3>Overall Score Over Time</h3>
            <canvas id="scoreChart"></canvas>
        </div>
        <div class="chart-box">
            <h3>Total Latency Over Time</h3>
            <canvas id="latencyChart"></canvas>
        </div>
    </div>

    <div class="chart-row">
        <div class="chart-box">
            <h3>Per-Suite Score Trends</h3>
            <canvas id="suiteChart"></canvas>
        </div>
        <div class="chart-box">
            <h3>Latest Run — Latency Breakdown</h3>
            <canvas id="latencyBreakdown"></canvas>
        </div>
    </div>

    <div class="section">
        <h2>Latest Run — Details</h2>
        {suite_rows_html}
    </div>

    <script>
    const labels = {json.dumps(labels)};

    new Chart(document.getElementById('scoreChart'), {{
        type: 'line',
        data: {{
            labels: labels,
            datasets: [{{
                label: 'Score %',
                data: {json.dumps(scores)},
                borderColor: '#4caf50',
                backgroundColor: '#4caf5033',
                tension: 0.3,
                fill: true,
            }}]
        }},
        options: {{ scales: {{ y: {{ min: 0, max: 100, ticks: {{ color: '#888' }} }}, x: {{ ticks: {{ color: '#888' }} }} }}, plugins: {{ legend: {{ labels: {{ color: '#ccc' }} }} }} }}
    }});

    new Chart(document.getElementById('latencyChart'), {{
        type: 'line',
        data: {{
            labels: labels,
            datasets: [{{
                label: 'Total Latency (s)',
                data: {json.dumps(latencies)},
                borderColor: '#2196f3',
                backgroundColor: '#2196f333',
                tension: 0.3,
                fill: true,
            }}]
        }},
        options: {{ scales: {{ y: {{ min: 0, ticks: {{ color: '#888' }} }}, x: {{ ticks: {{ color: '#888' }} }} }}, plugins: {{ legend: {{ labels: {{ color: '#ccc' }} }} }} }}
    }});

    new Chart(document.getElementById('suiteChart'), {{
        type: 'line',
        data: {{
            labels: labels,
            datasets: [{suite_chart_datasets}]
        }},
        options: {{ scales: {{ y: {{ min: 0, max: 100, ticks: {{ color: '#888' }} }}, x: {{ ticks: {{ color: '#888' }} }} }}, plugins: {{ legend: {{ labels: {{ color: '#ccc' }} }} }} }}
    }});

    new Chart(document.getElementById('latencyBreakdown'), {{
        type: 'bar',
        data: {{
            labels: {json.dumps(latency_labels)},
            datasets: [{{
                label: 'Latency (s)',
                data: {json.dumps(latency_values)},
                backgroundColor: {json.dumps(latency_colors)},
            }}]
        }},
        options: {{
            indexAxis: 'y',
            scales: {{ x: {{ ticks: {{ color: '#888' }} }}, y: {{ ticks: {{ color: '#888', font: {{ size: 10 }} }} }} }},
            plugins: {{ legend: {{ display: false }} }}
        }}
    }});
    </script>
</body>
</html>"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS Test Runner")
    parser.add_argument("--suite", type=str, help="Run a specific suite only")
    parser.add_argument("--dashboard", action="store_true", help="Regenerate dashboard only")
    args = parser.parse_args()

    if args.dashboard:
        generate_dashboard()
        print("Dashboard regenerated: tests/results/dashboard.html")
    elif args.suite:
        run_all(suites=[args.suite])
    else:
        run_all()
