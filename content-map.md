# ai-quiz-system 内容关联映射表（Impact Matrix）

## 使用说明

本文件是项目的"反向索引追溯表"，记录每个可修改内容在哪些位置被引用/定义。
**修改任何内容前，先查本表+运行where命令，确保所有关联位置同步修改。**

- **主定义位置（SSOT）**：唯一的事实来源，修改时只改这里
- **引用位置**：必须同步检查的位置，包括代码引用、文档描述、模板示例、定时任务prompt
- **自动化程度**：
  - ✅ `代码引用`：通过config.py import自动同步，无需手动改
  - ⚠️ `文档引用`：需手动同步修改
  - 🔧 `脚本生成`：由脚本自动生成/读取，无需手动改

---

## 一、代码常量（主定义：`scripts/config.py`）——SSOT第一层

> ⚠️ 所有代码常量只在config.py中定义，quiz_pull.py和quiz_push.py通过import引用。
> 修改常量只改config.py即可，代码中自动同步。

| 常量名 | 含义 | 主定义位置 | 引用位置 | 自动化 |
|-------|------|-----------|---------|--------|
| `LARK` | lark-cli路径 | config.py | quiz_pull.py、quiz_push.py（import）、scripts/README.md（文字描述） | ✅ |
| `SKILL_DIR/PROJECT_DIR/SCRIPT_DIR` | 目录结构 | config.py | quiz_pull.py、quiz_push.py（import） | ✅ |
| `BASE_TOKEN/TABLE_ID` | 飞书表格ID | config.py | quiz_pull.py、quiz_push.py（import） | ✅ |
| `TODAY_QUIZ_FILE/PROMPT_FILE/GRADING_FILE` | 运行时文件路径 | config.py | quiz_pull.py、quiz_push.py（import）、SKILL.md路径表、grading-checklist.md | ✅ |
| `CUMULATIVE` | 艾宾浩斯间隔数组[1,3,7,15,30] | config.py | quiz_pull.py、quiz_push.py（import）、02-grading-rules.md（轮次-间隔对照表）、SKILL.md（术语解释） | ⚠️ |
| `LEVELS/LEVEL_ORDER` | 级别三元组+排序权重 | config.py | quiz_pull.py（import）、01-question-format.md、03-knowledge-ingest.md、question-checklist.md、quiz-paper.md模板 | ✅ |
| `ONE_STAR_ACTIVE` | ★☆☆是否主动出题 | config.py | quiz_pull.py（import） | ✅ |
| `TYPE_A_SOURCES/TYPE_B_SOURCES/ALL_SOURCES` | 来源标签5种分类 | config.py | quiz_pull.py、quiz_push.py（import）、SKILL.md、01-question-format.md、02-grading-rules.md、quiz-paper.md模板、出题指令.txt（脚本生成） | ✅ |
| `WEAK_SOURCES` | 标🔥的来源标签 | config.py | quiz_pull.py（import）、SKILL.md、01-question-format.md | ✅ |
| `SOURCE_ICONS` | 来源标签→emoji图标字典 | config.py | quiz_pull.py（import，控制台输出+试卷头） | ✅ |
| `STATUS_UNTESTED/LEARNING/MASTERED/REVIEW` | 掌握状态四种值 | config.py | quiz_pull.py、quiz_push.py（import）、02-grading-rules.md、03-knowledge-ingest.md、飞书字段选项 | ✅ |
| `STATUS_VALUES/STATUS_ICONS` | 状态元组+图标字典 | config.py | quiz_pull.py、quiz_push.py（import） | ✅ |
| `QUESTION_TYPES/QUESTION_TYPE_LETTERS` | 题型三元组 | config.py | quiz_pull.py（import）、01-question-format.md、question-checklist.md | ✅ |
| `DEFAULT_MAX_QUESTIONS` | 默认最大题数(20) | config.py | quiz_pull.py（argparse默认值）、SKILL.md | ⚠️ |
| `MIN_QUESTIONS` | 触发P5的题量阈值(10) | config.py | quiz_pull.py（P5逻辑） | ✅ |
| `RATIO_CHOICE/FILL/SHORT` | 题型比例55/25/20 | config.py | quiz_pull.py（题型分配）、01-question-format.md（百分比描述）、出题指令.txt（脚本生成） | ⚠️ |
| `WEAK_REMOVE_THRESHOLD` | 薄弱点解除阈值(2) | config.py | quiz_push.py（连续答对判断）、02-grading-rules.md（FIX#2说明）、SKILL.md | ⚠️ |
| `FILL_BLANK_PATTERN/COUNT` | 填空题下划线格式 | config.py | quiz_pull.py（生成示例）、出题指令.txt（脚本生成）、01-question-format.md、question-checklist.md | ⚠️ |
| `RESET_MARK` | [重置]标记字符串 | config.py | quiz_push.py（查找重置位置+追加标记）、02-grading-rules.md（FIX#3说明） | ✅ |
| `LOG_WEAK_CORRECT/REVIEW_CORRECT/WRONG` | 薄弱点日志格式串 | config.py | quiz_push.py（追加日志） | ✅ |
| `REGEX_CONSECUTIVE_CORRECT` | 匹配连续到期答对的正则 | config.py | quiz_push.py（count_consecutive_correct） | ✅ |
| `DATE_FORMAT/DATE_FORMAT_DAY` | 日期格式串 | config.py | quiz_push.py（日期格式化）、quiz_pull.py（日期解析） | ✅ |
| `FIELD_*`（19个） | 飞书多维表格字段名 | config.py | quiz_pull.py（读取解析）、quiz_push.py（写入更新）、content-map.md飞书字段表 | ✅ |
| `GRADING_FIELD_*`（3个） | grading.json字段名 | config.py | quiz_push.py（解析批改结果）、grading-result.json模板 | ✅ |
| `QUIZ_ENDING` | 试卷结尾语 | config.py | quiz_pull.py（出题指令末尾）、01-question-format.md、quiz-paper.md模板 | ⚠️ |
| `DOC_*/TEMPLATE_*/CHECKLIST_*` | 文档/模板/清单路径 | config.py | quiz_pull.py（动态读取checklist）、check_consistency.py | ✅ |

---

## 二、分类体系（主定义：飞书多维表格 + `references/04-knowledge-taxonomy.md`）

| 内容项 | 主定义位置 | 引用/关联位置 | 修改注意事项 |
|-------|-----------|-------------|------------|
| L0-L4层级名称和缩写 | 04-knowledge-taxonomy.md + 飞书字段选项 | 03-knowledge-ingest.md、SKILL.md、思维导图HTML、quiz_pull.py（显示分类） | 新增/修改L2/L3/L4时：①更新飞书单选字段选项 ②更新04-taxonomy文档 ③思维导图更新 ④03-ingest文档同步 |
| 知识点ID格式（6段式） | 04-knowledge-taxonomy.md | 01-question-format.md、quiz_pull.py（示例ID）、飞书知识点ID字段 | ID一旦分配不轻易修改；若改ID需更新飞书+所有文档示例 |
| 双维度分类（技术领域/建模逻辑） | 思维导图HTML + 04-taxonomy.md | 03-knowledge-ingest.md、知识标签字段 | DL下分类变更需更新04-taxonomy+思维导图 |
| 知识标签选项 | 飞书"知识标签"多选字段 + 04-taxonomy.md标签表 | 03-knowledge-ingest.md、quiz_pull.py | 新增标签需更新飞书字段和04-taxonomy标签表 |

---

## 三、出题格式规则（主定义：`references/01-question-format.md` + `config.py`）

| 规则项 | 主定义位置 | 关联位置 | 修改注意事项 |
|-------|-----------|---------|------------|
| **🔴题目顺序强制规则** | quiz_pull.py generate_quiz_prompt()最高优先级规则 | SKILL.md步骤A5+红线第1条、quiz-paper.md模板、question-checklist.md第0条、check_consistency.py检查4 | ⚠️ P0级规则！必须严格按知识点清单顺序出题，第N题ID必须对应清单[N]，不得打乱顺序、不得按题型分组；违反会导致批改时对错更新到错误知识点 |
| 题型列表（选择/填空/简答） | QUESTION_TYPES（config.py）+ 01文档 | SKILL.md、quiz-paper.md模板、出题指令.txt（脚本生成）、question-checklist.md | 新增题型需更新：①config.QUESTION_TYPES ②01文档 ③quiz_pull.py题型分配逻辑 ④自检清单 |
| 选择题4选项规则 | 01-question-format.md | 出题指令.txt（脚本生成）、question-checklist.md | 修改规则需同步01文档；选项位置可随机但题目顺序不变 |
| **填空题下划线格式** `____（N）____` | config.FILL_BLANK_PATTERN + 01文档 | quiz_pull.py（使用config常量生成示例）、出题指令.txt（脚本生成）、question-checklist.md第1条 | ⚠️ 最高频出错点！格式串定义在config.py，01文档和checklist文字描述需同步 |
| 填空题字数提示规则 | 01-question-format.md | 出题指令.txt（脚本生成）、question-checklist.md | |
| 简答题最少要点数要求 | 01-question-format.md | 出题指令.txt（脚本生成）、question-checklist.md | |
| 专业名词首次解释规则 | 01-question-format.md | SKILL.md、出题指令.txt、question-checklist.md第4条 | |
| 元信息格式（题号/ID/题型/来源/🔥） | 01-question-format.md | quiz-paper.md模板、出题指令.txt（脚本生成） | 🔥标记规则由config.WEAK_SOURCES决定 |
| 题型-级别绑定（★☆☆只出选择） | 01文档 + config.ONE_STAR_ACTIVE | quiz_pull.py（过滤逻辑）、出题指令.txt、question-checklist.md第9条 | |
| 试卷头格式 | quiz-paper.md模板 + quiz_pull.py生成逻辑 | 01文档试卷头章节、SKILL.md | 修改试卷头需同步模板和quiz_pull.py |
| **出题自检清单** | assets/checklists/question-checklist.md | quiz_pull.py（read_checklist动态读取）、出题指令.txt（脚本嵌入）、SKILL.md步骤A6 | ✅ 从config.CHECKLIST_QUESTION动态读取，修改checklist文件即可，无需改代码 |
| QUIZ_ENDING结尾语 | config.QUIZ_ENDING | quiz-paper.md模板、01文档 | |

---

## 四、批改规则（主定义：`references/02-grading-rules.md` + `scripts/quiz_push.py` + `config.py`）

| 规则项 | 主定义位置 | 关联位置 | 修改注意事项 |
|-------|-----------|---------|------------|
| A/B/C三类判定条件 | 02文档 + config.TYPE_A_SOURCES/TYPE_B_SOURCES | quiz_push.py（compute_push_patch）、SKILL.md步骤B | 来源标签与类型映射在config.py定义 |
| 类型A：推进轮次规则 | 02文档 + quiz_push.py代码 | config.CUMULATIVE（间隔天数） | 修改间隔天数改config.CUMULATIVE |
| 类型B：不推进轮次 | 02文档 + quiz_push.py代码 | | |
| 类型C：答错归零+薄弱点 | 02文档 + quiz_push.py代码 | | |
| FIX#1防回溯日期公式 | quiz_push.py代码 | 02文档（文字说明） | 修改公式需同步02文档 |
| FIX#2薄弱点解除条件 | config.WEAK_REMOVE_THRESHOLD + quiz_push.py | 02文档 | 阈值在config.py定义；正则REGEX_CONSECUTIVE_CORRECT必须匹配LOG_WEAK_CORRECT格式 |
| FIX#3[重置]标记规则 | config.RESET_MARK + quiz_push.py | 02文档 | 修改标记字符串改config.RESET_MARK |
| FIX#4随机巩固不推进 | quiz_push.py代码 | 02文档 | |
| FIX#5去重 | quiz_pull.py代码 | 02文档 | |
| FIX#6优先级截断顺序 | quiz_pull.py代码 | 02文档 | |
| 掌握状态流转（⚪→🟡→🟢/🔴） | config.STATUS_* + quiz_push.py代码 | 02文档、飞书"掌握状态"字段选项 | 新增状态需更新config.STATUS_VALUES+飞书字段+代码+文档 |
| grading.json格式 | TEMPLATE_GRADING_RESULT + config.GRADING_FIELD_* | SKILL.md步骤B3、02文档、quiz_push.py解析逻辑 | 修改字段名改config.GRADING_FIELD_*即可 |
| 批改总结格式 | grading-summary.md模板 | SKILL.md步骤B5 | |
| 批改自检清单 | grading-checklist.md | SKILL.md步骤B | 第5项路径必须是ai-quiz-system/下 |
| 薄弱点日志格式 | config.LOG_WEAK_* + REGEX_CONSECUTIVE_CORRECT | quiz_push.py、02文档 | ⚠️ 修改LOG格式必须同步REGEX，否则连续答对计数失效（check_consistency.py自动校验） |

---

## 五、知识点入库流程（主定义：`references/03-knowledge-ingest.md`）

| 规则项 | 主定义位置 | 关联位置 | 修改注意事项 |
|-------|-----------|---------|------------|
| 7步入库流程 | 03-knowledge-ingest.md | SKILL.md工作流C | |
| 6项科学性审查标准 | 03-knowledge-ingest.md | | |
| 查重4种策略 | 03-knowledge-ingest.md | | |
| 三问定级法（★判定） | 03-knowledge-ingest.md | | |
| 入库反馈格式 | ingest-feedback.md模板 | SKILL.md步骤C4 | |
| 新知识点初始值规则 | quiz_push.py逻辑（轮次0/⚪未测试/明天复习） | 03文档第5章 | 初始值在入库时设定 |

---

## 六、飞书多维表格字段（主定义：`config.py FIELD_*`常量）

> ⚠️ 所有字段名常量定义在config.py中。修改飞书字段名时：
> 1. 先在飞书表格中修改字段名
> 2. 修改config.py中对应的FIELD_*常量值
> 3. check_consistency.py会验证脚本引用

| 常量名 | 飞书字段名 | 类型 | 引用脚本 |
|-------|-----------|------|---------|
| FIELD_RECORD_ID | record_id | 系统字段 | quiz_pull.py、quiz_push.py |
| FIELD_KP_ID | 知识点ID | 文本 | quiz_pull.py、quiz_push.py |
| FIELD_KP_TITLE | 知识点标题 | 文本 | quiz_pull.py |
| FIELD_CORE_CONTENT | 核心内容 | 多行文本 | quiz_pull.py（出题指令） |
| FIELD_STATUS | 掌握状态 | 单选（STATUS_VALUES） | quiz_pull.py、quiz_push.py |
| FIELD_LEVEL | 重要程度 | 单选（LEVELS） | quiz_pull.py、quiz_push.py |
| FIELD_ROUND | 复习轮次 | 数字 | quiz_pull.py、quiz_push.py |
| FIELD_CORRECT_COUNT | 正确次数 | 数字 | quiz_pull.py、quiz_push.py |
| FIELD_WRONG_COUNT | 错误次数 | 数字 | quiz_pull.py、quiz_push.py |
| FIELD_IS_WEAK | 薄弱点 | 复选框 | quiz_pull.py、quiz_push.py |
| FIELD_WEAK_DESC | 薄弱点描述 | 多行文本 | quiz_push.py（追加日志） |
| FIELD_IN_WRONG_BOOK | 错题本 | 复选框 | quiz_push.py |
| FIELD_ADD_DATE | 添加日期 | 日期 | quiz_pull.py、quiz_push.py |
| FIELD_NEXT_DATE | 下次复习日期 | 日期 | quiz_pull.py、quiz_push.py |
| FIELD_L0~L4 | L0阶段~L4章节 | 单选 | quiz_pull.py（出题指令显示分类） |
| FIELD_TAGS | 知识标签 | 多选 | quiz_pull.py（出题指令显示） |

---

## 七、项目外关联

| 关联项 | 位置 | 关联内容 | 修改注意事项 |
|-------|------|---------|------------|
| 定时任务prompt | Schedule工具（ID: a2a6b4fd） | 完整执行流程、所有路径、规则摘要 | 修改Skill路径/脚本名/核心流程后，必须用Schedule工具update |
| AI知识思维导图.html | 项目根目录 | 完整知识分类结构、知识点列表 | 飞书新增知识点、分类结构变更后需更新HTML |
| lark-cli | 全局npm安装 | 飞书API调用 | lark-cli路径变更需更新config.LARK |

---

## 八、文件清单（修改时对照）

```
ai-quiz-system/
├── SKILL.md                              # 🔴 主指令入口（含修改协议第九章）
├── check_consistency.py                  # 🔴 一致性校验脚本（55+项检查）
├── content-map.md                        # 🔴 本文件（映射表）
├── scripts/
│   ├── config.py                         # 🔴🔴 SSOT：所有常量唯一来源（改常量只改这里）
│   ├── quiz_pull.py                      # 出题筛选+出题指令生成（动态读取checklist）
│   ├── quiz_push.py                      # 批改+艾宾浩斯计算+飞书写回
│   └── README.md                         # 脚本说明文档
├── references/
│   ├── 01-question-format.md             # 出题格式规则
│   ├── 02-grading-rules.md               # 批改规则
│   ├── 03-knowledge-ingest.md            # 入库流程
│   └── 04-knowledge-taxonomy.md          # 分类体系（改分类必改）
├── assets/
│   ├── templates/
│   │   ├── quiz-paper.md                 # 试卷模板
│   │   ├── grading-result.json           # grading.json格式
│   │   ├── grading-summary.md            # 批改总结模板
│   │   └── ingest-feedback.md            # 入库反馈模板
│   └── checklists/
│       ├── question-checklist.md         # 出题自检（quiz_pull.py动态读取）
│       └── grading-checklist.md          # 批改自检
├── today_quiz.json                       # 运行时生成（不手动改）
├── 出题指令.txt                           # 运行时生成（不手动改）
└── grading.json                          # 运行时生成（AI写入）

项目根目录：
└── AI知识思维导图.html                   # 思维导图（改分类必更新）
```

---

## 九、三位一体自指更新映射（⚠️修改防护体系本身时必看）

> 当修改的内容涉及config.py/content-map.md/check_consistency.py/SKILL.md这四个核心文件时，属于"自指修改"，必须按照下表同步更新，否则防护体系本身会失效。

| 修改对象 | 需要同步更新的位置 | 校验方式 |
|---------|------------------|---------|
| **config.py（新增常量）** | ①content-map.md第一章常量表添加一行 ②check_consistency.py检查2的required_constants列表添加常量名 | check_consistency.py检查2自动验证常量存在 |
| **config.py（修改路径常量）** | ①SKILL.md第七章路径速查表 ②content-map.md第八章文件清单 | check_consistency.py检查1验证文件存在 |
| **content-map.md（新增章节/表格）** | ①SKILL.md第九章引用是否正确 ②check_consistency.py是否需要新增对应检查项 | 人工核对+check_consistency.py检查9 |
| **content-map.md（修改文件清单）** | ①check_consistency.py检查1的required_files列表 | check_consistency.py检查1自动验证 |
| **check_consistency.py（新增检查项）** | ①content-map.md对应章节"修改注意事项"添加说明 ②SKILL.md第九章"修改后"部分说明（必要时） | 人工核对 |
| **check_consistency.py（新增bad_pattern）** | ①content-map.md对应章节"修改注意事项"添加禁止模式说明 | 人工核对 |
| **SKILL.md（修改流程步骤）** | ①content-map.md第九章"修改流程Checklist"同步更新步骤 | check_consistency.py检查9验证三阶段存在 |
| **SKILL.md（新增流程E/F...）** | ①SKILL.md第二章工作流判断表添加触发词 ②配套references文档 ③配套templates/checklists ④content-map.md新增对应章节 ⑤check_consistency.py检查1添加新文件 | check_consistency.py检查9+检查1 |
| **SKILL.md（修改本协议本身）** | ①content-map.md第九章同步更新 ②修改完成后必须二次运行check_consistency.py | 二次校验 |

---

## 十、新增功能/内容纳入流程

> 新增任何常量、文档、模板、清单、脚本、流程时，必须按照以下流程纳入三位一体防护体系，否则新内容会成为"漏改盲区"。

| 新增类型 | 纳入步骤 |
|---------|---------|
| **新增常量** | ①在config.py定义 ②content-map.md第一章加条目 ③check_consistency.py的required_constants加常量名 |
| **新增规则文档（references/*.md）** | ①创建md文件 ②SKILL.md对应流程加"必须读取" ③SKILL.md第七章加路径 ④content-map.md对应章节加映射 ⑤check_consistency.py检查1加文件 |
| **新增模板（assets/templates/*）** | ①创建模板文件 ②config.py加TEMPLATE_*路径常量 ③SKILL.md第七章加路径 ④content-map.md第八章加清单 ⑤代码中通过config常量引用路径 |
| **新增清单（assets/checklists/*）** | ①创建checklist文件 ②config.py加CHECKLIST_*路径常量 ③SKILL.md第七章加路径 ④content-map.md第八章加清单 ⑤代码中动态读取（参考read_checklist函数），不要硬编码副本 |
| **新增脚本（scripts/*.py）** | ①创建脚本文件 ②脚本中所有常量 `from config import` ③SKILL.md对应流程加"必须执行" ④SKILL.md第七章加路径 ⑤content-map.md第八章加清单 ⑥check_consistency.py检查1的required_files加文件 |
| **新增流程（如流程E）** | ①SKILL.md加新流程章节 ②SKILL.md第二章判断表加触发词 ③配套references文档+模板+清单按上述步骤纳入 ④content-map.md加新章节记录关联关系 |

---

## 修改流程Checklist（零漏改标准流程）

> ⚠️ 此流程已写入SKILL.md第九章"Skill修改协议"，修改Skill时AI会自动遵守。

### 修改前
1. **快速定位所有关联位置**：运行 `python ai-quiz-system/check_consistency.py where 关键词`
2. **对照本表确认主定义位置**：找到"主定义位置"（只改这里）
3. **⚠️自指检查**：判断是否修改config.py/content-map.md/check_consistency.py/SKILL.md本身，如果是，对照第九章"自指更新映射表"准备同步更新

### 修改中
4. 修改主定义位置（常量改config.py，规则改对应文档）
5. 逐一修改所有引用位置（脚本import自动同步，文档需手动改）
6. 代码中不要硬编码中文字符串/数字，全部引用config常量
7. quiz_pull.py的自检清单从checklist文件动态读取，不要硬编码副本
8. **自指同步**：如果修改了三位一体本身，按第九章映射表同步更新所有关联位置
9. **新内容纳入**：如果是新增功能/内容，按第十章"新增功能纳入流程"逐步纳入防护体系

### 修改后
10. **运行自动校验**：执行 `python ai-quiz-system/check_consistency.py`
    - 如有❌错误，必须修复后重新校验
    - ⚠️警告视情况处理
11. 如果修改了config.py常量/新增字段/新增规则，更新本content-map.md
12. 如果修改了分类结构，更新思维导图HTML
13. 如果修改了核心流程/路径/脚本名，用Schedule工具update定时任务prompt
14. **⚠️二次校验**：如果修改了content-map.md或check_consistency.py本身，必须**再运行一次**check_consistency.py，确保护栏更新后仍然有效

### 校验工具命令速查

| 命令 | 作用 | 什么时候用 |
|------|------|-----------|
| `python check_consistency.py` | 全量一致性检查（60+项） | 修改完成后必跑；自指修改后跑两次 |
| `python check_consistency.py where 关键词` | 搜索关键词在所有文件中的位置 | 修改前，找所有需要改的地方 |
| `python check_consistency.py help` | 显示帮助 | 忘记命令时 |
