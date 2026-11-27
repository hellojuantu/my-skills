#!/usr/bin/env python3
"""Create and verify operational backups under the user's fixed backup root."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import stat
import sys
import tarfile
import uuid


BACKUP_ROOT = Path("/tmp/codex-backup")


def check_path(path):
    path = Path(path).absolute()
    try:
        parts = path.relative_to(BACKUP_ROOT).parts
    except ValueError:
        raise ValueError("Backup destination must use /tmp/codex-backup/<task>/<host-or-slot>; use backup.py directory or archive")
    if len(parts) < 2 or ".." in parts or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", part) for part in parts[:2]):
        raise ValueError("Use one task name and one host-or-slot name below /tmp/codex-backup")
    current = BACKUP_ROOT
    for part in (None, *parts):
        if part is not None:
            current = current / part
        if current.is_symlink():
            raise ValueError(f"Backup destination must not traverse a symlink: {current}")
    if not path.resolve().is_relative_to(BACKUP_ROOT.resolve()):
        raise ValueError("Backup destination escapes /tmp/codex-backup")
    return path


def directory(task, scope):
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) for name in (task, scope)):
        raise ValueError("Task and host-or-slot must each be one directory name")
    path = check_path(BACKUP_ROOT / task / scope)
    for current in (BACKUP_ROOT, BACKUP_ROOT / task, path):
        current.mkdir(mode=0o700, exist_ok=True)
        mode = current.stat()
        if mode.st_uid != os.getuid() or stat.S_IMODE(mode.st_mode) & 0o077:
            raise ValueError(f"Backup directory must belong to this user with mode 0700: {current}")
    return path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as data:
        for block in iter(lambda: data.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def private_file(path):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")


def verify(manifest_path):
    manifest_path = check_path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["format"] != 1 or not manifest["restore"]:
        raise ValueError("Expected a version 1 restore manifest")
    if manifest_path.parent != BACKUP_ROOT / manifest["task"] / manifest["scope"]:
        raise ValueError("Restore manifest must be in its recorded task and host-or-slot directory")
    archive = check_path(manifest_path.parent / manifest["archive"])
    if archive.parent != manifest_path.parent:
        raise ValueError("Archive must be beside its restore manifest")
    for path in (BACKUP_ROOT, manifest_path.parent.parent, manifest_path.parent, manifest_path, archive):
        mode = path.stat()
        if mode.st_uid != os.getuid() or stat.S_IMODE(mode.st_mode) & 0o077:
            raise ValueError(f"Backups must belong to this user with no group or other permissions: {path}")
    if sha256(archive) != manifest["sha256"]:
        raise ValueError("Backup archive SHA-256 does not match the restore manifest")
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        names = {member.name for member in members}
        if any(entry["archiveMember"] not in names for entry in manifest["restore"]):
            raise ValueError("Backup is missing a source recorded in its restore manifest")
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError("Backup contains an unsafe archive member")
            if member.isfile():
                with bundle.extractfile(member) as data:
                    while data.read(1024 * 1024):
                        pass
    return {"manifest": str(manifest_path), "archive": str(archive), "sha256": manifest["sha256"], "restore": manifest["restore"]}


def archive_sources(args):
    target = directory(args.task, args.scope)
    sources = [Path(source).absolute() for source in args.source]
    if args.restore_target and len(sources) != 1:
        raise ValueError("--restore-target requires exactly one source")
    for source in sources:
        if not source.exists() and not source.is_symlink():
            raise ValueError(f"Backup source does not exist: {source}")
        if source.is_dir() and target.resolve().is_relative_to(source.resolve()):
            raise ValueError("Backup source directory contains its destination")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"backup-{stamp}-{uuid.uuid4().hex[:8]}"
    archive = target / f"{name}.tar.gz"
    manifest_path = target / f"{name}.json"
    restore = []
    output = private_file(archive)
    manifest_created = False
    try:
        with output, tarfile.open(fileobj=output, mode="w:gz") as bundle:
            for index, source in enumerate(sources):
                member = f"sources/{index}/{source.name}"
                bundle.add(source, arcname=member)
                restore.append({"archiveMember": member, "restoreTarget": args.restore_target or str(source)})
        manifest = {
            "format": 1, "createdAt": datetime.now(timezone.utc).isoformat(), "host": socket.gethostname(),
            "task": args.task, "scope": args.scope, "archive": archive.name, "sha256": sha256(archive), "restore": restore,
        }
        with private_file(manifest_path) as output:
            manifest_created = True
            output.write((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        return verify(manifest_path)
    except Exception:
        if manifest_created:
            manifest_path.unlink(missing_ok=True)
        archive.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("directory", "archive"):
        create = commands.add_parser(command)
        create.add_argument("--task", required=True)
        create.add_argument("--scope", required=True, help="Host name or slot name")
        if command == "archive":
            create.add_argument("--source", action="append", required=True)
            create.add_argument("--restore-target", help="Original destination, such as MySQL database motherdata")
    for command in ("check-path", "verify"):
        commands.add_parser(command).add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "directory":
            print(directory(args.task, args.scope))
        elif args.command == "archive":
            print(json.dumps(archive_sources(args), ensure_ascii=False, indent=2))
        elif args.command == "verify":
            print(json.dumps(verify(args.path), ensure_ascii=False, indent=2))
        else:
            print(check_path(args.path))
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        print(f"Backup refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
