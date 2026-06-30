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
