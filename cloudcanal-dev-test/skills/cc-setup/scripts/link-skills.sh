#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname "$0")/../../../.." && pwd)
repo_phys=$(CDPATH= cd -- "$repo_dir" && pwd -P)
skills_dir=${HOME}/.codex/skills
mkdir -p "$skills_dir"

for skill in pstack cloudcanal-dev-test datasource-lab cloudcanal-console-automation; do
  source_dir=$repo_dir/$skill
  dest=$skills_dir/$skill
  expected=$(CDPATH= cd -- "$source_dir" && pwd -P)
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    if [ ! -L "$dest" ]; then
      printf '已有目录，先核对：%s\n' "$dest" >&2
      exit 1
    fi
    action=$(python3 - "$dest" "$repo_phys" "$skill" "$expected" <<'PY'
import os
from pathlib import Path
import sys

dest, repo, skill, expected = sys.argv[1:]
dest, repo = Path(dest), Path(repo)
legacy_suffix = Path(".codex", "skills", skill)
legacy = repo / legacy_suffix
actual = Path(os.path.realpath(dest))

if actual == Path(expected):
    print("keep")
elif actual == legacy:
    print("migrate")
elif (
    Path(os.readlink(dest)) == Path(repo.name) / legacy_suffix
    and not os.path.lexists(dest.parent / repo.name)
    and Path(os.path.realpath(legacy)) == legacy
):
    print("migrate")
else:
    print("refuse")
PY
    )
    if [ "$action" = keep ]; then
      continue
    fi
    if [ "$action" = migrate ]; then
      ln -sfn "$source_dir" "$dest"
      continue
    fi
    printf '软链指向别处，先核对：%s\n' "$dest" >&2
    exit 1
  fi
  ln -s "$source_dir" "$dest"
done
