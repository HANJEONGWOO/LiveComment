#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3를 찾을 수 없습니다." >&2
  exit 1
fi

if [[ ! -f client_secret.json ]]; then
  echo "client_secret.json 파일을 찾을 수 없습니다." >&2
  echo "먼저 Google OAuth 클라이언트 JSON 파일을 프로젝트 루트에 client_secret.json 이름으로 저장해주세요." >&2
  exit 1
fi

printf "video url 입력해주세요. "
IFS= read -r video_url

if [[ -z "${video_url//[[:space:]]/}" ]]; then
  echo "video url이 비어 있습니다." >&2
  exit 1
fi

printf "message 입력해주세요. "
IFS= read -r message

if [[ -z "${message//[[:space:]]/}" ]]; then
  echo "message가 비어 있습니다." >&2
  exit 1
fi

exec python3 -m livecomment announce \
  --client-secrets client_secret.json \
  --video "$video_url" \
  --message "$message"
