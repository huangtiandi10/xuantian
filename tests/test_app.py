from __future__ import annotations

import io
from pathlib import Path

from xuantian.web import create_app


def create_test_client(tmp_path: Path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE_PATH": tmp_path / "test.db",
        }
    )
    return app.test_client()


def register_and_login(client):
    client.post(
        "/register",
        data={"username": "tester", "password": "secret123"},
        follow_redirects=True,
    )
    return client.post(
        "/login",
        data={"username": "tester", "password": "secret123"},
        follow_redirects=True,
    )


def test_auth_flow_and_dashboard(tmp_path: Path):
    client = create_test_client(tmp_path)
    response = register_and_login(client)
    assert "你的本地题库空间" in response.get_data(as_text=True)


def test_import_bank_and_render_saved_bank(tmp_path: Path):
    client = create_test_client(tmp_path)
    register_and_login(client)

    response = client.post(
        "/banks/import",
        data={
            "bank_file": (
                io.BytesIO(
                    b'{"title":"Web Test","description":"demo","questions":[{"id":"q1","type":"choice","prompt":"2+2=?","options":["3","4"],"answer":"B","explanation":"2+2=4"}]}'
                ),
                "bank.json",
            )
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    content = response.get_data(as_text=True)
    assert "Web Test" in content
    assert "开始练习" in content


def test_wrong_book_is_grouped_page(tmp_path: Path):
    client = create_test_client(tmp_path)
    register_and_login(client)

    client.post(
        "/banks/import",
        data={
            "bank_file": (
                io.BytesIO(
                    b'{"title":"WrongBook","description":"demo","questions":[{"id":"q1","type":"blank","prompt":"HTTP default","answer":"80","explanation":"port 80"}]}'
                ),
                "wrong.json",
            )
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    bank_page = client.get("/dashboard")
    assert "WrongBook" in bank_page.get_data(as_text=True)


def test_can_go_back_to_previous_feedback_and_jump_to_question(tmp_path: Path):
    client = create_test_client(tmp_path)
    register_and_login(client)

    client.post(
        "/banks/import",
        data={
            "bank_file": (
                io.BytesIO(
                    b'{"title":"Navigator","description":"demo","questions":[{"id":"q1","type":"choice","prompt":"1+1=?","options":["1","2"],"answer":"B","explanation":"1+1=2"},{"id":"q2","type":"blank","prompt":"HTTP","answer":"80","explanation":"default port"},{"id":"q3","type":"choice","prompt":"2+2=?","options":["3","4"],"answer":"B","explanation":"2+2=4"}]}'
                ),
                "nav.json",
            )
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    start_response = client.post(
        "/banks/1/start",
        data={"mode": "all", "order_mode": "sequential", "source_kind": "bank"},
        follow_redirects=False,
    )
    session_path = start_response.headers["Location"]

    first_question = client.get(session_path)
    assert "第 1 / 3 题" in first_question.get_data(as_text=True)

    feedback_one = client.post("/sessions/1/answer", data={"answer": "B"}, follow_redirects=True)
    assert "1+1=2" in feedback_one.get_data(as_text=True)

    second_question = client.post("/sessions/1/next", follow_redirects=True)
    assert "第 2 / 3 题" in second_question.get_data(as_text=True)

    feedback_two = client.post("/sessions/1/answer", data={"blank_answer": "80"}, follow_redirects=True)
    feedback_two_text = feedback_two.get_data(as_text=True)
    assert "default port" in feedback_two_text
    assert "上一题" in feedback_two_text

    previous_feedback = client.post("/sessions/1/previous", follow_redirects=True)
    previous_feedback_text = previous_feedback.get_data(as_text=True)
    assert "1+1=2" in previous_feedback_text
    assert "第 1 / 3 题" in previous_feedback_text

    jumped_question = client.post(
        "/sessions/1/jump",
        data={"question_number": "3"},
        follow_redirects=True,
    )
    jumped_question_text = jumped_question.get_data(as_text=True)
    assert "第 3 / 3 题" in jumped_question_text
    assert "2+2=?" in jumped_question_text
