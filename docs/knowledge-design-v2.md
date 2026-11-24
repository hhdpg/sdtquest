# 知识库设计 v2：面向业务人员的生产级智能问答知识体系

> 版本：v2.0-draft　｜　日期：2026-11-24　｜　状态：待评审
>
> 本文替代现有「前端代码解析 → 页面说明文档」的知识构建方式，重新定义知识单元、
> 摄取流程、检索链路与运营闭环，目标是在生产环境中服务**半熟业务人员**。
> 现有实现作为素材来源保留，但不再直接产出知识。

---

## 1. 背景与问题诊断

### 1.1 现状

线上 `question_records` 共 148 条记录，去重后的真实业务问题仅 12 个左右：

```
怎么下单 / 订单怎么创建 / 订单审批流程是什么 / 怎么批量导出POD
阿迪订单页面有哪些操作按钮 / 怎么查询所有订单 / 库存怎么管理
新增报表里没看到体积 / 为什么权限被拒绝 / 页面样式乱了 / 运单是什么 / 数据库有哪些表
```

知识库现状（`analytics.db.knowledge_items` 与 ChromaDB）：

| 类型 | 条数 | 实际内容形态 |
|---|---|---|
| page | 151 | 页面名 + 按钮名 + 方法名（`「查询」—— 触发 handleSelectButton`） |
| workflow | 63 | 按钮 → method → API 函数名的调用链路 |
| manual | 95 | 后端 `knowledge/*.md` 按 3000 字硬切块的碎片（`Business Domain (第2部分)`） |

文档嵌入特征：平均 1082 字，最长 3024 字，整篇一次性向量化。

### 1.2 问题定性

回答质量高度依赖是否命中后端业务规则文档：

- `订单审批流程是什么` → 答得好。命中 `knowledge/rules/business-rules.md` 的审批触发条件、自动驳回、时效阈值。
- `怎么下单` → 三次中两次 `no_match`。命中的是页面卡片，只含按钮清单，无任何"什么情况下不能下单"。

结论：**问题不在 RAG 检索，而在知识的"形状"错了。**

### 1.3 根因：三个错位

| 错位 | 现状 | 应该 |
|---|---|---|
| **提问者错位** | 产出"页面有什么按钮" | 业务人员问"我这单为什么下不了""这状态下一步是什么" |
| **来源权重错位** | 前端 741 页面抽 151 条；后端 342KB 规则/表/MQ 仅进 95 条碎片 | 业务真相在后端（规则文档、406 枚举、368 Controller、ErrorCode） |
| **粒度错位** | 1000+ 字整篇 embedding，语义稀释 | 一卡一事，200–500 字 |

### 1.4 一个关键观测

`怎么下单` 在 17:11、17:15 两次 `no_match`，17:59 之后全部 `success`。知识内容未变，是阈值/文档被调整过。

这说明：**当前通过调阈值（`RAG_THRESHOLD_STANDARD=0.52` 等）来掩盖知识质量问题**。卡片化后 `one_liner` 仅一行，相似度天然在 0.7+，阈值调参将不再是主要手段。

---

## 2. 行业实践调研

| 产品 | 知识单元 | 核心规则 |
|---|---|---|
| **Intercom Fin** | 文章 / 章节 | 一节一主题；标题写成客户问法（query-answer 对称）；数字必须精确，禁用"几分钟"；表格须带引导句（可能脱离标题单独召回） |
| **Guru** | Card（知识卡） | 一卡一小块、可执行；每卡有验证人 + 有效期 + 复核间隔；未验证且长期无使用的卡自动归档 |
| **Zendesk** | 文章 + FAQ | 零散事实放 FAQ，不硬撑成文章 |
| **Anthropic（生产 RAG）** | 带上下文的 chunk | 每 chunk 补"在原文中的位置"；向量 + BM25 混合 + rerank，检索失败率降低 67% |

### 2.1 提取的四条共性

1. **知识单元是"卡"不是"文档"**——一卡只回答一个问题。
2. **按用户提问方式写**，不按代码结构写。
3. **每块自包含**——能被单独召回，脱开标题也读得懂。
4. **有 owner、有效期、验证机制**——否则知识必然腐烂。

### 2.2 可量化的运营标准（Intercom）

- 按**解决率**（目标 ≥ 90%）评估内容，而非浏览量。
- 每周处理 AI 建议与人工反馈；每月重构一次低效内容。
- 高曝光 + 低解决率 = 需要重构的强信号。

### 2.3 生产 RAG 参数（Anthropic / 阿里云实测）

- 中文分块 500–800 字，重叠 10–20%。
- 向量 + BM25 混合优于纯向量；加入 rerank 后收益再叠加。
- Top-10 / Top-20 优于 Top-5。
- 知识库 < 200k tokens 时可整库入 prompt（本项目当前 342KB ≈ 150k tokens，接近边界，仍应以检索为主）。

---

## 3. 目标用户与设计原则

### 3.1 用户画像：半熟业务人员

- **能听懂**：下单页、提交按钮、待审批、POD、合单、月结卡。
- **听不懂**：`us_order`、`handleCreateOrder`、`orderStatus=3`、`store action`。

### 3.2 设计原则

| 编号 | 原则 | 落地要求 |
|---|---|---|
| P1 | 一卡一事 | 每张卡只回答一个问题，200–500 字，超出即拆 |
| P2 | 双视图 | 检索视图带技术锚点，呈现视图纯业务语言 |
| P3 | 自包含 | 每张卡脱开上下文仍可独立读懂 |
| P4 | 有出处 | `source_ref` 必填，无出处的卡不入库 |
| P5 | 前后端合并 | 前端提供入口，后端提供规则，合成任务卡 |
| P6 | 可治理 | owner + verified_at + expires_at 必填 |
| P7 | 不硬答 | 未命中直接说没资料，禁止编造 |

### 3.3 双视图规范

**检索视图**（用于召回，不展示给用户）：

- 包含表名、枚举值、错误码、方法名、接口路径、按钮原文。
- 全部放入 `anchors` 字段，参与 BM25 / 关键词召回。

**呈现视图**（用于回答）：

- 只出现：页面名、按钮名（用「」标注）、单据名、状态名、业务术语。
- 禁止出现：类名、方法名、字段名、表名、SQL、枚举常量。

> 目录：现有实现把两者混在 `content` 里，技术噪声直接进入知识正文，
> 是本项目"回答浅且不可用"的直接成因之一。

---

## 4. 知识卡 Schema

### 4.1 字段定义

```yaml
card_id:        string    # 稳定 ID，建议 {module}-{cardtype}-{slug}，如 order-task-create
type:           enum      # glossary | task | rule | state | trouble | flow | faq
title:          string    # 用户问法，≤ 30 字，不含内部团队名/代码名
one_liner:      string    # 一句话答案，单行 ≤ 80 字，检索主力字段
body:           string    # 正文，200–500 字，按 cardtype 结构组织
anchors:        list[str] # 别名·同义词·错误码·枚举值·按钮名·表名·方法名（检索视图）
module:         string    # 业务域：订单 / 运单 / 商品 / 库存 / 财务 ...
entry_path:     string?   # 页面路由，如 /adiBus/order
roles:          list[str] # 适用角色，空表示全员
permissions:    list[str] # 所需权限点，如 adiBus:order:create
source_ref:     list[str] # 出处，必填，形如 knowledge/rules/business-rules.md#1.1
owner:          string    # 复核人（工号）
verified_at:    date      # 最近验证时间
expires_at:     date?     # 过期时间；空表示长期有效
version:        string    # 语义化版本，如 2026-11.1
related:        list[str] # 关联 card_id
```

### 4.2 字段约束

| 字段 | 约束 | 违反后果 |
|---|---|---|
| `title` | 必须写成用户问法；不含类名、表名、团队名 | Fin 会把标题复述给用户，技术名会造成困惑 |
| `one_liner` | 单行 ≤ 80 字，必须先说"怎么做/是什么" | 这是召回与首句答案的主力，过长则失去作用 |
| `body` | 200–500 字；超 500 字必须拆卡 | 语义稀释，见 §1.3 |
| `anchors` | 至少 3 个；必须覆盖用户可能使用的所有别名 | 词汇鸿沟，见 §7.2 |
| `source_ref` | 必填且需可定位到具体章节 | 无法追溯 = 无法治理 |
| `owner` | 必填，须为在职工号 | 无主知识必然腐烂（Guru 反面案例） |
| `expires_at` | 规则类卡建议 6 个月；术语卡可长期 | 规则变更（如箱号唯一性 2026-09 调整）后旧卡会误导 |

### 4.3 校验规则（入库前强制）

```python
REQUIRED_FIELDS = ("card_id", "type", "title", "one_liner", "body",
                   "anchors", "module", "source_ref", "owner", "verified_at")

def validate_card(card: dict) -> list[str]:
    """返回错误列表，空列表表示通过"""
    errors = []
    for f in REQUIRED_FIELDS:
        if not card.get(f):
            errors.append(f"缺少必填字段: {f}")
    if len(card.get("one_liner", "")) > 80:
        errors.append("one_liner 超过 80 字")
    if not (100 <= len(card.get("body", "")) <= 500):
        errors.append("body 长度须在 100–500 字之间")
    if len(card.get("anchors", [])) < 3:
        errors.append("anchors 至少 3 个")
    if _contains_code_leak(card.get("title", "") + card.get("one_liner", "")):
        errors.append("标题/一句话答案含代码名，违反双视图规范")
    return errors
```

`_contains_code_leak` 检测：驼峰标识符、`us_` 前缀表名、全大写枚举常量、`/api/` 路径。

### 4.4 与现有模型的映射

现有 `KnowledgeItem`（`src/domain/models/knowledge.py`）需要扩展：

| 现有字段 | 处理 | 说明 |
|---|---|---|
| `id` | → `card_id` | 改为语义化 ID，便于人工维护与追溯 |
| `type` | → `type` | `KnowledgeType` 枚举需替换为七类卡型 |
| `title` | 保留 | 需按"用户问法"重写全部 309 条 |
| `content` | → `body` | 需重切并去技术噪声 |
| `tags` | → `anchors` | 概念扩展：从"标签"变为"召回锚点" |
| `page_name` / `page_path` | 合并为 `entry_path` | — |
| `source_file` | → `source_ref` | 升级为必须可定位到章节 |
| — | 新增 `one_liner` | 检索主力，现无此字段 |
| — | 新增 `owner` / `verified_at` / `expires_at` / `version` | 治理字段，现完全缺失 |
| `embedding` | 保留 | 但向量化对象改为 `title + one_liner + body 摘要` |

---

## 5. 七类卡型定义与模板

### 5.1 卡型总览

| 卡型 | 用户问法 | 内容骨架 | 主要来源 | 预估数量 |
|---|---|---|---|---|
| `glossary` 术语卡 | "POD 是什么""体积在哪" | 业务定义 → 系统里叫什么 → 在哪看 | 枚举 desc、表注释、页面标题 | 50–80 |
| `task` 任务卡 | "我要下单""怎么导出" | 一句话答案 + 入口 + 步骤 + 前置 + 限制 | **前端入口 + 后端规则合并** | 60–80 |
| `rule` 规则卡 | "为什么下不了""有什么限制" | 规则 → 触发条件 → 失败表现 → 怎么办 | `business-rules.md`、`BizException` | 80–120 |
| `state` 状态卡 | "待审批能改吗" | 状态含义 → 可做什么 → 下一步 | `*Enum.java`（406 个） | 60–100 |
| `trouble` 故障卡 | "提示权限不足怎么办" | 报错原文（anchors）→ 原因 → 处理 | ErrorCode、校验文案 | 40–60 |
| `flow` 流程卡 | "审批流程是怎样的" | 步骤 → 谁审批 → 时效 | 规则文档、PRD | 20–30 |
| `faq` 问答卡 | 高频问题 | 问 → 标准答案 | 日志 + 人工确认 | 30–50 |

> **数量说明**：表中是理论上限。实际应按真实问题覆盖率排序，
> 只做 Top 50 问题涉及的卡（见 §9.2），避免卡片爆炸。

### 5.2 术语卡模板

```yaml
card_id: order-glossary-pod
type: glossary
title: POD 是什么？在系统哪里看？
one_liner: POD 就是签收凭证；在「运单管理」查运单，详情里的「签收单」就是 POD。
body: |
  POD 是 Proof of Delivery 的缩写，中文叫「签收单」，是收货方确认收到货物的凭证。

  在系统里：
  · 位置：运单管理 → 选择运单 → 详情 → 「签收单」页签
  · 数据表：us_waybill_pod（内部调用）
  · 字段：签收人、签收时间、签收图片

  常见用法：
  · 客户要签收证明 → 提供 POD
  · 理赔需要举证 → 调取 POD
anchors: [POD, 签收单, 签收凭证, 回单, proof of delivery, us_waybill_pod]
module: 运单
entry_path: /waybill
source_ref: [knowledge/business/waybill.md, src/pages/waybill/detail.vue]
owner: 01415465
verified_at: 2026-11-24
```

> 注意 `body` 中 `us_waybill_pod` 仅作内部说明，**呈现给用户时应剔除**（见 §7.3）。

### 5.3 任务卡模板（核心）

任务卡必须**前后端合并**才能生成——前端提供入口，后端提供限制。

```yaml
card_id: order-task-create
type: task
title: 怎么下单？订单怎么创建？
one_liner: 进「下单」页，点右上「下单」按钮，填完收寄信息后提交。
body: |
  【入口】页面左上菜单「阿迪业务 → 下单」，或直接访问 /adiBus/order。

  【步骤】
  1. 点「下单」按钮，打开新建订单弹窗
  2. 填寄件人、收件人（可先从地址簿选择）
  3. 填货物信息：名称、数量、重量；数量不填按 1 件处理
  4. 选择取件时间、快递类型
  5. 点「确定」提交

  【注意（来自后端校验规则）】
  · 取件时间须晚于当前 2 小时，否则创建失败
  · 同一客户订单号已存在且状态不是「导入」的，会被直接拒绝
  · 命中审批规则的订单会进入「待审批」，不会立即下单
  · 跨境订单需填报关明细，货物数量必须等于明细项之和

  【常见报错】提示「权限不足」→ 需 adiBus:order:create 权限，找组织管理员开通
anchors: [下单, 创建订单, 新建订单, 下订单, handleCreateOrder, /adiBus/order, us_order, adiBus:order:create]
module: 订单
entry_path: /adiBus/order
roles: [阿迪业务操作员, 客服]
permissions: [adiBus:order:create]
source_ref:
  - knowledge/rules/business-rules.md#1.1
  - src/pages/adiBus/order/index.vue
owner: 01415465
verified_at: 2026-11-24
expires_at: 2027-05-24
related: [order-flow-approval, order-rule-duplicate]
```

**关键点**：
- `【注意】` 段只能来自后端规则文档，不可能从前端代码得出——这正是合并的价值。
- 前端素材（`src/pages/adiBus/order/index.vue`）只贡献入口与步骤。
- `anchors` 同时包含用户词（下单/新建订单）与代码词（handleCreateOrder/us_order），兼顾召回。

### 5.4 规则卡模板

```yaml
card_id: order-rule-duplicate
type: rule
title: 为什么提示「订单号已存在」？
one_liner: 同一个客户订单号已存在且状态不是「导入」，系统会拒绝重复下单。
body: |
  【规则】同一客户订单号（customerOrderNo）已存在且状态大于「导入」时，拒绝创建。

  【会触发的情况】
  · 重复导入同一批 Excel
  · 客户系统重推了同一单号

  【处理办法】
  1. 先在「下单」页用「客户运单号」查询是否已存在
  2. 若订单在「导入」状态，可继续处理或删除后重建
  3. 若需重新下单，换一个新客户订单号
  4. 确需覆盖，联系管理员处理原订单

  【不受限制】原订单已被删除时，可重新使用同一单号。
anchors: [订单号已存在, 重复下单, customerOrderNo, 客户订单号, 重复订单, IMPORT]
module: 订单
source_ref: [knowledge/rules/business-rules.md#1.1]
owner: 01415465
verified_at: 2026-11-24
```

### 5.5 状态卡模板

```yaml
card_id: order-state-review
type: state
title: 订单「待审批」是什么意思？能修改吗？
one_liner: 待审批表示订单已提交但还没人审，此状态下不能改单，只能等审批或撤回。
body: |
  【含义】订单创建时命中了审批规则，进入审批队列，等待审批人处理。

  【这个状态能做什么】
  · 查看：可以，在订单列表筛「待审批」状态
  · 修改：不可以，需先撤回
  · 取消：可以，仅未取件的单可取消
  · 打印面单：不可以，需审批通过后才能打

  【下一步】
  · 审批通过 → 系统自动向顺丰下单 → 状态转为「已下单」
  · 审批驳回 → 订单终止，运费预算配额释放
  · 超时未审 → 系统按配置的时效阈值自动驳回

  【提醒】审批单次最多通过 1000 单、驳回 200 单。
anchors: [待审批, 审批中, 审批状态, orderStatus, 审批通过, 审批驳回, us_order_review]
module: 订单
source_ref: [knowledge/rules/business-rules.md#1.2, knowledge/business/order.md]
owner: 01415465
verified_at: 2026-11-24
```

### 5.6 故障卡模板

```yaml
card_id: common-trouble-permission
type: trouble
title: 提示「权限不足」怎么办？
one_liner: 说明你的账号没有该操作权限，找所在组织管理员在「权限管理」里开通对应权限点。
body: |
  【报错原文】无操作权限 / 权限不足 / 403

  【原因】账号未被授予该菜单或按钮的权限点。

  【处理步骤】
  1. 记下报错时正在做的操作（如「下单」「导出」）
  2. 找所在组织的管理员，说明需要开通的权限
  3. 管理员在「系统管理 → 角色权限」里为你的角色勾选对应权限
  4. 重新登录生效

  【最快的确认方式】把报错截图发到本群，并说明是在哪个页面点的什么按钮。
anchors: [权限不足, 无权限, 403, 没有权限, 访问被拒绝, permission denied]
module: 通用
source_ref: [src/pages/**/permission.js, knowledge/business/user.md]
owner: 01415465
verified_at: 2026-11-24
```

### 5.7 流程卡模板

```yaml
card_id: order-flow-approval
type: flow
title: 订单审批流程是怎样的？
one_liner: 下单命中审批规则 → 进入待审批 → 审批人通过后系统自动下单，驳回或超时则终止。
body: |
  【触发】下单时按成本类型、订单类型、付款方式、快递类型、货物等维度匹配审批规则，命中则进入「待审批」。

  【流程】
  1. 下单 → 命中规则 → 状态「待审批」
  2. 审批人在「订单审批」页查看并处理
  3. 通过 → 系统向顺丰下单 → 状态「已下单」
     驳回 → 订单终止，释放运费预算
  4. 超时 → 按配置的审批时效自动驳回

  【时效】审批时效可在审批配置里设置；超时自动驳回。
  【限制】单次通过 ≤ 1000 单，单次驳回 ≤ 200 单。
  【审批通过后取件时间已过】标记异常并发企微通知。
anchors: [审批流程, 订单审批, 审批规则, 待审批, 自动驳回, us_order_review_conf]
module: 订单
source_ref: [knowledge/rules/business-rules.md#1.2, knowledge/business/order.md]
owner: 01415465
verified_at: 2026-11-24
```

### 5.8 问答卡模板

用于高频且不适合归入以上卡型的零散事实。

```yaml
card_id: order-faq-volume-field
type: faq
title: 新增报表里为什么没有体积字段？
one_liner: 体积字段需要报表模板支持，当前模板不含体积；可在报表配置里添加或换带体积的模板。
body: |
  【现象】新建报表时字段列表里找不到「体积」。

  【原因】报表可用字段来自所选的报表模板，当前模板未包含体积字段。

  【怎么办】
  1. 检查报表模板，确认是否选了含「体积（立方米）」列的模板
  2. 若模板确实没有，联系管理员在报表配置中补充该字段
  3. 临时需求可先从「下单」页导出的 Excel 里看体积

  【说明】体积在下单页列表是有的（列名「体积（立方米）」），只是报表模板未映射。
anchors: [体积, 体积字段, 新增报表, 报表模板, volume, 立方米]
module: 报表
source_ref: [src/pages/report/**, src/pages/adiBus/order/index.vue]
owner: 01415465
verified_at: 2026-11-24
```

---

## 6. 摄取与切分规范

### 6.1 总体流程

```
来源采集 → 结构化清洗 → 卡片合成 → 校验 → 向量化 → 入库
         ↑                              ↓
         └────────── 人工评审 ◄──────────┘
```

### 6.2 来源与职责

| 来源 | 采集什么 | 产出卡型 | 现有代码 |
|---|---|---|---|
| `knowledge/business/*.md` | 业务目标、核心流程、涉及表 | flow、rule | 已有 342KB，需重切 |
| `knowledge/rules/business-rules.md` | 业务约束、校验规则、状态机 | rule（主力） | 已有 68KB，最有价值 |
| `knowledge/database/tables.md` | 表名、表说明 | glossary（补充） | 已有 54KB |
| `*Enum.java`（406 个） | 枚举 code + desc | state、glossary | 待开发脚本 |
| `*Controller.java`（368 个） | 接口路径、权限点 | task 的 anchors | 待开发脚本 |
| `ErrorCode.java`、校验文案 | 错误码、中文报错 | trouble | 待开发脚本 |
| 前端 `src/pages/**/*.vue`（741 个） | 页面 → 路由 → 按钮 → 表单字段 → 调用接口 | **task 的素材** | 已有 `parser/`，改造输出 |
| **Word 操作手册（docx）** | 业务视角的步骤、字段、限制、截图 | **task、flow、faq（主力）** | 新增 `scripts/import_docx.py`，见 §6.7 |
| `question_records`（148 条） | 真实问题、未命中问题 | faq、待补清单 | 已有数据，从未使用 |
| 人工编写 | 审核、补全、纠错 | 全部 | 新增 |

### 6.3 切分规则（硬性）

| 规则 | 说明 |
|---|---|
| **只在标题处切** | 禁止按字数硬切。现有 `import_from_file` 的 `_split_content(max_chunk_size=3000)` 必须废弃 |
| 中文块上限 500–800 字 | 超出按二级标题继续拆；仍超出则拆分语义为多张卡 |
| 10–20% 重叠 | 相邻块保留首尾重叠，避免语义断裂 |
| 上下文前缀 | 每张卡开头补一句"属于哪个模块、用于解决什么问题"（Contextual Retrieval） |
| 单卡 ≤ 500 字 | 保证召回精度，见 §4.2 |

### 6.4 合成规则

**规则卡 / 流程卡**（纯后端来源，自动化程度高）：

```
business-rules.md 标题树
  └─ "## 一、订单规则"
       └─ "### 1.1 订单创建规则"
            └─ 每个 bullet "**防重复下单**：..."  →  一张 rule 卡
```

- 标题升级为 `title`（须改写为用户问法，批量改写后人工抽检）。
- bullet 原文进 `body`，保留原始数值与阈值。
- `source_ref` 记为 `business-rules.md#1.1`。
- **不做 LLM 润色**，仅做标题改写；正文中的技术词保持原样，由检索视图承载。

**状态卡**（枚举自动化）：

```
// UsRequireOrderStateEnum.java
CREATED(0, "已创建"), WAIT_ALLOCATE(1, "待分配"), ...
```

- 每个枚举值 → 一张 state 卡（`title`: "「待分配」是什么意思？"）。
- `anchors` 自动收 code、常量名、desc。
- `body` 的"能做什么/下一步"需人工补充——自动生成只能填含义。

**故障卡**（错误码 + 校验文案）：

- 扫 `throw new BizException("...")`、`ErrorCode` 常量，收集中文报错。
- 每条报错 → 一张 trouble 卡骨架，`title` 用报错原文，`anchors` 含错误码。
- 原因与处理办法由人工补全。

**任务卡**（前后端合并，半自动）：

```
前端 parser 输出：               后端反查：
  页面 → 路由 /adiBus/order       入口按钮的 @click → handleCreateOrder
  按钮「下单」→ handleCreateOrder    → 对应 Controller 接口
  表单字段列表                       → 该接口 service 里的校验规则
                                   → business-rules.md 对应章节
        ↓                              ↓
              合成一张 task 卡（入口+步骤来自前端，限制来自后端）
```

- 现有 `parser/builder.py` 的"按钮→方法→API"链路逻辑保留，但**输出物改为素材**（JSON），不再直接生成 KnowledgeItem。
- 任务卡的 `【注意】` 段若后端未找到对应规则，留空并标记"待补"，不得编造。

### 6.5 必须废除的现有做法

| 现有做法 | 位置 | 为什么废除 |
|---|---|---|
| 按 3000 字硬切块 | `knowledge_service._split_content` | 产生 `Business Domain (第2部分)` 无标题碎片 |
| 用 LLM"丰富"页面描述 | `knowledge_service._enrich_items` | 纯润色产出空话，无事实增量，是"答得浅"的成因 |
| 一个页面一条知识 | `builder._build_page_document` | 界面清单不是业务知识 |
| 技术名直接进正文 | `builder._describe_button_action` | 违反双视图规范 |
| 阈值调参救召回 | `config.RAG_THRESHOLD_*` | 掩盖知识质量问题（见 §1.4） |

### 6.6 旧知识的处置

现有 309 条（151 page + 63 workflow + 95 manual）**直接删除后重做并不合适**——里面包含
前端解析出的入口信息，仍有复用价值。建议按以下方式处置：

| 类型 | 处置 | 理由 |
|---|---|---|
| page（151 条） | **降级为素材**，不作为答案来源 | 按钮清单不是业务知识，但入口信息可复用于 task 卡 |
| workflow（63 条） | **降级为素材** | "按钮→方法→API"链路可作为 task 卡的前端素材 |
| manual（95 条） | **丢弃后重切** | 硬切块丢失标题，无法修复，直接按 §6.4 重新生成 |

操作方式：

1. 构建新卡片库时，把 page/workflow 条目导出为 `data/_legacy_materials.json`，
   供任务卡合成时查询"某页面有哪些按钮、调用了什么接口"。
2. 从向量库中移除全部 309 条旧记录，避免与新卡片混淆召回。
3. 保留 SQLite 中的历史记录（不删表），便于对比与回溯。

> 关键原则：**旧知识可以当素材，不能当答案。**

### 6.7 操作手册（Word 文档）的利用

业务侧提供的系统操作手册 docx 是**最高价值来源之一**——它本身就是按"业务人员视角"写的，
与目标读者一致，可直接产出 `task` 卡与 `flow` 卡。

**入口脚本**：`scripts/import_docx.py`（基于 pandoc）

```bash
# 预览（强烈建议先预览）
uv run scripts/import_docx.py --file ./操作手册.docx --dry-run

# 批量转换
uv run scripts/import_docx.py --dir ./manuals --output data/docs_md

# 保留截图（部分手册的关键步骤靠图说明）
uv run scripts/import_docx.py --dir ./manuals --keep-media
```

**处理链路**：

```
docx ──pandoc──> Markdown ──清洗──> 分节 ──> 手册节（素材）
                    │                │
                    ├ 去页码/页眉     ├ 按标题层级切
                    ├ 去目录/修订记录 ├ 超 800 字继续细分
                    ├ 去版权/封面     ├ 按段落兜底
                    └ 压缩表格空格    └ 合并过小碎片
```

**与知识卡的映射**：

| 手册内容形态 | 产出卡型 | 处理方式 |
|---|---|---|
| "如何 XX"类章节（含步骤） | `task` | 章节标题 → `title`；步骤 → `body`；入口 → `entry_path` |
| "XX 流程"类章节 | `flow` | 步骤 + 角色 + 时效 → `body` |
| "字段说明"表格 | 合并进 `task` 的 `body` 或 `glossary` | 保留表格，但需压缩对齐空格 |
| "常见问题/FAQ"章节 | `faq` | 逐条拆卡 |
| "注意事项/限制"段落 | `rule` | 提炼为规则卡，`source_ref` 指向手册章节 |
| 截图 | 不作为卡内容 | 提取到 `media/`，在卡中记录路径，暂不参与检索 |

**质量要求**：

1. **必须人工过一遍**。手册常有版本滞后，与实际系统不符的段落要剔除或标注。
2. **手册的"限制/注意事项"段最值钱**——这正是当前知识库缺失、导致"答得浅"的部分。
3. **截图暂不进入 RAG**。当前本地 9B 模型不便做多模态；如后续需要，单独建图片索引。
4. **`source_ref` 记录为 `手册名#章节标题`**，便于追溯与失效联动。

**已验证效果**（用 `企业服务平台接入技术规范` 实测）：

| 指标 | 结果 |
|---|---|
| 转换正确性 | 标题层级、表格结构完整保留 |
| 体积优化 | 614K → 320K 字（pipe 表格 + 空白压缩，-48%） |
| 分节 | 原始 57 节 → 细分后 487 节，全部 ≤ 841 字，平均 650 字 |
| 噪声清理 | 目录、封面、版权页自动丢弃 |

> 注意：技术类手册（如接口规范）产出的大多是 `task` 的锚点素材，而非直接可用的业务卡。
> 业务操作手册（面向操作员）才直接产出 `task` / `flow` 卡。

**手册与代码的关系**：

```
手册（业务视角，含限制）  ←→  代码（入口、最新字段）  ←→  日志（真实问法）
        ↓                          ↓                        ↓
     步骤、注意事项            页面路径、按钮名            高频问题、别名
        └──────────────────────────┴────────────────────────┘
                                   ↓
                            合成完整 task 卡
```

三者冲突时以**代码为准**（手册会滞后），并在卡中标注"手册已过时，以系统实际为准"。

### 6.8 Word 手册获取渠道（钉钉文档）

手册存在钉钉文档时，有两条获取路径：

| 路径 | 适用 | 说明 |
|---|---|---|
| **dws CLI 直接下载** | 已知 nodeId | `dws drive download --node <id> --output x.docx` |
| **浏览器登录后取 nodeId** | 无列目录权限时 | 用工作区浏览器登录，点开文档，从 URL 取 `i/nodes/<nodeId>` |

**关键坑：`dws drive list` 与 `dws drive download` 权限不同**

- 列目录（`list`）需要**知识库成员身份**，无权限时返回 `forbidden.accessDenied`
- 按 nodeId 下载（`download`）只需**文档自身可见权限**，通常能成功

实测：某知识库 `list` 报"您没有权限访问该知识库"，但用文档 nodeId `download` 成功取回 50MB 主手册。**所以拿不到目录列表时，不要放弃——逐个取 nodeId 仍可下载。**

获取 nodeId 的批量做法：

```bash
# 1. 浏览器登录钉钉文档（工作区浏览器，独立于 CLI 登录态）
# 2. 逐个点开左侧目录中的文档
# 3. 从地址栏读取：https://sf-alidocs.dingtalk.com/i/nodes/<nodeId>
# 4. 用 dws download 批量拉取
dws drive download --node <nodeId> --output "/tmp/manuals/<名称>.docx"
```

**注意**：
- dws 的登录态与浏览器登录态**互相独立**，浏览器登录不会让 CLI 获得权限
- 超大手册（50MB+，含大量截图）pandoc 转换可能超时，建议用 `--keep-media=false` 或拆分处理

**实测产出**（顺店通-面客资料库，26 个文档）：

| 文档 | 大小 | 用途 |
|---|---|---|
| 顺店通操作手册-1202（含供应链服务）.docx | 50MB | 全量操作指南，截图多 |
| 顺店通常见问题集-客服.docx | 1.6MB | **24 条真实客服问答，最高价值** |
| 顺店通企业微信授权操作指引V1.0.docx | 1.7MB | 企微授权流程 |
| 顺店通-同城急送服务操作指引.docx | 14MB | 同城业务操作 |

### 6.9 卡片验收标准（实测基线）

用 `scripts/eval_cards.py` 验证，判定标准：

| 指标 | 合格线 | 实测（19 张卡 / 27 个问题） |
|---|---|---|
| 本域问题命中率 | 100% | **19/19** |
| 预期卡片正确 | 100% | **19/19** |
| 跨域假阳性 | ≤ 1 | **1/10**（且为真实缺口） |

### 检索排序的八条防误召回规则（实测有效，必须实现）

关键词/混合检索在真实业务语料上会产生大量假阳性。以下八条按**实现顺序**排列，
每条都对应一类实测踩过的坑：

| # | 规则 | 解决的问题 | 实现要点 |
|---|---|---|---|
| 1 | **泛化词不给分** | "怎么下单"误命中所有含"下单"的卡 | 维护 `DOMAIN_GENERIC_TOKENS`（下单/系统/配置/批量…），这些词单独命中不计分 |
| 2 | **中文 n-gram 碎片过滤** | "怎么批量导出"产生 `么批`/`么批量导` 等跨词边界碎片，误匹配卡片正文 | 过滤含"么/样"的 token |
| 3 | **卡型意图一致性** | 非排障问题命中报错卡 | 问题无"提示/报错/失败"时，trouble 卡降权 75% |
| 4 | **IDF 自动降权** | "同城急送"在多张卡里都出现，互相抢分 | 按文档频率计算 IDF，独有词权重高 |
| 5 | **业务域隔离** | 问订单却召回测评/账号卡 | 定义 `DOMAIN_KEYWORDS`，问题与卡片域无交集时降权 85% |
| 6 | **反向动作排除** | 问"导出"召回讲"导入"的卡 | 导入/导出、新增/删除、启用/禁用 互为反向，交叉命中降权 |
| 7 | **跨字段去重计分** | "同城急送"在 one_liner+title+anchors 各计一次分，淹没真正有区分度的词 | 同一 token 跨字段只按最高权重计一次 |
| 8 | **标题命中加权** | 两张卡内容相近时排序随机 | title 命中按覆盖率额外加权（最高 +60%），标题是最精确的语义标签 |

**阈值标定**：21 张卡实测，本域问题得分均 > 10，跨域噪声多在 < 2，
故定 `threshold=3.0`。**卡片量增加后需重新标定**（分数随卡片数上浮）。

**实测效果**：
- 规则 5（域隔离）效果最大，假阳性从 5 降到 1
- 规则 7+8（去重计分 + 标���加权）解决了"内容相近的卡抢同一问题"的排序不稳定
- 规则 2（碎片过滤）最容易被忽略，但影响显著

> 这八条应同步实现在正式检索器 `src/rag/retriever.py` 中，而非仅用于评估脚本。

**卡片写作的隐含约束**（由规则 7、8 反推）：
- **flow 卡不要重复下游卡的细节**——只写"有哪几步、细节见哪张卡"，把具体字段留给 rule 卡。
  否则两张卡内容重叠，检索时互相抢分。
- **title 必须精确覆盖该卡唯一回答的那个问题**，因为它是排序的决定性信号。

### 6.9.1 「配置值不可查」的边界设计（实测结论）

有一类问题知识库**永远无法正确回答**：用户问"我们组织配了哪些成本类型"。
答案是随组织、随时间变化的实时数据，写进知识库必然过期。

**实测数据**（qwen3.5:9b + 3 张配置卡）：

| 测试问题 | 是否编造 | 模型回答 |
|---|---|---|
| 我们组织配了哪些成本类型？ | 否 | "以实际显示为准，我不能替你查" |
| 我这边有哪些付款方式可以选？ | 否 | "系统默认支持寄付、到付、月结；具体可选值……以实际显示为准" |
| 我们公司配了几个成本类型？ | 否 | "这个问题我暂时没有资料……不能替你查具体的配置值" |

**3/3 未编造。** 关键机制是卡片正文里的固定边界话术：

> **以下单页实际显示为准，我不能替你查**

外加系统提示词的约束：

> 如果知识库明确说了"以下单页实际显示为准，我不能替你查"，
> 你必须原样转达这个边界，绝不能编造具体的配置值、下拉选项、数量

**必须同时具备三个条件**，缺一不可：
1. 卡片正文里有边界话术（给模型一个合法的"拒绝依据"）
2. 系统提示词要求转达这个边界（而不是让模型自行发挥）
3. 温度设为 0.1（降低随机性）

**配套要求：配置类卡片一律带边界话术**

凡是"选项值随组织变化"的卡（成本类型、付款方式、计价类型等），
正文末尾必须加边界说明。否则模型会拿训练数据里的常见值来编造。

**一个已知的检索局限**：

不同业务的同类字段（顺店通同城急送的成本类型 vs 订单的成本类型）
在不加业务限定词时（"配了几个成本类型"）会互相串。
但只要用户带上业务词（"同城急送成本类型" / "订单成本类型"），两域完全分得开（实测）。
考虑到这类无限定问法本身就该被边界话术兜住，**不额外做域隔离**，避免误伤。

### 6.10 目录组织

```
data/cards/                       # 卡片源文件（YAML，可版本控制）
├── order/
│   ├── glossary/
│   ├── task/
│   ├── rule/
│   ├── state/
│   ├── trouble/
│   └── flow/
├── waybill/
├── product/
└── common/
    ├── trouble/
    └── faq/
```

- 卡片以 YAML 存于仓库，便于 code review、diff、回滚。
- 构建脚本读取 YAML → 校验 → 向量化 → 入库。
- 线上「点踩/未命中」生成的草稿卡也走同一目录（`data/cards/_draft/`），人工评审后移入正式目录。

---

## 7. 存储与检索链路

### 7.1 链路总览

```html
<div style="font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;max-width:780px;background:#fbfbfd;border:1px solid #e3e3ea;border-radius:12px;padding:20px 22px;color:#1b1b22;">
  <div style="font-weight:700;font-size:15px;margin-bottom:14px;">新检索链路</div>
  <div style="display:flex;flex-direction:column;gap:8px;">
    <div style="background:#fff;border:1px solid #dcdce6;border-left:4px solid #6b7cff;border-radius:8px;padding:10px 12px;">
      <b>① 意图路由</b>　<span style="color:#555">寒暄 / 查列表 / 怎么做 / 为什么不行 / 报错 / 流程 → 走不同卡型；寒暄本地直回，不进 RAG</span>
    </div>
    <div style="background:#fff;border:1px solid #dcdce6;border-left:4px solid #6b7cff;border-radius:8px;padding:10px 12px;">
      <b>② 术语归一</b>　<span style="color:#555">读 glossary 卡的 anchors 倒排表，把「POD/体积/加急」扩成标准词 + 同义词 + 枚举值</span>
    </div>
    <div style="background:#fff;border:1px solid #dcdce6;border-left:4px solid #6b7cff;border-radius:8px;padding:10px 12px;">
      <b>③ 多路召回</b>　<span style="color:#555">语义（title+one_liner）+ BM25（anchors）+ 结构过滤（module/roles）</span>
    </div>
    <div style="background:#fff;border:1px solid #dcdce6;border-left:4px solid #6b7cff;border-radius:8px;padding:10px 12px;">
      <b>④ Rerank 取 Top3</b>　<span style="color:#555">卡片短，3 张卡 ≈ 600 字，9B 模型不会撑爆</span>
    </div>
    <div style="background:#fff;border:1px solid #dcdce6;border-left:4px solid #46b47a;border-radius:8px;padding:10px 12px;">
      <b>⑤ 受约束生成</b>　<span style="color:#555">以 one_liner 开题，附步骤/限制；剔除代码名；标明来源卡</span>
    </div>
  </div>
</div>
```

### 7.2 术语归一（词汇鸿沟）

**问题**：用户说"POD""加急""体积""卡住了"，系统里叫签收单、isUrgent、体积字段、某状态码。现有 n-gram + 停用词方案无法跨越这个鸿沟。

**方案**：利用 glossary 卡与所有卡的 `anchors` 构建同义词倒排表。

```python
# 构建期：从所有卡片的 anchors 建立 alias → card_id 映射
# 查询期：先扩写问题，再检索

ALIAS_EXPANSION = {
    "POD":    ["签收单", "运单签收", "回单"],
    "加急":   ["加急标识", "isUrgent", "「是否加急」"],
    "体积":   ["体积字段", "volume", "「体积（立方米）」"],
    "卡住了": ["待审批", "审批中", "长时间未更新"],
}

def expand_query(q: str) -> tuple[str, list[str]]:
    """返回 (扩写后文本, 命中的卡片ID列表)"""
    extra_terms, hit_cards = [], []
    for alias, expansion in ALIAS_EXPANSION.items():
        if alias in q:
            extra_terms.extend(expansion)
    return q + " " + " ".join(extra_terms), hit_cards
```

扩写后的文本同时用于向量检索与 BM25，**不展示给用户**。

### 7.3 双视图分离（关键）

```python
_CODE_PATTERNS = [
    r"\bus_[a-z_]+\b",           # 表名
    r"\b[a-z]+[A-Z]\w*\b",       # 驼峰方法名/字段名
    r"\b[A-Z][A-Z0-9_]{3,}\b",   # 枚举常量
    r"/api/[a-zA-Z0-9/_-]+",     # 接口路径
]

def to_presentation(card: dict) -> str:
    """生成给用户看的文本：剔除代码名、保留业务语言"""
    text = f"{card['one_liner']}\n\n{card['body']}"
    text = _strip_code_refs(text)      # 删代码名，或替换为业务名
    return text
```

**规则**：
- `title`、`one_liner` 在入库前就禁止含代码名（§4.3 校验）。
- `body` 可含代码名，但**合成 prompt 时剔除**；代码信息只由 `anchors` 承担召回职责。
- 例外：错误码、报错原文可保留，因为用户会在报错里看到。

### 7.4 检索实现要点

| 环节 | 做法 | 依据 |
|---|---|---|
| 向量化对象 | `title + one_liner + body 前 200 字` | one_liner 是核心语义，需高权重 |
| 混合检索 | 向量 + BM25/关键词，权重 0.7 / 0.3 | 阿里云生产 RAG 实测 |
| Rerank | 引入 cross-encoder（如 bge-reranker）重排 Top 10 → Top 3 | Anthropic：rerank 再降失败率 18 个百分点 |
| 召回数量 | Top 10 召回，rerank 后取 3 | Anthropic：Top-20 > Top-5 |
| 阈值 | 仅作兜底安全线（如 0.4），不再作为主要调参手段 | 见 §1.4 |
| 结构过滤 | 按 `module` / `roles` 预过滤 | 避免跨域误召回 |

### 7.5 生成约束

系统提示词需强化（现有 `src/llm/prompts/qa.py` 需改写）：

```
1. 第一句必须是卡片里的一句话答案，不改写、不加铺垫
2. 只讲命中的那一张卡，不要罗列多张卡的不同场景
3. 有【注意/限制】段必须完整转述，不能省略
4. 禁止出现表名、方法名、枚举常量；改用业务名称
5. 页面路径和按钮名用「」标注
6. 卡片里没有的信息不要补充；没有命中就说"这个问题我暂时没有资料"
```

### 7.6 需要改造的现有模块

| 模块 | 改造内容 |
|---|---|
| `src/domain/models/knowledge.py` | `KnowledgeItem` 扩展为卡片 schema（§4.4） |
| `src/domain/enums.py` | 新增 `CardType`（七类），`KnowledgeType` 保留兼容期别名 |
| `src/rag/retriever.py` | 加入术语归一（§7.2）、模块过滤、rerank 钩子 |
| `src/rag/context.py` | 双视图分离（§7.3），向量化对象调整 |
| `src/services/knowledge_service.py` | 删除 `_split_content` 硬切、`_enrich_items` 润色；新增 YAML 卡片加载与校验 |
| `src/parser/builder.py` | 输出物改为素材 JSON，不直接产 KnowledgeItem |
| `src/llm/prompts/qa.py` | 按 §7.5 重写系统提示词 |
| `scripts/build_knowledge.py` | 改为读取 `data/cards/**/*.yaml` 构建 |

---

## 8. 治理闭环与指标

### 8.1 三条闭环

现有 148 条日志躺在库里从未回流，这是最大浪费。必须建三条回路：

| 回路 | 触发 | 处理 | 周期 |
|---|---|---|---|
| **① 未命中 → 待补卡** | `status=no_match` 或低置信度 | 按语义聚类 → 生成草稿卡 → 人工审核入库 | 每周 |
| **② 点踩 → 复审** | 用户点 👎 | 进复审队列 → 判断是卡片错还是检索错 → 修卡或补卡 | 每周 |
| **③ 规则变更 → 失效** | 后端规则文档更新 | 按 `source_ref` 反查受影响卡片 → 标记待验证 → 复核人确认 | 发布后 |

### 8.2 回路①：未命中处理

```python
# 每周执行
no_match = query("SELECT question, COUNT(*) n FROM question_records "
                 "WHERE status='no_match' GROUP BY question ORDER BY n DESC")

# 语义聚类 → 相似问题归并
clusters = cluster_by_embedding(no_match)

# 每个簇生成一张草稿卡（骨架，不含编造内容）
for cluster in clusters:
    draft = {
        "card_id": f"draft-{slugify(cluster.representative)}",
        "title": cluster.representative,
        "one_liner": "【待补】",          # 留空，人工填写
        "body": "【待补】",
        "anchors": cluster.keywords,
        "source_ref": [],
        "owner": None,                    # 人工指定
    }
    write_yaml(f"data/cards/_draft/{draft['card_id']}.yaml", draft)
```

**要点**：草稿卡只提供"用户这么问了、这类问题无答案"的信号，**内容必须人工补**，防止模型编造。

### 8.3 回路②：点踩机制

钉钉消息末尾追加交互：

```
（这条回答有帮助吗？👍 / 👎）
```

- 点 👎 弹出选项：`答非所问 / 内容错误 / 太笼统 / 没解决我的问题`。
- 记录到 `feedback` 表（新增）：`card_ids`、`reason`、`question`、`created_at`。
- 每周按卡片聚合点踩数，Top 卡片进复审。

### 8.4 回路③：卡片失效

- 每张卡有 `owner` + `expires_at`。
- 到期未验证 → 状态变 `unverified` → 检索时降权或排除（可配置）。
- 后端 `knowledge/` 目录有 git 变更时，按 `source_ref` 匹配受影响卡片，自动标记"待验证"并通知 owner。
- 长期（如 180 天）未被验证且未被使用的卡 → 自动归档（Guru 做法），不删除。

### 8.5 指标（对齐 Intercom 框架）

| 指标 | 定义 | 目标 | 说明 |
|---|---|---|---|
| **解决率** | 未点踩且未被追问的会话 / 总会话 | ≥ 85% | 核心指标，替代"浏览量" |
| **未命中率** | `no_match` / 总提问 | ≤ 10% | 反映覆盖度 |
| **点踩率** | 点踩数 / 有交互的回答数 | ≤ 5% | 反映准确度 |
| **Top10 未覆盖问题** | 未命中问题按频次排序 | 每周清零 | 驱动补卡 |
| **过期卡数** | `expires_at < today` 且未复核 | 0 | 反映治理健康度 |
| **检索命中卡片数** | 平均召回 Top3 中的有效卡数 | ≥ 2 | 反映检索质量 |

> 现有 `analytics_service.py` 已有分类统计，需扩展上述指标。

### 8.6 评审与发布流程

```
草稿卡(_draft) → 内容评审(owner 指定) → 校验脚本通过 → 移入正式目录
                                                    → 构建向量化 → 灰度(仅内部群)
                                                    → 观察 1 周指标 → 全量
```

- 所有卡片变更走 git，可 review、可回滚。
- 卡片修改需 owner 确认，非 owner 修改自动标记 `unverified`（Guru 规则）。

---

## 9. 迁移与落地路线

### 9.1 阶段划分

| 阶段 | 内容 | 产出 | 验证方式 | 依赖 |
|---|---|---|---|---|
| **0 冻结** | 现有 309 条降级为"素材"，不再直接答 | 基线记录 | — | — |
| **1 标杆** | 术语卡 + 20 张标杆卡（下单/审批/POD/体积/权限/合单） | 可评审卡片集 | 用 12 个真实问题回归 | — |
| **2 规则** | `business-rules.md` 按标题重切 → rule + flow 卡 | 约 100–150 张 | 规则类问题回归 | 阶段 1 schema 定稿 |
| **3 枚举** | 枚举 + ErrorCode 脚本 → state + trouble 卡 | 约 100 张 | 报错/状态类问题回归 | 阶段 1 |
| **4 任务** | 前端素材 + 后端规则合并 → task 卡 | 约 60–80 张 | 操作类问题回归 | 阶段 2、3 |
| **5 闭环** | 日志回流 + 点踩 + owner 有效期 | 运营机制 | 周度复盘 | 阶段 1–4 |

### 9.2 关键建议：阶段 1 后就停下评审

**不要先铺量。** 20 张卡就能用现有 12 个真实问题跑一轮 A/B：

```
对照组：现有 309 条知识库
实验组：20 张标杆卡 + 术语归一
测试集：怎么下单 / 订单怎么创建 / 订单审批流程是什么 / 怎么批量导出POD
       阿迪订单页面有哪些操作按钮 / 怎么查询所有订单 / 库存怎么管理
       新增报表里没看到体积 / 为什么权限被拒绝 / 运单是什么
判据：解决率、回答是否含可执行动作、是否出现代码名
```

确认"卡片化 + 术语归一"确实解决"答得浅"，再铺量。否则可能批量生成上千张卡，方向依然错。

### 9.3 卡片数量控制

| 现象 | 风险 | 对策 |
|---|---|---|
| 406 枚举全展开 | 状态卡爆炸 | 只做真实问题涉及的；低频状态归并 |
| 368 Controller 全展开 | 任务卡爆炸 | 按 Top 50 问题反向选卡 |
| 前端 741 页面全展开 | 素材冗余 | 只取 Top 50 问题涉及的页面 |

**排序原则**：按 `question_records` 的真实频次选卡，而不是按代码规模选卡。

### 9.4 风险与约束

| 风险 | 说明 | 缓解 |
|---|---|---|
| **9B 模型跨卡推理弱** | "我这单为什么被驳回到现在没退款"需串联多卡 | 简单卡直答；复杂问题降级转人工或换更强模型 |
| **卡片维护成本** | 数百张卡需持续维护 | owner 制 + 自动失效 + 只维护 Top 卡 |
| **前后端合并难自动化** | 任务卡的"限制"段需语义匹配 | 阶段 4 半自动 + 人工兜底；未匹配留"待补" |
| **技术名泄漏** | 生成时仍可能带出表名 | §7.3 双视图分离 + 后置正则清洗 |
| **规则时效** | 后端规则频繁变更（如箱号唯一性 2026-09 调整） | `expires_at` + git 变更联动 |

### 9.5 验收标准

阶段 1 完成时，需同时满足：

- [ ] 20 张卡全部通过 §4.3 校验（无缺字段、无代码名泄漏）
- [ ] 12 个真实问题中，至少 10 个能命中正确卡片
- [ ] 回答中含明确可执行动作（页面路径 + 按钮名）
- [ ] 回答中不出现表名、方法名、枚举常量
- [ ] 术语归一使 "POD / 体积 / 加急" 类问题命中率明显提升

---

## 附录 A：现状数据摘要

### A.1 真实问题样本（去重后 12 个）

```
怎么下单 / 订单怎么创建 / 订单审批流程是什么 / 怎么批量导出POD
阿迪订单页面有哪些操作按钮 / 怎么查询所有订单 / 库存怎么管理
新增报表里没看到体积 / 为什么权限被拒绝 / 页面样式乱了 / 运单是什么 / 数据库有哪些表
```

其中 `数据库有哪些表`、`页面样式乱了` 属开发视角问题，业务人员不应提；
如仍出现，说明当前回答暴露了技术细节，反而引导用户问技术问题——是双视图缺失的副作用。

### A.2 同一问题结果不一致的证据

```
如何创建订单?  2026-07-09  confidence=1.0  success
如何创建订单?  2026-11-23  confidence=0.0  no_match
怎么下单       2026-11-23 17:11  no_match
怎么下单       2026-11-23 17:15  no_match
怎么下单       2026-11-23 17:59  confidence=0.85  success
```

同一问题在不同时间点结果从 success 变 no_match 再变 success，知识未变 → 阈值/文档调整所致。

### A.3 知识条目样本（现有，作为反例）

```text
### 收件地址管理页面操作指南 [page]
【页面说明】收件地址管理
访问路径: /address/recAddress
来源文件: /Users/xie_cd/workproject/eps-store-core-fenew/src/pages/address/recAddress.vue

【可用操作】
  - 「查询」 —— 触发 handleSelectButton
  - 「重置」 —— 触发 handleReset
  ...
```

问题：
1. 无任何业务判断（"什么情况下不能导入"）
2. `handleSelectButton` 等技术名直接进正文
3. 暴露了本地绝对路径
4. 与业务人员真实问题无关

### A.4 有价值但被切碎的来源

`knowledge/rules/business-rules.md`（68KB）包含大量可直接用的业务规则，例如：

```text
### 1.1 订单创建规则
- **防重复下单**：同一客户订单号若已存在且状态大于 IMPORT，则拒绝创建
- **取件时间约束**：预约取件时间必须在当前时间至少 2 小时之后，否则拒绝创建
```

这类内容正是 `rule` / `task` 卡的原料，但当前按 3000 字硬切后标题丢失，
无法与具体操作建立关联。

### A.5 现状知识库规模

| 项 | 数值 |
|---|---|
| knowledge_items 总数 | 309 |
| page / workflow / manual | 151 / 63 / 95 |
| 文档平均长度 | 1082 字 |
| 文档最长 | 3024 字 |
| 后端规则文档总量 | 342KB |
| 后端枚举类 | 406 |
| 后端 Controller | 368 |
| 前端页面 | 741 |

---

## 附录 B：变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v2.0-draft | 2026-11-24 | 初始版本：七类卡型、双视图、术语归一、治理闭环、落地路线 |
