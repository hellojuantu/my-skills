# 给代理的规则

| 规则 | 执行检查 |
| --- | --- |
| 读 Console 返回值时，一个值只用接口里的那一个字段。不要再写 `fsmId` / `fsmID` 这种别名。 | `python3 cloudcanal-console-automation/scripts/check_console_field_aliases.py` |
| 启动任务不查槽位预留。 | `python3 cloudcanal-console-automation/scripts/check_no_invented_gates.py` |
| Mini 控制台主机名从 `mini.env` 读取。不要在脚本里写死 `http://mini:`。 | `python3 cloudcanal-console-automation/scripts/check_mini_host.py` |
| 查询预留走共享锁。`change_claim` 必须拿独占锁。对照器要看到这次调用，不能只检查锁函数本身。 | `python3 cloudcanal-dev-test/skills/verify-slot-claim/scripts/code_matches_model.py` |
