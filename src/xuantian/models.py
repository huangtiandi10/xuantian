from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SUPPORTED_TYPES = {"choice", "blank"}


@dataclass(slots=True)
class Question:
    id: str
    type: str
    prompt: str
    answer: str
    explanation: str
    options: list[str] | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any], index: int) -> "Question":
        question_id = str(raw.get("id") or f"q{index}")
        question_type = str(raw.get("type", "")).strip().lower()
        prompt = str(raw.get("prompt", "")).strip()
        answer = str(raw.get("answer", "")).strip()
        explanation = str(raw.get("explanation", "")).strip()
        options = raw.get("options")

        if question_type not in SUPPORTED_TYPES:
            raise ValueError(f"题目 {question_id} 的 type 不合法: {question_type}")
        if not prompt:
            raise ValueError(f"题目 {question_id} 缺少 prompt")
        if not answer:
            raise ValueError(f"题目 {question_id} 缺少 answer")
        if not explanation:
            raise ValueError(f"题目 {question_id} 缺少 explanation")

        if question_type == "choice":
            if not isinstance(options, list) or len(options) < 2:
                raise ValueError(f"选择题 {question_id} 需要至少 2 个选项")
            normalized_options = [str(item).strip() for item in options]
            if any(not item for item in normalized_options):
                raise ValueError(f"选择题 {question_id} 的 options 不能为空")
        else:
            normalized_options = None

        return cls(
            id=question_id,
            type=question_type,
            prompt=prompt,
            answer=answer,
            explanation=explanation,
            options=normalized_options,
        )

    def matches_answer(self, user_answer: str) -> bool:
        if self.type == "choice":
            actual = self.normalize_choice_answer(user_answer)
            expected = self.normalize_choice_answer(self.answer)
            if actual == expected:
                return True
            if self.options and expected not in self.option_letters():
                return user_answer.strip().lower() == self.answer.strip().lower()
            return False
        return user_answer.strip().lower() == self.answer.strip().lower()

    def option_letters(self) -> list[str]:
        if not self.options:
            return []
        return [chr(65 + index) for index, _ in enumerate(self.options)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "prompt": self.prompt,
            "answer": self.answer,
            "explanation": self.explanation,
            "options": self.options,
        }

    @staticmethod
    def normalize_choice_answer(value: str) -> str:
        answer = value.strip().upper()
        if answer and len(answer) == 1 and answer.isalpha():
            return answer
        return value.strip().lower()


@dataclass(slots=True)
class QuestionBank:
    title: str
    description: str
    questions: list[Question]

    def question_map(self) -> dict[str, Question]:
        return {question.id: question for question in self.questions}

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "questions": [question.to_dict() for question in self.questions],
        }
