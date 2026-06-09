# LiveComment

터미널에서 YouTube 실시간 방송의 라이브 채팅에 직접 입력한 댓글이나 제한된 반복 공지를 보내는 작은 CLI 프로그램입니다.

이 프로젝트는 사람이 직접 입력한 메시지를 한 번에 하나씩 보내는 용도로 만들었습니다. 스팸, 대량 전송, 계정 전환 자동화, 속도 제한 우회, 차단 우회 같은 기능은 포함하지 않습니다. YouTube API와 채팅 정책을 존중하는 선에서 안전하게 쓰는 것을 목표로 합니다.

## 목차

- [기능 요약](#기능-요약)
- [동작 방식](#동작-방식)
- [준비물](#준비물)
- [Google Cloud 설정](#google-cloud-설정)
- [프로젝트 파일 준비](#프로젝트-파일-준비)
- [처음 인증하기](#처음-인증하기)
- [사용법](#사용법)
- [명령어와 옵션](#명령어와-옵션)
- [환경 변수](#환경-변수)
- [파일과 보안](#파일과-보안)
- [테스트](#테스트)
- [문제 해결](#문제-해결)
- [운영 팁](#운영-팁)
- [공식 문서](#공식-문서)
- [현재 한계](#현재-한계)

## 기능 요약

LiveComment가 하는 일은 다음과 같습니다.

- YouTube 실시간 방송 URL 또는 영상 ID를 입력받습니다.
- YouTube Data API로 해당 영상의 현재 활성 라이브 채팅 ID를 찾습니다.
- Google OAuth 인증을 통해 내 YouTube 계정으로 댓글을 보낼 권한을 얻습니다.
- `send` 명령으로 댓글 하나를 즉시 보냅니다.
- `chat` 명령으로 터미널에서 한 줄씩 입력하며 댓글을 보냅니다.
- `announce` 명령으로 정해진 간격과 횟수만큼 방송 공지를 반복 전송합니다.
- `watch-up` 명령으로 `streamList`를 통해 채팅을 읽고, 다른 사람이 말한 `ㅇㅇ업` 문구에 맞춰 응답을 보냅니다.
- 실수로 같은 댓글을 연속 전송하는 것을 기본적으로 막습니다.
- 대화형 모드에서 기본 쿨다운을 적용해 너무 빠른 연속 전송을 줄입니다.
- 토큰을 로컬 파일에 저장해서 다음 실행부터는 매번 로그인하지 않아도 됩니다.

하지 않는 일도 명확히 해두는 편이 좋습니다.

- 무기한 자동 댓글 반복 전송을 하지 않습니다.
- YouTube 허용량을 탐색하거나 최대 속도에 맞춰 전송하지 않습니다.
- 여러 계정으로 돌아가며 댓글을 보내지 않습니다.
- YouTube의 속도 제한이나 채팅 제한을 우회하지 않습니다.
- 채팅 금지, 슬로우 모드, 구독자 전용 채팅, 회원 전용 채팅 같은 방송 설정을 우회하지 않습니다.
- 라이브 영상 자체를 송출하거나 관리하지 않습니다. 이 도구는 "채팅 메시지 전송"만 다룹니다.

## 동작 방식

전체 흐름은 이렇습니다.

1. 사용자가 YouTube 라이브 영상 URL 또는 영상 ID를 입력합니다.
2. 프로그램이 `videos.list` API를 호출합니다.
3. 응답의 `liveStreamingDetails.activeLiveChatId` 값을 읽습니다.
4. 사용자가 메시지를 입력합니다.
5. 프로그램이 `liveChatMessages.insert` API를 호출해 `textMessageEvent`를 보냅니다.

`announce` 명령은 같은 API를 사용하지만, 사용자가 지정한 `--interval` 간격과 `--count` 횟수만큼만 전송합니다. `--interval`을 생략하면 `MIN_ANNOUNCE_INTERVAL_SECONDS` 값이, `--count`를 생략하면 `MAX_ANNOUNCE_COUNT` 값이 자동으로 사용됩니다. 이것은 방송 공지처럼 합리적인 반복 메시지를 보내기 위한 기능이고, 속도 제한에 가깝게 밀어붙이는 기능은 아닙니다.

`watch-up` 명령은 `liveChatMessages.streamList`로 채팅을 읽습니다. 다른 사람이 `모카업`처럼 `업`으로 끝나는 문구를 말하면, 프로그램은 그 문구를 기억해두고 현재 전송 간격마다 `모카업 + messages.txt의 다음 줄` 형태로 보냅니다.

즉, 실제 댓글 전송은 YouTube 웹페이지를 조작하는 방식이 아니라 공식 YouTube Data API를 사용하는 방식입니다. 그래서 브라우저 자동화보다 안정적이고, 계정 권한도 Google OAuth를 통해 명시적으로 승인합니다.

라이브 채팅 ID는 방송이 현재 라이브 상태이고 채팅이 활성화되어 있을 때만 얻을 수 있습니다. 방송이 예약 상태이거나 이미 종료되었거나 채팅이 꺼져 있으면 `activeLiveChatId`가 나오지 않습니다.

## 준비물

필요한 것은 다음과 같습니다.

- Python 3.11 이상
- Google 계정
- YouTube 채널이 연결된 Google 계정
- Google Cloud 프로젝트
- 사용 설정된 YouTube Data API v3
- Desktop app 유형의 OAuth 클라이언트 JSON 파일
- 현재 라이브 중이고 채팅이 켜져 있는 YouTube 영상

기본 전송 기능은 외부 Python 패키지 없이 동작합니다. 다만 `streamList`를 쓰는 `watch-up` 기능은 gRPC 패키지가 필요합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[stream]'
```

`run.sh`는 기본적으로 현재 폴더의 `.venv/bin/python`을 사용합니다.

Python 버전 확인:

```bash
python3 --version
```

작업 폴더로 이동:

```bash
cd /home/hjw/git/LiveComment
```

## Google Cloud 설정

YouTube API를 쓰려면 Google Cloud에서 OAuth 클라이언트를 만들어야 합니다. 이 과정이 제일 헷갈리는 부분이라 조금 자세히 적어둡니다.

### 1. Google Cloud 프로젝트 만들기 또는 선택

1. Google Cloud Console에 접속합니다.
2. 기존 프로젝트를 선택하거나 새 프로젝트를 만듭니다.
3. 이 프로젝트에서 YouTube Data API v3와 OAuth 클라이언트를 관리합니다.

프로젝트 이름은 아무거나 괜찮습니다. 예를 들면 `LiveComment Local Tool` 정도면 충분합니다.

### 2. YouTube Data API v3 사용 설정

1. Google Cloud Console에서 **APIs & Services**로 이동합니다.
2. **Library**를 엽니다.
3. `YouTube Data API v3`를 검색합니다.
4. **Enable**을 눌러 API를 켭니다.

API를 켜지 않으면 인증이 되어도 YouTube API 호출에서 권한 또는 API 미사용 오류가 납니다.

### 3. OAuth 동의 화면 설정

1. **APIs & Services**의 **OAuth consent screen**으로 이동합니다.
2. 앱 유형을 선택합니다.
   - 개인 계정으로 테스트할 거라면 보통 **External**을 선택합니다.
   - Google Workspace 조직 내부에서만 쓸 거라면 **Internal**을 선택할 수 있습니다.
3. 앱 이름, 사용자 지원 이메일, 개발자 연락처 이메일을 입력합니다.
4. 테스트 단계라면 **Test users**에 실제로 사용할 Google 계정을 추가합니다.

테스트 앱 상태에서는 테스트 사용자로 등록된 계정만 OAuth 인증을 통과할 수 있습니다. 본인 계정으로 인증할 예정이면 본인 이메일을 Test users에 넣어두세요.

OAuth 화면에서 "Google hasn't verified this app" 같은 경고가 보일 수 있습니다. 개인 테스트 앱이라면 고급 옵션을 눌러 계속 진행할 수 있습니다. 공개 서비스로 배포하려면 Google의 앱 검증 절차가 필요할 수 있습니다.

### 4. OAuth 클라이언트 만들기

1. **APIs & Services**의 **Credentials**로 이동합니다.
2. **Create Credentials**를 누릅니다.
3. **OAuth client ID**를 선택합니다.
4. Application type은 **Desktop app**을 선택합니다.
5. 이름을 입력합니다. 예: `LiveComment Desktop`
6. 생성 후 JSON 파일을 다운로드합니다.

다운로드한 JSON 파일에는 `client_id`, `client_secret`, `auth_uri`, `token_uri` 등이 들어 있습니다.

### 5. JSON 파일 배치

다운로드한 파일 이름을 `client_secret.json`으로 바꾸고 프로젝트 루트에 둡니다.

```bash
mv ~/Downloads/client_secret_*.json /home/hjw/git/LiveComment/client_secret.json
```

파일 위치:

```text
/home/hjw/git/LiveComment/client_secret.json
```

이 파일은 비밀 파일입니다. 이미 `.gitignore`에 들어 있어서 Git에는 올라가지 않게 해두었습니다.

## 프로젝트 파일 준비

현재 폴더 구조는 대략 다음과 같습니다.

```text
LiveComment/
├── README.md
├── pyproject.toml
├── livecomment/
│   ├── __main__.py
│   ├── cli.py
│   ├── errors.py
│   ├── http.py
│   ├── oauth.py
│   ├── video.py
│   └── youtube.py
└── tests/
    └── test_video.py
```

바로 실행할 때는 설치가 필요 없습니다.

```bash
python3 -m livecomment --help
```

원한다면 editable install로 `livecomment` 명령을 등록할 수도 있습니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/livecomment --help
```

단, `watch-up`을 쓰려면 gRPC 의존성을 설치해야 합니다. 일반 전송 기능만 쓴다면 `python3 -m livecomment ...` 방식이 가장 단순합니다.

## 처음 인증하기

처음 한 번은 OAuth 인증을 해야 합니다.

```bash
cd /home/hjw/git/LiveComment
python3 -m livecomment auth --client-secrets client_secret.json
```

실행하면 터미널에 Google 인증 URL이 출력되고, 가능한 환경에서는 기본 브라우저가 자동으로 열립니다.

브라우저가 자동으로 열리지 않으면 터미널에 출력된 URL을 직접 복사해서 브라우저 주소창에 붙여 넣으면 됩니다.

인증 흐름은 다음과 같습니다.

1. 프로그램이 로컬 임시 콜백 서버를 `127.0.0.1`에 엽니다.
2. Google OAuth 인증 페이지를 엽니다.
3. 사용자가 Google 계정을 선택하고 권한을 승인합니다.
4. Google이 로컬 콜백 주소로 인증 코드를 돌려줍니다.
5. 프로그램이 인증 코드를 액세스 토큰과 리프레시 토큰으로 교환합니다.
6. 토큰을 `.livecomment/token.json`에 저장합니다.

성공하면 다음과 비슷한 출력이 나옵니다.

```text
Authorized. Token saved to .livecomment/token.json
Scope: https://www.googleapis.com/auth/youtube.force-ssl
```

기본 권한 범위는 다음입니다.

```text
https://www.googleapis.com/auth/youtube.force-ssl
```

이 권한은 YouTube 계정의 댓글/평점/캡션/영상 관련 작업을 포함하는 민감한 범위입니다. 그래서 `client_secret.json`과 `.livecomment/token.json`은 절대 공유하지 마세요.

이미 토큰이 있는데 다시 인증하고 싶다면:

```bash
python3 -m livecomment auth --client-secrets client_secret.json --force
```

## 사용법

### 도움말 보기

전체 명령어:

```bash
python3 -m livecomment --help
```

하위 명령어별 도움말:

```bash
python3 -m livecomment auth --help
python3 -m livecomment resolve --help
python3 -m livecomment send --help
python3 -m livecomment chat --help
python3 -m livecomment announce --help
python3 -m livecomment watch-up --help
```

### 라이브 채팅 ID 확인

먼저 영상 URL에서 현재 활성 라이브 채팅 ID가 잘 나오는지 확인할 수 있습니다.

```bash
python3 -m livecomment resolve \
  --video "https://www.youtube.com/watch?v=VIDEO_ID"
```

또는 영상 ID만 넣을 수도 있습니다.

```bash
python3 -m livecomment resolve --video "VIDEO_ID"
```

성공하면 다음과 비슷하게 출력됩니다.

```text
Video: VIDEO_ID
Title: 방송 제목
Live chat ID: CHAT_ID
```

`Live chat ID`가 나오면 댓글 전송에 필요한 대상 채팅을 찾은 것입니다.

### 댓글 하나 보내기

단건 댓글 전송:

```bash
python3 -m livecomment send \
  --video "https://www.youtube.com/watch?v=VIDEO_ID" \
  --message "안녕하세요!"
```

전송 전에 대상만 확인하고 실제로 보내지 않으려면 `--dry-run`을 붙입니다.

```bash
python3 -m livecomment send \
  --video "https://www.youtube.com/watch?v=VIDEO_ID" \
  --message "안녕하세요!" \
  --dry-run
```

이미 라이브 채팅 ID를 알고 있다면 영상 조회를 건너뛸 수 있습니다.

```bash
python3 -m livecomment send \
  --live-chat-id "CHAT_ID" \
  --message "안녕하세요!"
```

### 대화형으로 댓글 보내기

방송을 보면서 터미널에 한 줄씩 입력하고 싶다면 `chat`을 사용합니다.

```bash
python3 -m livecomment chat \
  --video "https://www.youtube.com/watch?v=VIDEO_ID"
```

실행 후 프롬프트가 뜹니다.

```text
Ready. Sending to live chat CHAT_ID. Type /quit to exit.
> 
```

이제 메시지를 입력하고 Enter를 누르면 전송됩니다.

```text
> 안녕하세요!
Sent: MESSAGE_ID at 2026-06-06T12:34:56.000Z
```

종료:

```text
> /quit
```

또는:

```text
> /exit
```

빈 줄은 무시됩니다.

기본적으로 같은 메시지를 바로 연속해서 보내면 프로그램이 막습니다. 실수로 Enter를 두 번 누르는 상황을 줄이기 위한 장치입니다.

```text
Skipped duplicate message. Use --allow-repeat to allow it.
```

정말 같은 메시지를 연속으로 보내야 한다면:

```bash
python3 -m livecomment chat \
  --video "https://www.youtube.com/watch?v=VIDEO_ID" \
  --allow-repeat
```

대화형 모드에는 기본 7초 쿨다운이 있습니다.

```bash
python3 -m livecomment chat \
  --video "https://www.youtube.com/watch?v=VIDEO_ID" \
  --cooldown 10
```

쿨다운을 끄려면:

```bash
python3 -m livecomment chat \
  --video "https://www.youtube.com/watch?v=VIDEO_ID" \
  --cooldown 0
```

YouTube 자체의 속도 제한은 여전히 적용됩니다. 로컬 쿨다운을 꺼도 YouTube가 메시지를 거절할 수 있습니다.

### 채팅의 `ㅇㅇ업`에 맞춰 응답 보내기

다른 사람이 `모카업`, `초코업`처럼 `업`으로 끝나는 문구를 말하면, 그 문구를 붙여서 응답하려면 `watch-up`을 사용합니다. 이 기능은 `streamList`를 사용하므로 gRPC 의존성이 필요합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[stream]'
```

가장 간단하게 실행하려면 `run.sh`를 사용할 수 있습니다. 실행하면 영상 URL만 물어보고, `messages.txt`에 적힌 각 줄을 순서대로 사용합니다.

처음에는 예시 파일을 복사해서 메시지 파일을 만듭니다.

```bash
cp messages.txt.example messages.txt
```

그 다음 `messages.txt`를 열어서 실제로 보낼 문구를 한 줄에 하나씩 적습니다.

```bash
./run.sh
```

프롬프트:

```text
video url 입력해주세요.
```

`messages.txt` 형식:

```text
# 빈 줄과 #으로 시작하는 줄은 무시됩니다.
채팅 매너를 지켜주세요.
질문은 한 번만 남겨주시면 확인하겠습니다.
방송 관련 공지는 고정 댓글도 확인해주세요.
```

예를 들어 다른 사람이 채팅에 이렇게 말하면:

```text
모카업
```

`messages.txt`의 첫 줄이 `사랑해 ❤❤❤`일 때 프로그램은 현재 인터벌에 맞춰 다음처럼 보냅니다.

```text
모카업 사랑해 ❤❤❤
```

다음 전송 때는 `messages.txt`의 다음 줄을 사용합니다. 채팅에서 새로운 `ㅇㅇ업` 문구가 감지되면 이후 전송부터 그 최신 문구를 사용합니다.

직접 실행:

```bash
python3 -m livecomment watch-up \
  --video "https://www.youtube.com/watch?v=VIDEO_ID" \
  --message-file messages.txt
```

전송 없이 설정만 확인하려면:

```bash
python3 -m livecomment watch-up \
  --video "https://www.youtube.com/watch?v=VIDEO_ID" \
  --message-file messages.txt \
  --dry-run
```

### 정해진 간격으로 공지 보내기

채팅 내용을 읽지 않고 같은 안내 문구를 방송 중 몇 번 반복해서 보내야 한다면 `announce`를 사용합니다.

간격과 횟수를 생략하면 코드에 정의된 기본값이 사용됩니다. 문구 파일을 직접 지정하려면 `--message-file`을 사용합니다.

```bash
python3 -m livecomment announce \
  --video "https://www.youtube.com/watch?v=VIDEO_ID" \
  --message-file messages.txt
```

현재 기본값:

| 항목 | 값 |
| --- | --- |
| `--interval` 기본값 | `MIN_ANNOUNCE_INTERVAL_SECONDS`, 현재 120초 |
| `--count` 기본값 | `MAX_ANNOUNCE_COUNT`, 현재 9876543210회 |

직접 간격과 횟수를 지정할 수도 있습니다.

```bash
python3 -m livecomment announce \
  --video "https://www.youtube.com/watch?v=VIDEO_ID" \
  --message-file messages.txt \
  --interval 300 \
  --count 6
```

위 예시는 `messages.txt`의 문구를 즉시 한 번 보내고, 이후 300초마다 다음 문구를 순환해서 총 6회 전송합니다.

전송 전에 계획만 확인하려면 `--dry-run`을 붙입니다.

```bash
python3 -m livecomment announce \
  --video "https://www.youtube.com/watch?v=VIDEO_ID" \
  --message-file messages.txt \
  --interval 300 \
  --count 6 \
  --dry-run
```

첫 전송도 바로 하지 않고 조금 기다리고 싶다면 `--start-delay`를 사용합니다.

```bash
python3 -m livecomment announce \
  --video "https://www.youtube.com/watch?v=VIDEO_ID" \
  --message-file messages.txt \
  --interval 300 \
  --count 3 \
  --start-delay 60
```

`announce`에는 안전 제한이 있습니다.

| 제한 | 값 |
| --- | --- |
| 최소 반복 간격 | 120초 |
| 최대 반복 횟수 | 9876543210회 |
| 무기한 반복 | 지원하지 않음 |

YouTube가 허용하는 최대치에 가깝게 반복 전송하는 기능은 제공하지 않습니다. 실제 방송 운영에서는 채팅 분위기와 방송자 설정을 고려해 `--interval 300`처럼 넉넉한 간격을 권장합니다.

## 명령어와 옵션

### `auth`

OAuth 인증을 수행하고 토큰을 저장합니다.

```bash
python3 -m livecomment auth [옵션]
```

주요 옵션:

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--client-secrets` | `client_secret.json` | Google OAuth 클라이언트 JSON 파일 경로 |
| `--token` | `.livecomment/token.json` | OAuth 토큰 저장 경로 |
| `--scope` | `https://www.googleapis.com/auth/youtube.force-ssl` | 요청할 OAuth 권한 범위 |
| `--force` | 꺼짐 | 기존 토큰이 있어도 인증을 다시 수행 |

예시:

```bash
python3 -m livecomment auth --force
```

### `resolve`

YouTube 영상 URL 또는 영상 ID에서 활성 라이브 채팅 ID를 찾습니다.

```bash
python3 -m livecomment resolve --video "VIDEO_URL_OR_ID"
```

주요 옵션:

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--video` | 필수 | YouTube 라이브 영상 URL 또는 영상 ID |
| `--client-secrets` | `client_secret.json` | Google OAuth 클라이언트 JSON 파일 경로 |
| `--token` | `.livecomment/token.json` | OAuth 토큰 저장 경로 |

지원하는 입력 예시:

```text
dQw4w9WgXcQ
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/dQw4w9WgXcQ
https://www.youtube.com/live/dQw4w9WgXcQ
https://www.youtube.com/embed/dQw4w9WgXcQ
https://www.youtube.com/shorts/dQw4w9WgXcQ
```

### `send`

댓글 하나를 전송합니다.

```bash
python3 -m livecomment send --video "VIDEO_URL_OR_ID" --message "메시지"
```

또는:

```bash
python3 -m livecomment send --live-chat-id "CHAT_ID" --message "메시지"
```

주요 옵션:

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--video` | `--live-chat-id`와 둘 중 하나 필수 | YouTube 라이브 영상 URL 또는 영상 ID |
| `--live-chat-id` | `--video`와 둘 중 하나 필수 | 이미 알고 있는 라이브 채팅 ID |
| `--message` | 필수 | 보낼 메시지 |
| `--max-length` | `200` | 로컬 메시지 길이 제한. `0`이면 비활성화 |
| `--allow-repeat` | 꺼짐 | 같은 메시지 연속 전송 허용. 단건 모드에서는 큰 의미가 없습니다 |
| `--dry-run` | 꺼짐 | 실제 전송 없이 대상과 메시지만 검증 |
| `--quota-retry-delay` | `900` | `quotaExceeded` 또는 resource 계열 오류 후 재시도 전 대기 시간 |
| `--quota-max-retries` | `0` | quota/resource 오류 재시도 최대 횟수. `0`이면 무제한 |
| `--client-secrets` | `client_secret.json` | Google OAuth 클라이언트 JSON 파일 경로 |
| `--token` | `.livecomment/token.json` | OAuth 토큰 저장 경로 |

메시지 길이 제한은 로컬에서 먼저 막기 위한 장치입니다. 이 제한을 통과해도 YouTube가 자체 기준으로 메시지를 거절할 수 있습니다.

### `chat`

터미널에서 한 줄씩 입력하며 댓글을 보냅니다.

```bash
python3 -m livecomment chat --video "VIDEO_URL_OR_ID"
```

또는:

```bash
python3 -m livecomment chat --live-chat-id "CHAT_ID"
```

주요 옵션:

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--video` | `--live-chat-id`와 둘 중 하나 필수 | YouTube 라이브 영상 URL 또는 영상 ID |
| `--live-chat-id` | `--video`와 둘 중 하나 필수 | 이미 알고 있는 라이브 채팅 ID |
| `--cooldown` | `7.0` | 메시지 전송 사이에 기다릴 최소 초 |
| `--allow-repeat` | 꺼짐 | 같은 메시지 연속 전송 허용 |
| `--max-length` | `200` | 로컬 메시지 길이 제한. `0`이면 비활성화 |
| `--dry-run` | 꺼짐 | 실제 전송 없이 준비 상태만 확인 |
| `--quota-retry-delay` | `900` | `quotaExceeded` 또는 resource 계열 오류 후 재시도 전 대기 시간 |
| `--quota-max-retries` | `0` | quota/resource 오류 재시도 최대 횟수. `0`이면 무제한 |
| `--client-secrets` | `client_secret.json` | Google OAuth 클라이언트 JSON 파일 경로 |
| `--token` | `.livecomment/token.json` | OAuth 토큰 저장 경로 |

대화형 모드에서 사용할 수 있는 입력:

| 입력 | 동작 |
| --- | --- |
| 일반 텍스트 | 해당 텍스트를 라이브 채팅에 전송 |
| 빈 줄 | 무시 |
| `/quit` | 종료 |
| `/exit` | 종료 |

### `announce`

정해진 간격과 횟수만큼 공지 메시지를 보냅니다. `--message-file`을 사용하면 파일 안의 여러 문구를 순서대로 순환 전송합니다.

```bash
python3 -m livecomment announce \
  --video "VIDEO_URL_OR_ID" \
  --message-file messages.txt
```

또는:

```bash
python3 -m livecomment announce \
  --live-chat-id "CHAT_ID" \
  --message-file messages.txt
```

간격과 횟수를 직접 지정하려면:

```bash
python3 -m livecomment announce \
  --video "VIDEO_URL_OR_ID" \
  --message-file messages.txt \
  --interval 300 \
  --count 6
```

주요 옵션:

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--video` | `--live-chat-id`와 둘 중 하나 필수 | YouTube 라이브 영상 URL 또는 영상 ID |
| `--live-chat-id` | `--video`와 둘 중 하나 필수 | 이미 알고 있는 라이브 채팅 ID |
| `--message` | `--message-file`과 둘 중 하나 필수 | 반복해서 보낼 단일 공지 메시지 |
| `--message-file` | `--message`와 둘 중 하나 필수 | 한 줄에 하나씩 적힌 공지 메시지 파일. 빈 줄과 `#` 주석은 무시 |
| `--interval` | `120` | 전송 사이 간격. 기본값과 최소값은 `MIN_ANNOUNCE_INTERVAL_SECONDS` |
| `--count` | `9876543210` | 전송 횟수. 기본값과 최대값은 `MAX_ANNOUNCE_COUNT` |
| `--start-delay` | `0` | 첫 전송 전 대기 시간 |
| `--max-length` | `200` | 로컬 메시지 길이 제한. `0`이면 비활성화 |
| `--dry-run` | 꺼짐 | 실제 전송 없이 계획만 확인 |
| `--quota-retry-delay` | `900` | `quotaExceeded` 또는 resource 계열 오류 후 재시도 전 대기 시간 |
| `--quota-max-retries` | `0` | quota/resource 오류 재시도 최대 횟수. `0`이면 무제한 |
| `--client-secrets` | `client_secret.json` | Google OAuth 클라이언트 JSON 파일 경로 |
| `--token` | `.livecomment/token.json` | OAuth 토큰 저장 경로 |

`announce`는 무기한 실행되지 않습니다. 전송 횟수를 생략하면 `MAX_ANNOUNCE_COUNT`가 사용되며, 지정되거나 기본 적용된 횟수를 모두 보내면 종료됩니다. 중간에 멈추려면 `Ctrl+C`를 누르면 됩니다.

### `watch-up`

`streamList`로 채팅을 읽고, 다른 사람이 말한 `ㅇㅇ업` 문구를 감지해 응답을 보냅니다.

```bash
python3 -m livecomment watch-up \
  --video "VIDEO_URL_OR_ID" \
  --message-file messages.txt
```

동작:

```text
다른 사람 채팅: 모카업
messages.txt 현재 줄: 사랑해 ❤❤❤
내가 보내는 메시지: 모카업 사랑해 ❤❤❤
```

주요 옵션:

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--video` | `--live-chat-id`와 둘 중 하나 필수 | YouTube 라이브 영상 URL 또는 영상 ID |
| `--live-chat-id` | `--video`와 둘 중 하나 필수 | 이미 알고 있는 라이브 채팅 ID |
| `--message-file` | `messages.txt` | 한 줄에 하나씩 적힌 응답 뒷부분 파일 |
| `--interval` | `120` | 응답 전송 사이 간격. 기본값과 최소값은 `MIN_ANNOUNCE_INTERVAL_SECONDS` |
| `--count` | `9876543210` | 전송 횟수. 기본값과 최대값은 `MAX_ANNOUNCE_COUNT` |
| `--start-delay` | `0` | 전송 가능 상태가 되기 전 대기 시간 |
| `--stream-max-results` | `200` | `streamList` 응답당 최대 메시지 수. YouTube 허용 최소값은 200 |
| `--quota-retry-delay` | `900` | `RESOURCE_EXHAUSTED`, `quotaExceeded` 또는 resource 계열 오류 후 재시도 전 대기 시간 |
| `--quota-max-retries` | `0` | quota/resource 오류 재시도 최대 횟수. `0`이면 무제한 |
| `--max-length` | `200` | 로컬 메시지 길이 제한. `ㅇㅇ업` 접두어까지 포함해서 검사 |
| `--dry-run` | 꺼짐 | 실제 전송 없이 설정만 확인 |
| `--client-secrets` | `client_secret.json` | Google OAuth 클라이언트 JSON 파일 경로 |
| `--token` | `.livecomment/token.json` | OAuth 토큰 저장 경로 |

`watch-up`은 `streamList`를 사용하므로 아래 의존성이 필요합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[stream]'
```

채팅 전송 API에서 `quotaExceeded`가 발생하거나, `streamList`에서 `RESOURCE_EXHAUSTED`가 발생하면 기본적으로 900초 기다린 뒤 재시도합니다. 더 길게 기다리려면:

```bash
python3 -m livecomment watch-up \
  --video "VIDEO_URL_OR_ID" \
  --message-file messages.txt \
  --quota-retry-delay 1800
```

## 환경 변수

CLI 옵션 대신 환경 변수로 기본 경로를 지정할 수 있습니다.

| 환경 변수 | 설명 |
| --- | --- |
| `LIVECOMMENT_CLIENT_SECRETS` | 기본 OAuth 클라이언트 JSON 파일 경로 |
| `LIVECOMMENT_TOKEN` | 기본 OAuth 토큰 저장 경로 |

예시:

```bash
export LIVECOMMENT_CLIENT_SECRETS=/home/hjw/git/LiveComment/client_secret.json
export LIVECOMMENT_TOKEN=/home/hjw/git/LiveComment/.livecomment/token.json

python3 -m livecomment chat --video "https://www.youtube.com/watch?v=VIDEO_ID"
```

## 파일과 보안

민감한 파일은 다음 두 가지입니다.

### `client_secret.json`

Google Cloud에서 다운로드한 OAuth 클라이언트 정보입니다.

이 파일이 있다고 해서 바로 계정 접근이 가능한 것은 아니지만, 앱 식별 정보가 들어 있으므로 공개 저장소에 올리지 않는 것이 좋습니다.

### `.livecomment/token.json`

OAuth 인증 후 생성되는 토큰 캐시입니다.

이 파일에는 액세스 토큰과 리프레시 토큰이 저장될 수 있습니다. 리프레시 토큰이 있으면 새 액세스 토큰을 발급받을 수 있으므로 특히 조심해야 합니다.

프로그램은 토큰 파일을 저장할 때 권한을 `600`으로 설정합니다. 그래도 파일 자체를 다른 사람에게 보내거나 공개 저장소에 올리면 안 됩니다.

토큰을 폐기하고 싶다면 파일을 삭제하면 됩니다.

```bash
rm .livecomment/token.json
```

그 다음 다시 인증합니다.

```bash
python3 -m livecomment auth --client-secrets client_secret.json --force
```

Google 계정 보안 페이지에서 앱 권한을 직접 철회할 수도 있습니다.

## 테스트

현재 테스트는 YouTube 영상 URL/ID 파싱, `announce`/`watch-up` 스케줄 제한, `ㅇㅇ업` 패턴 감지, 401 재시도, YouTube API와 streamList quota 재시도 로직을 확인합니다.

```bash
cd /home/hjw/git/LiveComment
python3 -B -m unittest discover -s tests
```

성공하면 다음과 비슷하게 나옵니다.

```text
...............................
----------------------------------------------------------------------
Ran 31 tests in 0.011s

OK
```

CLI 도움말 확인:

```bash
python3 -B -m livecomment --help
python3 -B -m livecomment send --help
python3 -B -m livecomment chat --help
python3 -B -m livecomment announce --help
python3 -B -m livecomment watch-up --help
```

`-B` 옵션은 Python이 `__pycache__` 파일을 만들지 않도록 하는 옵션입니다. 테스트에는 필수는 아니지만 작업 폴더를 깔끔하게 유지하는 데 좋습니다.

## 문제 해결

### `OAuth client secrets file not found`

예시:

```text
Error: OAuth client secrets file not found: client_secret.json
```

원인:

- `client_secret.json` 파일이 현재 폴더에 없습니다.
- 파일 이름이 다릅니다.
- 다른 경로에 두었는데 `--client-secrets`를 지정하지 않았습니다.

해결:

```bash
python3 -m livecomment auth \
  --client-secrets /정확한/경로/client_secret.json
```

또는 파일을 프로젝트 루트로 옮깁니다.

```bash
mv /정확한/경로/client_secret.json /home/hjw/git/LiveComment/client_secret.json
```

### 브라우저가 자동으로 열리지 않음

프로그램은 `webbrowser.open()`으로 브라우저를 열려고 시도합니다. 서버 환경, WSL, 원격 SSH 환경에서는 자동으로 안 열릴 수 있습니다.

해결:

- 터미널에 출력된 긴 Google OAuth URL을 복사합니다.
- 직접 브라우저 주소창에 붙여 넣습니다.
- 인증을 완료합니다.

로컬 콜백 주소가 `127.0.0.1`이므로, 프로그램이 실행 중인 같은 머신의 브라우저에서 여는 것이 가장 안정적입니다.

### `Timed out waiting for OAuth callback`

인증 URL을 열지 않았거나, 5분 안에 인증을 끝내지 못했거나, 콜백이 프로그램으로 돌아오지 못한 경우입니다.

해결:

```bash
python3 -m livecomment auth --client-secrets client_secret.json --force
```

다시 실행하고 인증을 끝까지 진행합니다.

### `This video does not have an active live chat`

예시:

```text
Error: This video does not have an active live chat. It may not be live, chat may be disabled, or the broadcast may have ended.
```

가능한 원인:

- 영상이 현재 라이브가 아닙니다.
- 방송이 아직 시작하지 않았습니다.
- 방송이 이미 끝났습니다.
- 라이브 채팅이 비활성화되어 있습니다.
- 채팅이 리플레이 상태일 뿐, 현재 활성 라이브 채팅이 아닙니다.
- YouTube가 해당 영상에 `activeLiveChatId`를 제공하지 않는 상태입니다.

확인:

```bash
python3 -m livecomment resolve --video "VIDEO_URL_OR_ID"
```

라이브 중인 다른 영상으로도 테스트해 보세요.

### `liveChatDisabled`

YouTube API가 채팅 비활성화 상태라고 응답한 것입니다.

해결:

- 방송 채팅이 켜져 있는지 확인합니다.
- 방송자가 채팅을 꺼둔 경우 이 프로그램으로 보낼 수 없습니다.

### `liveChatEnded`

라이브 채팅이 이미 종료된 상태입니다.

해결:

- 현재 진행 중인 라이브 영상인지 확인합니다.
- 종료된 방송의 채팅 리플레이에는 새 메시지를 보낼 수 없습니다.

### `forbidden`

권한이 부족하거나 계정/방송 설정 때문에 전송할 수 없는 상태입니다.

가능한 원인:

- OAuth 인증한 계정이 YouTube 채팅을 사용할 수 없는 상태입니다.
- 방송 채팅 조건을 충족하지 않습니다.
- 구독자 전용, 회원 전용, 슬로우 모드, 차단, 제한 모드 등이 걸려 있습니다.
- OAuth 범위가 충분하지 않습니다.
- 앱이 테스트 모드인데 현재 계정이 Test users에 없습니다.

해결:

- 브라우저에서 같은 계정으로 해당 방송 채팅에 직접 댓글을 달 수 있는지 확인합니다.
- Google Cloud OAuth consent screen의 Test users에 계정이 들어 있는지 확인합니다.
- 다시 인증합니다.

```bash
python3 -m livecomment auth --client-secrets client_secret.json --force
```

### `rateLimitExceeded`

YouTube가 너무 빠르거나 많은 메시지 전송으로 판단한 것입니다.

해결:

- `chat` 모드의 `--cooldown` 값을 늘립니다.
- `announce` 모드라면 `--interval` 값을 늘립니다.
- 잠시 기다린 뒤 다시 시도합니다.
- 같은 메시지를 반복해서 보내지 않습니다.

예:

```bash
python3 -m livecomment chat \
  --video "VIDEO_URL_OR_ID" \
  --cooldown 15
```

공지 반복이라면:

```bash
python3 -m livecomment announce \
  --video "VIDEO_URL_OR_ID" \
  --message-file messages.txt \
  --interval 300 \
  --count 3
```

### `messageTextInvalid`

YouTube가 메시지 내용을 유효하지 않다고 판단한 것입니다.

가능한 원인:

- 메시지가 너무 깁니다.
- 허용되지 않는 문자나 형식이 포함되어 있습니다.
- YouTube 채팅 정책상 거절되는 내용입니다.

해결:

- 메시지를 짧고 평범한 텍스트로 바꿔 테스트합니다.
- `--max-length`를 낮춰 실수를 줄입니다.

```bash
python3 -m livecomment send \
  --video "VIDEO_URL_OR_ID" \
  --message "테스트 메시지" \
  --max-length 100
```

### `401 authError`

예시:

```text
Error: YouTube API error 401 authError: Request had invalid authentication credentials.
```

Access token이 만료되었거나 Google이 기존 토큰을 거절한 상태입니다. 장시간 `announce`를 실행하거나, 여러 터미널에서 동시에 실행하면서 한쪽에서 재인증/토큰 갱신이 일어나면 만날 수 있습니다.

현재 코드는 전송 중 401이 발생하면 OAuth 토큰을 강제로 갱신하고 같은 메시지를 한 번 재시도합니다. 그래도 같은 오류가 반복되면 토큰 파일을 삭제하고 다시 인증하세요.

```bash
rm .livecomment/token.json
python3 -m livecomment auth --client-secrets client_secret.json --force
```

그 뒤 프로그램을 다시 실행합니다. 동시에 여러 개를 띄울 때는 같은 `.livecomment/token.json`을 공유한다는 점도 기억해두세요.

### `invalid_grant`

OAuth 토큰이 만료, 폐기, 불일치 상태일 때 발생할 수 있습니다.

해결:

```bash
rm .livecomment/token.json
python3 -m livecomment auth --client-secrets client_secret.json --force
```

그 뒤 다시 실행합니다.

### API 할당량 문제

YouTube Data API에는 프로젝트별 할당량이 있습니다. 댓글 전송과 영상 조회는 API 호출을 소비합니다.

해결:

- 불필요한 반복 실행을 줄입니다.
- `--live-chat-id`를 사용하면 이미 알고 있는 채팅 ID에 대해 영상 조회를 건너뛸 수 있습니다.
- Google Cloud Console에서 YouTube Data API quota 상태를 확인합니다.

예:

```bash
python3 -m livecomment resolve --video "VIDEO_URL_OR_ID"

python3 -m livecomment chat --live-chat-id "위에서_확인한_CHAT_ID"
```

## 운영 팁

- 처음에는 `resolve`로 대상 라이브 채팅 ID가 잘 나오는지 확인하세요.
- 실제 전송 전에는 `send --dry-run`으로 한 번 확인하세요.
- 반복 공지는 `announce --dry-run`으로 계획을 먼저 확인하세요.
- 장시간 실행할 때는 `--quota-retry-delay`를 넉넉하게 잡아 quota/resource 오류 후 바로 재시도하지 않게 하세요.
- 방송 채팅이 느린 모드라면 `--cooldown`을 방송 설정보다 넉넉하게 잡으세요.
- 공지 반복은 `--interval 300` 이상처럼 충분히 드문 간격을 권장합니다.
- 같은 메시지를 반복해서 보내면 YouTube가 제한할 수 있습니다.
- 장시간 사용할 때는 터미널에 표시되는 오류를 확인하면서 운용하세요.
- 토큰 파일을 백업하거나 공유하지 마세요.

## 공식 문서

이 프로젝트가 사용하는 주요 YouTube/Google API 문서입니다.

- YouTube Live Streaming API `liveChatMessages.insert`  
  https://developers.google.com/youtube/v3/live/docs/liveChatMessages/insert

- YouTube Live Streaming API `liveChatMessages.streamList`  
  https://developers.google.com/youtube/v3/live/docs/liveChatMessages/streamList

- YouTube Streaming Live Chat guide  
  https://developers.google.com/youtube/v3/live/streaming-live-chat

- YouTube Data API `videos` 리소스  
  https://developers.google.com/youtube/v3/docs/videos

- YouTube Data API OAuth 2.0 for Mobile & Desktop Apps  
  https://developers.google.com/youtube/v3/guides/auth/installed-apps

핵심 필드와 메서드:

- `videos.list`
- `liveStreamingDetails.activeLiveChatId`
- `liveChatMessages.insert`
- `liveChatMessages.streamList`
- `snippet.type = textMessageEvent`
- `snippet.textMessageDetails.messageText`

## 현재 한계

- GUI는 없습니다. 터미널 CLI만 제공합니다.
- 라이브 채팅 읽기는 `watch-up`의 `streamList` 기반 패턴 감지 용도로만 제공합니다.
- `announce`는 제한된 반복 공지만 지원합니다. 무기한 반복이나 최대 속도 전송은 지원하지 않습니다.
- 정교한 예약 전송 기능은 없습니다. 첫 전송 전 대기 시간은 `--start-delay`로만 지정할 수 있습니다.
- YouTube가 거절한 메시지를 우회해서 보내는 기능은 없습니다.
- OAuth 앱 검증이나 Google Cloud 프로젝트 생성 자체를 자동화하지 않습니다.

필요하다면 다음 단계로는 라이브 채팅 읽기, 간단한 데스크톱 UI, 자주 쓰는 문구 목록, 전송 전 확인 프롬프트 같은 기능을 붙일 수 있습니다.
