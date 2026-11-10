<div align="center">

<img src="assets/taotie-hero.jpg" alt="Taotie skill fusion" width="100%" />

# Taotie · 饕餮

### 吃掉重复，留下长处，锻造一个更强的 Agent Skill

一个面向 Codex、Claude Code 等 Agent 的 Skill 管理与融合工具。

[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-SKILL.md-cb8a2e?style=flat-square)](SKILL.md)
[![License](https://img.shields.io/badge/license-pending-59636e?style=flat-square)](#许可)
[![Status](https://img.shields.io/badge/status-experimental-f0b429?style=flat-square)](#当前状态)

</div>

## 它解决什么问题

当你有多个功能相近的 Skill 时，真正困难的不是安装，而是判断：

> 哪个 Skill 适合当主骨架？其他 Skill 的哪些经验值得吸收？哪些规则重复、冲突或只是看起来很专业？

Taotie 会把候选 Skill 拆成具体能力，比较证据，处理冲突，生成一个独立的融合版本，并留下可追溯的取舍记录。

## 它怎么工作

```text
候选 Skills
    ↓
盘点输入、输出、工具、依赖和边界
    ↓
能力矩阵：重复 / 互补 / 冲突 / 缺口
    ↓
选择主骨架，逐项吸收有效能力
    ↓
生成自包含 Skill + 融合报告
    ↓
结构检查与真实任务对比测试
    ↓
保留有效版本，支持回退和继续升级
```

## 快速使用

把这个仓库作为 Skill 安装到目标 Agent 的 Skill 目录，然后直接说：

```text
使用 Taotie，以漫剧老李为主，比较 screenwriting-skills、video-understand
和我指定的其他漫剧 Skill，吸收各自优势，生成独立融合版，并做对比验证。
```

也可以只要求分析：

```text
用 Taotie 比较这三个 Skill，先输出能力矩阵和冲突报告，不要修改任何文件。
```

## 主要能力

| 能力 | 作用 |
| --- | --- |
| 候选盘点 | 读取 Skill 的触发范围、流程、资源和依赖 |
| 能力拆解 | 按剧本、分镜、工具调用、验收等具体能力比较 |
| 主骨架选择 | 以用户指定 Skill 或证据最充分的 Skill 为主入口 |
| 优势吸收 | 将互补方法、模板、脚本和参考资料迁移到独立包 |
| 冲突处理 | 把互相矛盾的规则改成适用条件或保留待验证分支 |
| 去重清理 | 删除重复、空泛、无效或无法执行的指令 |
| 可追溯记录 | 记录每项保留、替换、舍弃和待验证决定的来源 |
| 对比验证 | 用同一组任务比较主 Skill 与融合版本 |
| 版本升级 | 根据来源变化和用户反馈做局部吸收、保留用户改动 |
| 能力学习 | 从 Skill、流程或案例提炼一项可迁移能力，展示来源、限制、重叠与验证证据 |
| 长期能力库 | 审核后入库，按关键词检索、追踪来源变化、保留修订和撤销历史 |

## 学习模式

```text
使用 $taotie 学习这两个本地 Skill，挑出值得复用的能力，列出来源、适用条件和验证等级，先给我审阅。
```

用 Python 3.11+ 运行 `python scripts/knowledge.py --help`。知识库默认保存在 `~/.taotie/knowledge.sqlite3`，与仓库、源 Skill 和融合候选分开。只读盘点和对比沿用原流程。学习和入库方法见 [能力学习与记忆](references/learning.md)。

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

- [SKILL.md](SKILL.md)：Taotie 主入口。
- [references/fusion.md](references/fusion.md)：能力拆解、融合和取舍规则。
- [references/evaluation.md](references/evaluation.md)：结构检查与行为对比方法。
- [references/sources.md](references/sources.md)：设计参考和边界说明。
- [scripts/knowledge.py](scripts/knowledge.py)：来源指纹、候选、版本确认、检索与撤销。
- [assets/taotie-hero.jpg](assets/taotie-hero.jpg)：Taotie 项目封面图。

## 当前状态

Taotie 当前是可用的实验版，已经覆盖 Skill 盘点、能力融合、冲突处理、报告和验证流程。真实业务效果仍取决于候选 Skill 的质量、模型能力、外部工具和测试样本。

## 许可

本仓库暂未指定开源许可。再次分发或将其他项目内容吸收到融合版前，请遵守各来源项目的许可证和署名要求。
