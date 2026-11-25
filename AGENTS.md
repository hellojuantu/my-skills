# 给代理的规则

| 规则 | 执行检查 |
| --- | --- |
| 读 Console 返回值时，一个值只用接口里的那一个字段。不要再写 `fsmId` / `fsmID` 这种别名。 | `python3 cloudcanal-console-automation/scripts/check_console_field_aliases.py` |
| 启动任务不查槽位预留。批测只有 dev。不要写 `RELEASE_STAGES_NOT_RUN`，也不要在 start-job 里检查预留。 | `python3 cloudcanal-console-automation/scripts/check_no_invented_gates.py` |
