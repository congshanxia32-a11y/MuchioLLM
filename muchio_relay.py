"""Optional Supabase Realtime relay for Muchio-to-Muchio conversations.

The relay is deliberately independent from the main Muchio loop.  It uses an
async Supabase client in a daemon thread, while the main loop communicates via
thread-safe queues.  When the feature is disabled, or when supabase-py is not
installed, the rest of MuchioLLM remains usable.
"""
from __future__ import annotations

import asyncio
import queue
import re
import threading
import time
import uuid
from typing import Any, Callable, Dict, Iterable, Optional

try:
    from supabase import acreate_client
except ImportError:  # Optional dependency: setup without peer chat still works.
    acreate_client = None


MAX_TEXT = 512
MAX_ROOM = 120
MAX_QUEUE = 32
ROOM_RE = re.compile(r"^[A-Za-z0-9_-]{8,120}$")


def make_sender_id() -> str:
    """Return a per-process identifier; it is not a user/account identifier."""
    return uuid.uuid4().hex[:16]


def make_message(text: str, sender_id: str, conversation_id: str,
                 turn: int) -> Dict[str, Any]:
    return {
        "type": "peer_reply",
        "version": 1,
        "message_id": uuid.uuid4().hex,
        "sender_id": str(sender_id),
        "conversation_id": str(conversation_id),
        "text": str(text).strip()[:MAX_TEXT],
        "turn": int(turn),
    }


def validate_settings(cfg: Dict[str, Any]) -> Optional[str]:
    """Return a user-facing error, or None when relay settings are usable."""
    url = str(cfg.get("peer_supabase_url") or "").strip()
    key = str(cfg.get("peer_supabase_key") or "").strip()
    room = str(cfg.get("peer_room") or "").strip()
    if not url or not key or not room:
        return "Supabase URL・公開キー・ルームコードを入力してください"
    if not (url.startswith("https://") and "." in url):
        return "Supabase URLが正しくありません"
    if "service_role" in key.lower():
        return "service_roleキーは使わず、公開キーを入力してください"
    if not ROOM_RE.fullmatch(room):
        return "ルームコードは英数字・_・-の8〜120文字にしてください"
    return None


def _unwrap_event(event: Any) -> Any:
    """Supabase callback payloads wrap the application payload in ``payload``."""
    if isinstance(event, dict) and isinstance(event.get("payload"), dict):
        return event["payload"]
    return event


def validate_message(event: Any, self_id: str, max_turns: int) -> Optional[Dict[str, Any]]:
    """Validate and normalize an incoming Broadcast application message."""
    event = _unwrap_event(event)
    if not isinstance(event, dict):
        return None
    if event.get("type") != "peer_reply" or event.get("version") != 1:
        return None
    sender = str(event.get("sender_id") or "")
    if not sender or sender == self_id:
        return None
    message_id = str(event.get("message_id") or "")
    conversation_id = str(event.get("conversation_id") or "")
    text = str(event.get("text") or "").strip()
    if not message_id or not conversation_id or not text or len(text) > MAX_TEXT:
        return None
    try:
        turn = int(event.get("turn"))
    except (TypeError, ValueError):
        return None
    if turn < 0 or turn > max(1, int(max_turns)):
        return None
    return {
        "type": "peer_reply",
        "version": 1,
        "message_id": message_id,
        "sender_id": sender,
        "conversation_id": conversation_id,
        "text": text,
        "turn": turn,
        "received_at": time.time(),
    }


class PeerRelay:
    """Thread-safe facade around Supabase Realtime Broadcast."""

    def __init__(self, get_config: Callable[[], Dict[str, Any]],
                 logger: Optional[Callable[[str], None]] = None):
        self._get_config = get_config
        self._log = logger or (lambda _msg: None)
        self.sender_id = make_sender_id()
        self._incoming: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=MAX_QUEUE)
        self._outgoing: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=MAX_QUEUE)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._status_lock = threading.Lock()
        self._status: Dict[str, Any] = {
            "state": "disabled",
            "detail": "Muchio間通信はOFFです",
            "sender_id": self.sender_id,
        }
        self._seen_ids = set()
        self._seen_lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._thread_main,
                                        name="MuchioPeerRelay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def status(self) -> Dict[str, Any]:
        with self._status_lock:
            return dict(self._status)

    def publish(self, text: str, conversation_id: str, turn: int) -> bool:
        """Queue one generated reply for sending.  Never blocks the main loop."""
        cfg = self._snapshot()
        if not cfg.get("peer_enabled") or validate_settings(cfg):
            return False
        try:
            turn = int(turn)
        except (TypeError, ValueError):
            return False
        payload = make_message(text, self.sender_id, conversation_id, turn)
        if not payload["text"] or len(payload["text"]) > MAX_TEXT or turn < 0:
            return False
        try:
            self._outgoing.put_nowait(payload)
            return True
        except queue.Full:
            self._log("Muchio間通信: 送信待ちが満杯なので古い発言を破棄しました")
            return False

    def poll(self, limit: int = 8) -> list[Dict[str, Any]]:
        out = []
        for _ in range(max(0, int(limit))):
            try:
                out.append(self._incoming.get_nowait())
            except queue.Empty:
                break
        return out

    def _set_status(self, state: str, detail: str) -> None:
        with self._status_lock:
            self._status.update({"state": state, "detail": detail})

    def _snapshot(self) -> Dict[str, Any]:
        try:
            cfg = self._get_config() or {}
            return dict(cfg)
        except Exception as exc:
            self._log(f"Muchio間通信: 設定を読めません: {exc}")
            return {}

    @staticmethod
    def _signature(cfg: Dict[str, Any]) -> tuple[Any, ...]:
        return (
            bool(cfg.get("peer_enabled")),
            str(cfg.get("peer_supabase_url") or "").strip(),
            str(cfg.get("peer_supabase_key") or "").strip(),
            str(cfg.get("peer_room") or "").strip(),
        )

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._async_main())
        except Exception as exc:
            self._set_status("error", f"中継スレッド: {exc}")
            self._log(f"Muchio間通信: 中継スレッドが終了しました: {exc}")

    async def _async_main(self) -> None:
        while not self._stop.is_set():
            cfg = self._snapshot()
            if not cfg.get("peer_enabled"):
                self._set_status("disabled", "Muchio間通信はOFFです")
                await asyncio.sleep(0.5)
                continue
            if acreate_client is None:
                self._set_status("missing_dependency", "supabaseパッケージがありません。setup.batを実行してください")
                await asyncio.sleep(5.0)
                continue
            error = validate_settings(cfg)
            if error:
                self._set_status("invalid", error)
                await asyncio.sleep(1.0)
                continue
            try:
                await self._run_session(cfg, self._signature(cfg))
            except Exception as exc:
                if not self._stop.is_set():
                    self._set_status("error", f"接続エラー: {exc}")
                    self._log(f"Muchio間通信: {exc}")
                    await asyncio.sleep(3.0)

    async def _run_session(self, cfg: Dict[str, Any], signature: tuple[Any, ...]) -> None:
        self._set_status("connecting", "Supabaseへ接続中です")
        client = await asyncio.wait_for(
            acreate_client(str(cfg["peer_supabase_url"]).strip(),
                           str(cfg["peer_supabase_key"]).strip()),
            timeout=20.0,
        )
        room = str(cfg["peer_room"]).strip()
        channel = client.channel(f"muchio:{room}")

        def on_broadcast(event: Any) -> None:
            try:
                max_turns = max(1, int(float(cfg.get("peer_max_turns", 8))))
            except (TypeError, ValueError):
                max_turns = 8
            msg = validate_message(event, self.sender_id, max_turns)
            if not msg:
                return
            with self._seen_lock:
                if msg["message_id"] in self._seen_ids:
                    return
                self._seen_ids.add(msg["message_id"])
                if len(self._seen_ids) > 512:
                    self._seen_ids = set(list(self._seen_ids)[-256:])
            try:
                self._incoming.put_nowait(msg)
            except queue.Full:
                self._log("Muchio間通信: 受信待ちが満杯なので発言を破棄しました")

        channel = channel.on_broadcast(event="peer_reply", callback=on_broadcast)
        await asyncio.wait_for(channel.subscribe(), timeout=20.0)
        self._set_status("connected", f"ルーム「{room}」に接続中です")
        try:
            while not self._stop.is_set():
                if self._signature(self._snapshot()) != signature:
                    return
                while True:
                    try:
                        payload = self._outgoing.get_nowait()
                    except queue.Empty:
                        break
                    await channel.send_broadcast("peer_reply", payload)
                await asyncio.sleep(0.25)
        finally:
            try:
                await client.remove_channel(channel)
            except Exception:
                pass
