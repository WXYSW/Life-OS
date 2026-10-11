# 学习闭环 v2

生效2026-10-11，用户授权按助手设计实施。目标→能力/任务→知识→学习动作→实际证据→下次安排。生活记录与周期报告继续沿用workflow。

## 数据与依据

- goals/initial.json：目标状态、用户重要性high/medium/low或null、具体日期、完成标准、差距、时间预算及证据。未知不填零；月级期限不能当精确考试日。重要性须来自用户，差距须有测评依据。
- knowledge/capabilities.json：真实任务示例、所需能力与知识ID；初始结构仅部分覆盖，不是完整考试大纲。
- knowledge/items/：goal_links按目标分别记贡献high/medium/low及理由、依据；capability_ids、prerequisite_ids、内容难度、时长估计。前置关系只用于已核验依赖，缺失引用和循环报错。无前置边仅表示尚未建模。
- mastery分别保存recall/explain/apply的unknown/gap/supported/demonstrated、依据及时间；延迟和迁移证据单独记录。不能从一次答对推导长期掌握，也不能从两道题推算目标总差距。
- queue负责调度状态，items负责知识内容和证据；session保留实际派题记录。旧priority保留，low仍默认不新派，core不再自动优先于目标贡献。

## 日常唯一入口

```sh
python scripts/learning.py --day 2026-10-11
python scripts/learning.py --day 2026-10-12 --review-limit 10 --new-limit 0 --minutes 30
python scripts/learning.py --day 2026-10-12 --focus-goal G-CS-ABROAD --energy low
```

review.py select与questions.plan保留兼容旧记录和测试，日常不用它们代替v2决策。learning.py从目标、queue、知识详情、backlog及当日session组装输入，不修改文件。

## 可解释决策

1. 先列出待评价回答，由助手评价后重新规划；这些不占出题额度。知识未经核验、暂停、参考归档不自动选入。已有开放题不能重复派；题目ID转换为知识ID后做同日去重。
2. 未完成题优先续接，使用原题ID；延期未到恢复日、暂停题不派。旧题占对应新题/复习额度。用户明确focus时只选择该目标的映射知识，其余题继续保留。
3. 新动作仅选择active目标下已映射的知识；用户指定focus可临时选择长期目标，不永久改变目标状态。缺少目标映射的候选先由助手核验和补映射，不猜考试贡献。
4. 活跃目标临时份额：用户重要性high/medium/low对应3/2/1，未知中性1；有精确日期且30天内到期加1，有证据的大差距加1。这是可解释的初始规则，非学习科学定律，不自动学习权重。按本批已分配的预计分钟/份额轮流选目标，避免只选最高权重目标。小批次不保证每个目标都有内容；跨批长期份额由周复盘检查。
5. 同一目标内：续题优先；贡献高优先；作为其他知识前置的基础优先；已有薄弱证据优先；然后到期日、估计成本、稳定ID。前置知识尚无独立应用证据时，新的后续动作阻塞并列出原因；原待答题仍允许继续以收集证据。
6. pending→diagnose；到期且需提示/补学→relearn；到期但缺少应用证据→apply；已有应用证据→delayed_review。续题→continue_question。不会自动新派未到期复习。用户主动要提前巩固时由助手记录practice，不推进阶梯。
7. 数量由用户决定；无固定每日上限，默认新题2、复习5是批量。minutes为本批时间预算，只纳入能装入预算的动作。时长未知使用临时10分钟，低精力5分钟，输出明确标记估计。低精力时由助手缩小任务、减少步骤，不能把5分钟当已测耗时。

每项输出动作、目标、理由及成本。输出只是候选；助手仍须拟题、核验答案与评价标准，原子保存backlog+session+current后才能报告已派题。无法适配时间则少给或不给，不凑数。讲解内容本身不作为独立测验证据。

## 执行与证据

- diagnose：用少量题区分缺口；relearn：简短讲解/例题后针对练习；apply：换情境应用；delayed_review：间隔后的独立验证。需要额外练习时记录practice。
- 事件字段见templates/learning-event.json，必须说明dimension、outcome、是否独立、是否延迟、是否迁移、评价依据及是否符合调度条件。delayed与transfer由实际情境判断，不能根据动作名称自动认定。
- learning.record_evidence是纯函数，输入已可评估事件，返回知识状态。重复事件ID相同内容不重复记录；同ID变内容拒绝。迟到事件需按时间重放；评价更正追加revision并按有效历史重算。
- 助手同时保存真实attempt、知识状态、queue、backlog及current。部分回答继续走questions.change；完成后才给整题评价。公开授权沿用workflow；知识回答无需逐次询问。
- 采用ladder-v2：初学、短期巩固、长期保持三个阶段。基础间隔1、3、7、14、30天，稳定长期证据可延长到60、90天。独立正确区分费力/稳定/迁移；费力不升阶，提示或遗忘/概念缺口进入1→3→7天巩固，不直接恢复旧长间隔。有明确依据的局部失误适度缩短；未知错误按巩固处理。实际间隔不足不升阶；近期多次失败暂缓延长。30天及以上须两次足间隔独立通过才延长。跳过不变；讲解/即时练习不推进，同日同知识只改变调度一次。具体判断与参数见schedule-policy.md。
- record_evidence将quality（effortful/stable/transfer）、error_type（unknown/forgetting/conceptual/slip）和可选target_date传给grade。字段缺省采用stable/unknown，助手须在有证据时填写，不能从耗时单独推断。
- 当前只更新明确被测维度；跳过不降低掌握。delayed_evidence_id和transfer_evidence_id是历史证据索引，最近状态仍须结合outcome和日期判断。前置基础是否需重新诊断由证据判断。

## 效果检查与探索

周复盘查看延迟独立表现、迁移表现、重复错误、真实目标任务和实际耗时；注明样本数及缺失，不用题量代替能力。每周在用户愿意且预算允许时安排一个尚不清楚的能力诊断，避免只围绕已知错题。探索、知识核验、讲解与任务设计目前由助手执行，未实现自动探索抽样或权重学习。

目标time_budget_minutes目前用于助手跨批/周计划，不是CLI本批硬预算；CLI硬预算使用--minutes。迁移中没有虚构成本、用户重要性或测验。新增模型字段缺省未知，155个待核验候选保持原状态。现有回答、日期和来源保持可追溯。

## 暂时归档知识点

“未测试”描述掌握证据，“暂时归档”描述当前是否安排学习，两者独立。暂时归档使用status=paused、archive.kind=temporary；archive.previous_status保留原needs_validation/pending/review等状态，原due、stage、作答证据和来源保留。归档条目单独统计展示，不混入当前待测试/到期队列；归档期间不自动派题、续题、不占额度、不累计欠题。对应开放题暂停，保留原ID、回答片段及恢复前状态。

恢复时按archive.previous_status恢复知识，题目按其archive.previous_status和previous_resume_on恢复，并追加恢复事件；清除当前archive标记但保留归档索引/修订历史。原未核验内容仍须核验，原未测试内容仍待诊断；原复习内容保留日期，若已过期，只安排一次当前独立验证，不批量补做。明确说“恢复C语言/Shell”才恢复；仅指定目标不自动解除归档。暂停/归档不代表不会或学会。

本次（2026-10-11）按来源目录将C语言与Shell的73条知识暂时归档，包括7条已有诊断的C知识和4个训练入口；其他主题保持现有安排。清单见knowledge/archives/2026-10-11-c-shell.json。
