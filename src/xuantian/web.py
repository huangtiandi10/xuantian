from __future__ import annotations

import json
import random
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, session, url_for

from .repository import (
    QUESTION_TYPE_LABELS,
    active_sessions_for_user,
    authenticate_user,
    clear_feedback_ack,
    create_session,
    create_user,
    current_question_from_session,
    feedback_payload,
    filter_bank_questions,
    get_active_session_for_mode,
    get_active_sessions_for_bank,
    get_bank_for_user,
    get_session_for_user,
    get_user_by_id,
    import_bank_from_path,
    import_bank_from_upload,
    init_db,
    list_banks_for_user,
    load_bank_from_row,
    record_answer,
    refresh_bank_from_source,
    wrong_book_by_bank,
)


def create_app(test_config: dict | None = None) -> Flask:
    project_root = Path(__file__).resolve().parents[2]
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent / "static"),
    )

    data_dir = project_root / ".xuantian_data"
    app.config.update(
        SECRET_KEY="xuantian-local-dev-secret",
        DATABASE_PATH=data_dir / "app.db",
        APP_NAME="玄天题练",
    )

    if test_config:
        app.config.update(test_config)

    init_db(Path(app.config["DATABASE_PATH"]))

    @app.before_request
    def load_current_user() -> None:
        user_id = session.get("user_id")
        g.user = None
        if user_id is not None:
            g.user = get_user_by_id(Path(app.config["DATABASE_PATH"]), int(user_id))

    @app.context_processor
    def inject_common() -> dict:
        return {
            "app_name": app.config["APP_NAME"],
            "question_type_labels": QUESTION_TYPE_LABELS,
            "option_letter": lambda index: chr(65 + index),
        }

    def login_required(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped_view

    @app.get("/")
    def index():
        if g.user:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            success, message = create_user(
                Path(app.config["DATABASE_PATH"]),
                request.form.get("username", ""),
                request.form.get("password", ""),
            )
            flash(message, "success" if success else "error")
            if success:
                return redirect(url_for("login"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            user = authenticate_user(
                Path(app.config["DATABASE_PATH"]),
                request.form.get("username", ""),
                request.form.get("password", ""),
            )
            if user:
                session.clear()
                session["user_id"] = int(user["id"])
                flash("欢迎回来，开始今天的练习吧。", "success")
                return redirect(url_for("dashboard"))
            flash("用户名或密码错误。", "error")
        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout():
        session.clear()
        flash("你已退出当前账号。", "success")
        return redirect(url_for("login"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        db_path = Path(app.config["DATABASE_PATH"])
        banks = list_banks_for_user(db_path, int(g.user["id"]))
        active_sessions = active_sessions_for_user(db_path, int(g.user["id"]))
        return render_template(
            "dashboard.html",
            banks=banks,
            active_sessions=active_sessions,
        )

    @app.route("/banks/import", methods=["GET", "POST"])
    @login_required
    def import_bank():
        if request.method == "POST":
            db_path = Path(app.config["DATABASE_PATH"])
            source_path = request.form.get("source_path", "").strip()
            upload = request.files.get("bank_file")

            try:
                if source_path:
                    bank, bank_id = import_bank_from_path(db_path, int(g.user["id"]), source_path)
                elif upload and upload.filename:
                    raw_text = upload.read().decode("utf-8")
                    bank, bank_id = import_bank_from_upload(
                        db_path,
                        int(g.user["id"]),
                        upload.filename,
                        raw_text,
                    )
                else:
                    raise ValueError("请填写本地题库路径，或者上传一个 JSON 题库文件。")
            except Exception as exc:  # noqa: BLE001
                flash(f"导入失败：{exc}", "error")
            else:
                flash(f"题库《{bank.title}》已保存。", "success")
                return redirect(url_for("bank_detail", bank_id=bank_id))

        return render_template("bank_import.html")

    @app.get("/banks/<int:bank_id>")
    @login_required
    def bank_detail(bank_id: int):
        db_path = Path(app.config["DATABASE_PATH"])
        bank_row = get_bank_for_user(db_path, int(g.user["id"]), bank_id)
        if not bank_row:
            flash("题库不存在。", "error")
            return redirect(url_for("dashboard"))

        bank = load_bank_from_row(bank_row)
        active_sessions = get_active_sessions_for_bank(db_path, int(g.user["id"]), bank_id)
        mode_counts = {
            "choice": len([question for question in bank.questions if question.type == "choice"]),
            "blank": len([question for question in bank.questions if question.type == "blank"]),
            "all": len(bank.questions),
        }
        return render_template(
            "bank_detail.html",
            bank_row=bank_row,
            bank=bank,
            active_sessions=active_sessions,
            mode_counts=mode_counts,
        )

    @app.post("/banks/<int:bank_id>/refresh")
    @login_required
    def refresh_bank(bank_id: int):
        success, message = refresh_bank_from_source(
            Path(app.config["DATABASE_PATH"]),
            int(g.user["id"]),
            bank_id,
        )
        flash(message, "success" if success else "error")
        return redirect(url_for("bank_detail", bank_id=bank_id))

    @app.post("/banks/<int:bank_id>/start")
    @login_required
    def start_bank(bank_id: int):
        mode = request.form.get("mode", "all")
        if mode not in {"choice", "blank", "all"}:
            flash("题型模式无效。", "error")
            return redirect(url_for("bank_detail", bank_id=bank_id))

        db_path = Path(app.config["DATABASE_PATH"])
        existing = get_active_session_for_mode(db_path, int(g.user["id"]), bank_id, mode)
        if existing:
            flash("已恢复上次未完成的进度。", "success")
            return redirect(url_for("practice_session", session_id=int(existing["id"])))

        bank_row = get_bank_for_user(db_path, int(g.user["id"]), bank_id)
        if not bank_row:
            flash("题库不存在。", "error")
            return redirect(url_for("dashboard"))
        bank = load_bank_from_row(bank_row)
        questions = filter_bank_questions(bank, mode)
        if not questions:
            flash("当前题库里没有这个题型。", "error")
            return redirect(url_for("bank_detail", bank_id=bank_id))

        question_ids = [question.id for question in questions]
        random.shuffle(question_ids)
        session_id = create_session(db_path, int(g.user["id"]), bank_id, mode, question_ids)
        flash("新的练习已开始。", "success")
        return redirect(url_for("practice_session", session_id=session_id))

    @app.get("/sessions/<int:session_id>")
    @login_required
    def practice_session(session_id: int):
        db_path = Path(app.config["DATABASE_PATH"])
        session_row = get_session_for_user(db_path, int(g.user["id"]), session_id)
        if not session_row:
            flash("练习记录不存在。", "error")
            return redirect(url_for("dashboard"))
        if int(session_row["needs_ack"]) == 1:
            return redirect(url_for("practice_feedback", session_id=session_id))
        if session_row["status"] == "finished":
            return redirect(url_for("practice_summary", session_id=session_id))

        bank_row = get_bank_for_user(db_path, int(g.user["id"]), int(session_row["bank_id"]))
        bank = load_bank_from_row(bank_row)
        question = current_question_from_session(session_row, bank)
        if question is None:
            return redirect(url_for("practice_summary", session_id=session_id))

        question_order = session_row["question_order_json"]
        total_questions = len(json.loads(question_order))
        return render_template(
            "practice_question.html",
            session_row=session_row,
            question=question,
            current_number=int(session_row["current_index"]) + 1,
            total_questions=total_questions,
        )

    @app.post("/sessions/<int:session_id>/answer")
    @login_required
    def submit_answer(session_id: int):
        db_path = Path(app.config["DATABASE_PATH"])
        session_row = get_session_for_user(db_path, int(g.user["id"]), session_id)
        if not session_row:
            flash("练习记录不存在。", "error")
            return redirect(url_for("dashboard"))
        if int(session_row["needs_ack"]) == 1:
            return redirect(url_for("practice_feedback", session_id=session_id))

        bank_row = get_bank_for_user(db_path, int(g.user["id"]), int(session_row["bank_id"]))
        bank = load_bank_from_row(bank_row)
        question = current_question_from_session(session_row, bank)
        if question is None:
            return redirect(url_for("practice_summary", session_id=session_id))

        if question.type == "choice":
            user_answer = request.form.get("answer", "").strip()
        else:
            user_answer = request.form.get("blank_answer", "").strip()

        if not user_answer:
            flash("请先作答再提交。", "error")
            return redirect(url_for("practice_session", session_id=session_id))

        record_answer(db_path, session_row, question, user_answer)
        return redirect(url_for("practice_feedback", session_id=session_id))

    @app.get("/sessions/<int:session_id>/feedback")
    @login_required
    def practice_feedback(session_id: int):
        db_path = Path(app.config["DATABASE_PATH"])
        session_row = get_session_for_user(db_path, int(g.user["id"]), session_id)
        if not session_row:
            flash("练习记录不存在。", "error")
            return redirect(url_for("dashboard"))
        payload = feedback_payload(session_row)
        if not payload:
            return redirect(url_for("practice_session", session_id=session_id))

        return render_template(
            "practice_feedback.html",
            session_row=session_row,
            feedback=payload,
        )

    @app.post("/sessions/<int:session_id>/next")
    @login_required
    def practice_next(session_id: int):
        db_path = Path(app.config["DATABASE_PATH"])
        session_row = get_session_for_user(db_path, int(g.user["id"]), session_id)
        if not session_row:
            flash("练习记录不存在。", "error")
            return redirect(url_for("dashboard"))
        clear_feedback_ack(db_path, int(g.user["id"]), session_id)
        if session_row["status"] == "finished":
            return redirect(url_for("practice_summary", session_id=session_id))
        return redirect(url_for("practice_session", session_id=session_id))

    @app.get("/sessions/<int:session_id>/summary")
    @login_required
    def practice_summary(session_id: int):
        db_path = Path(app.config["DATABASE_PATH"])
        session_row = get_session_for_user(db_path, int(g.user["id"]), session_id)
        if not session_row:
            flash("练习记录不存在。", "error")
            return redirect(url_for("dashboard"))

        question_total = len(json.loads(session_row["question_order_json"]))
        accuracy = 0
        if int(session_row["answered_count"]) > 0:
            accuracy = round(int(session_row["correct_count"]) / int(session_row["answered_count"]) * 100)

        return render_template(
            "practice_summary.html",
            session_row=session_row,
            question_total=question_total,
            accuracy=accuracy,
        )

    @app.get("/wrong-book")
    @login_required
    def wrong_book():
        grouped = wrong_book_by_bank(Path(app.config["DATABASE_PATH"]), int(g.user["id"]))
        return render_template("wrong_book.html", grouped=grouped)

    return app
