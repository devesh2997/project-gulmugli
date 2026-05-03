"""
Pre-filter regression test suite.

Tests that the keyword pre-filter correctly catches obvious commands and
returns None for ambiguous inputs that should go to the LLM. Run on every
change to prefilter.py to catch regressions.

Two critical properties:

1. **No false positives.** If the pre-filter matches, it MUST be correct.
   A wrong pre-filter result bypasses the LLM entirely → wrong action.
   This is the property that protects the user from "play music" being
   mistaken for "play game" or vice-versa.

2. **False negatives are fine.** The LLM catches anything the pre-filter
   misses. The downside of a false negative is one extra LLM round-trip
   (~3s on Jetson), which is annoying but not broken.

Test count goal: ≥1 test per matcher × 2 (one positive, one negative
boundary case) + adversarial cases for false-positive guards.

Run via:
    python tests/runner.py prefilter
"""

import time
from core.prefilter import prefilter_intent
from core.logger import get_logger

log = get_logger("tests.prefilter")


def _t(input_text, expect_intent=None, expect_param=None, desc=""):
    """Compact test-case builder. Avoids dict boilerplate everywhere."""
    return {
        "input": input_text,
        "expect_intent": expect_intent,
        "expect_param": expect_param,
        "desc": desc or input_text,
    }


PREFILTER_TESTS = [
    # ═══════════════════════════════════════════════════════════════════
    #  Music control: pause / resume / stop / skip
    # ═══════════════════════════════════════════════════════════════════
    _t("pause", "music_control", ("action", "pause"), "bare 'pause'"),
    _t("pause the music", "music_control", ("action", "pause"), "pause the music"),
    _t("pause the song", "music_control", ("action", "pause")),
    _t("pause the gaana", "music_control", ("action", "pause"), "Hinglish pause"),
    _t("resume", "music_control", ("action", "resume")),
    _t("continue", "music_control", ("action", "resume")),
    _t("stop", "music_control", ("action", "stop")),
    _t("stop the music", "music_control", ("action", "stop")),
    _t("gaana rok do", "music_control", ("action", "stop"), "Hindi stop"),
    _t("gaana band karo", "music_control", ("action", "stop"), "Hindi stop"),
    _t("skip", "music_control", ("action", "skip")),
    _t("skip this", "music_control", ("action", "skip")),
    _t("skip this one", "music_control", ("action", "skip")),
    _t("skip this song", "music_control", ("action", "skip")),
    _t("skip song", "music_control", ("action", "skip")),
    _t("skip track", "music_control", ("action", "skip")),
    _t("next", "music_control", ("action", "skip")),
    _t("next song", "music_control", ("action", "skip")),
    _t("next track", "music_control", ("action", "skip")),
    _t("agla gaana", "music_control", ("action", "skip"), "Hindi next"),
    _t("dusra gaana", "music_control", ("action", "skip"), "Hindi 'another song'"),
    _t("change the song", "music_control", ("action", "skip")),

    # ═══════════════════════════════════════════════════════════════════
    #  Music play: "play X" patterns (added in 13f173a)
    # ═══════════════════════════════════════════════════════════════════
    _t("play Sajni", "music_play", ("query", "sajni")),
    _t("Play Sajni", "music_play", ("query", "sajni"), "case-insensitive"),
    _t("play Channa Mereya", "music_play", ("query", "channa mereya")),
    _t("play Husn by Anuv Jain", "music_play", ("query", "husn by anuv jain"),
       "play with artist hint"),
    _t("put on Coldplay", "music_play", ("query", "coldplay")),
    _t("put on some Bollywood", "music_play", ("query", "some bollywood")),
    _t("start playing Sajni", "music_play", ("query", "sajni")),
    _t("play me Tum Hi Ho", "music_play", ("query", "tum hi ho")),
    _t("Sajni bajao", "music_play", ("query", "sajni"), "Hinglish suffix bajao"),
    _t("Sajni chalao", "music_play", ("query", "sajni")),
    _t("Sajni laga do", "music_play", ("query", "sajni")),
    _t("Sajni lagao", "music_play", ("query", "sajni")),
    _t("bajao Sajni", "music_play", ("query", "sajni"), "Hinglish prefix bajao"),
    _t("chalao Sajni", "music_play", ("query", "sajni")),
    _t("lagao Sajni", "music_play", ("query", "sajni")),
    # False-positive guards — verifying intent routing
    _t("play quiz", "quiz", ("action", "start"),
       "play quiz → quiz matcher (runs before music_play in chain)"),
    _t("play trivia", "quiz", ("action", "start"),
       "play trivia → quiz matcher"),
    _t("play game", None, None, "play game → fall through (no game matcher)"),
    _t("play it", None, None, "play it → ambiguous pronoun, LLM"),
    _t("play this", None, None, "play this → ambiguous pronoun, LLM"),
    _t("play that", None, None, "play that → ambiguous pronoun, LLM"),
    _t("play music", None, None, "play music → too ambiguous, let LLM choose"),

    # ═══════════════════════════════════════════════════════════════════
    #  Music play with video — must beat _match_music_play in the chain
    # ═══════════════════════════════════════════════════════════════════
    _t("play Sajni with video", "music_play", ("with_video", True)),
    _t("Sajni ka video lagao", "music_play", ("with_video", True),
       "Hindi 'play X video'"),
    _t("play Sajni video mein", "music_play", ("with_video", True)),

    # ═══════════════════════════════════════════════════════════════════
    #  Volume
    # ═══════════════════════════════════════════════════════════════════
    _t("volume 50", "volume", ("level", "50")),
    _t("volume 100", "volume", ("level", "100")),
    _t("volume 0", "volume", ("level", "0")),
    _t("volume up", "volume", ("level", "80")),
    _t("volume down", "volume", ("level", "30")),
    _t("loud", "volume", ("level", "80")),
    _t("louder", "volume", ("level", "80")),
    _t("quiet", "volume", ("level", "30")),
    _t("quieter", "volume", ("level", "30")),
    _t("awaaz badhao", "volume", ("level", "80"), "Hindi volume up"),
    _t("awaaz kam karo", "volume", ("level", "30"), "Hindi volume down"),
    _t("mute", "volume", ("level", "0")),
    _t("mute the volume", "volume", ("level", "0")),
    _t("mute the sound", "volume", ("level", "0")),
    _t("awaaz band karo", "volume", ("level", "0"), "Hindi mute"),
    # Volume false-positive guards
    _t("volume 200", None, None, "out-of-range volume → fall through"),
    _t("set volume to 50", None, None, "verbose set → LLM (no exact prefilter form)"),
    _t("brightness 30 percent", None, None, "brightness, not volume"),

    # ═══════════════════════════════════════════════════════════════════
    #  Lights (basic on/off)
    # ═══════════════════════════════════════════════════════════════════
    _t("lights off", "light_control", ("action", "off")),
    _t("light off", "light_control", ("action", "off")),
    _t("turn off the lights", "light_control", ("action", "off")),
    _t("turn off the light", "light_control", ("action", "off")),
    _t("batti band karo", "light_control", ("action", "off"), "Hindi lights off"),
    _t("light band karo", "light_control", ("action", "off"), "Hinglish"),
    _t("lights band karo", "light_control", ("action", "off")),
    _t("lights on", "light_control", ("action", "on")),
    _t("light on", "light_control", ("action", "on")),
    _t("turn on the lights", "light_control", ("action", "on")),
    _t("turn on the light", "light_control", ("action", "on")),
    _t("batti jalao", "light_control", ("action", "on"), "Hindi lights on"),
    # Light false-positive guards (scenes/colors need LLM)
    _t("lights to purple", None, None, "color setting → LLM"),
    _t("dim the lights", None, None, "brightness change → LLM"),
    _t("study mode", None, None, "scene → LLM (handled by light_control via classifier)"),
    _t("party mode laga do", None, None, "scene + Hindi → LLM"),

    # ═══════════════════════════════════════════════════════════════════
    #  System: time / date (expanded in da6ce48)
    # ═══════════════════════════════════════════════════════════════════
    _t("what time is it", "system", ("action", "time")),
    _t("what's the time", "system", ("action", "time")),
    _t("what is the time", "system", ("action", "time")),
    _t("what is the time right now", "system", ("action", "time")),
    _t("whats the time", "system", ("action", "time"), "no apostrophe"),
    _t("tell me the time", "system", ("action", "time")),
    _t("tell me the current time", "system", ("action", "time")),
    _t("give me the time", "system", ("action", "time")),
    _t("give me the current time", "system", ("action", "time")),
    _t("do you know the time", "system", ("action", "time")),
    _t("do you have the time", "system", ("action", "time")),
    _t("current time", "system", ("action", "time")),
    _t("the time please", "system", ("action", "time")),
    _t("kitne baje hain", "system", ("action", "time"), "Hindi"),
    _t("abhi kya time hai", "system", ("action", "time"), "Hindi"),
    _t("what's the date", "system", ("action", "date")),
    _t("what is the date", "system", ("action", "date")),
    _t("what is todays date", "system", ("action", "date"), "no apostrophe"),
    _t("today's date", "system", ("action", "date")),
    _t("todays date", "system", ("action", "date")),
    _t("what day is today", "system", ("action", "date")),
    _t("what day is it", "system", ("action", "date")),
    _t("aaj kya date hai", "system", ("action", "date"), "Hindi"),

    # ═══════════════════════════════════════════════════════════════════
    #  Weather (broad keyword match)
    # ═══════════════════════════════════════════════════════════════════
    _t("what's the weather", "weather", None),
    _t("how is the weather", "weather", None),
    _t("how hot is it", "weather", None),
    _t("will it rain today", "weather", None),
    _t("kitni garmi hai", "weather", None, "Hindi heat"),

    # ═══════════════════════════════════════════════════════════════════
    #  Timer / alarm
    # ═══════════════════════════════════════════════════════════════════
    _t("set a timer for 5 minutes", "timer", ("action", "set_timer")),
    _t("timer 10 minutes", "timer", ("action", "set_timer")),
    _t("5 minute timer", "timer", ("action", "set_timer")),
    _t("set timer 30 seconds", "timer", ("action", "set_timer")),
    _t("set alarm for 7am", "timer", ("action", "set_alarm")),
    _t("wake me up at 7", "timer", ("action", "set_alarm")),
    _t("cancel the timer", "timer", ("action", "cancel")),
    _t("stop the alarm", "timer", ("action", "cancel")),
    _t("snooze", "timer", ("action", "snooze")),

    # ═══════════════════════════════════════════════════════════════════
    #  Story / sleep / quiz / ambient
    # ═══════════════════════════════════════════════════════════════════
    _t("tell me a story", "story", ("action", "start")),
    _t("tell me a bedtime story", "story", ("action", "start")),
    _t("kahani sunao", "story", ("action", "start"), "Hindi 'tell a story'"),
    _t("good night", "sleep", ("action", "sleep")),
    _t("good morning", "sleep", ("action", "wake")),
    _t("play quiz", "quiz", ("action", "start")),
    _t("trivia start", "quiz", ("action", "start")),
    _t("play rain sounds", "ambient", ("action", "play")),
    _t("rain sounds", "ambient", ("action", "play")),

    # ═══════════════════════════════════════════════════════════════════
    #  Adversarial / ambiguous — must NOT match (false-positive prevention)
    # ═══════════════════════════════════════════════════════════════════
    _t("hello", None, None, "greeting → chat"),
    _t("hi there", None, None, "greeting → chat"),
    _t("how are you", None, None, "chat opener → chat"),
    _t("tell me a joke", None, None, "chat → LLM"),
    _t("what is the speed of light", None, None, "factual question → chat"),
    _t("explain quantum computing", None, None, "factual → chat"),
    _t("who is the PM of India", None, None, "knowledge → LLM"),
    _t("switch to Chandler mode", None, None, "personality switch → LLM"),
    _t("become Devesh", None, None, "personality switch → LLM"),
    _t("kuch sad sa bajao", None, None, "mood-music → LLM (needs mood→genre mapping)"),
    _t("play Tum Hi Ho and set lights to purple", None, None,
       "command chain → LLM"),
    _t("when did Einstein die", None, None, "knowledge → LLM"),
    _t("what's 2 plus 2", None, None, "math → LLM"),
]


def run_prefilter_tests() -> dict:
    """Run all pre-filter tests."""
    results = []
    total_latency = 0
    failures = []

    for test_case in PREFILTER_TESTS:
        user_input = test_case["input"]
        expected_intent = test_case["expect_intent"]
        expected_param = test_case["expect_param"]
        desc = test_case["desc"]

        start = time.time()
        try:
            result = prefilter_intent(user_input)
            latency = time.time() - start
            total_latency += latency

            if expected_intent is None:
                # Should NOT have matched
                passed = result is None
                detail = "" if passed else f"Should be None, got {result[0].name} (params={result[0].params})"
            else:
                # Should have matched
                if result is None:
                    passed = False
                    detail = f"Expected {expected_intent}, got None (no match)"
                else:
                    actual_intent = result[0].name
                    passed = actual_intent == expected_intent
                    detail = "" if passed else f"Expected {expected_intent}, got {actual_intent}"

                    # Check param if specified
                    if passed and expected_param:
                        param_name, param_val = expected_param
                        actual_val = result[0].params.get(param_name, "")
                        # Loose comparison: bool vs str, etc.
                        if str(actual_val).lower() != str(param_val).lower():
                            passed = False
                            detail = f"Param {param_name}: expected '{param_val}', got '{actual_val}'"

        except Exception as e:
            latency = time.time() - start
            total_latency += latency
            passed = False
            detail = f"Exception: {e}"

        latency_ms = latency * 1000
        status = "PASS" if passed else "FAIL"
        log.info("[%s] %s (%.2fms) %s", status, desc, latency_ms,
                 detail if not passed else "")

        if not passed:
            failures.append({"input": user_input, "desc": desc, "detail": detail})

        results.append({
            "name": desc,
            "input": user_input,
            "passed": passed,
            "latency": latency,
            "detail": detail,
        })

    passed_count = sum(1 for r in results if r["passed"])

    return {
        "total": len(results),
        "passed": passed_count,
        "total_latency": total_latency,
        "tests": results,
        "failures": failures,
    }


def main():
    """Run as a script: python tests/test_prefilter.py — for direct invocation."""
    import sys
    res = run_prefilter_tests()
    print(f"\n{'═' * 60}")
    print(f"  Prefilter tests: {res['passed']}/{res['total']} passed")
    print(f"  Total latency:   {res['total_latency']*1000:.1f}ms "
          f"({res['total_latency']*1000/res['total']:.2f}ms/test avg)")
    if res["failures"]:
        print(f"\n  FAILURES ({len(res['failures'])}):")
        for f in res["failures"]:
            print(f"    {f['input']!r}")
            print(f"      {f['detail']}")
    print(f"{'═' * 60}\n")
    sys.exit(0 if res["passed"] == res["total"] else 1)


if __name__ == "__main__":
    main()
