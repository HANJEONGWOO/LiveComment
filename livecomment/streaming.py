from __future__ import annotations

import importlib
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Iterator

from .errors import LiveCommentError

GRPC_TARGET = "dns:///youtube.googleapis.com:443"
PROTO_DIR = Path(__file__).resolve().parent / "grpc"
PROTO_PATH = PROTO_DIR / "stream_list.proto"
GENERATED_DIR = Path(".livecomment") / "grpc_gen"
UP_TRIGGER_RE = re.compile(r"([0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ]{1,30}업)")


@dataclass(frozen=True)
class StreamChatMessage:
    message_id: str
    text: str
    author_name: str | None = None
    author_channel_id: str | None = None
    published_at: str | None = None


class StreamListError(LiveCommentError):
    def __init__(self, code: str, details: str) -> None:
        self.code = code
        self.details = details
        super().__init__(f"streamList failed: {code}: {details}")


class UpTriggerState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest_trigger: str | None = None
        self._latest_message_id: str | None = None
        self._sent_message_ids: set[str] = set()

    def update_trigger(self, trigger: str, message_id: str) -> None:
        with self._lock:
            self._latest_trigger = trigger
            self._latest_message_id = message_id

    def latest_trigger(self) -> str | None:
        with self._lock:
            return self._latest_trigger

    def mark_sent(self, response: dict[str, object]) -> None:
        message_id = response.get("id")
        if not isinstance(message_id, str) or not message_id:
            return
        with self._lock:
            self._sent_message_ids.add(message_id)

    def is_sent_message(self, message_id: str) -> bool:
        with self._lock:
            return message_id in self._sent_message_ids


def extract_up_trigger(text: str) -> str | None:
    matches = UP_TRIGGER_RE.findall(text)
    if not matches:
        return None
    return matches[-1]


def build_prefixed_message(trigger: str, message: str, *, max_length: int) -> str:
    trigger = trigger.strip()
    message = message.strip()
    if not trigger:
        raise LiveCommentError("Trigger text is empty.")
    if not message:
        raise LiveCommentError("Message is empty.")

    combined = f"{trigger} {message}"
    if max_length > 0 and len(combined) > max_length:
        raise LiveCommentError(
            f"Prefixed message is {len(combined)} characters, over the local limit of {max_length}."
        )
    return combined


def stream_live_chat_messages(
    *,
    access_token: str,
    live_chat_id: str,
    stop_event: threading.Event,
    max_results: int = 200,
    reconnect_delay: float = 3.0,
) -> Iterator[StreamChatMessage]:
    grpc, pb2, pb2_grpc = load_stream_modules()
    metadata = (("authorization", "Bearer " + access_token),)
    next_page_token = ""

    while not stop_event.is_set():
        credentials = grpc.ssl_channel_credentials()
        with grpc.secure_channel(GRPC_TARGET, credentials) as channel:
            stub = pb2_grpc.V3DataLiveChatMessageServiceStub(channel)
            request = pb2.LiveChatMessageListRequest(
                live_chat_id=live_chat_id,
                part=["snippet", "authorDetails"],
                max_results=max_results,
                page_token=next_page_token,
            )
            try:
                for response in stub.StreamList(request, metadata=metadata):
                    if stop_event.is_set():
                        return
                    if response.next_page_token:
                        next_page_token = response.next_page_token
                    for item in response.items:
                        message = stream_message_from_proto(item)
                        if message:
                            yield message
            except grpc.RpcError as exc:
                raise StreamListError(exc.code().name, exc.details() or "") from exc

        if not next_page_token:
            return
        time.sleep(reconnect_delay)


def stream_message_from_proto(item: object) -> StreamChatMessage | None:
    snippet = getattr(item, "snippet", None)
    if snippet is None:
        return None

    text_details = getattr(snippet, "text_message_details", None)
    text = ""
    if text_details is not None:
        text = getattr(text_details, "message_text", "") or ""
    if not text:
        text = getattr(snippet, "display_message", "") or ""
    text = text.strip()
    if not text:
        return None

    author = getattr(item, "author_details", None)
    return StreamChatMessage(
        message_id=str(getattr(item, "id", "") or ""),
        text=text,
        author_name=getattr(author, "display_name", None) if author else None,
        author_channel_id=getattr(author, "channel_id", None) if author else None,
        published_at=getattr(snippet, "published_at", None),
    )


def load_stream_modules() -> tuple[ModuleType, ModuleType, ModuleType]:
    try:
        import grpc
    except ImportError as exc:
        raise LiveCommentError(stream_dependency_message()) from exc

    ensure_generated_stream_modules()
    generated_path = str(GENERATED_DIR.resolve())
    if generated_path not in sys.path:
        sys.path.insert(0, generated_path)

    return (
        grpc,
        importlib.import_module("stream_list_pb2"),
        importlib.import_module("stream_list_pb2_grpc"),
    )


def ensure_generated_stream_modules() -> None:
    pb2 = GENERATED_DIR / "stream_list_pb2.py"
    pb2_grpc = GENERATED_DIR / "stream_list_pb2_grpc.py"
    if (
        pb2.exists()
        and pb2_grpc.exists()
        and pb2.stat().st_mtime >= PROTO_PATH.stat().st_mtime
        and pb2_grpc.stat().st_mtime >= PROTO_PATH.stat().st_mtime
    ):
        return

    try:
        import grpc_tools
        from grpc_tools import protoc
    except ImportError as exc:
        raise LiveCommentError(stream_dependency_message()) from exc

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    proto_include = Path(grpc_tools.__file__).resolve().parent / "_proto"
    result = protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{PROTO_DIR}",
            f"-I{proto_include}",
            f"--python_out={GENERATED_DIR}",
            f"--grpc_python_out={GENERATED_DIR}",
            str(PROTO_PATH),
        ]
    )
    if result != 0:
        raise LiveCommentError("Failed to generate streamList gRPC Python modules.")


def stream_dependency_message() -> str:
    return (
        "streamList mode requires grpcio, grpcio-tools, and protobuf. "
        "Install them with: python3 -m pip install -e '.[stream]'"
    )
