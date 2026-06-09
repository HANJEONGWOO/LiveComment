from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

from .errors import LiveCommentError, YouTubeApiError
from .oauth import (
    DEFAULT_SCOPE,
    TokenStore,
    authorize,
    default_client_secrets_path,
    default_token_path,
    get_access_token,
    load_oauth_client,
    refresh_access_token,
)
from .youtube import LiveChat, YouTubeClient
from .streaming import (
    UpTriggerState,
    build_prefixed_message,
    extract_up_trigger,
    stream_live_chat_messages,
)

MIN_ANNOUNCE_INTERVAL_SECONDS = 120.0
MAX_ANNOUNCE_COUNT = 9876543210


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
    except LiveCommentError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="livecomment",
        description="Send manual messages and bounded announcements to a YouTube live chat.",
    )
    parser.set_defaults(func=lambda args: parser.print_help() or 0)

    shared_auth = argparse.ArgumentParser(add_help=False)
    shared_auth.add_argument(
        "--client-secrets",
        type=Path,
        default=default_client_secrets_path(),
        help="Google OAuth client secrets JSON path.",
    )
    shared_auth.add_argument(
        "--token",
        type=Path,
        default=default_token_path(),
        help="OAuth token cache path.",
    )
    shared_auth.add_argument(
        "--scope",
        default=DEFAULT_SCOPE,
        help="OAuth scope to request.",
    )

    subparsers = parser.add_subparsers(dest="command")

    auth = subparsers.add_parser("auth", parents=[shared_auth], help="Authorize this app.")
    auth.add_argument("--force", action="store_true", help="Run OAuth even if a token exists.")
    auth.set_defaults(func=cmd_auth)

    resolve = subparsers.add_parser(
        "resolve",
        parents=[shared_auth],
        help="Resolve a video URL or ID to its active live chat ID.",
    )
    resolve.add_argument("--video", required=True, help="YouTube live video URL or ID.")
    resolve.set_defaults(func=cmd_resolve)

    send = subparsers.add_parser("send", parents=[shared_auth], help="Send one chat message.")
    add_send_args(send)
    send.set_defaults(func=cmd_send)

    chat = subparsers.add_parser("chat", parents=[shared_auth], help="Open interactive sender.")
    add_send_args(chat, message_required=False)
    chat.add_argument(
        "--cooldown",
        type=float,
        default=7.0,
        help="Minimum seconds between sent messages.",
    )
    chat.set_defaults(func=cmd_chat)

    announce = subparsers.add_parser(
        "announce",
        parents=[shared_auth],
        help="Send a bounded recurring announcement.",
    )
    add_announce_args(announce)
    announce.set_defaults(func=cmd_announce)

    watch_up = subparsers.add_parser(
        "watch-up",
        parents=[shared_auth],
        help="Use streamList to react to chat messages ending with '업'.",
    )
    add_watch_up_args(watch_up)
    watch_up.set_defaults(func=cmd_watch_up)

    return parser


def add_send_args(parser: argparse.ArgumentParser, *, message_required: bool = True) -> None:
    add_target_args(parser)
    parser.add_argument(
        "--message",
        required=message_required,
        help="Message text. If omitted in chat mode, messages are read from stdin.",
    )
    parser.add_argument(
        "--allow-repeat",
        action="store_true",
        help="Allow the exact same message twice in a row.",
    )
    add_message_guard_args(parser)


def add_announce_args(parser: argparse.ArgumentParser) -> None:
    add_target_args(parser)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--message", help="Announcement text.")
    source.add_argument(
        "--message-file",
        type=Path,
        help="Path to a text file with one announcement message per line.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=MIN_ANNOUNCE_INTERVAL_SECONDS,
        help=(
            "Seconds between announcements. "
            f"Default/minimum: {MIN_ANNOUNCE_INTERVAL_SECONDS:.0f}."
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=MAX_ANNOUNCE_COUNT,
        help=f"Number of announcements to send. Default/maximum: {MAX_ANNOUNCE_COUNT}.",
    )
    parser.add_argument(
        "--start-delay",
        type=float,
        default=0.0,
        help="Seconds to wait before the first announcement.",
    )
    add_message_guard_args(parser)


def add_watch_up_args(parser: argparse.ArgumentParser) -> None:
    add_target_args(parser)
    parser.add_argument(
        "--message-file",
        type=Path,
        default=Path("messages.txt"),
        help="Path to a text file with one message suffix per line.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=MIN_ANNOUNCE_INTERVAL_SECONDS,
        help=(
            "Seconds between sent responses. "
            f"Default/minimum: {MIN_ANNOUNCE_INTERVAL_SECONDS:.0f}."
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=MAX_ANNOUNCE_COUNT,
        help=f"Number of responses to send. Default/maximum: {MAX_ANNOUNCE_COUNT}.",
    )
    parser.add_argument(
        "--start-delay",
        type=float,
        default=0.0,
        help="Seconds to wait before sending can start.",
    )
    parser.add_argument(
        "--stream-max-results",
        type=int,
        default=200,
        help="Maximum chat messages per streamList response. Minimum accepted by YouTube: 200.",
    )
    add_message_guard_args(parser)


def add_target_args(parser: argparse.ArgumentParser) -> None:
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--video", help="YouTube live video URL or ID.")
    target.add_argument("--live-chat-id", help="Known YouTube live chat ID.")


def add_message_guard_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--max-length",
        type=int,
        default=200,
        help="Local message length guard. Set to 0 to disable.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve and validate, but do not send.",
    )


def cmd_auth(args: argparse.Namespace) -> int:
    client = load_oauth_client(args.client_secrets)
    token = authorize(
        client,
        TokenStore(args.token),
        scope=args.scope,
        force=args.force,
    )
    scope = token.get("scope", args.scope)
    print(f"Authorized. Token saved to {args.token}")
    print(f"Scope: {scope}")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    youtube = authed_youtube(args)
    chat = youtube.resolve_live_chat(args.video)
    print_live_chat(chat)
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    message = normalize_message(args.message, max_length=args.max_length)
    youtube = authed_youtube(args)
    live_chat_id = resolve_target_chat_id(youtube, args)

    if args.dry_run:
        print(f"Dry run: would send to {live_chat_id}: {message}")
        return 0

    response, youtube = send_text_message_with_auth_retry(args, youtube, live_chat_id, message)
    print_sent(response)
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    youtube = authed_youtube(args)
    live_chat_id = resolve_target_chat_id(youtube, args)

    if args.dry_run:
        print(f"Dry run: ready to send to {live_chat_id}")
        return 0

    print(f"Ready. Sending to live chat {live_chat_id}. Type /quit to exit.")
    last_sent_at = 0.0
    last_message = None

    while True:
        raw = input("> ")
        if raw.strip() in {"/quit", "/exit"}:
            return 0
        if not raw.strip():
            continue

        message = normalize_message(raw, max_length=args.max_length)
        if message == last_message and not args.allow_repeat:
            print("Skipped duplicate message. Use --allow-repeat to allow it.")
            continue

        wait_for_cooldown(last_sent_at, args.cooldown)
        response, youtube = send_text_message_with_auth_retry(args, youtube, live_chat_id, message)
        last_sent_at = time.monotonic()
        last_message = message
        print_sent(response)


def cmd_announce(args: argparse.Namespace) -> int:
    messages = load_announce_messages(
        message=args.message,
        message_file=args.message_file,
        max_length=args.max_length,
    )
    interval, count, start_delay = validate_announce_schedule(
        args.interval,
        args.count,
        args.start_delay,
    )
    youtube = authed_youtube(args)
    live_chat_id = resolve_target_chat_id(youtube, args)

    if args.dry_run:
        preview = messages[0]
        if len(messages) > 1:
            preview = f"{preview} ... (+{len(messages) - 1} more)"
        print(
            "Dry run: would send "
            f"{count} announcement(s) to {live_chat_id} every {interval:.1f}s: {preview}"
        )
        if start_delay:
            print(f"First announcement would wait {start_delay:.1f}s.")
        return 0

    if start_delay:
        print(f"Waiting {start_delay:.1f}s before the first announcement...")
        time.sleep(start_delay)

    print(
        f"Ready. Sending {count} announcement(s) to live chat {live_chat_id} "
        f"every {interval:.1f}s. Press Ctrl+C to stop."
    )
    for index in range(1, count + 1):
        message = messages[(index - 1) % len(messages)]
        print(f"Sending announcement {index}/{count}: {message}")
        response, youtube = send_text_message_with_auth_retry(args, youtube, live_chat_id, message)
        print_sent(response)
        if index < count:
            print(f"Waiting {interval:.1f}s before the next announcement...")
            time.sleep(interval)

    return 0


def cmd_watch_up(args: argparse.Namespace) -> int:
    messages = load_announce_messages(
        message=None,
        message_file=args.message_file,
        max_length=args.max_length,
    )
    interval, count, start_delay = validate_announce_schedule(
        args.interval,
        args.count,
        args.start_delay,
    )
    if args.stream_max_results < 200:
        raise LiveCommentError("streamList max results must be at least 200.")

    youtube = authed_youtube(args)
    live_chat_id = resolve_target_chat_id(youtube, args)

    if args.dry_run:
        print(
            "Dry run: would watch streamList for '*업' messages and send "
            f"{count} response(s) to {live_chat_id} every {interval:.1f}s."
        )
        print(f"Message file: {args.message_file}")
        return 0

    state = UpTriggerState()
    stop_event = threading.Event()
    watcher = threading.Thread(
        target=watch_up_triggers,
        args=(args, live_chat_id, state, stop_event),
        daemon=True,
    )
    watcher.start()

    if start_delay:
        print(f"Waiting {start_delay:.1f}s before sending can start...")
        time.sleep(start_delay)

    print(
        f"Ready. Watching streamList for '*업' messages and sending up to {count} "
        f"response(s) every {interval:.1f}s. Press Ctrl+C to stop."
    )
    sent_count = 0
    try:
        while sent_count < count:
            if stop_event.is_set():
                raise LiveCommentError("streamList watcher stopped.")

            trigger = state.latest_trigger()
            if not trigger:
                print(f"No '*업' trigger seen yet. Waiting {interval:.1f}s...")
                time.sleep(interval)
                continue

            suffix = messages[sent_count % len(messages)]
            try:
                message = build_prefixed_message(trigger, suffix, max_length=args.max_length)
            except LiveCommentError as exc:
                print(f"Skipped response: {exc}")
                time.sleep(interval)
                continue

            print(f"Sending response {sent_count + 1}/{count}: {message}")
            response, youtube = send_text_message_with_auth_retry(args, youtube, live_chat_id, message)
            state.mark_sent(response)
            print_sent(response)
            sent_count += 1
            if sent_count < count:
                print(f"Waiting {interval:.1f}s before the next response...")
                time.sleep(interval)
    finally:
        stop_event.set()

    return 0


def watch_up_triggers(
    args: argparse.Namespace,
    live_chat_id: str,
    state: UpTriggerState,
    stop_event: threading.Event,
) -> None:
    while not stop_event.is_set():
        client = load_oauth_client(args.client_secrets)
        token_store = TokenStore(args.token)
        access_token = get_access_token(client, token_store, scope=args.scope)
        try:
            for chat_message in stream_live_chat_messages(
                access_token=access_token,
                live_chat_id=live_chat_id,
                stop_event=stop_event,
                max_results=args.stream_max_results,
            ):
                if stop_event.is_set():
                    return
                if chat_message.message_id and state.is_sent_message(chat_message.message_id):
                    continue
                trigger = extract_up_trigger(chat_message.text)
                if not trigger:
                    continue
                state.update_trigger(trigger, chat_message.message_id)
                author = chat_message.author_name or "unknown"
                print(f"Detected trigger from {author}: {trigger}")
        except LiveCommentError as exc:
            if stop_event.is_set():
                return
            if is_stream_auth_error(exc):
                print("streamList access token was rejected. Refreshing OAuth token...")
                client = load_oauth_client(args.client_secrets)
                token_store = TokenStore(args.token)
                refresh_access_token(client, token_store, scope=args.scope)
                continue
            print(f"streamList watcher stopped: {exc}", file=sys.stderr)
            stop_event.set()
            return


def authed_youtube(args: argparse.Namespace) -> YouTubeClient:
    client = load_oauth_client(args.client_secrets)
    token_store = TokenStore(args.token)
    access_token = get_access_token(client, token_store, scope=args.scope)
    return YouTubeClient(access_token)


def refresh_youtube(args: argparse.Namespace) -> YouTubeClient:
    client = load_oauth_client(args.client_secrets)
    token_store = TokenStore(args.token)
    access_token = refresh_access_token(client, token_store, scope=args.scope)
    return YouTubeClient(access_token)


def send_text_message_with_auth_retry(
    args: argparse.Namespace,
    youtube: YouTubeClient,
    live_chat_id: str,
    message: str,
) -> tuple[dict[str, object], YouTubeClient]:
    try:
        return youtube.send_text_message(live_chat_id, message), youtube
    except YouTubeApiError as exc:
        if not is_auth_error(exc):
            raise

        print("Access token was rejected. Refreshing OAuth token and retrying once...")
        refreshed_youtube = refresh_youtube(args)
        return refreshed_youtube.send_text_message(live_chat_id, message), refreshed_youtube


def is_auth_error(exc: YouTubeApiError) -> bool:
    return exc.status == 401 or exc.reason == "authError"


def is_stream_auth_error(exc: LiveCommentError) -> bool:
    message = str(exc)
    return "UNAUTHENTICATED" in message or "auth" in message.lower()


def resolve_target_chat_id(youtube: YouTubeClient, args: argparse.Namespace) -> str:
    if args.live_chat_id:
        return str(args.live_chat_id)

    chat = youtube.resolve_live_chat(args.video)
    print_live_chat(chat)
    return chat.live_chat_id


def normalize_message(message: str, *, max_length: int) -> str:
    stripped = message.strip()
    if not stripped:
        raise LiveCommentError("Message is empty.")
    if max_length > 0 and len(stripped) > max_length:
        raise LiveCommentError(
            f"Message is {len(stripped)} characters, over the local limit of {max_length}."
        )
    return stripped


def load_announce_messages(
    *,
    message: str | None,
    message_file: Path | None,
    max_length: int,
) -> list[str]:
    if message is not None:
        return [normalize_message(message, max_length=max_length)]

    if message_file is None:
        raise LiveCommentError("Either --message or --message-file is required.")
    if not message_file.exists():
        raise LiveCommentError(f"Message file not found: {message_file}")
    if not message_file.is_file():
        raise LiveCommentError(f"Message file is not a file: {message_file}")

    messages = []
    with message_file.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                messages.append(normalize_message(stripped, max_length=max_length))
            except LiveCommentError as exc:
                raise LiveCommentError(f"{message_file}:{line_number}: {exc}") from exc

    if not messages:
        raise LiveCommentError(f"Message file has no usable messages: {message_file}")
    return messages


def validate_announce_schedule(interval: float, count: int, start_delay: float) -> tuple[float, int, float]:
    if interval < MIN_ANNOUNCE_INTERVAL_SECONDS:
        raise LiveCommentError(
            f"Announcement interval must be at least {MIN_ANNOUNCE_INTERVAL_SECONDS:.0f} seconds."
        )
    if count < 1:
        raise LiveCommentError("Announcement count must be at least 1.")
    if count > MAX_ANNOUNCE_COUNT:
        raise LiveCommentError(f"Announcement count must be at most {MAX_ANNOUNCE_COUNT}.")
    if start_delay < 0:
        raise LiveCommentError("Start delay cannot be negative.")
    return interval, count, start_delay


def wait_for_cooldown(last_sent_at: float, cooldown: float) -> None:
    if cooldown <= 0 or last_sent_at <= 0:
        return
    elapsed = time.monotonic() - last_sent_at
    remaining = cooldown - elapsed
    if remaining > 0:
        print(f"Waiting {remaining:.1f}s for cooldown...")
        time.sleep(remaining)


def print_live_chat(chat: LiveChat) -> None:
    print(f"Video: {chat.video_id}")
    if chat.title:
        print(f"Title: {chat.title}")
    print(f"Live chat ID: {chat.live_chat_id}")


def print_sent(response: dict[str, object]) -> None:
    message_id = response.get("id", "(no id)")
    snippet = response.get("snippet")
    published_at = None
    if isinstance(snippet, dict):
        published_at = snippet.get("publishedAt")
    if published_at:
        print(f"Sent: {message_id} at {published_at}")
    else:
        print(f"Sent: {message_id}")


if __name__ == "__main__":
    raise SystemExit(main())
