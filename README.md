<div align="center">

<img src="assets/taotie-hero.jpg" alt="Taotie skill fusion" width="100%" />

# Taotie · 饕餮

### 吃掉重复，留下长处，锻造一个更强的 Agent Skill

面向 Codex、Claude Code 等 Agent 的 Skill 学习、对比、融合和管理工具。

[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-SKILL.md-cb8a2e?style=flat-square)](SKILL.md)
[![License](https://img.shields.io/badge/license-pending-59636e?style=flat-square)](#许可)
[![Status](https://img.shields.io/badge/status-experimental-f0b429?style=flat-square)](#当前状态)

</div>

## 主要能力

| 你想做什么 | 饕餮怎么处理 | 得到什么 |
| --- | --- | --- |
| **发现新增或更新的 Skill** | 扫描配置的本地目录，对比来源指纹，跳过排除项和宿主禁用项 | 新增、变更和待分析清单 |
| **盘点手里的 Skill** | 拆解触发范围、输入、输出、工作步骤、工具、依赖和限制 | 能力矩阵，标出重复、互补、冲突和缺口 |
| **比较两个 Skill 谁在哪一步更好** | 按目的和输入输出对齐共通步骤，单列独有步骤；条件允许时用同一组任务分别验证 | 步骤对照表、证据和逐项保留或替换建议。[逐步对比](references/comparison.md) |
| **从来源学习一种方法** | 从 Skill、文档或案例提炼单项能力，记录方法、适用条件、限制、来源和验证证据 | 可单独审阅的能力卡。[能力学习](references/learning.md) |
| **审核、保存并复用能力** | 将审批绑定到具体候选和来源版本；确认后入库，支持关键词检索，标记来源或证据变化 | 已确认的能力记录及审阅历史 |
| **为一个任务挑选能力组合** | 按结构化任务要求检查覆盖、输入、输出、依赖、冲突与排除偏好，组合主工作流与专项能力 | 规划候选、具备执行条件的候选和各自的缺口。[能力路由](references/library.md#任务路由) |
| **融合出一个独立 Skill** | 选择主骨架，吸收互补方法、脚本或参考资料，去重并按适用条件处理冲突 | 自包含候选 Skill、融合报告及来源和取舍记录。[融合规则](references/fusion.md) |
| **判断融合有没有收益** | 检查结构、引用链和依赖；有独立执行条件时，按预设标准比较原版与融合版的实际输出 | 静态检查与行为结果分别报告。[验证规则](references/evaluation.md) |
| **迭代已有融合版** | 对照旧融合版、旧来源和新来源，保留用户改动，局部吸收有价值的变化 | 新候选版本、差异和待验证事项 |
| **维护长期偏好** | 提议并审核不同场景下喜欢或避免的做法，收藏或排除具体能力 | 已确认偏好；收藏影响路由排序，排除阻止进入路由 |
| **维护记录和版本** | 暂缓或重新审阅候选，撤销已确认记录，查询修订，从旧版发起恢复提议 | 审计历史、状态汇总和索引维护。[记录维护](references/library.md#偏好与维护) |

## 快速使用

把仓库作为 Skill 安装到目标 Agent 的 Skill 目录。可以直接指定想走哪条流程。

```text
对比：用 $taotie 对齐 A 和 B 的共同步骤，单列独有步骤，给出取舍建议。只出报告。
学习：用 $taotie 扫描我指定的 Skill 目录，把值得复用的方法拆成能力卡，先给我审阅。
路由：用 $taotie 从已确认能力里给这个任务选组合，标出输入、依赖和执行缺口。
融合：用 $taotie 以 A 为主，吸收 B 有证据支持的做法，交付独立候选和融合报告。
升级：用 $taotie 比较这个融合版与来源的新版本，保留我的改动，给出增量升级候选。
```

## 工作流程

```text
已知来源或本地扫描 → 盘点与拆解
                       ├─ 对比 → 步骤对照与取舍建议
                       ├─ 学习 → 能力卡 → 用户确认 → 长期库 → 检索或任务路由
                       └─ 融合或升级 → 独立候选 + 融合报告 → 结构与行为验证
```

能力卡的验证等级依次为 `read`（已读来源）、`runnable`（最小流程跑通）、`reproduced`（代表任务复现）、`reusable`（多组不同条件验证）。入库审批和实测等级分别记录。

本地知识库使用 Python 3.11+ 和 SQLite，默认保存在 `~/.taotie/knowledge.sqlite3`。运行 `python scripts/knowledge.py --help` 查看命令。[能力库操作手册](references/library.md)

## 产物结构

```text
task-skill/
├── SKILL.md                 # 融合后的入口和路由
├── references/              # 按模式拆开的专业规则
├── scripts/                 # 需要重复执行的确定性操作
├── assets/                  # 模板、字体或其他输出资源
└── fusion-report.md         # 来源、取舍、冲突和验证证据
```

Taotie 会优先生成候选版本和报告。安装、替换、禁用或删除原 Skill 需要明确授权，并保留回退路径。

## 设计原则

- 以能力为单位吸收，不整份复制。
- 先读取元数据，再按需读取正文和引用资源。
- “作者声称”“静态检查通过”“真实测试通过”分别记录。
- 规则冲突时保留适用场景，不把两个互相矛盾的全局命令硬塞在一起。
- 融合版必须能独立运行，不能依赖原 Skill 仍然存在。
- 用真实输出验证效果，不把篇幅、星数或术语数量当成质量证明。

## 仓库内容

- Taotie 主入口及操作模式。[SKILL.md](SKILL.md)
- 逐步对比、融合规则和验证方法。[对比](references/comparison.md) · [融合](references/fusion.md) · [验证](references/evaluation.md)
- 能力学习、能力库操作及设计来源。[学习](references/learning.md) · [能力库](references/library.md) · [来源](references/sources.md)
- 本地命令入口，以及发现与路由实现。[knowledge.py](scripts/knowledge.py) · [discovery.py](scripts/discovery.py) · [routing.py](scripts/routing.py)

## 当前状态

Taotie 处于实验阶段。已验证 Skill 结构和本地知识库的关键流程，包括目录发现、版本审批、依赖与冲突检查、偏好及撤销恢复。融合效果仍需按具体任务、模型和工具做独立对照。

## 许可

本仓库暂未指定开源许可。再次分发或将其他项目内容吸收到融合版前，请遵守各来源项目的许可证和署名要求。
