# Back up only when the user asks

Create a backup only when the user explicitly asks. Do the work that is already authorized, and do not ask again just to back up.

Move an existing backup and check it. Do not copy it, pack it again, or add another copy, and do not remove an old backup that another session left.

When the user asks for a backup, put the files on the machine you are backing up, under `/tmp/codex-backup/<task>/<host-or-slot>/`. Leave release artifacts, test inputs, evidence, and decision records in their original directories.

Create and check the backup with [backup.py](../scripts/backup.py). The script pins the backup root to the path above, sets the directory mode to 0700, and sets the archive and the restore manifest to mode 0600. Run the script on the machine you are backing up. The script uses only the standard library. You can copy it to Mini and run it there.

When the user asks you to back up a live file or directory:

```sh
python3 cloudcanal-dev-test/scripts/backup.py archive --task "$RELEASE_ID" --scope slot-03 --source '<current JAR or config directory>'
```

Pass `--source` again for each extra source. After the archive is written, the script reads the whole archive back, checks the SHA-256, and returns the path of the archive and the path of the JSON restore manifest. The manifest records the restoreTarget for each archiveMember. To restore, check the manifest first, then restore by those pairs.

```sh
python3 cloudcanal-dev-test/scripts/backup.py verify '<returned JSON restore manifest>'
```

When the user asks you to back up a database, get the private directory with `backup.py directory --task "$RELEASE_ID" --scope '<hostname>'`, write the export as mode 0600, and put it in that directory. After the export succeeds, archive it with `archive --source '<export file>' --restore-target 'MySQL database motherdata'` and the same `--task` and `--scope`. After the archive check passes, delete the duplicate raw export that this round created.

When the user asks for a backup and Docker or a VM must stage the old files inside itself first, move the complete archive into `/tmp/codex-backup/<task>/<host-or-slot>/` and record the original volume or the restore target. When a complete archive already exists, move it and check it, and do not add another copy. After you check the restore manifest, the archive, and the rollback path, delete the extra internal copy that this round created.

A file staged for the swap, such as `.new`, is part of the replacement. A `rollback` file, a `.pre-*` file, or a `.bak` file kept for rollback is a backup. Do not leave that backup in HOME, the project directory, the release record directory, or a container.

When the user asks an external release script to create a backup, check the target first with `backup.py check-path '<backup target>'`. `check-path` rejects the old `private/releases/<id>/rollback` path. `check-path` does not block an arbitrary operating-system copy command, so the external script must receive a backup path you already checked. When the user did not ask for a backup, turn off or skip that script's automatic backup.
