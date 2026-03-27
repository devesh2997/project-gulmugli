"""
Trivia quiz provider — LLM-generated questions with personality-flavored hosting.

Uses the brain provider (Ollama) to:
  1. Generate trivia questions with 4 options in JSON format
  2. Fuzzy-match user answers (handles abbreviations, partial answers, option letters)
  3. Generate hints without revealing the answer
  4. Produce personality-flavored reactions to correct/wrong answers

No hardcoded question bank — every question is generated on the fly by the LLM,
so the quiz never runs out of fresh content. The personality tone is injected
into every prompt so Chandler hosts sarcastically, Jarvis hosts formally, etc.

Categories: general, bollywood, music, geography, tech, movies, food, cricket
"""

import json

from core.interfaces import QuizProvider
from core.registry import register
from core.config import config
from core.logger import get_logger

log = get_logger("quiz.trivia")


@register("quiz", "trivia")
class TriviaQuizProvider(QuizProvider):
    """LLM-powered trivia quiz with personality-driven hosting."""

    def __init__(self, brain=None, **kwargs):
        """
        Args:
            brain: A BrainProvider instance (e.g., OllamaBrainProvider) used
                   for question generation and answer evaluation.
        """
        self._brain = brain

        # Session state
        self._active = False
        self._category = "general"
        self._difficulty = "medium"
        self._num_questions = 10
        self._personality_tone = ""
        self._question_number = 0
        self._score = 0

        # Current question state (internal — correct answer hidden from caller)
        self._current_question: dict | None = None
        self._current_correct: str = ""       # letter: "A", "B", "C", "D"
        self._current_explanation: str = ""
        self._current_options: list[str] = []

        # History of asked questions (prevents repeats within a session)
        self._asked_questions: list[str] = []

        # Config defaults
        quiz_cfg = config.get("quiz", {})
        self._default_num = quiz_cfg.get("default_num_questions", 10)

    def start_session(self, category: str = "general", difficulty: str = "medium",
                      num_questions: int = 0, personality_tone: str = "") -> dict:
        if not self._brain:
            log.error("No brain provider — cannot start quiz.")
            return {"session_started": False, "error": "No brain provider available."}

        self._active = True
        self._category = category or "general"
        self._difficulty = difficulty or "medium"
        self._num_questions = num_questions or self._default_num
        self._personality_tone = personality_tone
        self._question_number = 0
        self._score = 0
        self._current_question = None
        self._current_correct = ""
        self._current_explanation = ""
        self._current_options = []
        self._asked_questions = []

        log.info("Quiz started: category=%s, difficulty=%s, questions=%d",
                 self._category, self._difficulty, self._num_questions)

        return {
            "session_started": True,
            "category": self._category,
            "difficulty": self._difficulty,
            "total": self._num_questions,
        }

    def generate_question(self) -> dict:
        if not self._active:
            return {"error": "No active quiz session."}

        self._question_number += 1

        # Build the question generation prompt
        already_asked = ""
        if self._asked_questions:
            recent = self._asked_questions[-5:]  # only last 5 to keep prompt short
            already_asked = (
                "\n\nDo NOT repeat these questions (already asked):\n"
                + "\n".join(f"- {q}" for q in recent)
            )

        prompt = (
            f"You are hosting a {self._category} trivia quiz. "
            f"Personality: {self._personality_tone}\n"
            f"Generate question #{self._question_number} at {self._difficulty} difficulty.\n"
            f"Return ONLY valid JSON: "
            f'{{"question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], '
            f'"correct": "B", "explanation": "..."}}\n'
            f"Make it fun and engaging. Vary the topics within the category."
            f"{already_asked}"
        )

        resp = self._brain.generate(
            prompt=prompt,
            system="You are a trivia question generator. Return ONLY valid JSON, no markdown, no explanation.",
            json_mode=True,
            temperature=0.8,  # higher temp for variety
        )

        try:
            data = json.loads(resp.text)
        except json.JSONDecodeError:
            log.warning("LLM returned invalid JSON for quiz question: %s", resp.text[:200])
            # Fallback: return a generic error question
            self._question_number -= 1
            return {"error": "Failed to generate question. Try again."}

        question_text = data.get("question", "Unknown question")
        options = data.get("options", ["A) ?", "B) ?", "C) ?", "D) ?"])
        correct = data.get("correct", "A")
        explanation = data.get("explanation", "")

        # Store internally (hidden from user until answer checked)
        self._current_correct = correct.strip().upper()
        self._current_explanation = explanation
        self._current_options = options
        self._current_question = {
            "question_number": self._question_number,
            "total": self._num_questions,
            "text": question_text,
            "options": options,
        }

        self._asked_questions.append(question_text)

        log.debug("Quiz Q%d: %s (correct: %s)", self._question_number, question_text[:60], correct)

        # Return without correct answer or explanation
        return self._current_question

    def check_answer(self, user_answer: str) -> dict:
        if not self._active or not self._current_question:
            return {"error": "No active question to check."}

        # Find the full correct option text for context
        correct_option_text = ""
        for opt in self._current_options:
            if opt.startswith(f"{self._current_correct})"):
                correct_option_text = opt
                break

        # Use LLM for fuzzy matching — handles "SRK" = "Shah Rukh Khan",
        # "B" = option B, partial answers, etc.
        prompt = (
            f'The correct answer is: "{correct_option_text}" (option {self._current_correct})\n'
            f'The user answered: "{user_answer}"\n'
            f"Is this correct? Consider fuzzy matching, abbreviations, partial answers.\n"
            f"Personality: {self._personality_tone}\n"
            f'Return ONLY valid JSON: {{"correct": true/false, "reaction": "personality-flavored response"}}'
        )

        resp = self._brain.generate(
            prompt=prompt,
            system="You are a quiz answer evaluator. Return ONLY valid JSON.",
            json_mode=True,
            temperature=0.5,
        )

        try:
            data = json.loads(resp.text)
        except json.JSONDecodeError:
            log.warning("Answer check JSON parse failed: %s", resp.text[:200])
            # Fall back to simple string matching
            is_correct = (
                user_answer.strip().upper() == self._current_correct
                or user_answer.strip().upper().rstrip(")") == self._current_correct
            )
            data = {"correct": is_correct, "reaction": "Let's move on!"}

        is_correct = bool(data.get("correct", False))
        reaction = data.get("reaction", "")

        if is_correct:
            self._score += 1

        result = {
            "correct": is_correct,
            "correct_answer": correct_option_text or f"{self._current_correct}",
            "explanation": self._current_explanation,
            "reaction": reaction,
            "score": self._score,
            "question_number": self._question_number,
            "total": self._num_questions,
        }

        # Clear current question
        self._current_question = None

        log.debug("Quiz answer: %s → %s (score: %d/%d)",
                  user_answer, "correct" if is_correct else "wrong",
                  self._score, self._question_number)

        return result

    def get_hint(self) -> str:
        if not self._active or not self._current_question:
            return "No active question to give a hint for."

        prompt = (
            f"The question is: {self._current_question['text']}\n"
            f"Options: {', '.join(self._current_options)}\n"
            f"The correct answer is: {self._current_correct}\n"
            f"Personality: {self._personality_tone}\n"
            f"Give a helpful hint WITHOUT revealing the answer. Keep it to one sentence."
        )

        resp = self._brain.generate(
            prompt=prompt,
            system="You are a quiz host giving a hint. Do NOT reveal the answer directly.",
            temperature=0.7,
        )

        return resp.text.strip()

    def get_session_stats(self) -> dict:
        total_answered = self._question_number
        if self._current_question is not None:
            # Current question hasn't been answered yet
            total_answered = max(0, self._question_number - 1)

        accuracy = (self._score / total_answered * 100) if total_answered > 0 else 0.0

        return {
            "correct": self._score,
            "total": total_answered,
            "out_of": self._num_questions,
            "accuracy": round(accuracy, 1),
            "category": self._category,
            "difficulty": self._difficulty,
        }

    def end_session(self) -> None:
        log.info("Quiz ended: %d/%d correct in %s (%s)",
                 self._score, self._question_number,
                 self._category, self._difficulty)
        self._active = False
        self._current_question = None
        self._current_correct = ""
        self._current_explanation = ""
        self._current_options = []

    def is_active(self) -> bool:
        return self._active
