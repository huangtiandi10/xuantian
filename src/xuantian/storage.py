from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Question, QuestionBank


def load_question_bank(path: str | Path) -> QuestionBank:
    bank_path = Path(path).expanduser().resolve()
    if not bank_path.exists():
        raise FileNotFoundError(f"题库文件不存在: {bank_path}")

    with bank_path.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    return load_question_bank_from_raw(raw)


def load_question_bank_from_json_text(raw_text: str) -> QuestionBank:
    return load_question_bank_from_raw(json.loads(raw_text))


def load_question_bank_from_raw(raw: dict[str, Any]) -> QuestionBank:
    if not isinstance(raw, dict):
        raise ValueError("题库文件格式错误，根节点必须是对象")

    title = str(raw.get("title", "未命名题库")).strip() or "未命名题库"
    description = str(raw.get("description", "")).strip()
    raw_questions = raw.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ValueError("题库中 questions 必须是非空数组")

    questions = [Question.from_dict(item, index + 1) for index, item in enumerate(raw_questions)]
    return QuestionBank(title=title, description=description, questions=questions)


def _wrong_book_path(bank_path: str | Path) -> Path:
    source = Path(bank_path).expanduser().resolve()
    if source.stem.endswith("_wrong_book"):
        return source
    return source.with_name(f"{source.stem}_wrong_book.json")


def load_wrong_book(bank_path: str | Path) -> dict[str, Any]:
    path = _wrong_book_path(bank_path)
    if not path.exists():
        source = str(Path(bank_path).expanduser().resolve())
        stem = Path(bank_path).expanduser().resolve().stem
        return {
            "title": f"{stem} 错题集",
            "description": "自动生成的错题集，可直接作为题库再次练习。",
            "source_bank": source,
            "questions": [],
        }

    with path.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    if not isinstance(raw, dict):
        source = str(Path(bank_path).expanduser().resolve())
        stem = Path(bank_path).expanduser().resolve().stem
        return {
            "title": f"{stem} 错题集",
            "description": "自动生成的错题集，可直接作为题库再次练习。",
            "source_bank": source,
            "questions": [],
        }
    raw.setdefault("source_bank", str(Path(bank_path).expanduser().resolve()))
    raw.setdefault("title", f"{Path(bank_path).expanduser().resolve().stem} 错题集")
    raw.setdefault("description", "自动生成的错题集，可直接作为题库再次练习。")
    raw.setdefault("questions", [])
    return raw


def record_wrong_question(bank_path: str | Path, question: Question, user_answer: str) -> Path:
    path = _wrong_book_path(bank_path)
    wrong_book = load_wrong_book(bank_path)
    questions = wrong_book["questions"]

    for item in questions:
        if item.get("id") == question.id:
            stats = item.setdefault("stats", {})
            stats["last_user_answer"] = user_answer
            stats["wrong_count"] = int(stats.get("wrong_count", 1)) + 1
            break
    else:
        questions.append(
            {
                "id": question.id,
                "type": question.type,
                "prompt": question.prompt,
                "answer": question.answer,
                "explanation": question.explanation,
                "options": question.options,
                "stats": {
                    "last_user_answer": user_answer,
                    "wrong_count": 1,
                },
            }
        )

    with path.open("w", encoding="utf-8") as file:
        json.dump(wrong_book, file, ensure_ascii=False, indent=2)
    return path
