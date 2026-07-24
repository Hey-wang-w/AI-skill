#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reset_all.py — 重置飞书知识库所有知识点状态（测试用）

核心功能：
    将飞书多维表格中所有知识点的学习状态重置为初始值，用于从0开始测试艾宾浩斯巩固计划逻辑。
    ⚠️ 此操作不可逆，会清除所有学习进度（轮次、对错次数、薄弱点标记、错题本、日志）。
    知识点内容、ID、分级、分类、添加日期等基础信息保留不变。

重置字段：
    - 复习轮次 → 0
    - 掌握状态 → ⚪未测试
    - 正确次数 → 0
    - 错误次数 → 0
    - 薄弱点 → false
    - 薄弱点描述 → 清空
    - 错题本 → false
    - 下次复习日期 → 今天（所有知识点到期，便于立即测试）

保留字段（不修改）：
    - 知识点ID、知识点标题、核心内容、知识标签
    - 重要程度、L0-L4分类
    - 添加日期、来源

用法：
    python reset_all.py          # 执行重置
    python reset_all.py --dry-run # 仅显示将要重置的记录数，不实际修改

注意：
    SKILL.md流程F规定：执行此脚本前，AI必须先用AskUserQuestion工具向用户确认风险，
    用户明确同意后才能执行，不得直接运行。
"""
import argparse
import json
import subprocess
import sys

# 从共享配置导入常量
from config import (
    LARK, BASE_TOKEN, TABLE_ID, STATUS_UNTESTED,
    SKILL_DIR, DATE_FORMAT_DAY
)
from datetime import date

# 执行lark-cli的工作目录（与其他脚本一致）
CWD = SKILL_DIR


def lark_json_cmd(args):
    """
    调用lark-cli并解析JSON输出。
    输入参数：args为lark-cli命令参数列表（不含lark-cli本身路径）。
    返回值：解析后的JSON字典，失败返回None。
    """
    cmd = [LARK] + args
    r = subprocess.run(cmd, cwd=CWD, capture_output=True, text=True, encoding="utf-8", timeout=60)
    if r.returncode != 0:
        print(f"❌ lark-cli调用失败: {r.stderr[:300]}", file=sys.stderr)
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"❌ JSON解析失败，输出前200字符: {r.stdout[:200]}", file=sys.stderr)
        return None


def fetch_all_record_ids():
    """
    获取飞书表格中所有知识点的record_id列表。
    输入参数：无。
    返回值：record_id字符串列表。
    """
    data = lark_json_cmd([
        "base", "+record-list",
        "--base-token", BASE_TOKEN,
        "--table-id", TABLE_ID,
        "--page-size", "200",
        "--format", "json"
    ])
    if not data:
        return []
    d = data.get("data", {})
    return d.get("record_id_list", [])


def build_reset_patch(today):
    """
    构造重置patch（将所有学习状态字段恢复初始值）。
    输入参数：today为date对象，用于设置下次复习日期为今天。
    返回值：字段patch字典。
    """
    today_str = today.strftime(DATE_FORMAT_DAY) + " 00:00:00"
    return {
        "复习轮次": 0,
        "掌握状态": STATUS_UNTESTED,
        "正确次数": 0,
        "错误次数": 0,
        "薄弱点": False,
        "薄弱点描述": "",
        "错题本": False,
        "下次复习日期": today_str,
    }


def batch_update(record_ids, patch, dry_run=False):
    """
    批量更新飞书记录（同一份patch应用到所有record_id）。
    输入参数：record_ids为记录ID列表；patch为字段更新字典；dry_run为True时只打印不执行。
    返回值：(成功数量, 总数量)。
    """
    if dry_run:
        return 0, len(record_ids)

    body = {"record_id_list": record_ids, "patch": patch}
    payload = json.dumps(body, ensure_ascii=False)
    data = lark_json_cmd([
        "base", "+record-batch-update",
        "--base-token", BASE_TOKEN,
        "--table-id", TABLE_ID,
        "--json", payload
    ])
    if data and data.get("ok"):
        return len(record_ids), len(record_ids)
    else:
        print(f"❌ 批量更新失败: {json.dumps(data, ensure_ascii=False)[:300] if data else '无返回'}", file=sys.stderr)
        return 0, len(record_ids)


def main():
    """
    主函数：解析参数→获取记录→确认→执行重置→打印结果。
    输入参数：从命令行读取--dry-run和--date参数。
    返回值：无（直接打印控制台输出）。
    """
    ap = argparse.ArgumentParser(description="重置飞书知识库所有知识点学习状态（测试用）")
    ap.add_argument("--dry-run", action="store_true", help="演练模式：只统计记录数，不实际修改飞书")
    ap.add_argument("--date", default=None, help="重置后下次复习日期 YYYY-MM-DD，默认今天")
    args = ap.parse_args()

    today = date.today()
    if args.date:
        from datetime import datetime
        today = datetime.strptime(args.date, "%Y-%m-%d").date()

    print("=" * 60)
    print("🔄 飞书知识库状态重置工具")
    print("=" * 60)

    # 获取记录数
    print("📋 正在获取知识点记录...")
    record_ids = fetch_all_record_ids()
    if not record_ids:
        print("❌ 未获取到任何记录，终止操作")
        sys.exit(1)
    print(f"   共 {len(record_ids)} 条知识点")

    # 显示重置内容
    patch = build_reset_patch(today)
    print()
    print("⚠️  将要重置的字段：")
    for k, v in patch.items():
        print(f"   {k} → {repr(v)}")
    print()
    print("🔒 保留不变的字段：知识点ID、标题、核心内容、分级、分类、标签、添加日期")

    if args.dry_run:
        print()
        print(f"[DRY-RUN] 将要重置 {len(record_ids)} 条记录，但未实际修改（去掉--dry-run参数以执行）")
        print("=" * 60)
        return

    # 执行重置
    print()
    print(f"🔄 正在批量重置 {len(record_ids)} 条记录...")
    ok, total = batch_update(record_ids, patch, dry_run=False)

    print()
    print("=" * 60)
    if ok == total:
        print(f"✅ 重置完成！{ok}/{total} 条记录已恢复初始状态")
        print(f"📅 所有知识点下次复习日期设为 {today.strftime(DATE_FORMAT_DAY)}（今天）")
        print("💡 现在可以运行 quiz_pull.py 开始从零测试巩固计划")
    else:
        print(f"⚠️ 重置部分完成：{ok}/{total} 条成功，请检查飞书表格确认")
    print("=" * 60)


if __name__ == "__main__":
    main()
