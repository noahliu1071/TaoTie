# 设计来源

2026-11-03核对；以下为思想参考，未复制项目代码，也无运行依赖。

- https://github.com/tdfydfy/skill-map ：借鉴任务边界、能力贡献、冲突与缺口分析。Taotie侧重持久化独立融合包，而非仅临时任务编排。
- https://github.com/justinwetch/SkillEval ：借鉴同输入A/B比较和实际输出评审。Taotie不声称自带该项目的评测执行引擎。
- https://github.com/Rainnystone/skill-orchestration-system ：借鉴可审阅变更、备份和分组管理。Taotie不自动重写宿主配置，不采用“所有技能正文都会默认加载”的泛化说法。
- 本地 Codex skill-creator：采用渐进加载、明确触发、可用资源与行为验收原则。
- Codex Motion Director（LBS1111，源项目 MIT）：参考其 `learning/skill-learning.md`、`references/skill-contract.md`、`references/memory-policy.md`、`scripts/core.py` 与路由配置。吸收来源增量发现、版本绑定确认、证据分级、偏好管理、检索与组合、撤销和恢复提议。饕餮独立编写通用流程和 SQLite 实现，以显式任务标签替代原有动效词表。

这不是 binggandata 的 bggg-skill-taotie 的安装版或分支；名称按用户要求使用 Taotie。

