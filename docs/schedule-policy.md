# 日期调度 ladder-v2

更新2026-10-11。规则是可解释的工程初值，基于真实作答逐步检查效果，不宣称个体最优。与lifecycle-v1选题排序分开：目标重要性不直接缩短记忆间隔。

## 输入及职责

`review.grade(item, outcome, day, quality='stable', error_type='unknown', target_date=None)`返回新调度状态，不修改输入或保存文件。outcome仍为correct/hinted/wrong/skip；助手先依据答案评价，再调用。quality为effortful/stable/transfer，error_type为unknown/forgetting/conceptual/slip，必须在作答证据中说明理由。迁移表现不单独跳多阶。费力指需要明显检索努力但独立正确，不简单按慢答判定。

learning.record_evidence将这些参数转交；讲解relearn和即时练习practice不推进日期。补学后的独立延迟验证以diagnose/apply/delayed_review记录，不能把讲解后复述当独立正确。skip不改变状态，同日不重复推进。

## 日期规则

- 首次独立正确：初学阶段，1天后验证。
- 普通稳定独立通过，且实际间隔达到上次安排间隔：逐级1、3、7、14、30天。迟答不算错误，不按逾期天数跨级。
- 费力答对：阶段不升，最多3天后验证；这不是提示后答对。
- 提示后正确、遗忘、概念缺口、无法分类的关键错误：保存原stage供追溯，但回首阶，进入consolidation。1天后首次稳定独立通过安排3天；再通过安排7天，转入retention。提示/错误再次出现时重启巩固；费力不计巩固通过次数。
- 有明确证据的局部失误slip：降低一阶且最多7天；若处于巩固期则重新1天。不能把概念错误随意标为slip。
- 最近4次调度结果中至少2次wrong/hinted，普通保持阶段暂不升阶，最多7天再测；巩固期按上述专门规则处理。
- 30天及以上：每次需实际间隔达到当前阶梯长度，累计两次稳定独立通过才延长至下一阶（60、90天），最高90天。不足完整阶梯间隔的通过会清零该长期通过计数。
- 提前独立测验：实际间隔小于上次安排间隔时不升阶，从实际作答日按上次间隔重新安排。若用户仅做额外练习，应标practice，不调用调度。
- 所有due从实际作答日期算；实际间隔actual_gap_days单独保存。scheduled_interval_days是本次实际安排的天数，stage是基础阶梯索引，两者在巩固/短期验证时可能不同。

## 目标日期

助手可传已确认的精确target_date，日期未知则不传，月级期限不推成某一天。若普通due晚于目标前一天，就安排目标前验证，最早次日；目标为当天不另造未来的“考前验证”，过去日期拒绝。此缩短不改变记忆阶段，短期考前通过不算30天以上的足间隔证据。多个目标由助手选择当前相关的最近明确日期，并记录依据；脚本不自动从目标档案推断或创建考试日期。

## 存储与兼容

新增review_phase（initial/consolidation/retention）、consolidation_passes、long_interval_passes、recent_review_outcomes、scheduled_interval_days、actual_gap_days、schedule_reason以及可选pre_lapse_stage。queue与item必须同次保存这些调度字段，事件记录输入质量、错误类型和规则版本，保证下次CLI读到最新状态。

旧数据无新字段仍可按原stage读取，规则在下一次有效作答更新为ladder-v2；历史诊断迁移为知识点内精简证据，调度值不变。D-001/D-002因已有明确关键错误证据初始化consolidation，保持10月12日到期。更正通过revision和有效历史重放，不直接覆盖旧证据。

配置intervals_days为1/3/7/14/30/60/90；当前巩固1/3/7与短期上限属于规则代码，修改这些规则应同步测试和说明，不能只改配置注释。长期计数阈值可由schedule_policy.long_interval_required_passes配置。间隔数组至少保留前三阶，须递增正整数。


## 独立范围与派生索引

现行ladder-v2只作用于KP实体的schedule；queue由生命周期路由派生，禁止手工改队列日期。目标完成仅重检引用，不改变记忆日期。历史资料的旧stage/due作为迁移快照保留，不参与派题。新知识须用户主动诊断。


## review-v3：调度和强化边界（2026-10-12）

本次不改grade函数或已有日期。正常复习仍由due决定资格，使用基于到期、逾期和真实表现的风险标签排序。memory保存已观察的保持间隔与记忆状态，不把它当作概率预测。

reinforce、practice、relearn强制schedule_eligible=false；同日上述练习暴露后的正式回答也不推进阶梯。每次事件由引擎记录schedule_changed和memory_effect；长期验证只取不同日期的足间隔独立稳定正式成功，正式失败后重新积累。个体化间隔开关保持关闭。
