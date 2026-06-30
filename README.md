# 玄天互动答题工具

这是一个本地运行的命令行答题程序，支持：

- 从本地 JSON 题库读取题目
- 交互式练习选择题和填空题
- 作答后立即显示正确答案和讲解
- 自选题型：只做选择题、只做填空题、混合练习
- 自动记录错题集

## 运行环境

- Python 3.10 及以上

## 快速开始

```bash
python3 main.py --bank example_bank.json
```

如果你不想在命令里传题库路径，也可以直接运行：

```bash
python3 main.py
```

程序会启动后提示你输入本地题库路径。

## 题库格式

题库使用 JSON 文件，根结构示例如下：

```json
{
  "title": "你的题库名称",
  "description": "可选的题库说明",
  "questions": [
    {
      "id": "choice-1",
      "type": "choice",
      "prompt": "题目内容",
      "options": ["选项A内容", "选项B内容", "选项C内容", "选项D内容"],
      "answer": "A",
      "explanation": "题目讲解"
    },
    {
      "id": "blank-1",
      "type": "blank",
      "prompt": "题目内容",
      "answer": "正确答案",
      "explanation": "题目讲解"
    }
  ]
}
```

字段说明：

- `title`：题库名称
- `description`：题库说明，可选
- `questions`：题目数组
- `id`：题目唯一编号，建议不要重复
- `type`：题型，目前支持 `choice` 和 `blank`
- `prompt`：题目内容
- `options`：选择题选项，填空题不需要
- `answer`：正确答案
- `explanation`：答案讲解

## 答题规则

- 选择题建议输入 `A`、`B`、`C`、`D`
- 填空题按文字直接输入
- 当前版本会忽略英文大小写差异

## 错题集

答错的题会自动写入和题库同目录下的错题文件：

```text
你的题库文件名_wrong_book.json
```

比如题库是 `math.json`，错题集就会生成 `math_wrong_book.json`。

错题集本身也是标准题库格式，所以你也可以直接再次练：

```bash
python3 main.py --bank math_wrong_book.json
```

## 本地初始化 Git

```bash
git init
git add .
git commit -m "feat: initialize interactive quiz tool"
```

## 关联远程 GitHub 仓库

先去 GitHub 网站新建一个空仓库，然后在项目目录执行：

```bash
git remote add origin git@github.com:你的用户名/你的仓库名.git
git branch -M main
git push -u origin main
```

如果你还没配置 SSH，也可以用 HTTPS：

```bash
git remote add origin https://github.com/你的用户名/你的仓库名.git
git branch -M main
git push -u origin main
```

## 后续适合继续做的方向

- 支持多答案填空题
- 支持按章节筛题
- 支持从错题集重新练习
- 增加图形界面
