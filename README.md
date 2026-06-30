# 玄天题练

这是一个本地运行的网页答题系统，面向选择题和填空题练习，支持：

- 本地账户登录注册
- 保存多个题库，下次不用重新上传
- 按题型开始练习：选择题、填空题、混合练习
- 选择题用按钮点击作答，填空题用输入框作答
- 每题作答后立即展示正确答案和讲解
- 自动保存未完成进度，下次登录后可以继续
- 错题集按题库分类，再按题型二次分类

## 运行方式

如果你使用 Anaconda，可以先创建并进入环境：

```bash
conda env create -f environment.yml
conda activate xuantian
```

如果环境已经创建过，只需要：

```bash
conda activate xuantian
```

然后启动项目：

```bash
python3 main.py
```

启动后打开浏览器访问：

```text
http://127.0.0.1:5000
```

## 题库格式

题库文件使用 JSON，结构如下：

```json
{
  "title": "你的题库名称",
  "description": "可选说明",
  "questions": [
    {
      "id": "choice-1",
      "type": "choice",
      "prompt": "题目内容",
      "options": ["选项A", "选项B", "选项C", "选项D"],
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

## 导入题库

系统支持两种方式：

1. 填写本地 JSON 文件路径
2. 直接上传 JSON 文件

导入后题库会保存到本地数据库，下次登录还能继续使用。

## 数据保存位置

程序会在项目目录下自动生成：

```text
.xuantian_data/app.db
```

这里会保存用户账号、题库内容、练习进度和错题记录。

## 测试

```bash
python3 -m pytest
```
