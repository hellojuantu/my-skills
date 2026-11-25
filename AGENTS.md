# 给代理的规则

| 规则 | 执行检查 |
| --- | --- |
| 读 Console 返回值时，一个值只用接口里的那一个字段。不要再写 `fsmId` / `fsmID` 这种别名。 | `python3 cloudcanal-console-automation/scripts/check_console_field_aliases.py` |
