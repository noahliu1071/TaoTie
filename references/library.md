# 能力库操作

以下命令从 Taotie 根目录用 `python scripts/knowledge.py` 调用。数据库默认在 `~/.taotie/knowledge.sqlite3`，`--db <路径>` 放在子命令前，可用于隔离资料或验证。

## 增量发现

- `configure --root <目录> --root <目录>` 保存扫描根；`--exclude <路径>` 设置本库排除项，`--clear-excludes` 清空本库排除列表。默认读取 Codex 数据目录下的 skills 和用户的 .agents/skills。配置根、排除项时只替换此次指定的字段。
- `scan` 更新目录清单，`scan --root <目录>` 可附加本次扫描范围。文件指纹不变时保持同一个发现版本。扫描失败会列出错误，已确认记录保留。默认跳过自身、常见依赖目录、符号链接和宿主明确禁用的项。扫描由当前任务启动或恢复触发。
- `discoveries` 列出待分析来源，`inspect <发现ID>` 返回入口路径、指纹和文件清单。入口和相关引用由 Agent 读取，元数据只是筛选线索。一个来源可分别提议多张卡；写入第一张候选后，该版本视为已处理，后续仍可按 ID 检查和提议。
- `propose <记录ID> --card <卡片JSON> --discovery <发现ID>` 绑定扫描到的版本。结合 `pending` 和 `review` 区分已经分析的候选。发现项变更需重新扫描和分析，旧卡片保留历史。

## 任务路由

`route --brief <JSON>` 对当前任务生成候选组合。先把自然语言任务映射为本库卡片实际使用的能力、输入和输出标签，不维护固定的行业词表。简例：

```json
{
  "request": "按证据比较两套工作流",
  "required_capabilities": ["align-steps", "compare-evidence"],
  "inputs": ["skill-sources", "evaluation-cases"],
  "output": "comparison-report"
}
```

想让能力卡参与路由时，在普通卡片 JSON 增加 `routing` 对象。已保存的旧卡可继续检索；补充路由字段属于卡片修订，按原记录 ID 重新提议和确认。

```json
{
  "role": "primary",
  "capabilities": ["align-steps"],
  "inputs": ["skill-sources"],
  "outputs": ["comparison-report"],
  "conflicts": ["another-record-id"],
  "dependencies": [{"type": "executable", "value": "python"}]
}
```

- 每个组合最多一个 `primary`，其余是 `specialist`。支持任一方声明冲突，按记录 ID 检查。排序结合覆盖度、关键词、收藏和验证等级，再按优先顺序补齐缺口。组合是候选建议，必要时比较备选组合。
- `planning` 可包含仅阅读或依赖未验证的能力。`execution` 只包含当前来源和验证证据未变化、验证等级高于 `read`、依赖均可用的候选。两组各自报告未覆盖要求。输入缺失、输出不匹配、来源失效、禁用或明确排除的条目会列明原因。
- 依赖支持 `executable`、`path` 和 `manual`。手工检查项默认为 `unknown`，只有 `check` 中的 `path`、`sha256`、带时区的 `checked_at` 与 `expires_at` 共同证明有效时才为可用。脚本只检索和检查；Agent 结合任务和实际授权判断下一步。

## 偏好与维护

- `preference <记录ID> like|avoid <文字> --scope <适用范围>` 提议长期偏好。只在用户表达长期意图时提议，局部反馈按当前任务使用。
- `preference <记录ID> favorite|reject <能力记录ID>` 提议收藏或排除已确认能力。与其他候选一样，先 `review` 再按确认版本 `approve`。收藏增加路由权重，排除阻止路由。`profile` 返回已确认偏好及范围；同一任务有冲突时，以当前要求和具体适用条件判断。
- `dismiss <ID> --reason <原因>` 暂不保存某版发现项或分析候选，`reopen <ID>` 恢复审阅。暂缓属于候选状态，长期排除用独立偏好记录。
- `revoke <记录ID> --reason <原因>` 撤销正式记录，`history <记录ID>` 查看修订及审核记录。用 `restore-proposal <记录ID> --revision <版本>` 从曾确认的版本建立新候选；来源或证据已变时，按当前材料重新分析。恢复也需要确认。
- `status` 显示范围和数量，`report` 汇总正式记录、发现项和待审卡；`report --reviewed-only` 仅输出带候选 ID 的待审卡。SQLite 是正式记录的唯一存储，`rebuild-index` 重建数据库索引并返回完整性检查结果。
