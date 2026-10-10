# Life OS

第一版对话式记录与复习系统。每天自然描述生活，助手提取数据、必要追问、简短分析并保存；知识先入待诊断池，少量提问后加入复习队列。

- [当前状态](state/current.md)
- [操作流程](docs/workflow.md)
- [复习参数](config/review.json)
- [记录模板](templates/record.json)
- [知识模板](templates/knowledge.json)
- [报告模板](templates/report.md)

## 保存范围

本仓库为公开发布区：学习数据、知识点和脱敏报告可保存；用户原话及回答原文须逐次指定。完整原文目前保存在本地 `life-os-private/`，私有 GitHub 尚未配置。不得将本地私密目录整包推送。公开来源只引用 ID，不引用未授权的原文或回答片段。

## 使用

说“记录今天”“补记昨天”“今天结束”“开始复习”“简单记录”“更正某条”即可。默认每批最多 2 道新题和 3 道到期题；不足时不凑题，低精力时可以为零。同一天再次聊天不重复派题，未答题继续保留。

每次先读取仓库与本地记录，再分析。上传前检查公开范围；上传后读取核对，并返回提交链接。数据更正保留修订记录，关联报告标记待更新。

## 目录

`records/YYYY/MM/DD/` 学习数据；`reports/{daily,weekly,monthly,quarterly,yearly}/` 各周期报告；`goals/` 目标；`knowledge/items/` 知识；`knowledge/attempts/YYYY/MM/DD/` 作答历史；`knowledge/sessions/` 当日派题记录；`knowledge/review-plans/queue.json` 队列；`revisions/` 修订。

## 调度脚本

需要 Python 3.10+，无第三方依赖。

```sh
python scripts/review.py select knowledge/review-plans/queue.json --day 2026-10-10
python -m unittest discover -s tests -v
```

脚本只输出候选题对应的知识 ID，不自动生成题目、不修改文件、不上传。助手依据知识内容出题，并在实际派题后保存 session；作答调用 `grade` 后保存状态和作答历史。时间由调用方按 Asia/Shanghai 提供，拒绝依赖机器默认日期。

已配置的是对话时执行流程，未配置后台定时任务。初始信息尚待提供，没有虚构日记、题目或答题成绩。
