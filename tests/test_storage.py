from pathlib import Path

from xuantian.models import Question
from xuantian.storage import _wrong_book_path, load_question_bank, record_wrong_question


def test_load_question_bank():
    bank = load_question_bank(Path("example_bank.json"))
    assert bank.title == "示例题库"
    assert len(bank.questions) == 4
    assert bank.questions[0].type == "choice"


def test_record_wrong_question(tmp_path: Path):
    bank_path = tmp_path / "bank.json"
    bank_path.write_text(
        """
        {
          "title": "tmp",
          "questions": [
            {
              "id": "q1",
              "type": "blank",
              "prompt": "1+1=?",
              "answer": "2",
              "explanation": "基础加法"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    question = Question(
        id="q1",
        type="blank",
        prompt="1+1=?",
        answer="2",
        explanation="基础加法",
    )
    wrong_book_path = record_wrong_question(bank_path, question, "3")
    content = wrong_book_path.read_text(encoding="utf-8")
    assert "q1" in content
    assert "3" in content


def test_wrong_book_path_does_not_nest(tmp_path: Path):
    wrong_book = tmp_path / "math_wrong_book.json"
    assert _wrong_book_path(wrong_book) == wrong_book
