#!/bin/sh
set -eu

HOST="${DEMO_HOST:-127.0.0.1}"
PREFERRED_PORT="${DEMO_PORT:-8000}"
LOG_PATH="${DEMO_LOG_PATH:-/tmp/openclassrooms_projet5_demo.log}"

http_code() {
  curl -sS -o /dev/null -w '%{http_code}' "$1" 2>/dev/null || printf '000'
}

find_free_port() {
  uv run python - <<'PY'
import socket

preferred_port = int(__import__("os").environ.get("DEMO_PORT", "8000"))
for port in [preferred_port, *range(preferred_port + 1, preferred_port + 10)]:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            continue
        print(port)
        break
PY
}

start_server() {
  port="$1"
  setsid env ENABLE_DEMO_UI=true PORT="$port" \
    uv run uvicorn openclassrooms_projet5.api.main:app \
      --host "$HOST" \
      --port "$port" >"$LOG_PATH" 2>&1 < /dev/null &
}

wait_for_demo() {
  port="$1"
  demo_url="http://$HOST:$port/demo"
  for _ in $(seq 1 40); do
    if [ "$(http_code "$demo_url")" = "200" ]; then
      printf '%s' "$demo_url"
      return 0
    fi
    sleep 1
  done
  return 1
}

existing_demo_url="http://$HOST:$PREFERRED_PORT/demo"
existing_health_url="http://$HOST:$PREFERRED_PORT/health"

if [ "$(http_code "$existing_demo_url")" = "200" ]; then
  FINAL_URL="$existing_demo_url"
elif [ "$(http_code "$existing_health_url")" = "200" ]; then
  FREE_PORT="$(find_free_port)"
  start_server "$FREE_PORT"
  FINAL_URL="$(wait_for_demo "$FREE_PORT")"
else
  FREE_PORT="$(find_free_port)"
  start_server "$FREE_PORT"
  FINAL_URL="$(wait_for_demo "$FREE_PORT")"
fi

if [ -z "${FINAL_URL:-}" ]; then
  echo "Unable to start the soutenance dashboard. Check $LOG_PATH."
  exit 1
fi

echo "Preparing soutenance snapshot..."
ENABLE_DEMO_UI=true uv run python scripts/demo_snapshot.py --skip-quality >/dev/null || true

echo "Soutenance dashboard ready: $FINAL_URL"
echo "Log file: $LOG_PATH"

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$FINAL_URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "$FINAL_URL" >/dev/null 2>&1 || true
fi
