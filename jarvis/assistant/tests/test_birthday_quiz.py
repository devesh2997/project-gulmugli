"""
Tests for core.birthday_quiz.

Strategy: write each scenario to a temp YAML, build a BirthdayQuizEngine
pointing at it, drive sessions through judge_answer / score / run_reveal
with mocked voice_router + an injectable sleep_fn so reveal tests don't
sit on real beats.

Coverage:
  - Pack loads from disk (multi-question + reveal)
  - Shuffle vs no-shuffle session selection
  - judge_answer correct + wrong + case-insensitive contains-match
  - score() computation across a session
  - Empty pack file → graceful empty session
  - Malformed question skipped, others load
  - Reveal step calls voice_router.say with intro and outro
  - Reveal plays audio file when present (mocked play_file)
  - Reveal falls back to fallback_text TTS when audio file is missing
  - question_count override on start_session
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.birthday_quiz import (  # noqa: E402
    BirthdayQuizEngine, FinalReveal, QuizContext, QuizSession,
    _parse_question, _parse_reveal,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _write_pack(tmp: Path, body: str) -> Path:
    p = tmp / "about_us.yaml"
    p.write_text(body)
    return p


def _make_ctx(**overrides) -> tuple[QuizContext, list[float]]:
    """Returns ctx + list that captures sleep durations."""
    sleeps: list[float] = []
    base = {
        "voice_router": MagicMock(name="voice_router"),
        "sleep_fn": lambda s: sleeps.append(s),
    }
    base.update(overrides)
    return QuizContext(**base), sleeps


_FULL_PACK = """
shuffle_questions: false
question_count: 3

questions:
  - id: q_food
    question: "Astha ka favorite food?"
    expected_answers:
      - "biryani"
    on_correct: "Biryani! Predictable."
    on_wrong: "Biryani actually."
    tags: [taste]

  - id: q_singer
    question: "Favorite singer?"
    expected_answers:
      - "arijit"
      - "arijit singh"
    on_correct: "Of course Arijit."
    on_wrong: "Arijit Singh, har playlist mein."
    tags: [music]

  - id: q_band
    question: "Favorite band?"
    expected_answers:
      - "coldplay"
    on_correct: "Coldplay!"
    on_wrong: "It's Coldplay."
    tags: [music]

final_reveal:
  intro: "Aakhri cheez."
  audio_file: media/reveal.wav
  fallback_text: "Happy birthday."
  outro: "Saara saal pyaar."
"""


# ── Loading / parsing ────────────────────────────────────────────────


def test_pack_loads_questions_and_reveal():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, _FULL_PACK)
        eng = BirthdayQuizEngine(yaml_path=pack)
        qs = eng.list_questions()
        assert len(qs) == 3
        ids = [q.id for q in qs]
        assert ids == ["q_food", "q_singer", "q_band"]
        reveal = eng.final_reveal
        assert reveal.intro == "Aakhri cheez."
        assert reveal.audio_file == "media/reveal.wav"
        assert reveal.fallback_text == "Happy birthday."
        assert reveal.outro == "Saara saal pyaar."


def test_missing_pack_file_loads_zero_questions():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        eng = BirthdayQuizEngine(yaml_path=tmp / "ghost.yaml")
        assert eng.list_questions() == []
        # The reveal still loads as a sentinel — empty intro is fine.
        assert isinstance(eng.final_reveal, FinalReveal)


def test_malformed_question_skipped_others_load():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, """
shuffle_questions: false
question_count: 5
questions:
  - id: q_ok
    question: "Valid question?"
    expected_answers:
      - "yes"
    on_correct: "Right."
    on_wrong: "Wrong."
  - question: "Missing id"
    expected_answers:
      - "x"
  - id: q_no_answers
    question: "No expected answers"
    expected_answers: []
  - id: q_no_question
    expected_answers:
      - "x"
final_reveal:
  intro: "End."
""")
        eng = BirthdayQuizEngine(yaml_path=pack)
        qs = eng.list_questions()
        assert len(qs) == 1
        assert qs[0].id == "q_ok"


def test_parse_question_rejects_non_dict():
    try:
        _parse_question(["not", "a", "dict"])
    except ValueError as e:
        assert "must be a dict" in str(e)
    else:
        raise AssertionError("expected ValueError for non-dict question")


def test_parse_reveal_handles_missing_block():
    reveal = _parse_reveal(None)
    assert isinstance(reveal, FinalReveal)
    assert reveal.intro == ""
    assert reveal.audio_file is None


# ── Session selection ────────────────────────────────────────────────


def test_no_shuffle_preserves_order():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, _FULL_PACK)   # shuffle=False
        eng = BirthdayQuizEngine(yaml_path=pack)
        session = eng.start_session()
        ids = []
        while True:
            q = session.next_question()
            if q is None:
                break
            ids.append(q.id)
        assert ids == ["q_food", "q_singer", "q_band"]


def test_shuffle_session_chooses_subset():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, """
shuffle_questions: true
question_count: 2
questions:
  - id: a
    question: "A?"
    expected_answers: ["a"]
    on_correct: ""
    on_wrong: ""
  - id: b
    question: "B?"
    expected_answers: ["b"]
    on_correct: ""
    on_wrong: ""
  - id: c
    question: "C?"
    expected_answers: ["c"]
    on_correct: ""
    on_wrong: ""
  - id: d
    question: "D?"
    expected_answers: ["d"]
    on_correct: ""
    on_wrong: ""
final_reveal:
  intro: ""
""")
        eng = BirthdayQuizEngine(yaml_path=pack)
        # Run 50 sessions and confirm subset size + that NOT every
        # session is in the same fixed order (statistically near-certain).
        seen_orders = set()
        for _ in range(50):
            s = eng.start_session()
            assert s.total == 2
            ids = []
            while True:
                q = s.next_question()
                if q is None:
                    break
                ids.append(q.id)
            assert len(ids) == 2
            for qid in ids:
                assert qid in {"a", "b", "c", "d"}
            seen_orders.add(tuple(ids))
        # Across 50 shuffles of a 4-pool-pick-2, we should see >1
        # distinct order. Astronomically unlikely otherwise.
        assert len(seen_orders) > 1


def test_question_count_override():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, _FULL_PACK)
        eng = BirthdayQuizEngine(yaml_path=pack)
        s = eng.start_session(question_count=1)
        assert s.total == 1
        s2 = eng.start_session(question_count=10)
        # Pool has 3, requesting 10 caps to pool size.
        assert s2.total == 3


# ── judge_answer ─────────────────────────────────────────────────────


def test_judge_answer_correct_substring_match():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, _FULL_PACK)
        eng = BirthdayQuizEngine(yaml_path=pack)
        s = eng.start_session()
        q = s.next_question()
        assert q.id == "q_food"
        # "I'd say biryani" contains "biryani"
        result = s.judge_answer("I'd say biryani for sure")
        assert result.correct is True
        assert result.response == "Biryani! Predictable."
        assert result.question_id == "q_food"


def test_judge_answer_case_insensitive():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, _FULL_PACK)
        eng = BirthdayQuizEngine(yaml_path=pack)
        s = eng.start_session()
        s.next_question()   # q_food
        # All-caps answer must still hit the lower-case "biryani" expectation.
        result = s.judge_answer("BIRYANI")
        assert result.correct is True


def test_judge_answer_wrong_path():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, _FULL_PACK)
        eng = BirthdayQuizEngine(yaml_path=pack)
        s = eng.start_session()
        s.next_question()   # q_food
        result = s.judge_answer("pizza")
        assert result.correct is False
        assert result.response == "Biryani actually."


def test_judge_answer_before_first_question_returns_empty():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, _FULL_PACK)
        eng = BirthdayQuizEngine(yaml_path=pack)
        s = eng.start_session()
        # No next_question() yet — judging is a no-op.
        r = s.judge_answer("biryani")
        assert r.correct is False
        assert r.response == ""


# ── score() ─────────────────────────────────────────────────────────


def test_score_counts_only_correct():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, _FULL_PACK)   # shuffle=False, 3 Qs
        eng = BirthdayQuizEngine(yaml_path=pack)
        s = eng.start_session()
        s.next_question()   # q_food
        s.judge_answer("biryani")   # correct
        s.next_question()   # q_singer
        s.judge_answer("Atif Aslam")   # wrong
        s.next_question()   # q_band
        s.judge_answer("coldplay forever")   # correct
        assert s.score() == 2
        assert s.is_done() is True


# ── Reveal ──────────────────────────────────────────────────────────


def test_reveal_speaks_intro_and_outro_when_audio_missing():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, _FULL_PACK)
        eng = BirthdayQuizEngine(yaml_path=pack)
        s = eng.start_session()
        ctx, _sleeps = _make_ctx(bank_dir=tmp)
        # No audio file at tmp/media/reveal.wav → fallback path runs.
        r = s.run_reveal(ctx)
        assert r.delivered is True
        # Calls: intro, fallback_text (since audio missing), outro = 3
        assert ctx.voice_router.say.call_count == 3
        spoken = [c.args[0] for c in ctx.voice_router.say.call_args_list]
        assert spoken[0] == "Aakhri cheez."
        assert "Happy birthday" in spoken[1]
        assert spoken[2] == "Saara saal pyaar."


def test_reveal_plays_audio_when_present_and_skips_fallback_text():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, _FULL_PACK)
        # Drop a (zero-byte) placeholder so .is_file() is True.
        media_dir = tmp / "media"
        media_dir.mkdir()
        (media_dir / "reveal.wav").write_bytes(b"\x00\x00")

        eng = BirthdayQuizEngine(yaml_path=pack)
        s = eng.start_session()
        ctx, _sleeps = _make_ctx(bank_dir=tmp)

        # Patch play_file at the module level so we don't actually invoke
        # afplay/paplay. Return True to simulate a successful playback.
        with patch("core.birthday_quiz.play_file", return_value=True) as mock_play:
            r = s.run_reveal(ctx)
        assert r.delivered is True
        # play_file called exactly once with the resolved path.
        assert mock_play.call_count == 1
        called_path = Path(mock_play.call_args.args[0])
        assert called_path.name == "reveal.wav"
        # When audio plays, fallback_text MUST NOT be spoken — say()
        # should be called only for intro + outro (2 times).
        assert ctx.voice_router.say.call_count == 2
        spoken = [c.args[0] for c in ctx.voice_router.say.call_args_list]
        assert spoken[0] == "Aakhri cheez."
        assert spoken[1] == "Saara saal pyaar."


def test_reveal_with_no_voice_router_no_crash():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, _FULL_PACK)
        eng = BirthdayQuizEngine(yaml_path=pack)
        s = eng.start_session()
        ctx, _sleeps = _make_ctx(voice_router=None, bank_dir=tmp)
        r = s.run_reveal(ctx)
        assert r.delivered is True
        # No voice_router → no audio file present → "no_voice" detail.
        assert "no_voice" in r.detail


# ── Empty pack ──────────────────────────────────────────────────────


def test_empty_pack_yields_zero_question_session():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pack = _write_pack(tmp, """
shuffle_questions: false
question_count: 5
questions: []
final_reveal:
  intro: "Nothing to ask, but here's the reveal."
  fallback_text: "I love you."
  outro: "Bye."
""")
        eng = BirthdayQuizEngine(yaml_path=pack)
        s = eng.start_session()
        assert s.total == 0
        assert s.next_question() is None
        assert s.is_done() is True
        assert s.score() == 0
        # Reveal still runs cleanly.
        ctx, _sleeps = _make_ctx(bank_dir=tmp)
        r = s.run_reveal(ctx)
        assert r.delivered is True


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_birthday_quiz_tests() -> dict:
    results = []
    total_latency = 0.0
    for t in _collect_tests():
        start = time.time()
        try:
            t()
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__, "input": "", "passed": True,
                "latency": elapsed, "detail": "", "tier": "easy", "tags": [],
            })
        except AssertionError as e:
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__, "input": "", "passed": False,
                "latency": elapsed, "detail": str(e),
                "tier": "easy", "tags": [],
            })
        except Exception as e:
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__, "input": "", "passed": False,
                "latency": elapsed,
                "detail": f"{type(e).__name__}: {e}",
                "tier": "easy", "tags": [],
            })
    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(results), "passed": passed,
        "total_latency": total_latency, "tests": results,
    }


def main() -> int:
    s = run_birthday_quiz_tests()
    for r in s["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{s['passed']}/{s['total']} birthday_quiz tests passed.")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
