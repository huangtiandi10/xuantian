from __future__ import annotations

import random
from pathlib import Path

from .models import Question, QuestionBank
from .storage import record_wrong_question


QUESTION_TYPE_LABELS = {
    "choice": "选择题",
    "blank": "填空题",
}


def choose_bank_path(cli_path: str | None) -> Path:
    if cli_path:
        return Path(cli_path).expanduser().resolve()
    user_input = input("请输入题库文件路径: ").strip()
    return Path(user_input).expanduser().resolve()


def choose_question_type() -> str:
    print("\n请选择答题模式:")
    print("1. 只做选择题")
    print("2. 只做填空题")
    print("3. 混合练习")

    mapping = {"1": "choice", "2": "blank", "3": "all"}
    while True:
        selected = input("请输入 1/2/3: ").strip()
        if selected in mapping:
            return mapping[selected]
        print("输入无效，请重新输入 1、2 或 3。")


def filter_questions(bank: QuestionBank, selected_type: str) -> list[Question]:
    if selected_type == "all":
        return list(bank.questions)
    return [question for question in bank.questions if question.type == selected_type]


def format_choice_answer(question: Question, user_answer: str) -> str:
    answer = user_answer.strip().upper()
    if answer and len(answer) == 1 and answer.isalpha():
        return answer

    if question.options:
        for index, option in enumerate(question.options):
            if user_answer.strip() == option:
                return chr(65 + index)
    return user_answer.strip()


def ask_question(question: Question, bank_path: Path, current: int, total: int) -> bool:
    print(f"\n第 {current} / {total} 题")
    print(f"题型: {QUESTION_TYPE_LABELS[question.type]}")
    print(f"题目: {question.prompt}")

    if question.type == "choice" and question.options:
        for index, option in enumerate(question.options):
            print(f"{chr(65 + index)}. {option}")
        raw_answer = input("你的答案: ").strip()
        user_answer = format_choice_answer(question, raw_answer)
    else:
        user_answer = input("你的答案: ").strip()

    is_correct = question.matches_answer(user_answer)
    if is_correct:
        print("结果: 回答正确")
    else:
        print("结果: 回答错误")
        wrong_book_path = record_wrong_question(bank_path, question, user_answer)
        print(f"已加入错题集: {wrong_book_path}")

    print(f"正确答案: {question.answer}")
    print(f"讲解: {question.explanation}")
    return is_correct


def should_continue() -> bool:
    while True:
        selected = input("\n继续下一题？(y/n): ").strip().lower()
        if selected in {"y", "yes"}:
            return True
        if selected in {"n", "no"}:
            return False
        print("请输入 y 或 n。")


def run_quiz(bank: QuestionBank, bank_path: Path) -> None:
    print(f"\n已加载题库: {bank.title}")
    if bank.description:
        print(f"题库说明: {bank.description}")

    selected_type = choose_question_type()
    questions = filter_questions(bank, selected_type)
    if not questions:
        print("当前题库里没有这个题型的题目。")
        return

    random.shuffle(questions)
    correct_count = 0
    answered_count = 0

    for index, question in enumerate(questions, start=1):
        answered_count += 1
        if ask_question(question, bank_path, index, len(questions)):
            correct_count += 1

        if index < len(questions) and not should_continue():
            break

    print("\n本轮练习结束。")
    print(f"已作答: {answered_count} 题")
    print(f"答对: {correct_count} 题")
    print(f"正确率: {correct_count / answered_count:.0%}" if answered_count else "正确率: 0%")

