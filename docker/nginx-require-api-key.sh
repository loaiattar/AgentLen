#!/bin/sh
# Start-up guard of the `frontend` container (docker/frontend.Dockerfile).
#
# nginx adds `X-API-Key` to every proxied `/api` call from API_KEY
# (nginx.conf.template). Without it the interface would get a 401 on every
# call: refuse to start instead of serving that. The value itself is never
# printed.
set -eu

if [ -z "${API_KEY:-}" ]; then
    echo "API_KEY is empty: set it in .env, docker-compose.yml passes it to this container" >&2
    exit 1
fi

# The value is spliced into a double-quoted nginx string: a quote, a backslash
# or a `$` would change what nginx parses.
case "$API_KEY" in
    *'"'* | *'\'* | *'$'*)
        echo 'API_KEY must not contain ", \ or $: nginx would misread it' >&2
        exit 1
        ;;
esac
