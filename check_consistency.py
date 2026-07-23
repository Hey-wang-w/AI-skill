#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_consistency.py — ai-quiz-system 一致性校验脚本

核心功能：
    修改项目文件后运行本脚本，自动检查常见的不一致问题：
    1. 所有必需文件是否存在（含scripts/README.md）
    2. config.py能否正确导入、关键常量是否完整（SSOT验证）
    3. 文档中是否残留旧路径引用（指向根目录而非ai-quiz-system/）及旧标签残留
    4. 文档中是否残留旧来源标签（"到期"应拆分为"薄弱点到期"/"到期常规"）
    5. 填空题格式规范是否一致
    6. 两个脚本的关键常量、import语句、动态checklist读取是否与config.py一致
    7. 魔法值扫描：检测代码中硬编码、应该从config.py引用的字符串（覆盖两个脚本）
    8. REGEX_CONSECUTIVE_CORRECT正则与LOG_WEAK_CORRECT日志格式一致性检查
    9. SKILL.md修改协议完整性检查（含自指更新规则、新增内容纳入规则）
    10. 思维导图文件、__pycache__残留、根目录旧文件等杂项检查
    额外：提供"查询模式"，输入关键词快速找到所有关联位置
    额外：提供"联动检查模式"，自动发现文件间读写断裂（某文件被写入但从未被读取）

用法：
    python check_consistency.py              # 全量一致性检查
    python check_consistency.py check        # 同上（默认）
    python check_consistency.py where 关键词  # 查询关键词出现在哪些位置（修改前用）
    python check_consistency.py linkage      # 联动检查：发现文件间读写断裂（新增文件后用）

示例：
    python check_consistency.py where 薄弱点到期
    python check_consistency.py where 填空题
    python check_consistency.py linkage

输出：
    控制台打印检查结果：✅通过 / ⚠️警告 / ❌错误
    返回退出码：0=全部通过，1=有错误

术语解释：
    - SSOT（Single Source of Truth）：单一事实来源，即config.py
    - 魔法值（Magic Value）：代码中直接写死的字符串/数字，应该用config常量代替
    - 旧路径：指Skill重构前指向d:\\AI\\AI学习内容记忆测试\\根目录的路径引用（缺少ai-quiz-system子目录）
    - 旧标签：重构前的"到期"标签（应拆分为"薄弱点到期"+"到期常规"）
"""
import os
import sys
import re

# ── 路径配置 ──────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = SCRIPT_DIR  # 本脚本在Skill根目录
PROJECT_DIR = os.path.dirname(SKILL_DIR)

# 把scripts目录加入path以便import config
sys.path.insert(0, os.path.join(SKILL_DIR, 'scripts'))

errors = []
warnings = []
passed = []
_config_module = None  # 保存config模块引用，供后续检查复用


def check(condition, msg, is_warning=False):
    """
    记录一项检查结果。
    输入参数：condition为bool（True=通过，False=问题）；msg为描述信息；is_warning为True表示警告而非错误。
    返回值：无。
    """
    if condition:
        passed.append(msg)
    else:
        if is_warning:
            warnings.append(msg)
        else:
            errors.append(msg)


def read_file(path):
    """
    安全读取文本文件。
    输入参数：path为文件绝对路径。
    返回值：文件内容字符串，读取失败返回空字符串。
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ""


def scan_file_for_patterns(path, patterns, desc_prefix=""):
    """
    扫描文件中是否包含指定模式（不应出现的内容）。
    输入参数：path为文件路径；patterns为(正则模式, 问题描述)列表；desc_prefix为路径显示前缀。
    返回值：无（结果直接记入errors/warnings）。
    """
    content = read_file(path)
    if not content:
        return
    rel = os.path.relpath(path, PROJECT_DIR)
    for pattern, desc in patterns:
        matches = re.findall(pattern, content)
        if matches:
            errors.append(f"{desc_prefix}{rel}: 发现{desc}（{len(matches)}处）")


def find_all_project_files():
    """
    获取项目中所有需要扫描的文件列表（排除__pycache__和临时文件）。
    输入参数：无。
    返回值：文件绝对路径列表。
    """
    files = []
    for root, dirs, fnames in os.walk(SKILL_DIR):
        # 跳过__pycache__
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fname in fnames:
            if fname.endswith(('.md', '.py', '.json', '.txt')) and not fname.startswith('_push_patch'):
                files.append(os.path.join(root, fname))
    # 加上思维导图
    mindmap = os.path.join(PROJECT_DIR, 'AI知识思维导图.html')
    if os.path.exists(mindmap):
        files.append(mindmap)
    return files


def magic_value_scan():
    """
    【增强功能】扫描Python脚本中可能导致逻辑错误的硬编码值。
    注意：只检测"条件判断中"的硬编码（会影响逻辑的），不检测注释/prompt文本/打印输出中的字符串。
    输入参数：无。
    返回值：无（结果记入warnings）。
    """
    # 检测模式：只在条件判断（if/==/in/!=）中出现的硬编码才报警告
    # 格式：(正则匹配逻辑判断模式, 问题描述)
    logic_patterns = [
        # 检测 if xxx == "旧标签" 这种判断（旧的"到期"标签已经拆分）
        (r'==\s*[\'"]到期[\'"]',
         "条件判断中使用了旧标签'到期'（应改为'到期常规'或'薄弱点到期'，或引用config常量）"),
        (r'in\s*\([^)]*[\'"]到期[\'"][^)]*\)',
         "in判断中包含了旧标签'到期'"),
    ]

    # 只扫描两个核心脚本
    for script_name in ['quiz_pull.py', 'quiz_push.py']:
        script_path = os.path.join(SKILL_DIR, 'scripts', script_name)
        content = read_file(script_path)
        if not content:
            continue
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # 跳过注释行
            if stripped.startswith('#'):
                continue
            # 跳过文档字符串区域（简单启发式：三引号行跳过）
            if '"""' in line or "'''" in line:
                continue
            # 跳过import区域
            if stripped.startswith('from ') or stripped.startswith('import '):
                continue

            for pattern, desc in logic_patterns:
                if re.search(pattern, line):
                    rel = os.path.relpath(script_path, PROJECT_DIR)
                    warnings.append(f"{rel}:{i} {desc}")


def where_is(keyword):
    """
    【查询模式】搜索关键词在所有项目文件中出现的位置。
    修改内容前运行此命令，可以快速知道哪些地方需要同步修改。
    输入参数：keyword为要搜索的关键词字符串。
    返回值：无（直接打印结果）。
    """
    print("=" * 60)
    print(f"🔍 搜索关键词：「{keyword}」")
    print("=" * 60)

    files = find_all_project_files()
    found_count = 0

    for fpath in files:
        content = read_file(fpath)
        if not content or keyword not in content:
            continue
        rel = os.path.relpath(fpath, PROJECT_DIR)
        lines = content.split('\n')
        matches = []
        for i, line in enumerate(lines, 1):
            if keyword in line:
                # 提取该行前后关键词周围的文本用于预览
                idx = line.find(keyword)
                start = max(0, idx - 25)
                end = min(len(line), idx + len(keyword) + 25)
                preview = line[start:end].strip()
                if start > 0:
                    preview = "..." + preview
                if end < len(line):
                    preview = preview + "..."
                matches.append((i, preview))

        if matches:
            found_count += len(matches)
            print(f"\n📄 {rel}（{len(matches)}处）:")
            for line_no, preview in matches:
                print(f"   第{line_no}行: {preview}")

    print("\n" + "=" * 60)
    if found_count == 0:
        print(f"❌ 未找到「{keyword}」")
    else:
        print(f"✅ 共找到 {found_count} 处引用，修改时请逐一检查以上位置")
    print("=" * 60)

    # 同时提示去content-map.md中查看主定义位置
    map_path = os.path.join(SKILL_DIR, 'content-map.md')
    if os.path.exists(map_path):
        print(f"\n💡 提示：也可以查看 content-map.md 找到「{keyword}」的主定义位置和修改注意事项")


def check_linkage():
    """
    【联动检查模式】自动发现文件间读写断裂。
    检查每个references/和assets/下的文件是否同时有"写入方"和"读取方"。
    如果某文件只被写入（E8/修改协议引用）但从无被读取（流程A/B/C/D未引用），报告为断裂。
    新增文件或新增经验后运行此命令，可高效发现遗漏的联动机制。
    输入参数：无。
    返回值：int（0=无断裂，1=有断裂）。
    """
    print("=" * 60)
    print("🔗 文件联动检查：发现读写断裂")
    print("=" * 60)

    # 定义需要检查联动关系的文件及其读写方
    # 格式: (文件名, 写入方关键词列表, 读取方关键词列表)
    # 写入方 = 谁会往这个文件写内容（如E8入库）
    # 读取方 = 谁应该在执行时读取这个文件（如流程A/B/C/D步骤）
    linkage_specs = [
        ("references/quiz-experience.md",
         ["E8", "经验提取", "经验沉淀", "入库"],
         ["步骤A2", "步骤B1", "步骤C1", "必须读取"]),
        ("references/best-practices.md",
         ["E8", "经验提取", "经验沉淀", "入库", "BP-"],
         ["步骤A2", "步骤B1", "步骤C1", "必须读取", "遇到特定场景"]),
        ("references/risk-alerts.md",
         ["E8", "经验提取", "经验沉淀", "入库", "RISK-"],
         ["步骤A2", "步骤B1", "步骤C1", "必须读取", "预警"]),
        ("assets/checklists/question-checklist.md",
         ["出题自检", "自检清单"],
         ["步骤A6", "必须读取", "read_checklist"]),
        ("assets/checklists/grading-checklist.md",
         ["批改自检", "自检清单"],
         ["步骤B5", "必须读取"]),
        ("references/01-question-format.md",
         [],
         ["步骤A2", "必须读取"]),
        ("references/02-grading-rules.md",
         ["FIX#"],
         ["步骤B1", "必须读取"]),
        ("references/03-knowledge-ingest.md",
         [],
         ["步骤C1", "必须读取"]),
        ("references/04-knowledge-taxonomy.md",
         [],
         ["步骤C2", "必须读取"]),
        ("references/CHANGELOG.md",
         ["E6", "CHANGELOG", "经验沉淀", "经验更新"],
         ["E8.5", "延迟反馈", "追溯"]),
        ("assets/templates/quiz-paper.md",
         [],
         ["步骤A3", "必须读取", "试卷模板"]),
        ("assets/templates/grading-result.json",
         [],
         ["步骤B3", "grading.json", "格式模板"]),
        ("assets/templates/grading-summary.md",
         [],
         ["步骤B5", "必须读取", "总结模板"]),
        ("assets/templates/ingest-feedback.md",
         [],
         ["步骤C5", "反馈模板"]),
    ]

    skill_path = os.path.join(SKILL_DIR, "SKILL.md")
    skill_content = read_file(skill_path) or ""
    pull_path = os.path.join(SKILL_DIR, "scripts", "quiz_pull.py")
    pull_content = read_file(pull_path) or ""

    broken_count = 0
    ok_count = 0

    for filepath, write_keywords, read_keywords in linkage_specs:
        full_path = os.path.join(SKILL_DIR, filepath.replace("/", os.sep))
        file_exists = os.path.exists(full_path)

        if not file_exists:
            print(f"\n❌ {filepath} — 文件不存在！")
            broken_count += 1
            continue

        # 检查读取方：SKILL.md中是否有对应流程步骤引用此文件
        has_reader = False
        missing_readers = []
        for kw in read_keywords:
            # 检查SKILL.md中是否同时包含"步骤X"和文件名（或文件名的最后一段）
            filename_short = filepath.split("/")[-1]
            if kw in skill_content and filename_short in skill_content:
                has_reader = True
            else:
                # 对于quiz_pull.py动态读取的文件，检查代码中是否引用
                if "read_checklist" in pull_content and filename_short in pull_content:
                    has_reader = True
                else:
                    missing_readers.append(kw)

        if has_reader:
            print(f"\n✅ {filepath} — 读写闭环正常")
            ok_count += 1
        else:
            print(f"\n⚠️ {filepath} — 可能存在读写断裂！")
            print(f"   未找到读取方引用（缺少关键词: {', '.join(missing_readers[:3])}）")
            print(f"   建议: 在SKILL.md对应流程步骤中加入'必须读取'说明")
            broken_count += 1

    # 检查是否有新增的references/assets文件未被纳入linkage_specs
    print("\n" + "-" * 60)
    print("📋 检查是否有未纳入联动监控的新文件...")
    monitored_files = set(spec[0] for spec in linkage_specs)
    for subdir in ["references", "assets/templates", "assets/checklists"]:
        dir_path = os.path.join(SKILL_DIR, subdir.replace("/", os.sep))
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            if fname.endswith((".md", ".json")):
                rel_path = f"{subdir}/{fname}"
                if rel_path not in monitored_files:
                    print(f"   ⚠️ 新文件未纳入联动监控: {rel_path}")
                    print(f"      建议: 在check_linkage()的linkage_specs中添加此文件的读写方定义")
                    broken_count += 1

    print("\n" + "=" * 60)
    if broken_count == 0:
        print(f"🎉 联动检查通过！{ok_count}个文件读写闭环正常，无断裂。")
    else:
        print(f"⚠️ 发现 {broken_count} 项联动问题，请按建议修复。")
    print("=" * 60)
    return 1 if broken_count > 0 else 0


def run_full_check():
    """
    执行完整的一致性检查。
    输入参数：无。
    返回值：int（0=通过，1=有错误）。
    """
    print("=" * 60)
    print("🔍 ai-quiz-system 一致性校验")
    print("=" * 60)

    # ── 检查1：必需文件是否存在 ──
    print("\n📁 [1/10] 检查必需文件...")
    required_files = [
        os.path.join(SKILL_DIR, 'SKILL.md'),
        os.path.join(SKILL_DIR, 'README.md'),
        os.path.join(SKILL_DIR, 'content-map.md'),
        os.path.join(SKILL_DIR, 'scripts', 'config.py'),
        os.path.join(SKILL_DIR, 'scripts', 'quiz_pull.py'),
        os.path.join(SKILL_DIR, 'scripts', 'quiz_push.py'),
        os.path.join(SKILL_DIR, 'scripts', 'README.md'),
        os.path.join(SKILL_DIR, 'references', '01-question-format.md'),
        os.path.join(SKILL_DIR, 'references', '02-grading-rules.md'),
        os.path.join(SKILL_DIR, 'references', '03-knowledge-ingest.md'),
        os.path.join(SKILL_DIR, 'references', '04-knowledge-taxonomy.md'),
        os.path.join(SKILL_DIR, 'references', 'quiz-experience.md'),
        os.path.join(SKILL_DIR, 'references', 'best-practices.md'),
        os.path.join(SKILL_DIR, 'references', 'risk-alerts.md'),
        os.path.join(SKILL_DIR, 'references', 'CHANGELOG.md'),
        os.path.join(SKILL_DIR, 'assets', 'templates', 'quiz-paper.md'),
        os.path.join(SKILL_DIR, 'assets', 'templates', 'grading-result.json'),
        os.path.join(SKILL_DIR, 'assets', 'templates', 'grading-summary.md'),
        os.path.join(SKILL_DIR, 'assets', 'templates', 'ingest-feedback.md'),
        os.path.join(SKILL_DIR, 'assets', 'checklists', 'question-checklist.md'),
        os.path.join(SKILL_DIR, 'assets', 'checklists', 'grading-checklist.md'),
        os.path.join(SKILL_DIR, 'content-map.md'),
        os.path.join(PROJECT_DIR, 'AI知识思维导图.html'),
    ]
    for f in required_files:
        rel = os.path.relpath(f, PROJECT_DIR)
        check(os.path.exists(f), f"文件存在: {rel}", is_warning=False)

    # ── 检查2：config.py能否正确导入，且关键常量完整性 ──
    print("\n⚙️  [2/10] 检查config.py（SSOT）导入与常量完整性...")
    global _config_module
    try:
        os.chdir(os.path.join(SKILL_DIR, 'scripts'))
        import config
        _config_module = config  # 保存引用供后续检查使用
        check(hasattr(config, 'CUMULATIVE'), "config.CUMULATIVE 已定义")
        check(len(config.CUMULATIVE) == 5, f"config.CUMULATIVE 长度为5（当前{len(config.CUMULATIVE)}）")
        check(hasattr(config, 'TYPE_A_SOURCES'), "config.TYPE_A_SOURCES 已定义")
        check(hasattr(config, 'TYPE_B_SOURCES'), "config.TYPE_B_SOURCES 已定义")
        check(hasattr(config, 'FILL_BLANK_PATTERN'), "config.FILL_BLANK_PATTERN 已定义")
        # 验证填空格式串包含前后下划线
        expected_fill = "____（{}）____"
        check(config.FILL_BLANK_PATTERN == expected_fill,
              f"config.FILL_BLANK_PATTERN 格式正确（前后各4下划线）", is_warning=False)
        # 验证默认题数
        check(config.DEFAULT_MAX_QUESTIONS == 20,
              f"config.DEFAULT_MAX_QUESTIONS = 20（当前{config.DEFAULT_MAX_QUESTIONS}）")
        check(config.WEAK_REMOVE_THRESHOLD == 2,
              f"config.WEAK_REMOVE_THRESHOLD = 2（当前{config.WEAK_REMOVE_THRESHOLD}）")
        check(config.MIN_QUESTIONS == 10,
              f"config.MIN_QUESTIONS = 10（当前{config.MIN_QUESTIONS}）")
        # 验证来源标签完整
        all_src = config.TYPE_A_SOURCES + config.TYPE_B_SOURCES
        check("薄弱点到期" in all_src and "到期常规" in all_src,
              "来源标签包含'薄弱点到期'和'到期常规'（拆分正确）")
        check("到期" not in all_src or len([s for s in all_src if s == "到期"]) == 0,
              "来源标签不包含单独的'到期'（已拆分）")

        # ── 【新增】config.py常量完整性检查 ──
        required_constants = [
            # 状态常量
            'STATUS_UNTESTED', 'STATUS_LEARNING', 'STATUS_MASTERED', 'STATUS_REVIEW', 'STATUS_VALUES',
            # 来源图标与级别/题型
            'SOURCE_ICONS', 'LEVELS', 'QUESTION_TYPES',
            # 知识库字段常量
            'FIELD_RECORD_ID', 'FIELD_KP_ID', 'FIELD_KP_TITLE', 'FIELD_CORE_CONTENT',
            'FIELD_STATUS', 'FIELD_LEVEL', 'FIELD_ROUND', 'FIELD_CORRECT_COUNT',
            'FIELD_WRONG_COUNT', 'FIELD_IS_WEAK', 'FIELD_WEAK_DESC', 'FIELD_IN_WRONG_BOOK',
            'FIELD_ADD_DATE', 'FIELD_NEXT_DATE',
            'FIELD_L0', 'FIELD_L1', 'FIELD_L2', 'FIELD_L3', 'FIELD_L4', 'FIELD_TAGS',
            # 批改结果字段
            'GRADING_FIELD_QNO', 'GRADING_FIELD_CORRECT', 'GRADING_FIELD_REASON',
            # 其他关键常量
            'RESET_MARK', 'REGEX_CONSECUTIVE_CORRECT', 'QUIZ_ENDING',
            # 日志格式常量
            'LOG_WEAK_CORRECT', 'LOG_WEAK_REVIEW_CORRECT', 'LOG_WEAK_WRONG',
        ]
        missing_constants = [c for c in required_constants if not hasattr(config, c)]
        check(len(missing_constants) == 0,
              f"config.py关键常量完整（缺失: {', '.join(missing_constants)}）" if missing_constants else "config.py所有关键常量已定义")

        print("   ✅ config.py 导入成功，常量完整性检查完成")
    except Exception as e:
        errors.append(f"config.py 导入失败: {e}")

    # ── 检查3：文档中是否残留旧路径/旧引用 ──
    print("\n📝 [3/10] 扫描文档中的旧路径和旧标签残留...")

    files_to_scan = find_all_project_files()

    # 不应出现的旧模式
    bad_patterns = [
        # 旧路径：直接引用根目录下的脚本文件（但quiz_push.py/quiz_pull.py本身在scripts/下是正确的）
        (r'cwd[=:]\s*[r]?[\'"]d:\\AI\\AI学习内容记忆测试[\'"]\s*$',
         "旧工作目录（应为ai-quiz-system子目录）"),
        # 旧出题规范文件名
        (r'出题规范与学习内容处理方案\.md',
         "引用已删除的旧规范文件'出题规范与学习内容处理方案.md'（应引用SKILL.md或references/）"),
        # feishu_config.json不存在
        (r'feishu_config\.json',
         "引用不存在的feishu_config.json（配置已硬编码在config.py中）"),
        # 注意：检查"到期"标签的上下文，排除"到期常规""薄弱点到期""未到期""下次复习日期"等合法用法
        # 检查单独的"[到期]"标签（应该是"[到期常规]"或"[薄弱点到期]"）
        (r'\[到期\](?!常规)',
         "旧来源标签'[到期]'（应拆分为[薄弱点到期]或[到期常规]）"),
        # 来源标签"到期"后不跟"常规"也不跟"薄弱点"也不是"下次复习日期"等合法词
        (r'来源[标签为：:]*[\s]*[\'"`]?到期[\'"`]?(?!常规|薄弱|未到期|题|的|答|时|日|复习)',
         "旧来源标签'到期'（应明确为'到期常规'或'薄弱点到期'）"),
    ]

    # 【新增】文档旧路径检查：检测.md/.txt文件中引用缺少ai-quiz-system子目录的旧路径
    # 匹配 d:\AI\AI学习内容记忆测试\grading.json 等（后面没有紧跟ai-quiz-system）
    old_path_patterns = [
        (r'd:\\AI\\AI学习内容记忆测试\\grading\.json(?!\\ai-quiz-system)',
         "引用旧路径 grading.json（应为 ai-quiz-system\\\\grading.json）"),
        (r'd:\\AI\\AI学习内容记忆测试\\today_quiz\.json(?!\\ai-quiz-system)',
         "引用旧路径 today_quiz.json（应为 ai-quiz-system\\\\today_quiz.json）"),
        (r'd:\\AI\\AI学习内容记忆测试\\出题指令\.txt(?!\\ai-quiz-system)',
         "引用旧路径 出题指令.txt（应为 ai-quiz-system\\\\出题指令.txt）"),
    ]

    # 排除文件
    exclude_files = {
        os.path.join(SKILL_DIR, 'check_consistency.py'),
        os.path.join(SKILL_DIR, 'content-map.md'),  # content-map会提到旧标签作为说明
    }

    for f in files_to_scan:
        if f in exclude_files:
            continue
        # config.py中的TYPE_A_SOURCES定义是合法的
        if f.endswith('config.py'):
            continue
        scan_file_for_patterns(f, bad_patterns)
        # 【新增】仅对.md和.txt文件检查旧路径引用（Python代码中用os.path拼接不会出现硬编码完整路径）
        if f.endswith('.md') or f.endswith('.txt'):
            scan_file_for_patterns(f, old_path_patterns, desc_prefix="[旧路径] ")

    # ── 检查4：填空题格式与题目顺序规则 ──
    print("\n✏️  [4/10] 检查填空题格式规范与题目顺序规则...")
    q_format = read_file(os.path.join(SKILL_DIR, 'references', '01-question-format.md'))
    checklist = read_file(os.path.join(SKILL_DIR, 'assets', 'checklists', 'question-checklist.md'))
    quiz_pull_content = read_file(os.path.join(SKILL_DIR, 'scripts', 'quiz_pull.py'))
    skill_md_for_order = read_file(os.path.join(SKILL_DIR, 'SKILL.md'))
    paper_template = read_file(os.path.join(SKILL_DIR, 'assets', 'templates', 'quiz-paper.md'))

    check('____（N）____' in q_format or '____（1）____' in q_format,
          "01-question-format.md 中填空题格式包含前后下划线", is_warning=False)
    check('____（N）' in q_format and '____（N）____' in q_format,
          "01-question-format.md 中同时展示错误格式和正确格式对比")
    check('下划线前后' in q_format or '前后都有' in q_format or '前后都要' in q_format,
          "01-question-format.md 强调下划线前后都要有")
    check('下划线' in checklist and '前后' in checklist,
          "出题自检清单包含下划线前后检查项")
    # 【新增】检查题目顺序强制规则是否在所有关键位置都有
    check('不得打乱顺序' in quiz_pull_content or '严格按照' in quiz_pull_content and '顺序出题' in quiz_pull_content,
          "quiz_pull.py 出题指令中包含'不得打乱顺序'强制要求", is_warning=False)
    check('题目顺序' in checklist or '顺序与知识点ID' in checklist or '顺序出题' in checklist,
          "出题自检清单包含题目顺序与ID对应检查项", is_warning=False)
    check('不得打乱题目顺序' in skill_md_for_order or '不得打乱知识点顺序' in skill_md_for_order,
          "SKILL.md 硬性规则中包含'不得打乱题目顺序'红线", is_warning=False)
    check('不得打乱顺序' in paper_template or '严格按照' in paper_template and '顺序' in paper_template,
          "试卷模板quiz-paper.md中包含顺序强制要求", is_warning=False)

    # ── 检查5：脚本关键逻辑一致性 ──
    print("\n🔧 [5/10] 检查脚本逻辑一致性...")
    pull_content = read_file(os.path.join(SKILL_DIR, 'scripts', 'quiz_pull.py'))
    push_content = read_file(os.path.join(SKILL_DIR, 'scripts', 'quiz_push.py'))

    check('from config import' in pull_content,
          "quiz_pull.py 正确从config.py导入常量")
    check('from config import' in push_content,
          "quiz_push.py 正确从config.py导入常量")
    check('薄弱点到期' in pull_content and '到期常规' in pull_content,
          "quiz_pull.py 来源标签使用新五选一名称")
    check('薄弱点到期' in push_content and '到期常规' in push_content,
          "quiz_push.py 来源标签使用新五选一名称")
    check('TYPE_A_SOURCES' in push_content or 'DUE_SOURCES' in push_content,
          "quiz_push.py 使用config中定义的类型A来源标签")
    # 检查quiz_pull.py中P3来源标签是否是"到期常规"
    check('"到期常规"' in pull_content or "'到期常规'" in pull_content,
          "quiz_pull.py P3优先级标注来源为'到期常规'")

    # 【新增】脚本import常量检查：验证必要常量是否被导入
    # quiz_pull.py 应包含的关键导入标识
    pull_required_imports = ['from config import', 'SOURCE_ICONS', 'STATUS_', 'FIELD_']
    for imp_str in pull_required_imports:
        check(imp_str in pull_content,
              f"quiz_pull.py 包含 '{imp_str}' 导入/引用", is_warning=False)

    # quiz_push.py 应包含的关键导入标识
    push_required_imports = ['from config import', 'STATUS_', 'FIELD_', 'RESET_MARK']
    for imp_str in push_required_imports:
        check(imp_str in push_content,
              f"quiz_push.py 包含 '{imp_str}' 导入/引用", is_warning=False)

    # 【新增】quiz_pull.py动态读取checklist检查
    check('def read_checklist' in pull_content,
          "quiz_pull.py 包含 read_checklist 函数定义（动态读取自检清单）")
    check('CHECKLIST_QUESTION' in pull_content,
          "quiz_pull.py 使用 CHECKLIST_QUESTION 常量动态读取出题自检清单")

    # 【新增】检查quiz_pull.py中generate_quiz_prompt函数后不应有硬编码SOURCE_ICONS字典副本
    # 允许read_checklist函数的fallback中存在硬编码checklist
    if 'def generate_quiz_prompt' in pull_content:
        # 找到generate_quiz_prompt函数起始位置
        gq_start = pull_content.index('def generate_quiz_prompt')
        # 找到下一个def或文件结尾作为函数大致范围（简单取后面3000字符检查）
        gq_section = pull_content[gq_start:gq_start + 3000]
        # 检查是否有硬编码的 {"薄弱点到期" 字典（这是SOURCE_ICONS的硬编码副本标志）
        # 但排除在read_checklist fallback中的情况
        has_hardcoded_source_icons = False
        if '{"薄弱点到期"' in gq_section or "{'薄弱点到期'" in gq_section:
            # 进一步确认不在read_checklist的fallback中
            # 如果该位置不在read_checklist函数内，则报警
            hardcoded_pos = gq_section.find('{"薄弱点到期"')
            if hardcoded_pos == -1:
                hardcoded_pos = gq_section.find("{'薄弱点到期'")
            # 检查该硬编码位置前是否有read_checklist函数定义（不应有，因为gq_section从generate_quiz_prompt开始）
            if 'def read_checklist' not in gq_section[:hardcoded_pos + 50]:
                has_hardcoded_source_icons = True
        check(not has_hardcoded_source_icons,
              "quiz_pull.py 的 generate_quiz_prompt 中无硬编码 SOURCE_ICONS 字典副本（应使用 config.SOURCE_ICONS）",
              is_warning=False)

    # 【FIX#7校验】quiz_push.py必须使用CUMULATIVE[new_round]而非CUMULATIVE[new_round - 1]
    check('CUMULATIVE[new_round]' in push_content and 'CUMULATIVE[new_round - 1]' not in push_content,
          "quiz_push.py 使用CUMULATIVE[new_round]（FIX#7：下标正确，非new_round-1）")

    # 【出题优先级校验】quiz_pull.py的P4（未到期巩固）必须有MIN_QUESTIONS条件检查
    # P4代码块中应包含 if len(result) < MIN_QUESTIONS 条件
    check('if len(result) < MIN_QUESTIONS' in pull_content,
          "quiz_pull.py P4未到期巩固包含MIN_QUESTIONS条件检查（仅在题量不足时才出题）")
    print("\n🔮 [6/10] 扫描魔法值（硬编码字符串）...")
    magic_value_scan()
    print("   ✅ 魔法值扫描完成（已覆盖quiz_pull.py和quiz_push.py的条件判断区域）")

    # ── 检查7：【新增】REGEX_CONSECUTIVE_CORRECT与LOG格式一致性检查 ──
    print("\n🔍 [7/10] 检查正则与日志格式一致性...")
    try:
        cfg = _config_module
        if cfg is not None and hasattr(cfg, 'REGEX_CONSECUTIVE_CORRECT') and hasattr(cfg, 'LOG_WEAK_CORRECT'):
            sample_date = "2026-07-20"
            try:
                sample_log = cfg.LOG_WEAK_CORRECT.format(sample_date)
                regex_match = re.search(cfg.REGEX_CONSECUTIVE_CORRECT, sample_log)
                check(regex_match is not None,
                      "REGEX_CONSECUTIVE_CORRECT 能匹配 LOG_WEAK_CORRECT 格式（薄弱点连续答对计数正常）",
                      is_warning=False)
                if regex_match is None:
                    errors.append("正则REGEX_CONSECUTIVE_CORRECT无法匹配LOG_WEAK_CORRECT格式，薄弱点连续答对计数将失效")
            except Exception as fmt_e:
                warnings.append(f"LOG_WEAK_CORRECT格式化失败: {fmt_e}")
        else:
            warnings.append("无法检查REGEX_CONSECUTIVE_CORRECT一致性：config导入失败或缺少相关常量")
    except Exception as e:
        warnings.append(f"正则一致性检查跳过: {e}")

    # ── 检查8：【新增】批改清单路径检查 ──
    print("\n📋 [8/10] 检查批改清单与文档路径...")
    grading_checklist_path = os.path.join(SKILL_DIR, 'assets', 'checklists', 'grading-checklist.md')
    grading_checklist_content = read_file(grading_checklist_path)
    if grading_checklist_content:
        # 检查是否包含ai-quiz-system路径引用
        has_correct_path = 'ai-quiz-system' in grading_checklist_content
        check(has_correct_path,
              "grading-checklist.md 中路径包含 ai-quiz-system 子目录",
              is_warning=True)
    else:
        warnings.append("无法读取 grading-checklist.md，跳过路径检查")

    # ── 检查9：【增强】SKILL.md修改协议完整性检查 ──
    print("\n📄 [9/10] 检查SKILL.md修改协议完整性...")
    skill_md_path = os.path.join(SKILL_DIR, 'SKILL.md')
    skill_md_content = read_file(skill_md_path)
    if skill_md_content:
        check('check_consistency' in skill_md_content,
              "SKILL.md 中包含 check_consistency 相关修改协议说明",
              is_warning=True)
        # 检查自指更新规则是否存在
        has_self_reference = '自指更新' in skill_md_content or '自指检查' in skill_md_content
        check(has_self_reference,
              "SKILL.md 修改协议包含自指更新规则（修改三位一体本身时同步更新防护体系）",
              is_warning=False)
        # 检查新增内容纳入规则是否存在
        has_new_content_rule = '新增功能' in skill_md_content or '新增内容' in skill_md_content or '新增常量' in skill_md_content
        check(has_new_content_rule,
              "SKILL.md 修改协议包含新增功能/内容纳入规则",
              is_warning=False)
        # 检查二次校验要求是否存在
        has_double_check = '二次校验' in skill_md_content
        check(has_double_check,
              "SKILL.md 修改协议包含自指修改后二次校验要求",
              is_warning=True)
        # 检查修改协议是否分了修改前/修改中/修改后三个阶段
        has_before = '修改前' in skill_md_content
        has_during = '修改中' in skill_md_content
        has_after = '修改后' in skill_md_content
        check(has_before and has_during and has_after,
              "SKILL.md 修改协议完整包含修改前/修改中/修改后三个阶段",
              is_warning=False)
        # 【新增】检查自我迭代模块是否存在
        has_self_iteration = '自我迭代' in skill_md_content or '自我迭代模块' in skill_md_content
        check(has_self_iteration,
              "SKILL.md 包含自我迭代模块（第十一章）", is_warning=False)
        # 检查流程E步骤E8（经验提取）是否存在
        has_e8 = '步骤E8' in skill_md_content and '经验提取' in skill_md_content
        check(has_e8,
              "SKILL.md 流程E包含步骤E8经验提取（自我迭代与修改联动）", is_warning=False)
        # 检查铁律12是否包含E8经验提取要求（不再检查旧的"临时记录机制"）
        has_e8_iron = '修改后必须提取经验' in skill_md_content and 'E8' in skill_md_content
        check(has_e8_iron,
              "SKILL.md 铁律12包含E8经验提取要求（含不满意更新机制）", is_warning=False)
        # 检查变更分级P0-P3是否存在
        has_change_grading = 'P0' in skill_md_content and 'P1' in skill_md_content and 'P2' in skill_md_content and 'P3' in skill_md_content
        check(has_change_grading,
              "SKILL.md 修改协议包含变更分级P0-P3", is_warning=False)
        # 检查铁律编号化
        has_numbered_rules = '铁律' in skill_md_content
        check(has_numbered_rules,
              "SKILL.md 硬性规则已编号化（铁律1~12）", is_warning=False)
        # 检查E8不满意更新机制
        has_e8_update = '不满意更新' in skill_md_content or '不满意' in skill_md_content
        check(has_e8_update,
              "SKILL.md E8包含不满意更新机制（用户不满意时更新已沉淀经验）", is_warning=False)
        # 检查linkage子命令是否已注册（读取自身文件确认）
        _self_path = os.path.join(SKILL_DIR, "check_consistency.py")
        _self_content = read_file(_self_path) or ""
        check("check_linkage" in _self_content and "linkage" in _self_content,
              "check_consistency.py linkage子命令已注册（联动检查功能可用）", is_warning=False)
    else:
        warnings.append("无法读取 SKILL.md，跳过修改协议检查")

    # ── 检查10：思维导图文件与其他杂项 ──
    print("\n🗺️  [10/10] 其他检查...")
    mindmap = read_file(os.path.join(PROJECT_DIR, 'AI知识思维导图.html'))
    taxonomy = read_file(os.path.join(SKILL_DIR, 'references', '04-knowledge-taxonomy.md'))

    check('双维度' in taxonomy or '维度一' in taxonomy or '建模逻辑' in taxonomy,
          "04-knowledge-taxonomy.md 包含双维度分类说明", is_warning=True)
    check(mindmap and len(mindmap) > 1000,
          f"思维导图文件大小正常（{len(mindmap)}字节）", is_warning=True)

    # 检查是否有__pycache__残留（可以清理）
    pycache_paths = []
    for root, dirs, fnames in os.walk(SKILL_DIR):
        if '__pycache__' in dirs:
            pycache_paths.append(os.path.join(root, '__pycache__'))
    if pycache_paths:
        warnings.append(f"存在__pycache__目录（可删除）: {'; '.join(pycache_paths)}")
    else:
        passed.append("无__pycache__残留")

    # 检查根目录是否有旧的today_quiz.json/grading.json/出题指令.txt（应该在ai-quiz-system/下）
    root_old_files = []
    for fname in ['today_quiz.json', 'grading.json', '出题指令.txt']:
        if os.path.exists(os.path.join(PROJECT_DIR, fname)):
            root_old_files.append(fname)
    if root_old_files:
        warnings.append(f"项目根目录存在旧运行时文件（应在ai-quiz-system/下）: {', '.join(root_old_files)}")
    else:
        passed.append("根目录无旧运行时文件")

    # ── 打印结果 ──
    print("\n" + "=" * 60)
    print(f"📊 检查结果：✅通过 {len(passed)}项  ⚠️警告 {len(warnings)}项  ❌错误 {len(errors)}项")
    print("=" * 60)

    if passed:
        print("\n✅ 通过项：")
        for p in passed:
            print(f"   ✅ {p}")

    if warnings:
        print("\n⚠️ 警告（不影响运行，但建议处理）：")
        for w in warnings:
            print(f"   ⚠️ {w}")

    if errors:
        print("\n❌ 错误（必须修复）：")
        for e in errors:
            print(f"   ❌ {e}")
        print("\n💡 修复后重新运行本脚本验证。")
        print("💡 修改前可以运行: python check_consistency.py where 关键词  快速查找所有关联位置")
        return 1
    else:
        print("\n🎉 所有检查通过！项目一致性良好。")
        return 0


def print_usage():
    """
    打印使用说明。
    输入参数：无。
    返回值：无。
    """
    print("=" * 60)
    print("ai-quiz-system 一致性校验工具 使用说明")
    print("=" * 60)
    print()
    print("用法:")
    print("  python check_consistency.py              全量一致性检查")
    print("  python check_consistency.py check        同上（默认）")
    print("  python check_consistency.py where 关键词  查询关键词出现在哪些位置")
    print("  python check_consistency.py linkage      联动检查：发现文件间读写断裂")
    print()
    print("示例:")
    print("  python check_consistency.py where 薄弱点到期")
    print("  python check_consistency.py where 填空题")
    print("  python check_consistency.py where 艾宾浩斯")
    print("  python check_consistency.py linkage")
    print()


def main():
    """
    主函数：解析命令行参数，执行对应功能。
    输入参数：无（从sys.argv读取）。
    返回值：int（0=成功，1=有错误）。
    """
    if len(sys.argv) < 2:
        return run_full_check()

    cmd = sys.argv[1].lower()

    if cmd == 'check' or cmd == 'scan':
        return run_full_check()
    elif cmd == 'where' or cmd == 'find' or cmd == 'search':
        if len(sys.argv) < 3:
            print("❌ 请指定要搜索的关键词")
            print("示例: python check_consistency.py where 薄弱点到期")
            return 1
        keyword = ' '.join(sys.argv[2:])
        where_is(keyword)
        return 0
    elif cmd == 'linkage' or cmd == 'link':
        return check_linkage()
    elif cmd == 'help' or cmd == '-h' or cmd == '--help':
        print_usage()
        return 0
    else:
        print(f"❌ 未知命令: {cmd}")
        print_usage()
        return 1


if __name__ == "__main__":
    sys.exit(main())
