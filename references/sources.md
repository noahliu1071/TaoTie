# 设计来源

2026-11-03核对；以下为思想参考，未复制项目代码，也无运行依赖。

- https://github.com/tdfydfy/skill-map ：借鉴任务边界、能力贡献、冲突与缺口分析。Taotie侧重持久化独立融合包，而非仅临时任务编排。
- https://github.com/justinwetch/SkillEval ：借鉴同输入A/B比较和实际输出评审。Taotie不声称自带该项目的评测执行引擎。
- https://github.com/Rainnystone/skill-orchestration-system ：借鉴可审阅变更、备份和分组管理。Taotie不自动重写宿主配置，不采用“所有技能正文都会默认加载”的泛化说法。
- 本地 Codex skill-creator：采用渐进加载、明确触发、可用资源与行为验收原则。

这不是 binggandata 的 bggg-skill-taotie 的安装版或分支；名称按用户要求使用 Taotie。

