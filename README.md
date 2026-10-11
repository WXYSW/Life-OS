# Life OS

对话式生活记录与知识管理。新聊天先读 [接手指南](docs/HANDOFF.md)。

生活板块保存活动、学习时长、睡眠、情绪等生活数据；知识板块提取知识，管理检测、目标关联和复习。知识删除不会级联删除生活记录。

## 日常使用

- “记录今天”：整理生活数据；提取的新知识仅进入待检测区。
- “测试待检测知识”：先核验内容，再临时出题；默认每批2个范围。
- “开始复习”：只安排符合活跃目标的复习；默认先5个范围，可以继续或停止，无每日上限。
- “归档这个知识”：停止安排，保留证据；“恢复”后重新检查目标关联。
- “这个目标完成了”：重新检查相关知识；其他目标仍需要的继续保留，无匹配才提交处理选择，不自动删除。

## 入口

- [生活与知识当前摘要](state/current.md)
- [知识板块实时摘要](state/knowledge.md)
- [知识生命周期与操作](docs/knowledge-lifecycle.md)
- [待检测、复习、归档等视图](knowledge/lifecycle/views.json)
- [知识目录](knowledge/catalog/README.md)
- [目标](goals/initial.json)与[江西2026大纲章节索引](goals/syllabuses/jx-zsb-2026.json)
- [生活操作流程](docs/workflow.md)
- [学习决策](docs/learning-engine.md)与[ladder-v2规则](docs/schedule-policy.md)

## 存储与公开范围

knowledge/items/ 中 record_type=knowledge 的KP记录是现行知识实体；旧ID记录为legacy_source历史资料，保留来源与迁移前证据，不再参与调度。queue与各视图均从KP记录派生。题干、选项、答案原文和未回答清单不持久化；仅保存精简证据。Git历史保留。

用户已持续授权公开学习知识及精简评价，无需逐次询问；明确不公开/不保存的要求优先。原total.zip的164份资料已按原授权导入，其他日常新原话遵循既有范围。密码、凭据和第三方私人信息不进入公开记录。取消独立资料收藏的决定继续生效。

生活数据在records/，报告在reports/，知识清理操作不改这两个目录。原始导入在imports/，不因删除一个知识而整份删除共享来源。

## 本地操作与验证

需要Python 3.10+，无第三方依赖。脚本由对话时显式调用，没有后台自动任务。

```sh
python scripts/learning.py --day 2026-10-12
python scripts/learning.py --day 2026-10-12 --mode diagnose --new-limit 2
python scripts/lifecycle.py --day 2026-10-12 views
python scripts/catalogue.py --validate
python -m unittest discover -s tests -v
```

脚本默认只给候选或变更结果。lifecycle命令的--write仅写本地允许的知识/目标路径；助手核对后以一次普通Git提交同步并验证远程。具体命令见生命周期说明。
