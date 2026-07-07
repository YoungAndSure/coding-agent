#!/usr/bin/env bash
#
# chat.sh - 用 curl 调用 MiniMax 的 Anthropic 兼容接口
#
# 用法:
#   ./chat.sh "你好"                  # 单轮
#   echo "你好" | ./chat.sh           # 从 stdin 读
#   ./chat.sh --stream "你好"         # 流式输出
#   ./chat.sh --show-config           # 查看生效配置（token 隐去）
#   ./chat.sh --model MiniMax-M3 -s "只回答是/否" "天是蓝的吗"
#
# 配置来源（与 chat.py 一致）:
#   ./.claude/settings.json  ->  ~/.claude/settings.json
#   必读字段: ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN
#   可选:    ANTHROPIC_MODEL（缺省 MiniMax-M3）

set -euo pipefail

# ---------- 解析 CLI ----------
PROMPT=""
STREAM=0
MODEL_OVERRIDE=""
SYSTEM=""
MAX_TOKENS=1024
SHOW_CONFIG=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stream)        STREAM=1; shift ;;
    --show-config)   SHOW_CONFIG=1; shift ;;
    --model)         MODEL_OVERRIDE="$2"; shift 2 ;;
    -s|--system)     SYSTEM="$2"; shift 2 ;;
    --max-tokens)    MAX_TOKENS="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,16p' "$0"; exit 0 ;;
    --) shift; break ;;
    -*)
      echo "[错误] 未知选项: $1" >&2; exit 2 ;;
    *)
      PROMPT="$1"; shift ;;
  esac
done

# ---------- 定位 settings.json ----------
find_settings() {
  local p
  for p in "./.claude/settings.json" "$HOME/.claude/settings.json"; do
    if [[ -f "$p" ]]; then
      echo "$p"
      return 0
    fi
  done
  echo "[错误] 找不到 settings.json（已查找: $1)" >&2
  return 1
}
SETTINGS_PATH="$(find_settings)" || exit 1

# 把 STREAM 暴露给后面的 python heredoc
export CHAT_STREAM="$STREAM"

# ---------- 用 python3 抽取 env 字段 ----------
read_env() {
  python3 - "$SETTINGS_PATH" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    env = json.load(f).get("env") or {}
missing = [k for k in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN") if not env.get(k)]
if missing:
    sys.stderr.write(f"[错误] {path} 缺少 env 字段: " + ", ".join(missing) + "\n")
    sys.exit(2)
for k in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL",
          "ANTHROPIC_SMALL_FAST_MODEL", "API_TIMEOUT_MS"):
    v = env.get(k)
    if v is not None:
        print(f"{k}={v}")
PY
}

# 读取 KEY=VALUE 形式的环境
BASE_URL=""
AUTH_TOKEN=""
MODEL="MiniMax-M3"
TIMEOUT_MS=""
while IFS= read -r line; do
  key="${line%%=*}"; val="${line#*=}"
  case "$key" in
    ANTHROPIC_BASE_URL)        BASE_URL="$val" ;;
    ANTHROPIC_AUTH_TOKEN)      AUTH_TOKEN="$val" ;;
    ANTHROPIC_MODEL)           MODEL="$val" ;;
    API_TIMEOUT_MS)            TIMEOUT_MS="$val" ;;
  esac
done < <(read_env)

[[ -n "$MODEL_OVERRIDE" ]] && MODEL="$MODEL_OVERRIDE"
[[ -z "$TIMEOUT_MS" ]]     && TIMEOUT_MS="300000"

# ---------- --show-config ----------
if [[ $SHOW_CONFIG -eq 1 ]]; then
  cat <<EOF
[settings] $SETTINGS_PATH
ANTHROPIC_BASE_URL    = $BASE_URL
ANTHROPIC_AUTH_TOKEN  = ***
ANTHROPIC_MODEL       = $MODEL
API_TIMEOUT_MS       = $TIMEOUT_MS
EOF
  exit 0
fi

# ---------- 收集 prompt ----------
if [[ -z "$PROMPT" ]]; then
  if [[ ! -t 0 ]]; then
    PROMPT="$(cat)"
  else
    echo "[错误] 请提供 prompt，或通过 stdin 传入" >&2
    exit 2
  fi
fi
[[ -n "$PROMPT" ]] || { echo "[错误] prompt 为空" >&2; exit 2; }

# ---------- 构造请求体 ----------
ENDPOINT="${BASE_URL%/}/v1/messages"

BODY_FILE="$(mktemp -t chat-body.XXXXXX.json)"
RESP_FILE="$(mktemp -t chat-resp.XXXXXX.json)"
trap 'rm -f "$BODY_FILE" "$RESP_FILE"' EXIT

python3 - "$BODY_FILE" "$MODEL" "$MAX_TOKENS" "$SYSTEM" "$PROMPT" <<'PY'
import json, os, sys
(body_path, model, max_tokens, system, prompt) = sys.argv[1:]
body = {
    "model": model,
    "max_tokens": int(max_tokens),
    "messages": [{"role": "user", "content": prompt}],
}
if system:
    body["system"] = system
if os.environ.get("CHAT_STREAM") == "1":
    body["stream"] = True          # 关键：开 SSE
with open(body_path, "w", encoding="utf-8") as f:
    json.dump(body, f, ensure_ascii=False)
PY

# ---------- 发起请求 ----------
COMMON_OPTS=(
  --silent --show-error
  --connect-timeout 10
  --max-time "$(( TIMEOUT_MS / 1000 ))"
  --request POST "$ENDPOINT"
  --header "x-api-key: $AUTH_TOKEN"
  --header "anthropic-version: 2023-06-01"
  --header "content-type: application/json"
  --data-binary "@$BODY_FILE"
)

if [[ $STREAM -eq 1 ]]; then
  # 流式：直接 stdout，按行过滤 "data:"，交给 python 解 SSE
  curl "${COMMON_OPTS[@]}" --no-buffer 2>/tmp/chat.err \
    | grep --line-buffered '^data: ' \
    | sed 's/^data: //' \
    | python3 -u -c '
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line or line == "[DONE]":
        continue
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        continue
    t = ev.get("type", "")
    if t == "content_block_delta":
        d = ev.get("delta", {}) or {}
        if d.get("type") == "text_delta":
            sys.stdout.write(d.get("text", ""))
            sys.stdout.flush()
    elif t == "message_stop":
        break
    elif t == "error":
        sys.stderr.write("\n[stream error] " + json.dumps(ev.get("error"), ensure_ascii=False) + "\n")
        break
'
  echo
else
  # 非流式：HTTP code 走 stderr（-w），body 落盘
  HTTP_CODE="$(curl "${COMMON_OPTS[@]}" \
      -o "$RESP_FILE" -w '%{http_code}' 2>/tmp/chat.err || echo "000")"

  if [[ "$HTTP_CODE" != "200" ]]; then
    echo "[错误] HTTP $HTTP_CODE" >&2
    head -c 2000 "$RESP_FILE" >&2 || true
    echo >&2
    [[ -s /tmp/chat.err ]] && echo "[curl stderr] $(cat /tmp/chat.err)" >&2
    exit 1
  fi

  python3 - "$RESP_FILE" <<'PY'
import json, sys
path = sys.argv[1]
try:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    sys.stderr.write(f"[错误] 响应解析失败: {e}\n")
    sys.exit(1)
if "content" in data:
    out = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
    sys.stdout.write(out + "\n")
elif "error" in data:
    sys.stderr.write("[api error] " + json.dumps(data["error"], ensure_ascii=False) + "\n")
    sys.exit(1)
else:
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
PY
fi

if [[ -s /tmp/chat.err ]]; then
  echo "[curl stderr] $(cat /tmp/chat.err)" >&2
fi
