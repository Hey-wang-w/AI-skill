#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quiz_push.py — 读取批改结果，按规范A/B/C三类规则计算艾宾浩斯更新并批量写回飞书多维表格

核心功能：
    读取 today_quiz.json（题目清单，含来源标签）和 grading.json（批改结果），
    根据每题的来源标签判断属于A/B/C哪种类型：
    - 类型A（薄弱点到期/到期常规/新知识点答对）：推进轮次，FIX#1防回溯日期公式
    - 类型B（未到期巩固/随机巩固答对）：不推进轮次，日期不变（FIX#4）
    - 类型C（任何答错）：轮次归零，打薄弱点标记，[重置]计数器（FIX#3）

用法：
    1. 先运行 quiz_pull.py 生成 today_quiz.json
    2. AI批改完成后，在 grading.json 写入批改结果，格式：
       [
         {"题号": 1, "正确": true},
         {"题号": 2, "正确": false, "错因": "误选C，正确B——测试集反复调参会过拟合"},
         ...
       ]
    3. python quiz_push.py
       可选参数: --date 2026-07-08  指定测验日期，默认今天
                 --dry-run           只计算不写飞书，用于测试

输入文件：today_quiz.json（由 quiz_pull.py 生成）、grading.json（由AI写入）
输出：直接写回飞书多维表格（控制台打印更新摘要）
依赖：lark-cli（路径见config.py）
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta

# 从共享配置导入所有常量（单一事实来源）
from config import (
    LARK, SKILL_DIR, SCRIPT_DIR,
    BASE_TOKEN as BASE, TABLE_ID as TABLE,
    TODAY_QUIZ_FILE as QUIZ_FILE, GRADING_FILE,
    CUMULATIVE, TYPE_A_SOURCES as DUE_SOURCES, TYPE_B_SOURCES,
    WEAK_REMOVE_THRESHOLD,
    # 掌握状态
    STATUS_UNTESTED, STATUS_LEARNING, STATUS_MASTERED, STATUS_REVIEW,
    # 飞书字段名
    FIELD_ROUND, FIELD_CORRECT_COUNT, FIELD_WRONG_COUNT,
    FIELD_STATUS, FIELD_IS_WEAK, FIELD_WEAK_DESC, FIELD_IN_WRONG_BOOK,
    FIELD_NEXT_DATE, FIELD_KP_ID, FIELD_KP_TITLE, FIELD_RECORD_ID,
    # grading.json字段名
    GRADING_FIELD_QNO, GRADING_FIELD_CORRECT, GRADING_FIELD_REASON,
    # 日志/格式
    RESET_MARK, REGEX_CONSECUTIVE_CORRECT,
    LOG_WEAK_CORRECT, LOG_WEAK_REVIEW_CORRECT, LOG_WEAK_WRONG,
    DATE_FORMAT,
)

# lark-cli工作目录为Skill根
CWD = SKILL_DIR


def parse_date_safe(text):
    """
    安全解析日期字符串为date对象。
    输入参数：text为日期字符串或空。
    返回值：date对象，解析失败返回None。
    """
    if not text or not text.strip():
        return None
    t = text.strip()
    for fmt in (DATE_FORMAT, "%Y-%m-%d"):
        try:
            return datetime.strptime(t[:19] if len(t) >= 19 else t, fmt).date()
        except ValueError:
            continue
    return None


def count_consecutive_correct(desc):
    """
    从薄弱点描述中统计最后[重置]之后的连续"到期答对"次数。
    规范3.2（FIX#3）：只统计"到期答对"，不统计"未到期巩固答对"。
    输入参数：desc为薄弱点描述字符串。
    返回值：int，连续到期答对次数。
    """
    if not desc:
        return 0
    # 找到最后一个[重置]的位置
    reset_pos = desc.rfind(RESET_MARK)
    if reset_pos >= 0:
        # 只考虑[重置]之后的内容
        after = desc[reset_pos:]
    else:
        after = desc
    # 使用config中定义的正则匹配"到期答对"
    matches = re.findall(REGEX_CONSECUTIVE_CORRECT, after)
    return len(matches)


def compute_push_patch(q, correct, today, reason=""):
    """
    根据题目当前状态、来源标签和答题对错，计算要更新的飞书字段字典。

    类型判定规则（规范第三章）：
      - 来源标签为DUE_SOURCES中的（薄弱点到期/到期常规/新知识点）→ 类型A（答对推进轮次）
      - 来源标签为TYPE_B_SOURCES中的（未到期巩固/随机巩固）→ 类型B（答对不推进轮次）
      - 任何来源标签答错 → 类型C（归零+薄弱点）

    输入参数：
      q — 题目dict（含record_id/知识点ID/来源标签/复习轮次/添加日期 等字段）
      correct — bool，是否答对
      today — date对象，测验日期
      reason — str，错因分析（仅答错时使用）
    返回值：dict，要写入飞书的字段键值对。
    """
    source = q.get("来源标签", DUE_SOURCES[1])  # 默认为"到期常规"，保守处理
    cur_round = q.get(FIELD_ROUND, 0)
    was_weak = q.get(FIELD_IS_WEAK, False)
    was_status = q.get(FIELD_STATUS, "")
    weak_desc = q.get(FIELD_WEAK_DESC, "") or ""
    add_date = parse_date_safe(q.get("添加日期", ""))

    fields = {}

    if correct:
        if source in DUE_SOURCES:
            # ── 类型A：到期/新知识点答对 → 推进轮次，FIX#1防回溯 ──
            new_round = cur_round + 1
            fields[FIELD_ROUND] = new_round
            fields[FIELD_CORRECT_COUNT] = q.get(FIELD_CORRECT_COUNT, 0) + 1

            # 掌握状态判断
            if new_round >= 5:
                fields[FIELD_STATUS] = STATUS_MASTERED
                fields[FIELD_NEXT_DATE] = None  # 已掌握不再安排复习
            else:
                fields[FIELD_STATUS] = STATUS_LEARNING
                # FIX#1 防回溯加速公式：
                # 基准日期 = 添加日期 + CUMULATIVE[新轮次-1]
                # 若基准日期 < 今天 → 使用今天 + CUMULATIVE[新轮次-1]
                if add_date:
                    base = add_date + timedelta(days=CUMULATIVE[new_round - 1])
                    if base < today:
                        base = today + timedelta(days=CUMULATIVE[new_round - 1])
                    fields[FIELD_NEXT_DATE] = base.strftime("%Y-%m-%d 00:00:00")
                else:
                    # 兜底：用今天算
                    fields[FIELD_NEXT_DATE] = (today + timedelta(days=CUMULATIVE[new_round - 1])).strftime("%Y-%m-%d 00:00:00")

            # 薄弱点处理（仅原为薄弱点的）
            if was_weak:
                new_desc = weak_desc + "\n" + LOG_WEAK_CORRECT.format(today.strftime('%Y-%m-%d'))
                fields[FIELD_WEAK_DESC] = new_desc
                # 统计[重置]之后连续到期答对次数
                streak = count_consecutive_correct(new_desc)
                if streak >= WEAK_REMOVE_THRESHOLD:
                    # FIX#2：连续N次到期答对 → 清除薄弱点
                    fields[FIELD_IS_WEAK] = False
                    fields[FIELD_WEAK_DESC] = ""
                else:
                    fields[FIELD_IS_WEAK] = True
        else:
            # ── 类型B：未到期巩固/随机巩固答对 → 不推进轮次（FIX#4） ──
            fields[FIELD_ROUND] = cur_round  # 不变！
            fields[FIELD_CORRECT_COUNT] = q.get(FIELD_CORRECT_COUNT, 0) + 1
            # 若原为未测试状态，即使巩固答对也更新为学习中
            if was_status == STATUS_UNTESTED:
                fields[FIELD_STATUS] = STATUS_LEARNING
            # 薄弱点处理：记录但不计入连续答对清除（FIX#2）
            if was_weak and source == TYPE_B_SOURCES[0]:  # "未到期巩固"
                new_desc = weak_desc + "\n" + LOG_WEAK_REVIEW_CORRECT.format(today.strftime('%Y-%m-%d'))
                fields[FIELD_WEAK_DESC] = new_desc
                fields[FIELD_IS_WEAK] = True  # 保持标记，不清除
    else:
        # ── 类型C：任何情况答错 → 归零 + 薄弱点标记 + [重置]（FIX#3） ──
        fields[FIELD_ROUND] = 0
        fields[FIELD_WRONG_COUNT] = q.get(FIELD_WRONG_COUNT, 0) + 1
        fields[FIELD_IN_WRONG_BOOK] = True
        fields[FIELD_STATUS] = STATUS_REVIEW
        fields[FIELD_NEXT_DATE] = (today + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
        fields[FIELD_IS_WEAK] = True
        # FIX#3：[重置]标记，清零连续答对计数
        reason_text = f"：{reason}" if reason else ""
        fields[FIELD_WEAK_DESC] = weak_desc + "\n" + LOG_WEAK_WRONG.format(today.strftime('%Y-%m-%d'), RESET_MARK, reason_text)

    return fields


def call_upsert(record_id, fields):
    """
    调用lark-cli更新单条记录到飞书多维表格。
    输入参数：record_id为飞书记录ID；fields为要更新的字段dict。
    返回值：(ok, stdout, stderr) —— ok为bool，stdout/stderr为字符串。
    """
    # 处理None值：飞书datetime字段设为None表示清空
    clean = {}
    for k, v in fields.items():
        if v is None:
            clean[k] = None
        elif isinstance(v, bool):
            clean[k] = v
        elif isinstance(v, int):
            clean[k] = v
        else:
            clean[k] = v
    payload = json.dumps(clean, ensure_ascii=False)
    cmd = [
        LARK, "base", "+record-upsert",
        "--base-token", BASE,
        "--table-id", TABLE,
        "--record-id", record_id,
        "--json", payload
    ]
    r = subprocess.run(cmd, cwd=CWD, capture_output=True, text=True, encoding="utf-8")
    ok = r.returncode == 0 and '"ok": true' in r.stdout and '"created":true' not in r.stdout
    return ok, r.stdout, r.stderr


def main():
    """
    主函数：读取题目文件和批改结果→逐题计算A/B/C更新→批量写回飞书→打印总结。
    无输入参数（从命令行读取--date/--dry-run）。
    无返回值（直接写飞书和打印控制台）。
    """
    ap = argparse.ArgumentParser(description="批改后写回飞书多维表格")
    ap.add_argument("--date", default=None, help="测验日期 YYYY-MM-DD，默认今天")
    ap.add_argument("--dry-run", action="store_true", help="只计算不写飞书")
    args = ap.parse_args()
    today = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()

    # 检查输入文件
    if not os.path.exists(QUIZ_FILE):
        print(f"❌ 找不到题目文件 {QUIZ_FILE}，请先运行 quiz_pull.py", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(GRADING_FILE):
        print(f"❌ 找不到批改结果 {GRADING_FILE}，请在 grading.json 中写入批改结果", file=sys.stderr)
        sys.exit(1)

    with open(QUIZ_FILE, "r", encoding="utf-8") as f:
        quiz = json.load(f)
    with open(GRADING_FILE, "r", encoding="utf-8") as f:
        grading = json.load(f)

    # 题号 → 题目映射
    by_num = {q[GRADING_FIELD_QNO]: q for q in quiz}

    # 统计追踪
    results = {
        "答对": 0, "答错": 0, "成功": 0, "失败": 0,
        "类型A推进": [], "类型B巩固": [], "类型C重置": [],
        "新晋薄弱点": [], "解除薄弱点": [], "晋级已掌握": [],
    }

    mode_tag = "(dry-run，不写飞书)" if args.dry_run else ""
    print(f"📅 测验日期: {today.strftime('%Y-%m-%d')} {mode_tag}")
    print(f"📝 共 {len(grading)} 条批改结果")
    print()
    print("🔍 题号→知识点ID对应表（请核对试卷题目顺序是否与此一致）：")
    for q in sorted(quiz, key=lambda x: x[GRADING_FIELD_QNO]):
        weak_mark = "🔥" if q.get(FIELD_IS_WEAK) else "  "
        print(f"   第{q[GRADING_FIELD_QNO]:2d}题 {weak_mark} [{q.get(FIELD_KP_ID, '未知ID')}] {q.get(FIELD_KP_TITLE, '')[:30]}")
    print()
    print("-" * 70)

    for g in grading:
        num = g[GRADING_FIELD_QNO]
        correct = bool(g[GRADING_FIELD_CORRECT])
        reason = g.get(GRADING_FIELD_REASON, "").strip()

        if num not in by_num:
            print(f"第{num}题 ❓ 未在 today_quiz.json 中找到，跳过")
            continue
        q = by_num[num]
        source = q.get("来源标签", DUE_SOURCES[1])
        was_weak = q.get(FIELD_IS_WEAK, False)
        was_status = q.get(FIELD_STATUS, "")

        # 计算要更新的字段
        fields = compute_push_patch(q, correct, today, reason)

        # 执行更新
        if args.dry_run:
            ok = True
            err = ""
        else:
            ok, out, err = call_upsert(q[FIELD_RECORD_ID], fields)

        if ok:
            results["成功"] += 1
            mark = "✅" if correct else "❌"
            if correct:
                results["答对"] += 1
            else:
                results["答错"] += 1

            # 类型标签（使用config常量判断）
            if not correct:
                type_label = "C"
                results["类型C重置"].append(q[FIELD_KP_ID])
            elif source in DUE_SOURCES:
                type_label = "A"
                results["类型A推进"].append(q[FIELD_KP_ID])
            else:
                type_label = "B"
                results["类型B巩固"].append(q[FIELD_KP_ID])

            new_status = fields.get(FIELD_STATUS, was_status)

            # 薄弱点变化追踪
            weak_change = ""
            if was_weak and fields.get(FIELD_IS_WEAK) is False:
                weak_change = " 🎉薄弱点解除"
                results["解除薄弱点"].append(f"{q[FIELD_KP_ID]} {q[FIELD_KP_TITLE]}")
            elif (not was_weak) and fields.get(FIELD_IS_WEAK) is True:
                weak_change = " ⚠️新晋薄弱点"
                results["新晋薄弱点"].append(f"{q[FIELD_KP_ID]} {q[FIELD_KP_TITLE]}")
            if was_status != STATUS_MASTERED and new_status == STATUS_MASTERED:
                weak_change += " 🎓晋级已掌握"
                results["晋级已掌握"].append(f"{q[FIELD_KP_ID]} {q[FIELD_KP_TITLE]}")

            next_date_str = fields.get(FIELD_NEXT_DATE, None)
            if next_date_str is None:
                # 未修改则显示原值，标注不变
                orig_next = q.get(FIELD_NEXT_DATE, "")
                if orig_next and len(str(orig_next)) >= 10:
                    next_date_str = str(orig_next)[:10] + "(不变)"
                else:
                    next_date_str = "(不变)"
            elif next_date_str == "":
                next_date_str = "(不变)"
            elif isinstance(next_date_str, str) and len(next_date_str) >= 10:
                next_date_str = next_date_str[:10]

            print(f"第{num:2d}题 [{q[FIELD_KP_ID]}] {mark} 类型{type_label} [{source}] "
                  f"轮次{q.get(FIELD_ROUND, 0)}→{fields.get(FIELD_ROUND, q.get(FIELD_ROUND, 0))} "
                  f"状态 {was_status}→{new_status} 下次={next_date_str}{weak_change}")
        else:
            results["失败"] += 1
            print(f"第{num:2d}题 [{q[FIELD_KP_ID]}] ❌ 更新失败")
            if err:
                print(f"  STDERR: {err.strip()[-300:]}")

    # ── 打印总结 ──
    print("-" * 70)
    total = results["答对"] + results["答错"]
    rate = (results["答对"] / total * 100) if total else 0
    print(f"\n📊 总结：共{total}题，答对{results['答对']}，答错{results['答错']}，正确率 {rate:.1f}%")
    print(f"📤 飞书写回：成功{results['成功']}条，失败{results['失败']}条")
    print(f"📂 类型分布：A推进{len(results['类型A推进'])} B巩固{len(results['类型B巩固'])} C重置{len(results['类型C重置'])}")

    if results["晋级已掌握"]:
        print(f"\n🎓 新晋级🟢已掌握：")
        for s in results["晋级已掌握"]:
            print(f"   · {s}")
    if results["解除薄弱点"]:
        print(f"\n✅ 薄弱点解除：")
        for s in results["解除薄弱点"]:
            print(f"   · {s}")
    if results["新晋薄弱点"]:
        print(f"\n⚠️ 新晋薄弱点（明日重点复习）：")
        for s in results["新晋薄弱点"]:
            print(f"   · {s}")
    if results["类型C重置"]:
        print(f"\n🔄 以下知识点轮次已归零，重新走艾宾浩斯：")
        for kid in set(results["类型C重置"]):
            print(f"   · {kid}")


if __name__ == "__main__":
    main()
