#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quiz_pull.py — 从飞书多维表格拉取所有知识点，按5级优先级筛选今日测验题目（Skill版）

核心功能：
    读取飞书知识点库，按5级出题优先级（薄弱点到期→到期常规→新知识点→未到期巩固→随机巩固），
    结合从飞书"重要程度"字段读取的★★★/★★☆/★☆☆分级排序，输出今日测验题目清单。
    默认限制20题，可用--max参数调整；★☆☆不主动出题。

用法：
    python quiz_pull.py                       # 默认今天，默认20题
    python quiz_pull.py --date 2026-07-18     # 指定日期
    python quiz_pull.py --max 30              # 手动指定最大题数（可选）

输出（均保存至ai-quiz-system目录）：
    - today_quiz.json 供 quiz_push.py 批改写回
    - 出题指令.txt 给AI的完整出题规范+知识点清单
    - 控制台打印筛选统计

术语解释：
    - FIX#1~#7：防催熟（复习间隔过短）保护规则，本版全部保留
    - 催熟：复习间隔过短导致记忆效果虚高的问题
    - 配置常量全部从config.py导入，实现单一事实来源(SSOT)
    - SSOT（Single Source of Truth）：单一事实来源，即一个配置只在一处定义，其他地方引用
"""
import argparse
import json
import os
import random
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from itertools import groupby

# 从共享配置导入所有常量（单一事实来源）
from config import (
    LARK, SKILL_DIR, SCRIPT_DIR, PROJECT_DIR,
    BASE_TOKEN, TABLE_ID, TODAY_QUIZ_FILE, PROMPT_FILE,
    CUMULATIVE, LEVEL_ORDER, LEVELS, ONE_STAR_ACTIVE,
    TYPE_A_SOURCES, TYPE_B_SOURCES, ALL_SOURCES, WEAK_SOURCES,
    DEFAULT_MAX_QUESTIONS, MIN_QUESTIONS,
    RATIO_CHOICE, RATIO_FILL, RATIO_SHORT,
    DOC_QUESTION_FORMAT, DOC_GRADING_RULES, CHECKLIST_QUESTION,
    FILL_BLANK_PATTERN,
    # 新增导入
    SOURCE_ICONS,
    STATUS_UNTESTED, STATUS_LEARNING, STATUS_MASTERED, STATUS_REVIEW,
    FIELD_RECORD_ID, FIELD_KP_ID, FIELD_KP_TITLE, FIELD_CORE_CONTENT,
    FIELD_STATUS, FIELD_LEVEL, FIELD_ROUND, FIELD_CORRECT_COUNT,
    FIELD_WRONG_COUNT, FIELD_IS_WEAK, FIELD_WEAK_DESC, FIELD_IN_WRONG_BOOK,
    FIELD_ADD_DATE, FIELD_NEXT_DATE,
    FIELD_L0, FIELD_L1, FIELD_L2, FIELD_L3, FIELD_L4, FIELD_TAGS,
    QUESTION_TYPES, QUIZ_ENDING,
)

# lark-cli工作目录为Skill根
CWD = SKILL_DIR


def parse_lark_text(val):
    """
    将lark-cli返回的文本字段值转为纯字符串。
    lark-cli的text字段可能直接返回字符串，也可能是列表格式 [{"text":"..."},...]，或单选字段返回列表。
    输入参数：val为lark-cli返回的任意字段值。
    返回值：提取后的纯字符串。
    """
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        if len(val) > 0:
            if isinstance(val[0], dict):
                return val[0].get("text", str(val[0]))
            return str(val[0])
        return ""
    return str(val)


def parse_lark_multi_select(val):
    """
    解析多选字段（知识标签），返回标签字符串列表。
    输入参数：val为lark-cli返回的多选字段值。
    返回值：list[str] 标签列表。
    """
    if val is None:
        return []
    if isinstance(val, str):
        return [val] if val else []
    if isinstance(val, list):
        result = []
        for item in val:
            if isinstance(item, dict):
                result.append(item.get("text", ""))
            else:
                result.append(str(item))
        return [r for r in result if r]
    return []


def parse_date(val):
    """
    将lark-cli返回的日期字符串转为date对象。
    支持格式：'YYYY-MM-DD' 和 'YYYY-MM-DD HH:MM:SS'。
    输入参数：val为日期字符串或None。
    返回值：datetime.date对象，解析失败返回None。
    """
    text = parse_lark_text(val).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19] if len(text) >= 19 else text, fmt).date()
        except ValueError:
            continue
    return None


def read_checklist(path):
    """
    从markdown自检清单文件中动态读取checkbox项，格式化为出题prompt中使用的编号清单项。

    核心功能：
        读取指定md文件，提取所有以"- [ ]"开头的行（即未勾选的检查项），
        去掉前缀后按顺序编号为"N. [ ] 内容"的格式返回。
        如果文件不存在或读取失败，返回硬编码的兜底清单（fallback），保证程序不崩溃。

    输入参数：path为自检清单md文件的绝对路径（对应config.py中的CHECKLIST_QUESTION）。
    返回值：str，格式化后的自检清单文本（每行一项，以换行符分隔），可直接嵌入prompt。
    """
    # 兜底清单：当文件读取失败时使用，确保功能不中断
    fallback_items = [
        '🔴题目顺序与知识点ID完全对应：严格按照知识点清单顺序出题，第N题ID与清单[N]一致？（最高优先级，违反会导致批改错误）',
        '所有填空题都有"____（N）____"格式——编号**前后**都有4条下划线？',
        '所有专业名词首次出现都有中文解释？',
        '每题开头元信息格式正确（**第N题** [ID] [题型] [来源标签]），N和ID都与清单对应，来源标签是五选一？',
        '所有薄弱点题目（清单中标🔥的）都在末尾标了🔥？到期常规没标🔥？',
        '选择题都是4个选项，没有"以上都对/都不对"？正确选项位置随机但题目顺序不变？',
        '填空题末尾有字数提示？',
        '简答题标注了最少要点数？',
        '题与题之间空一行？',
        '★☆☆知识点只出了选择题？',
        '没有超纲内容，所有题目都来自上面的知识点清单？',
        '试卷头统计数字与实际题目数量一致？',
    ]

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # 提取所有以"- [ ]"开头的行（markdown未勾选项）
        items = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- [ ]"):
                # 去掉"- [ ] "前缀，保留后面的检查项文本
                text = stripped[len("- [ ] "):]
                items.append(text)
        # 如果文件中没有提取到任何项，使用兜底清单
        if not items:
            items = fallback_items
    except (FileNotFoundError, IOError, OSError):
        # 文件不存在或读取失败时使用兜底清单
        items = fallback_items

    # 格式化为编号清单："1. [ ] 内容"、"2. [ ] 内容"...
    formatted_lines = []
    for idx, text in enumerate(items, start=1):
        formatted_lines.append(f"{idx}. [ ] {text}")
    return "\n".join(formatted_lines)


def fetch_records():
    """
    调用lark-cli读取多维表格所有记录，并解析为知识点对象列表。

    核心功能：
        执行lark-cli命令获取飞书多维表格的全部记录，
        根据字段类型（布尔、整数、文本、多选、日期）分别解析，
        所有字段名使用config.py中定义的FIELD_*常量，避免硬编码。

    无输入参数（使用config.py中的全局配置LARK/BASE_TOKEN/TABLE_ID）。
    返回值：list[dict]，每个dict包含完整的知识点字段，键名与飞书字段名一致。
    """
    cmd = [
        LARK, "base", "+record-list",
        "--base-token", BASE_TOKEN,
        "--table-id", TABLE_ID,
        "--page-size", "200",
        "--format", "json"
    ]
    r = subprocess.run(cmd, cwd=CWD, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(f'❌ lark-cli调用失败: {r.stderr}', file=sys.stderr)
        sys.exit(1)

    data = json.loads(r.stdout)
    d = data.get("data", {})
    fields_order = d.get("fields", [])
    rows = d.get("data", [])
    rec_ids = d.get("record_id_list", [])

    # 布尔型字段（复选框）：薄弱点、错题本
    bool_fields = (FIELD_IS_WEAK, FIELD_IN_WRONG_BOOK)
    # 整数型字段：错误次数、复习轮次、正确次数
    int_fields = (FIELD_WRONG_COUNT, FIELD_ROUND, FIELD_CORRECT_COUNT)
    # 单选/文本型字段：掌握状态、重要程度、L0-L4分类
    text_fields = (FIELD_STATUS, FIELD_LEVEL, FIELD_L0, FIELD_L1, FIELD_L2, FIELD_L3, FIELD_L4)
    # 日期型字段：添加日期、下次复习日期
    date_fields = (FIELD_ADD_DATE, FIELD_NEXT_DATE)

    records = []
    for i, row in enumerate(rows):
        rec = {FIELD_RECORD_ID: rec_ids[i] if i < len(rec_ids) else ""}
        for j, field_name in enumerate(fields_order):
            val = row[j] if j < len(row) else None
            if field_name in bool_fields:
                # 布尔字段：lark-cli可能返回布尔值或列表形式
                rec[field_name] = bool(val) if not isinstance(val, list) else bool(val[0]) if val else False
            elif field_name in int_fields:
                # 整数字段：解析为int，失败默认为0
                try:
                    rec[field_name] = int(val) if val is not None else 0
                except (ValueError, TypeError):
                    rec[field_name] = 0
            elif field_name in text_fields:
                # 文本/单选字段：使用parse_lark_text解析
                rec[field_name] = parse_lark_text(val)
            elif field_name == FIELD_TAGS:
                # 多选字段（知识标签）：使用parse_lark_multi_select解析为列表
                rec[field_name] = parse_lark_multi_select(val)
            elif field_name in date_fields:
                # 日期字段：先取文本，后续用parse_date转为date对象
                rec[field_name] = parse_lark_text(val)
            else:
                # 其他字段（如知识点ID、标题、核心内容、薄弱点描述等）默认按文本处理
                rec[field_name] = parse_lark_text(val)
        records.append(rec)
    return records


def level_sort_key(kp):
    """
    返回知识点在组内排序的键值（级别优先→轮次低优先）。

    核心功能：
        为知识点生成排序键，使高级别（★★★）排在前面，
        同级别内复习轮次低的排在前面（优先复习早期阶段的知识点）。

    输入参数：kp为知识点dict（需包含FIELD_LEVEL和FIELD_ROUND字段）。
    返回值：tuple(级别权重, 复习轮次)，Python按此元组升序排列。
             级别权重来自LEVEL_ORDER字典，数值越小越优先。
    """
    lvl = LEVEL_ORDER.get(kp.get(FIELD_LEVEL, LEVELS[1]), 1)
    return (lvl, kp.get(FIELD_ROUND, 0))


def get_level(kp):
    """
    获取知识点的重要程度级别。

    输入参数：kp为知识点dict。
    返回值：str，★★★/★★☆/★☆☆三个级别字符串之一，默认为★★☆。
    """
    return kp.get(FIELD_LEVEL, LEVELS[1])


def filter_today(records, today, max_n=DEFAULT_MAX_QUESTIONS):
    """
    按5级优先级分层筛选当日测验知识点。FIX#1~#7保护规则全部保留。

    核心功能：
        将所有知识点按5个优先级（P1-P5）分层筛选，组成今日测验题目清单。
        到期项优先（P1/P2/P3），未到期项仅补位（P4/P5仅在题量不足时才出题）；
        ★☆☆知识点不主动出题，仅在P5无题可出时才兜底随机抽取。

    优先级定义（到期优先，未到期仅补位）：
      P1 — 薄弱点到期   → 来源标签=TYPE_A_SOURCES[0]（薄弱点=true且下次复习<=今天，标🔥）
      P2 — 到期常规     → 来源标签=TYPE_A_SOURCES[1]（薄弱点=false且下次复习<=今天且非已掌握）
      P3 — 新知识点     → 来源标签=TYPE_A_SOURCES[2]（⚪未测试且添加日期+1天=今天）
      P4 — 未到期巩固   → 来源标签=TYPE_B_SOURCES[0]（薄弱点=true且下次复习>今天，仅当题量<MIN_QUESTIONS时才出题，标🔥）
      P5 — 随机巩固     → 来源标签=TYPE_B_SOURCES[1]（题量仍<MIN_QUESTIONS时从学习中剩余KP补）

    输入参数：
        records — list[dict]，所有知识点列表（来自fetch_records()）；
        today — datetime.date对象，测验日期；
        max_n — int，最大题数（默认DEFAULT_MAX_QUESTIONS=20）。
    返回值：(selected, stats)。
        selected — list[dict]，选中的知识点列表，每个元素额外包含"来源标签"和"级别"字段；
        stats — dict，统计信息（总题数、来源分布、级别分布、各候选池大小）。
    """
    selected_ids = set()
    result = []

    # 来源标签常量引用（提高可读性）
    SRC_WEAK_DUE = TYPE_A_SOURCES[0]       # "薄弱点到期"
    SRC_WEAK_REVIEW = TYPE_B_SOURCES[0]    # "未到期巩固"
    SRC_NORMAL_DUE = TYPE_A_SOURCES[1]     # "到期常规"
    SRC_NEW = TYPE_A_SOURCES[2]            # "新知识点"
    SRC_RANDOM = TYPE_B_SOURCES[1]         # "随机巩固"

    def add_kp(kp, source_label):
        """
        将一个知识点加入结果列表。

        核心功能：
            执行FIX#5去重检查（已选ID跳过），执行★☆☆不主动出题规则，
            为知识点添加"来源标签"和"级别"两个额外字段后加入结果列表。

        输入参数：kp为知识点dict；source_label为来源标签字符串。
        返回值：bool，True表示成功加入，False表示被跳过。
        """
        rid = kp[FIELD_RECORD_ID]
        if rid in selected_ids or len(result) >= max_n:
            return False
        # ★☆☆不主动出题（P5随机巩固时才允许，除非ONE_STAR_ACTIVE=True）
        if source_label != SRC_RANDOM and not ONE_STAR_ACTIVE and get_level(kp) == LEVELS[2]:
            return False
        kp_out = dict(kp)
        kp_out["来源标签"] = source_label  # 自定义输出字段，不对应飞书原始字段
        kp_out["级别"] = get_level(kp)     # 自定义输出字段，不对应飞书原始字段
        result.append(kp_out)
        selected_ids.add(rid)
        return True

    def batch_add(candidates, source_label, sort_by_level=True):
        """
        批量加入一组候选知识点。

        输入参数：candidates为候选知识点列表；source_label为来源标签；
                   sort_by_level为True时先按level_sort_key排序再加入。
        返回值：无（直接修改result列表）。
        """
        if sort_by_level:
            candidates.sort(key=level_sort_key)
        for kp in candidates:
            if len(result) >= max_n:
                break
            add_kp(kp, source_label)

    # ── P1：薄弱点到期（最高优先级，不能裁） ──
    p1 = [
        kp for kp in records
        if kp.get(FIELD_IS_WEAK) is True
        and parse_date(kp.get(FIELD_NEXT_DATE, "")) is not None
        and parse_date(kp.get(FIELD_NEXT_DATE, "")) <= today
    ]
    p1.sort(key=level_sort_key)
    batch_add(p1, SRC_WEAK_DUE, sort_by_level=False)

    # ── P2：到期常规（非薄弱点、非已掌握，已到/过期复习日） ──
    p2 = [
        kp for kp in records
        if kp.get(FIELD_IS_WEAK) is not True
        and kp.get(FIELD_STATUS, "") != STATUS_MASTERED
        and parse_date(kp.get(FIELD_NEXT_DATE, "")) is not None
        and parse_date(kp.get(FIELD_NEXT_DATE, "")) <= today
    ]
    batch_add(p2, SRC_NORMAL_DUE)

    # ── P3：新知识点（未测试且添加日期+1天=今天） ──
    add_plus_one = today - timedelta(days=1)
    p3 = [
        kp for kp in records
        if kp.get(FIELD_STATUS, "") == STATUS_UNTESTED
        and parse_date(kp.get(FIELD_ADD_DATE, "")) == add_plus_one
    ]
    batch_add(p3, SRC_NEW)

    # ── P4：未到期巩固（薄弱点未到期，仅当题量不足时才出题） ──
    p4 = [
        kp for kp in records
        if kp.get(FIELD_IS_WEAK) is True
        and parse_date(kp.get(FIELD_NEXT_DATE, "")) is not None
        and parse_date(kp.get(FIELD_NEXT_DATE, "")) > today
    ]
    if len(result) < MIN_QUESTIONS:
        p4.sort(key=level_sort_key)
        batch_add(p4, SRC_WEAK_REVIEW, sort_by_level=False)

    # ── P5：随机巩固（若题量仍<MIN_QUESTIONS，从学习中/未测试剩余KP补） ──
    if len(result) < MIN_QUESTIONS:
        learning = [
            kp for kp in records
            if kp.get(FIELD_STATUS, "") in (STATUS_LEARNING, STATUS_UNTESTED)
            and kp.get(FIELD_IS_WEAK) is not True
            and kp[FIELD_RECORD_ID] not in selected_ids
            and get_level(kp) != LEVELS[2]
        ]
        # 同级别内随机：先按级别分组，同级别内shuffle
        learning.sort(key=level_sort_key)
        random.seed(hash(str(today)))
        shuffled = []
        for _, group in groupby(learning, key=level_sort_key):
            group_list = list(group)
            random.shuffle(group_list)
            shuffled.extend(group_list)
        batch_add(shuffled, SRC_RANDOM, sort_by_level=False)

    src_count = Counter(r["来源标签"] for r in result)
    lvl_count = Counter(r["级别"] for r in result)

    stats = {
        "total": len(result),
        "by_source": dict(src_count),
        "by_level": dict(lvl_count),
        "p1_pool": len(p1), "p2_pool": len(p2),
        "p3_pool": len(p3), "p4_pool": len(p4),
    }
    return result, stats


def generate_quiz_prompt(selected_kps, prompt_path, today_str):
    """
    生成AI出题指令文件，包含完整格式规范、正确示例和今日知识点清单。

    核心功能：
        1. 统计各来源/级别题数，计算题型分配（选择/填空/简答）；
        2. 从CHECKLIST_QUESTION文件动态读取自检清单项（失败则使用兜底清单）；
        3. 拼接完整的出题指令prompt，包含格式规则、示例、知识点清单、自检清单；
        4. 在试卷结尾处添加QUIZ_ENDING提示语；
        5. 将完整内容写入prompt_path指定的文件。

    输入参数：
        selected_kps — list[dict]，今日选中的知识点列表（来自main()中构建的out列表）；
        prompt_path — str，出题指令文件输出路径（对应PROMPT_FILE）；
        today_str — str，日期字符串（YYYY-MM-DD格式）。
    返回值：无（直接写入文件）。
    """
    src_count = Counter(r["来源标签"] for r in selected_kps)
    lvl_count = Counter(r["级别"] for r in selected_kps)

    # 来源标签常量引用
    SRC_WEAK_DUE = TYPE_A_SOURCES[0]       # "薄弱点到期"
    SRC_WEAK_REVIEW = TYPE_B_SOURCES[0]    # "未到期巩固"
    SRC_NORMAL_DUE = TYPE_A_SOURCES[1]     # "到期常规"
    SRC_NEW = TYPE_A_SOURCES[2]            # "新知识点"
    SRC_RANDOM = TYPE_B_SOURCES[1]         # "随机巩固"

    # 题型分配建议（★★★可出简答，★☆☆只出选择）
    total = len(selected_kps)
    n_choice = max(1, int(total * RATIO_CHOICE))
    n_fill = max(1, int(total * RATIO_FILL)) if total >= 4 else 0
    n_short = total - n_choice - n_fill
    if n_short < 0:
        n_short = 0
        n_fill = total - n_choice

    # 统计各来源题数（试卷头用），使用常量引用避免硬编码
    n_weak = src_count.get(SRC_WEAK_DUE, 0) + src_count.get(SRC_WEAK_REVIEW, 0)
    n_normal_due = src_count.get(SRC_NORMAL_DUE, 0)
    n_new = src_count.get(SRC_NEW, 0)
    n_random = src_count.get(SRC_RANDOM, 0)

    # 各来源图标（从SOURCE_ICONS常量获取）
    icon_weak_due = SOURCE_ICONS[SRC_WEAK_DUE]        # 🔥
    icon_weak_review = SOURCE_ICONS[SRC_WEAK_REVIEW]  # 🔄
    icon_normal_due = SOURCE_ICONS[SRC_NORMAL_DUE]    # 📅
    icon_new = SOURCE_ICONS[SRC_NEW]                  # ⚪
    icon_random = SOURCE_ICONS[SRC_RANDOM]            # 🎲

    # 填空格式示例，使用config中定义的FILL_BLANK_PATTERN
    fill_example1 = FILL_BLANK_PATTERN.format(1)
    fill_example2 = FILL_BLANK_PATTERN.format(2)

    # 动态读取自检清单（从question-checklist.md文件，失败则用兜底清单）
    checklist_text = read_checklist(CHECKLIST_QUESTION)

    # 级别名称常量引用（LEVELS = ("★★★", "★★☆", "★☆☆")）
    lvl_core = LEVELS[0]      # "★★★"
    lvl_important = LEVELS[1] # "★★☆"
    lvl_supplement = LEVELS[2] # "★☆☆"

    prompt_content = f"""# 📝 AI知识每日测验出题指令
日期：{today_str}
共 {total} 题

## ⚠️ 🔴 最高优先级规则（违反即批改错误，必须100%遵守）
**🔴 必须严格按照下面"今日待出题知识点清单"的顺序出题，不得打乱顺序！**
- 知识点清单中编号为[1]的知识点 → 必须是试卷上的**第1题**
- 知识点清单中编号为[2]的知识点 → 必须是试卷上的**第2题**
- ...以此类推，第N题必须对应知识点清单[N]
- **题目编号N和知识点ID必须与清单完全一致，不得重新排序、不得调整顺序、不得按题型分组**
- 题型混合在原顺序中自然分布即可，不需要把同题型放一起
- 违反此规则会导致批改时对错更新到错误的知识点上，造成复习进度完全错乱！

## ⚠️ 严格格式要求（必须100%遵守，否则题目不合格）

### 一、通用格式规则
1. **每题开头必须标注元信息**，格式：`**第N题** [知识点ID] [题型] [来源标签] 🔥`
   - N必须与知识点清单中的编号完全一致
   - 知识点ID必须与清单中该编号的ID完全一致，不得写错
   - 题型只能是：`[选择]`、`[填空]`、`[简答]`三选一
   - 来源标签只能是五选一，与下面知识点清单中的"来源"字段完全一致：
     * `[{SRC_WEAK_DUE}]` — 薄弱点且今天到期（标🔥）
     * `[{SRC_WEAK_REVIEW}]` — 薄弱点但今天没到期（标🔥）
     * `[{SRC_NORMAL_DUE}]` — 非薄弱点今天到期（不标🔥）
     * `[{SRC_NEW}]` — 昨天刚加的新知识点（不标🔥）
     * `[{SRC_RANDOM}]` — 题量不足时随机补充（不标🔥）
2. 专业名词**首次出现必须附括号中文解释**（如"过拟合（指模型死记硬背训练数据、遇到新题就错的现象）"）
3. 题与题之间空一行，不加分隔线
4. 不通过加粗、斜体、特殊排版暗示答案

---

### 二、选择题格式（{n_choice}题）
**格式模板：**
```
**第N题** [知识点ID] [选择] [来源标签] 🔥

[题干：一个完整的问句或陈述，指向单一明确的知识点]

A. [选项一]
B. [选项二]
C. [选项三]
D. [选项四]
```

**选择题规则：**
- 固定4个选项（A/B/C/D），正确选项位置随机
- 干扰项基于常见误解设计，不能明显荒唐
- 四个选项长度大致均衡
- 禁用"以上都对""以上都不对"（除非是"哪项不属于"类判断题）

**✅ 选择题正确示例：**
```
**第13题** [1-AI-ML-CORE-OVERFIT-01] [选择] [{SRC_NEW}]

过拟合（Overfitting，指模型在训练数据上表现极好但在新数据上表现很差的现象）是机器学习最核心的陷阱。以下哪种做法是防范过拟合的标准方法？

A. 用全部数据训练模型，反复训练直到训练误差为零
B. 把数据分成训练集和测试集，只用训练集训练，测试集只在最后评估用一次
C. 让模型记住所有训练样本的细节，确保训练集准确率100%
D. 用测试集反复调整模型参数，直到测试集准确率最高
```

---

### 三、填空题格式（{n_fill}题）
**⚠️ 填空题最容易出错，必须严格遵守下划线规则！**

**格式模板：**
```
**第N题** [知识点ID] [填空] [来源标签]

[一个完整句子，每个空白位置必须用"{fill_example1}"格式标记：编号前后都要有4条下划线]

（第1空X~Y个字，第2空X~Y个字……）
```

**填空题强制规则（违反即不合格）：**
1. **下划线前后都要有**：每个空格式必须是 `{fill_example1}`（4条下划线+括号编号+4条下划线），不能只写`（1）`不写下划线，也不能只写前导下划线不写尾部下划线！
2. **编号必须有**：每个空对应唯一编号（1）（2）（3）
3. **字数提示必须有**：题干末尾必须标注每个空的预期字数范围
4. 每道题1~3个空，整句话去掉空白后语法通顺

**❌ 错误示例（没有下划线或下划线不全，不合格）：**
```
大型语言模型（LLM）的训练目标是：给定一段文本，（1）。
大型语言模型（LLM）的训练目标是：给定一段文本，____（1）。
```

**✅ 填空题正确示例（必须照此格式，下划线前后都有）：**
```
**第7题** [1-AI-ETHIC-FUTURE-XAI-01] [填空] [{SRC_WEAK_DUE}] 🔥

欧盟GDPR（《通用数据保护条例》，欧盟出台的隐私保护法案）赋予用户的三大核心权利是{fill_example1}权、{fill_example2}权和____（3）____权。

（每空2~4个字）
```

**✅ 另一个正确示例：**
```
**第12题** [1-AI-ML-DL-LLM-01] [填空] [{SRC_NEW}]

大型语言模型（LLM，Large Language Model，如GPT系列）的训练目标极其简单：给定一段文本，{fill_example1}。当模型规模达到一定阈值后，会突然具备小模型没有的能力，如推理、编程、翻译等，这种现象叫做{fill_example2}。

（第1空6~12个字，第2空2~4个字）
```

---

### 四、简答题格式（{n_short}题，优先给★★★核心知识点）
**格式模板：**
```
**第N题** [知识点ID] [简答] [来源标签]

[一个开放式问题，要求回答原因/列举/解释/对比]

（请列出至少__个要点，共约__字）
```

**简答题规则：**
- 用于★★★核心知识点的因果分析、概念对比、机制解释
- 题干必须注明最少要点数
- 必须是理解性问题，不能是默写背诵题
- ★☆☆补充知识点不出简答题

**✅ 简答题正确示例：**
```
**第6题** [1-AI-ETHIC-FUTURE-DOOM-01] [简答] [{SRC_WEAK_DUE}] 🔥

为什么"终结者末日情景"（指科幻电影中AI突然觉醒并憎恨人类、试图毁灭人类的设想）在现有AI技术框架下不现实？

（请至少列出两个原因，约40~80字）
```

---

### 五、试卷开头格式
第一题之前必须输出试卷头：
```
## 📝 每日测验

（正式考核，答题后会更新飞书复习记录）

共 **{total} 题**
题型分布：选择题 {n_choice} 题 + 填空题 {n_fill} 题 + 简答题 {n_short} 题
来源分布：{icon_weak_due}薄弱点题 {n_weak} 题（{SRC_WEAK_DUE} {src_count.get(SRC_WEAK_DUE,0)} + {SRC_WEAK_REVIEW} {src_count.get(SRC_WEAK_REVIEW,0)}）+ {icon_normal_due}{SRC_NORMAL_DUE} {n_normal_due} 题 + {icon_new}{SRC_NEW} {n_new} 题 + {icon_random}{SRC_RANDOM} {n_random} 题
覆盖知识点分级：{lvl_core}核心 {lvl_count.get(lvl_core,0)} 题 / {lvl_important}重要 {lvl_count.get(lvl_important,0)} 题 / {lvl_supplement}补充 {lvl_count.get(lvl_supplement,0)} 题

---

```

---

## 📚 今日待出题知识点清单

请严格按照以下知识点的核心内容出题，不要超纲，不要编造知识点：

"""
    # 添加每个知识点的详细信息（使用FIELD_*常量访问字典键）
    for kp in selected_kps:
        tags_str = "、".join(kp.get(FIELD_TAGS, [])) if kp.get(FIELD_TAGS) else "无"
        weak_mark = "🔥【薄弱点】" if kp.get(FIELD_IS_WEAK) else ""
        prompt_content += f"""
### [{kp['题号']}] {kp[FIELD_KP_ID]} {weak_mark}
- 标题：{kp[FIELD_KP_TITLE]}
- 级别：{kp['级别']}
- 来源：{kp['来源标签']}
- 分类：{kp.get(FIELD_L0,'')} → {kp.get(FIELD_L1,'')} → {kp.get(FIELD_L2,'')} → {kp.get(FIELD_L3,'')} → {kp.get(FIELD_L4,'')}
- 知识标签：{tags_str}
- 掌握状态：{kp[FIELD_STATUS]}（复习轮次：{kp[FIELD_ROUND]}）
- 核心内容：
{kp.get(FIELD_CORE_CONTENT,'')}

"""

    prompt_content += f"""
---

## ✅ 出题前自检清单（出题后逐条核对，不通过不能输出）
{checklist_text}

全部检查通过后再输出最终题目！

{QUIZ_ENDING}
"""

    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt_content)


def main():
    """
    主函数：解析命令行参数→拉取飞书数据→优先级筛选→保存JSON→生成出题指令→打印统计。

    核心功能：
        1. 解析--date和--max命令行参数；
        2. 调用fetch_records()拉取飞书全部知识点；
        3. 打印全库状态/级别分布统计；
        4. 调用filter_today()筛选今日题目；
        5. 构建输出字典out（键名使用FIELD_*常量），保存为today_quiz.json；
        6. 调用generate_quiz_prompt()生成出题指令文件；
        7. 打印筛选结果统计和题目清单。

    无输入参数（命令行参数通过argparse解析）。
    返回值：无（结果写入文件，统计打印到控制台）。
    """
    ap = argparse.ArgumentParser(description="从飞书多维表格筛选今日测验题目（Skill版）")
    ap.add_argument("--date", default=None, help="测验日期 YYYY-MM-DD，默认今天")
    ap.add_argument("--max", type=int, default=DEFAULT_MAX_QUESTIONS, help=f"最大题数，默认{DEFAULT_MAX_QUESTIONS}")
    args = ap.parse_args()

    today = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    today_str = today.strftime("%Y-%m-%d")

    print(f"📅 测验日期: {today_str}")
    print(f"📂 工作目录: {SKILL_DIR}")
    print("🔄 正在从飞书拉取知识点...")
    records = fetch_records()
    print(f"✅ 共读取 {len(records)} 条知识点")

    # 全库分布统计（使用FIELD_*常量访问键名）
    status_dist = Counter(r.get(FIELD_STATUS, "未知") for r in records)
    level_dist = Counter(r.get(FIELD_LEVEL, "未知") for r in records)
    print(f"📊 掌握状态: {' / '.join(f'{k}:{v}' for k, v in status_dist.items())}")
    print(f"⭐ 知识点分级: {' / '.join(f'{k}:{v}' for k, v in level_dist.items())}")

    selected, stats = filter_today(records, today, args.max)

    # 构建输出JSON（键名使用FIELD_*常量，保持值不变）
    # 注意："题号"、"来源标签"、"级别"是quiz_pull自定义输出字段，不对应飞书原始字段，保持字符串字面量
    out = []
    for i, r in enumerate(selected):
        out.append({
            "题号": i + 1,
            FIELD_RECORD_ID: r[FIELD_RECORD_ID],
            FIELD_KP_ID: r.get(FIELD_KP_ID, ""),
            FIELD_KP_TITLE: r.get(FIELD_KP_TITLE, ""),
            FIELD_CORE_CONTENT: r.get(FIELD_CORE_CONTENT, ""),
            "级别": r.get("级别", ""),
            "来源标签": r.get("来源标签", ""),
            FIELD_STATUS: r.get(FIELD_STATUS, ""),
            FIELD_ROUND: r.get(FIELD_ROUND, 0),
            FIELD_IS_WEAK: r.get(FIELD_IS_WEAK, False),
            FIELD_WEAK_DESC: r.get(FIELD_WEAK_DESC, ""),
            FIELD_CORRECT_COUNT: r.get(FIELD_CORRECT_COUNT, 0),
            FIELD_WRONG_COUNT: r.get(FIELD_WRONG_COUNT, 0),
            FIELD_IN_WRONG_BOOK: r.get(FIELD_IN_WRONG_BOOK, False),
            FIELD_L0: r.get(FIELD_L0, ""),
            FIELD_L1: r.get(FIELD_L1, ""),
            FIELD_L2: r.get(FIELD_L2, ""),
            FIELD_L3: r.get(FIELD_L3, ""),
            FIELD_L4: r.get(FIELD_L4, ""),
            FIELD_TAGS: r.get(FIELD_TAGS, []),
            FIELD_ADD_DATE: parse_date(r.get(FIELD_ADD_DATE, "")).strftime("%Y-%m-%d") if parse_date(r.get(FIELD_ADD_DATE, "")) else "",
            FIELD_NEXT_DATE: parse_date(r.get(FIELD_NEXT_DATE, "")).strftime("%Y-%m-%d") if parse_date(r.get(FIELD_NEXT_DATE, "")) else "",
        })
    with open(TODAY_QUIZ_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 生成出题指令文件（含完整格式规范和示例）
    generate_quiz_prompt(out, PROMPT_FILE, today_str)

    print(f"\n📋 今日筛选结果（共{len(out)}题）")
    print(f"   💾 today_quiz.json → {TODAY_QUIZ_FILE}")
    print(f"   📝 出题指令.txt   → {PROMPT_FILE}")

    print(f"\n📂 来源分布:")
    for src, cnt in sorted(stats["by_source"].items()):
        icon = SOURCE_ICONS.get(src, "  ")
        print(f"  {icon} {src}: {cnt}题")
    print(f"\n⭐ 分级分布（目标: ★★★60-75% / ★★☆20-30% / ★☆☆0-10%）:")
    total = stats["total"] or 1
    for lvl in LEVELS:
        cnt = stats["by_level"].get(lvl, 0)
        print(f"  {lvl}: {cnt}题 ({cnt/total*100:.0f}%)")

    print(f"\n{'='*60}")
    for r in out:
        icon = SOURCE_ICONS.get(r["来源标签"], "  ")
        # 薄弱点题icon已经是🔥，mark不重复显示
        mark = "" if r["薄弱点"] and icon == "🔥" else ("🔥" if r["薄弱点"] else "  ")
        print(f"  {r['题号']:2d}. {mark} {icon} [{r['级别']}] [{r['知识点ID']}] {r['知识点标题']}  ({r['掌握状态']} 轮次{r['复习轮次']})")


if __name__ == "__main__":
    main()
