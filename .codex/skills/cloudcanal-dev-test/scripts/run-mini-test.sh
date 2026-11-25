#!/bin/sh
set -eu

host=$(hostname -s)
if [ "$host" != "clougences-Mac-mini" ]; then
    printf 'CloudCanal test refused on %s. Use ssh mini to execute run-mini-test.sh on Mini.\n' "$host" >&2
    exit 1
fi

if [ "$#" -eq 0 ]; then
    printf 'Usage: run-mini-test.sh COMMAND [ARG ...]\n' >&2
    exit 2
fi

printf 'CloudCanal test host: %s\n' "$host" >&2
status=0
"$@" </dev/null || status=$?
printf '\n%s=%d\n' "${CC_MINI_TEST_RECEIPT:-CloudCanal test exit}" "$status" >&2
exit "$status"
