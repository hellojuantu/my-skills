# 仅用户明确要求时备份

用户没有明确要求时，不要创建备份。

已经授权的操作直接做。

不要为了备份再问一次。

已有备份只移动和核对。

不要复制。

不要再打一份归档。

不要追加副本。

不要清理其他会话留下的旧备份。

用户要求备份时，文件放在被备份那台机器的 `/tmp/codex-backup/<task>/<host-or-slot>/`。

发布产物、测试输入、证据和决策记录仍放在原来的目录。

用 [backup.py](../scripts/backup.py) 创建和校验。

它把备份根目录固定在上面的路径。

目录权限是 0700。

归档和恢复清单的权限是 0600。

脚本要在被备份的那台机器上跑。

它只用标准库，可以拷到 Mini 上用。

用户要求备份现用文件或目录时：

```sh
python3 cloudcanal-dev-test/scripts/backup.py archive --task "$RELEASE_ID" --scope slot-03 --source '<现用 JAR 或配置目录>'
```

多个来源重复传 `--source`。

归档完成后，脚本读回整个归档并核对 SHA-256。

它返回归档和 JSON 恢复清单的位置。

清单记录每个 archiveMember 对应的 restoreTarget。

还原时先校验清单，再按这些对应关系恢复。

```sh
python3 cloudcanal-dev-test/scripts/backup.py verify '<返回的 JSON 恢复清单>'
```

用户要求备份数据库时，先用 `backup.py directory --task "$RELEASE_ID" --scope '<主机名>'` 取得私有目录。

把导出写成 0600，放进该目录。

导出命令成功后，用 `archive --source '<导出文件>' --restore-target 'MySQL database motherdata'` 归档。

归档时传同一组 `--task` 和 `--scope`。

归档验证通过后，删掉本轮自己创建的那份重复原始导出。

用户要求备份，并且 Docker 或 VM 必须先在内部暂存旧文件时，把完整归档收进上述目录。

记下原卷或恢复目标。

已经有完整归档时，直接移动并核对。

不要再套一份归档。

核对恢复清单、归档和回退路径后，删掉本轮自己创建的冗余内部副本。

`.new` 这类正在替换的暂存文件属于替换过程。

用来回退的 `rollback`、`.pre-*`、`.bak` 属于备份。

这些备份不能长期留在 HOME、项目目录、发布记录目录或容器里。

用户要求外部发布脚本创建备份时，先用 `backup.py check-path '<备份目标>'` 检查目标。

脚本会拒绝旧的 `private/releases/<id>/rollback` 路径。

它不拦截任意操作系统复制命令。

外部脚本必须传入已经核对过的备份位置。

用户没有要求备份时，关掉或跳过外部脚本的自动备份。
