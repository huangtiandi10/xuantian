from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from .models import Question, QuestionBank
from .storage import load_question_bank, load_question_bank_from_json_text


QUESTION_TYPE_LABELS = {
    "choice": "选择题",
    "blank": "填空题",
    "all": "混合练习",
}


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS banks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_path TEXT,
    raw_json TEXT NOT NULL,
    question_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS practice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    bank_id INTEGER NOT NULL,
    mode TEXT NOT NULL,
    question_order_json TEXT NOT NULL,
    current_index INTEGER NOT NULL DEFAULT 0,
    answered_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    needs_ack INTEGER NOT NULL DEFAULT 0,
    last_feedback_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(bank_id) REFERENCES banks(id)
);

CREATE TABLE IF NOT EXISTS wrong_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    bank_id INTEGER NOT NULL,
    question_id TEXT NOT NULL,
    question_type TEXT NOT NULL,
    prompt TEXT NOT NULL,
    answer TEXT NOT NULL,
    explanation TEXT NOT NULL,
    options_json TEXT,
    wrong_count INTEGER NOT NULL DEFAULT 1,
    last_user_answer TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, bank_id, question_id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(bank_id) REFERENCES banks(id)
);
"""


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_data_dir(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)


def init_db(db_path: Path) -> None:
    ensure_data_dir(db_path.parent)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(SCHEMA)
        connection.commit()


def get_connection(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def create_user(db_path: Path, username: str, password: str) -> tuple[bool, str]:
    normalized_username = username.strip()
    if len(normalized_username) < 3:
        return False, "用户名至少需要 3 个字符。"
    if len(password) < 6:
        return False, "密码至少需要 6 个字符。"

    now = utc_now()
    try:
        with get_connection(db_path) as connection:
            connection.execute(
                """
                INSERT INTO users (username, password_hash, created_at)
                VALUES (?, ?, ?)
                """,
                (normalized_username, generate_password_hash(password), now),
            )
            connection.commit()
    except sqlite3.IntegrityError:
        return False, "这个用户名已经存在。"

    return True, "注册成功，请登录。"


def authenticate_user(db_path: Path, username: str, password: str) -> sqlite3.Row | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        return row
    return None


def get_user_by_id(db_path: Path, user_id: int) -> sqlite3.Row | None:
    with get_connection(db_path) as connection:
        return connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


def import_bank_from_path(
    db_path: Path,
    user_id: int,
    source_path: str,
) -> tuple[QuestionBank, int]:
    resolved = Path(source_path).expanduser().resolve()
    bank = load_question_bank(resolved)
    raw_text = resolved.read_text(encoding="utf-8")
    bank_id = save_bank(
        db_path=db_path,
        user_id=user_id,
        bank=bank,
        raw_json=raw_text,
        source_name=resolved.name,
        source_path=str(resolved),
    )
    return bank, bank_id


def import_bank_from_upload(
    db_path: Path,
    user_id: int,
    filename: str,
    raw_text: str,
) -> tuple[QuestionBank, int]:
    bank = load_question_bank_from_json_text(raw_text)
    bank_id = save_bank(
        db_path=db_path,
        user_id=user_id,
        bank=bank,
        raw_json=raw_text,
        source_name=filename or f"{bank.title}.json",
        source_path=None,
    )
    return bank, bank_id


def save_bank(
    db_path: Path,
    user_id: int,
    bank: QuestionBank,
    raw_json: str,
    source_name: str,
    source_path: str | None,
) -> int:
    now = utc_now()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO banks (
                user_id, title, description, source_name, source_path, raw_json,
                question_count, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                bank.title,
                bank.description,
                source_name,
                source_path,
                raw_json,
                len(bank.questions),
                now,
                now,
            ),
        )
        bank_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        connection.commit()
    return bank_id


def refresh_bank_from_source(db_path: Path, user_id: int, bank_id: int) -> tuple[bool, str]:
    bank_row = get_bank_for_user(db_path, user_id, bank_id)
    if not bank_row:
        return False, "题库不存在。"
    if not bank_row["source_path"]:
        return False, "这个题库是上传保存的，没有原始本地路径可刷新。"

    source_path = Path(bank_row["source_path"])
    if not source_path.exists():
        return False, f"原始题库文件不存在: {source_path}"

    bank = load_question_bank(source_path)
    raw_text = source_path.read_text(encoding="utf-8")
    now = utc_now()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            UPDATE banks
            SET title = ?, description = ?, raw_json = ?, question_count = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                bank.title,
                bank.description,
                raw_text,
                len(bank.questions),
                now,
                bank_id,
                user_id,
            ),
        )
        connection.commit()
    return True, "题库已从本地源文件刷新。"


def list_banks_for_user(db_path: Path, user_id: int) -> list[sqlite3.Row]:
    with get_connection(db_path) as connection:
        return connection.execute(
            """
            SELECT
                banks.*,
                (
                    SELECT COUNT(*)
                    FROM wrong_questions
                    WHERE wrong_questions.bank_id = banks.id
                      AND wrong_questions.user_id = banks.user_id
                ) AS wrong_count,
                (
                    SELECT COUNT(*)
                    FROM practice_sessions
                    WHERE practice_sessions.bank_id = banks.id
                      AND practice_sessions.user_id = banks.user_id
                      AND practice_sessions.status = 'active'
                ) AS active_session_count
            FROM banks
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()


def get_bank_for_user(db_path: Path, user_id: int, bank_id: int) -> sqlite3.Row | None:
    with get_connection(db_path) as connection:
        return connection.execute(
            """
            SELECT
                banks.*,
                (
                    SELECT COUNT(*)
                    FROM wrong_questions
                    WHERE wrong_questions.bank_id = banks.id
                      AND wrong_questions.user_id = banks.user_id
                ) AS wrong_count
            FROM banks
            WHERE id = ? AND user_id = ?
            """,
            (bank_id, user_id),
        ).fetchone()


def load_bank_from_row(bank_row: sqlite3.Row) -> QuestionBank:
    return load_question_bank_from_json_text(bank_row["raw_json"])


def filter_bank_questions(bank: QuestionBank, mode: str) -> list[Question]:
    if mode == "all":
        return list(bank.questions)
    return [question for question in bank.questions if question.type == mode]


def get_active_sessions_for_bank(db_path: Path, user_id: int, bank_id: int) -> list[sqlite3.Row]:
    with get_connection(db_path) as connection:
        return connection.execute(
            """
            SELECT *
            FROM practice_sessions
            WHERE user_id = ? AND bank_id = ? AND status = 'active'
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id, bank_id),
        ).fetchall()


def get_active_session_for_mode(
    db_path: Path,
    user_id: int,
    bank_id: int,
    mode: str,
) -> sqlite3.Row | None:
    with get_connection(db_path) as connection:
        return connection.execute(
            """
            SELECT *
            FROM practice_sessions
            WHERE user_id = ? AND bank_id = ? AND mode = ? AND status = 'active'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (user_id, bank_id, mode),
        ).fetchone()


def create_session(
    db_path: Path,
    user_id: int,
    bank_id: int,
    mode: str,
    question_ids: list[str],
) -> int:
    now = utc_now()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO practice_sessions (
                user_id, bank_id, mode, question_order_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, bank_id, mode, json.dumps(question_ids), now, now),
        )
        session_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        connection.commit()
    return session_id


def get_session_for_user(db_path: Path, user_id: int, session_id: int) -> sqlite3.Row | None:
    with get_connection(db_path) as connection:
        return connection.execute(
            """
            SELECT sessions.*, banks.title AS bank_title
            FROM practice_sessions AS sessions
            JOIN banks ON banks.id = sessions.bank_id
            WHERE sessions.id = ? AND sessions.user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()


def parse_question_order(session_row: sqlite3.Row) -> list[str]:
    return json.loads(session_row["question_order_json"])


def current_question_from_session(session_row: sqlite3.Row, bank: QuestionBank) -> Question | None:
    question_order = parse_question_order(session_row)
    current_index = int(session_row["current_index"])
    if current_index >= len(question_order):
        return None
    return bank.question_map().get(question_order[current_index])


def feedback_payload(session_row: sqlite3.Row) -> dict[str, Any] | None:
    raw = session_row["last_feedback_json"]
    if not raw:
        return None
    return json.loads(raw)


def record_answer(
    db_path: Path,
    session_row: sqlite3.Row,
    question: Question,
    user_answer: str,
) -> None:
    question_order = parse_question_order(session_row)
    current_index = int(session_row["current_index"])
    answered_count = int(session_row["answered_count"]) + 1
    is_correct = question.matches_answer(user_answer)
    correct_count = int(session_row["correct_count"]) + (1 if is_correct else 0)
    next_index = current_index + 1
    finished = next_index >= len(question_order)
    now = utc_now()
    feedback = {
        "question_id": question.id,
        "prompt": question.prompt,
        "question_type": question.type,
        "options": question.options,
        "user_answer": user_answer,
        "user_answer_display": question.display_answer(user_answer),
        "correct_answer": question.answer,
        "correct_answer_display": question.display_answer(question.answer),
        "explanation": question.explanation,
        "is_correct": is_correct,
        "question_number": answered_count,
        "total_questions": len(question_order),
    }

    with get_connection(db_path) as connection:
        connection.execute(
            """
            UPDATE practice_sessions
            SET current_index = ?, answered_count = ?, correct_count = ?,
                status = ?, needs_ack = 1, last_feedback_json = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                next_index,
                answered_count,
                correct_count,
                "finished" if finished else "active",
                json.dumps(feedback, ensure_ascii=False),
                now,
                session_row["id"],
                session_row["user_id"],
            ),
        )
        connection.commit()

    if not is_correct:
        upsert_wrong_question(
            db_path=db_path,
            user_id=int(session_row["user_id"]),
            bank_id=int(session_row["bank_id"]),
            question=question,
            user_answer=user_answer,
        )


def clear_feedback_ack(db_path: Path, user_id: int, session_id: int) -> None:
    now = utc_now()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            UPDATE practice_sessions
            SET needs_ack = 0, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (now, session_id, user_id),
        )
        connection.commit()


def upsert_wrong_question(
    db_path: Path,
    user_id: int,
    bank_id: int,
    question: Question,
    user_answer: str,
) -> None:
    now = utc_now()
    options_json = json.dumps(question.options, ensure_ascii=False) if question.options else None
    with get_connection(db_path) as connection:
        existing = connection.execute(
            """
            SELECT id, wrong_count
            FROM wrong_questions
            WHERE user_id = ? AND bank_id = ? AND question_id = ?
            """,
            (user_id, bank_id, question.id),
        ).fetchone()
        if existing:
            connection.execute(
                """
                UPDATE wrong_questions
                SET wrong_count = ?, last_user_answer = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(existing["wrong_count"]) + 1, user_answer, now, existing["id"]),
            )
        else:
            connection.execute(
                """
                INSERT INTO wrong_questions (
                    user_id, bank_id, question_id, question_type, prompt, answer,
                    explanation, options_json, wrong_count, last_user_answer,
                    updated_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    bank_id,
                    question.id,
                    question.type,
                    question.prompt,
                    question.answer,
                    question.explanation,
                    options_json,
                    1,
                    user_answer,
                    now,
                    now,
                ),
            )
        connection.commit()


def wrong_book_by_bank(db_path: Path, user_id: int) -> list[dict[str, Any]]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                wrong_questions.*,
                banks.title AS bank_title
            FROM wrong_questions
            JOIN banks ON banks.id = wrong_questions.bank_id
            WHERE wrong_questions.user_id = ?
            ORDER BY banks.title COLLATE NOCASE, wrong_questions.question_type, wrong_questions.updated_at DESC
            """,
            (user_id,),
        ).fetchall()

    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        bank_entry = grouped.setdefault(
            int(row["bank_id"]),
            {
                "bank_id": int(row["bank_id"]),
                "bank_title": row["bank_title"],
                "types": {
                    "choice": [],
                    "blank": [],
                },
            },
        )
        bank_entry["types"][row["question_type"]].append(
            {
                "question_id": row["question_id"],
                "prompt": row["prompt"],
                "answer": row["answer"],
                "explanation": row["explanation"],
                "options": json.loads(row["options_json"]) if row["options_json"] else None,
                "wrong_count": int(row["wrong_count"]),
                "last_user_answer": row["last_user_answer"],
                "updated_at": row["updated_at"],
            }
        )

    return list(grouped.values())


def active_sessions_for_user(db_path: Path, user_id: int) -> list[sqlite3.Row]:
    with get_connection(db_path) as connection:
        return connection.execute(
            """
            SELECT sessions.*, banks.title AS bank_title
            FROM practice_sessions AS sessions
            JOIN banks ON banks.id = sessions.bank_id
            WHERE sessions.user_id = ? AND sessions.status = 'active'
            ORDER BY sessions.updated_at DESC
            """,
            (user_id,),
        ).fetchall()
