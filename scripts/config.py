#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.py — ai-quiz-system 全局共享配置（单一事实来源 SSOT）

核心作用：
    本文件是整个项目的"单一事实来源"（Single Source of Truth）。
    所有脚本共用的常量（路径、飞书配置、标签、规则参数、字段名、格式串）都定义在这里。
    修改配置时只改本文件，quiz_pull.py和quiz_push.py通过import引用，自动同步。

使用方式：
    from config import *
    或：from config import SKILL_DIR, LARK, CUMULATIVE, STATUS_VALUES

术语解释：
    - SSOT（Single Source of Truth）：单一事实来源，即一个配置只在一处定义，其他地方引用
    - 来源标签：题目来源的5种分类，决定批改时A/B/C类型的判定
    - 艾宾浩斯间隔：复习轮次推进时的累计天数间隔
    - 魔法值（Magic Value）：代码中直接写死的字符串/数字，应该用本文件中的常量代替
"""
import os

# ── 路径配置 ──────────────────────────────────────────
# lark-cli命令行工具的绝对路径
LARK = r'C:\Users\Administrator\AppData\Roaming\npm\lark-cli.cmd'

# 目录结构（自动计算，无需手动修改）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))          # scripts/目录
SKILL_DIR = os.path.dirname(SCRIPT_DIR)                           # ai-quiz-system/根目录
PROJECT_DIR = os.path.dirname(SKILL_DIR)                          # 项目根目录（d:\AI\AI学习内容记忆测试）

# 飞书多维表格配置
BASE_TOKEN = 'W9pSb30HIaJtOqsQyOrccXAEncf'
TABLE_ID = 'tblmHWZCrloxyZZs'

# 运行时生成文件路径（统一放在Skill根目录）
TODAY_QUIZ_FILE = os.path.join(SKILL_DIR, 'today_quiz.json')
PROMPT_FILE = os.path.join(SKILL_DIR, '出题指令.txt')
GRADING_FILE = os.path.join(SKILL_DIR, 'grading.json')

# ── 艾宾浩斯复习间隔 ──────────────────────────────────
# 累计间隔数组（天数，从添加日期起算）
# 轮次0→1间隔1天，轮次1→2间隔3天，轮次2→3间隔7天，轮次3→4间隔15天，轮次4→5间隔30天
# 修改此数组会改变所有知识点的复习节奏
CUMULATIVE = [1, 3, 7, 15, 30]

# ── 知识点级别配置 ────────────────────────────────────
# 级别名称元组（按优先级从高到低）
LEVELS = ("★★★", "★★☆", "★☆☆")
# 级别排序权重（数值越小越优先）
LEVEL_ORDER = {"★★★": 0, "★★☆": 1, "★☆☆": 2}

# ★☆☆是否主动出题（False=不主动出，只在P5随机巩固完全无题可出时才兜底）
ONE_STAR_ACTIVE = False

# ── 来源标签定义（五选一，批改A/B/C类型判定依据） ─────
# 类型A（答对推进轮次）的标签
TYPE_A_SOURCES = ("薄弱点到期", "到期常规", "新知识点")
# 类型B（答对不推进轮次）的标签
TYPE_B_SOURCES = ("未到期巩固", "随机巩固")
# 所有来源标签（用于校验）
ALL_SOURCES = TYPE_A_SOURCES + TYPE_B_SOURCES
# 薄弱点标签（标🔥的）
WEAK_SOURCES = ("薄弱点到期", "未到期巩固")

# 来源标签对应的图标（控制台输出和试卷显示用）
SOURCE_ICONS = {
    "薄弱点到期": "🔥",
    "未到期巩固": "🔄",
    "到期常规": "📅",
    "新知识点": "⚪",
    "随机巩固": "🎲",
}

# ── 掌握状态定义 ──────────────────────────────────────
# 掌握状态四种枚举值（飞书"掌握状态"单选字段选项必须与此一致）
STATUS_UNTESTED = "⚪未测试"       # 初始状态，未测验过
STATUS_LEARNING = "🟡学习中"       # 正在学习中，尚未完全掌握
STATUS_MASTERED = "🟢已掌握"       # 轮次≥5，完全掌握
STATUS_REVIEW = "🔴待复习"         # 答错后待复习状态
# 所有状态元组
STATUS_VALUES = (STATUS_UNTESTED, STATUS_LEARNING, STATUS_MASTERED, STATUS_REVIEW)
# 掌握状态对应的图标
STATUS_ICONS = {
    STATUS_UNTESTED: "⚪",
    STATUS_LEARNING: "🟡",
    STATUS_MASTERED: "🟢",
    STATUS_REVIEW: "🔴",
}

# ── 题型定义 ──────────────────────────────────────────
# 三种题型
QUESTION_TYPES = ("选择题", "填空题", "简答题")
# 题型对应字母
QUESTION_TYPE_LETTERS = {"选择题": "A", "填空题": "B", "简答题": "C"}

# ── 默认出题参数 ──────────────────────────────────────
DEFAULT_MAX_QUESTIONS = 20          # 默认最大题数
MIN_QUESTIONS = 10                  # 题量不足此数时触发P5随机巩固

# ── 题型分配比例 ──────────────────────────────────────
RATIO_CHOICE = 0.55                 # 选择题目标比例
RATIO_FILL = 0.25                   # 填空题目标比例
RATIO_SHORT = 1 - RATIO_CHOICE - RATIO_FILL  # 简答题自动计算剩余比例

# ── 薄弱点解除条件 ────────────────────────────────────
# 从[重置]标记后连续到期答对次数达到此值时，自动解除薄弱点标记
WEAK_REMOVE_THRESHOLD = 2

# ── 填空题格式规则 ────────────────────────────────────
# 下划线+编号的格式模板：编号前后各4条下划线
FILL_BLANK_PATTERN = "____（{}）____"
# 下划线数量
FILL_UNDERSCORE_COUNT = 4

# ── 批改/日志格式规则 ─────────────────────────────────
# [重置]标记（答错时重置连续答对计数器）
RESET_MARK = "[重置]"
# 薄弱点描述日志前缀（到期答对）
LOG_WEAK_CORRECT = "正式测验{}到期答对"
# 薄弱点描述日志前缀（未到期巩固答对）
LOG_WEAK_REVIEW_CORRECT = "正式测验{}未到期巩固答对"
# 薄弱点描述日志前缀（答错）
LOG_WEAK_WRONG = "正式测验{}答错 {}{}"
# 匹配连续到期答对的正则（用于count_consecutive_correct）
# 注意：此正则必须能匹配LOG_WEAK_CORRECT格式化后的字符串
REGEX_CONSECUTIVE_CORRECT = r'\d{4}-\d{2}-\d{2}到期答对'
# 日期写入格式
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT_DAY = "%Y-%m-%d"

# ── 飞书多维表格字段名（必须与飞书表格列名完全一致） ──
# 修改飞书字段名后，必须同步修改这里
FIELD_RECORD_ID = "record_id"           # 系统字段
FIELD_KP_ID = "知识点ID"                # 文本：6段式知识点ID
FIELD_KP_TITLE = "知识点标题"            # 文本：知识点名称
FIELD_CORE_CONTENT = "核心内容"          # 多行文本：知识点详细内容
FIELD_STATUS = "掌握状态"               # 单选：STATUS_VALUES中的值
FIELD_LEVEL = "重要程度"                # 单选：★★★/★★☆/★☆☆
FIELD_ROUND = "复习轮次"                # 数字：0-5
FIELD_CORRECT_COUNT = "正确次数"         # 数字
FIELD_WRONG_COUNT = "错误次数"           # 数字
FIELD_IS_WEAK = "薄弱点"                # 复选框：true/false
FIELD_WEAK_DESC = "薄弱点描述"           # 多行文本：追加日志
FIELD_IN_WRONG_BOOK = "错题本"          # 复选框
FIELD_ADD_DATE = "添加日期"             # 日期
FIELD_NEXT_DATE = "下次复习日期"         # 日期
FIELD_L0 = "L0阶段"                    # 单选
FIELD_L1 = "L1领域"                    # 单选
FIELD_L2 = "L2模块"                    # 单选
FIELD_L3 = "L3主题"                    # 单选
FIELD_L4 = "L4章节"                    # 单选
FIELD_TAGS = "知识标签"                # 多选

# 所有飞书字段名元组（用于校验）
ALL_FIELDS = (
    FIELD_KP_ID, FIELD_KP_TITLE, FIELD_CORE_CONTENT, FIELD_STATUS,
    FIELD_LEVEL, FIELD_ROUND, FIELD_CORRECT_COUNT, FIELD_WRONG_COUNT,
    FIELD_IS_WEAK, FIELD_WEAK_DESC, FIELD_IN_WRONG_BOOK,
    FIELD_ADD_DATE, FIELD_NEXT_DATE,
    FIELD_L0, FIELD_L1, FIELD_L2, FIELD_L3, FIELD_L4, FIELD_TAGS,
)

# ── grading.json 字段名（批改结果JSON格式） ──────────
GRADING_FIELD_QNO = "题号"       # 数字：题号
GRADING_FIELD_CORRECT = "正确"   # 布尔：true/false
GRADING_FIELD_REASON = "错因"    # 文本：答错时的错因分析

# ── 试卷结尾语 ────────────────────────────────────────
QUIZ_ENDING = "请按顺序作答，可以一次性写在一个回复里，也可以逐题回答。"

# ── 文件路径（文档和模板） ────────────────────────────
REFERENCES_DIR = os.path.join(SKILL_DIR, 'references')
TEMPLATES_DIR = os.path.join(SKILL_DIR, 'assets', 'templates')
CHECKLISTS_DIR = os.path.join(SKILL_DIR, 'assets', 'checklists')

# 参考文档路径
DOC_QUESTION_FORMAT = os.path.join(REFERENCES_DIR, '01-question-format.md')
DOC_GRADING_RULES = os.path.join(REFERENCES_DIR, '02-grading-rules.md')
DOC_KNOWLEDGE_INGEST = os.path.join(REFERENCES_DIR, '03-knowledge-ingest.md')
DOC_TAXONOMY = os.path.join(REFERENCES_DIR, '04-knowledge-taxonomy.md')
SKILL_MD = os.path.join(SKILL_DIR, 'SKILL.md')

# 模板文件路径
TEMPLATE_QUIZ_PAPER = os.path.join(TEMPLATES_DIR, 'quiz-paper.md')
TEMPLATE_GRADING_RESULT = os.path.join(TEMPLATES_DIR, 'grading-result.json')
TEMPLATE_GRADING_SUMMARY = os.path.join(TEMPLATES_DIR, 'grading-summary.md')
TEMPLATE_INGEST_FEEDBACK = os.path.join(TEMPLATES_DIR, 'ingest-feedback.md')

# 检查清单路径
CHECKLIST_QUESTION = os.path.join(CHECKLISTS_DIR, 'question-checklist.md')
CHECKLIST_GRADING = os.path.join(CHECKLISTS_DIR, 'grading-checklist.md')
