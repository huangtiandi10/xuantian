from __future__ import annotations

import argparse
import sys

from .quiz import choose_bank_path, run_quiz
from .storage import load_question_bank


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="玄天互动答题工具")
    parser.add_argument(
        "--bank",
        help="题库 JSON 文件路径。不传时，程序启动后会提示输入。",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        bank_path = choose_bank_path(args.bank)
        bank = load_question_bank(bank_path)
        run_quiz(bank, bank_path)
    except KeyboardInterrupt:
        print("\n已中断。")
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"程序启动失败: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

