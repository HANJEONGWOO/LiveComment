#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

python_bin="${LIVECOMMENT_PYTHON:-.venv/bin/python}"

if [[ ! -x "$python_bin" ]]; then
  echo "$python_bin 실행 파일을 찾을 수 없습니다." >&2
  echo "먼저 현재 폴더에서 가상환경을 만들고 필요한 패키지를 설치해주세요." >&2
  echo "예: python3 -m venv .venv" >&2
  echo "예: .venv/bin/python -m pip install -r requirement.txt" >&2
  exit 1
fi

if [[ ! -f client_secret.json ]]; then
  echo "client_secret.json 파일을 찾을 수 없습니다." >&2
  echo "먼저 Google OAuth 클라이언트 JSON 파일을 프로젝트 루트에 client_secret.json 이름으로 저장해주세요." >&2
  exit 1
fi

message_file="${1:-messages.txt}"

if [[ ! -f "$message_file" ]]; then
  echo "$message_file 파일을 찾을 수 없습니다." >&2
  echo "messages.txt.example을 참고해서 메시지 파일을 먼저 만들어주세요." >&2
  echo "예: cp messages.txt.example messages.txt" >&2
  exit 1
fi

printf "video url 입력해주세요. "
IFS= read -r video_url

if [[ -z "${video_url//[[:space:]]/}" ]]; then
  echo "video url이 비어 있습니다." >&2
  exit 1
fi

exec "$python_bin" -m livecomment announce \
  --client-secrets client_secret.json \
  --video "$video_url" \
  --message-file "$message_file" \
  --prefix "후원자업"
