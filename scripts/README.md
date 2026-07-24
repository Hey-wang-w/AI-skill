# scripts 目录说明

> 本目录包含AI学习系统的可执行Python脚本。
> ⚠️ AI必须在正确的时机执行对应脚本，不得跳过。

---

## 脚本列表

| 脚本文件名 | 何时执行 | 功能 | 输入文件 | 输出文件 |
|-----------|---------|------|---------|---------|
| `quiz_pull.py` | **流程A（出题测验）第一步必须执行** | 从飞书拉取所有知识点，按5级优先级筛选今日待考题目，生成题目清单和出题指令 | 无（自动从飞书读取） | `d:\AI\AI学习内容记忆测试\ai-quiz-system\today_quiz.json`<br>`d:\AI\AI学习内容记忆测试\ai-quiz-system\出题指令.txt` |
| `quiz_push.py` | **流程B（批改写回）第四步必须执行** | 读取批改结果，按艾宾浩斯规则计算更新，批量写回飞书多维表格 | `today_quiz.json`（pull生成）<br>`grading.json`（AI生成） | 直接写回飞书，控制台打印总结 |
| `reset_all.py` | **流程F（知识库重置）第二步执行** | 重置所有知识点学习状态为初始值（用于测试） | 无（自动从飞书读取） | 直接写回飞书，控制台打印总结 |
| `config.py` | **（配置文件，不直接执行）** | 全局共享配置（单一事实来源SSOT），所有常量都定义在这里 | — | — |

---

## 执行方式

所有脚本都在PowerShell中执行，使用绝对路径调用：

```powershell
# 拉取今日题目
python d:\AI\AI学习内容记忆测试\ai-quiz-system\scripts\quiz_pull.py

# 写回批改结果（必须先生成grading.json）
python d:\AI\AI学习内容记忆测试\ai-quiz-system\scripts\quiz_push.py

# 重置知识库（⚠️高危，需先AskUserQuestion确认）
python d:\AI\AI学习内容记忆测试\ai-quiz-system\scripts\reset_all.py
```

### 可选参数

**quiz_pull.py：**
- `--date 2026-07-18`：指定测验日期（默认今天）
- `--max 15`：指定最大题数（默认20）

**quiz_push.py：**
- `--date 2026-07-18`：指定测验日期（默认今天）
- `--dry-run`：只计算不写飞书，用于调试测试

**reset_all.py：**
- `--date 2026-07-23`：重置后下次复习日期（默认今天）
- `--dry-run`：只统计记录数，不实际修改

---

## 依赖说明

- Python 3.x
- lark-cli（飞书命令行工具），路径已在config.py中配置：`C:\Users\Administrator\AppData\Roaming\npm\lark-cli.cmd`
- 飞书配置已内置在config.py中（BASE token和TABLE id）
- **所有常量配置都在config.py中，修改配置只改config.py即可**

---

## ⚠️ 重要提示

1. **必须执行脚本**：出题前必须跑quiz_pull.py，批改后必须跑quiz_push.py，不得手动计算轮次和日期
2. **不要随意修改脚本逻辑**：脚本包含FIX#1~#7保护逻辑，修改逻辑会导致复习间隔计算错误
3. **修改配置只改config.py**：所有常量（路径、标签、阈值、字段名等）都定义在config.py中，不要在quiz_pull.py/quiz_push.py中硬编码
4. **文件路径**：脚本读取和生成的文件都在 `d:\AI\AI学习内容记忆测试\ai-quiz-system\` 目录下，不在scripts目录下，也不在项目根目录
5. **执行顺序**：必须是 quiz_pull.py → AI出题 → 用户作答 → AI批改写grading.json → quiz_push.py，不能颠倒
6. **修改后校验**：修改任何脚本或配置后，运行 `python d:\AI\AI学习内容记忆测试\ai-quiz-system\check_consistency.py` 检查一致性
