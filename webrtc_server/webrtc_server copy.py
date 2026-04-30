#!/usr/bin/env python3
"""
WebSocket signaling server + aiortc-based WebRTC relay + gravação no servidor.

Garante:
- Transmissão em tempo real (Sender -> Server -> vários Viewers)
- Gravação simultânea no servidor
- Retenção de 4 horas (limpeza automática)
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import websockets
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCIceCandidate, RTCSessionDescription
from aiortc.contrib.media import MediaRecorder, MediaRelay

# -------------------------
# Configuração
# -------------------------
HOST = "0.0.0.0"
PORT = 9000

# Guardar dentro da pasta da API (API/videos)
API_DIR = Path(__file__).resolve().parents[1]
RECORDINGS_DIR = API_DIR / "videos"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Retenção: 4 horas
RETENTION_SECONDS = 4 * 60 * 60
CLEANUP_INTERVAL_SECONDS = 10 * 60

# Formato de gravação (mkv é mais resiliente em quedas)
RECORDING_CONTAINER = "mkv"  # "mkv" | "mp4"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc-server")

relay = MediaRelay()

# room_id -> {"pc": RTCPeerConnection, "track": MediaStreamTrack|None, "recorder": MediaRecorder|None, "stamp": str}
ROOM_SENDERS: Dict[str, Dict[str, Any]] = {}
VIEWERS: Dict[Any, Dict[str, Any]] = {}


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


async def cleanup_old_recordings() -> None:
    """
    Remove ficheiros em RECORDINGS_DIR cujo mtime seja mais antigo que RETENTION_SECONDS.
    """
    import time as _time

    while True:
        try:
            cutoff = _time.time() - RETENTION_SECONDS
            deleted = 0
            for entry in RECORDINGS_DIR.iterdir():
                try:
                    if not entry.is_file():
                        continue
                    if entry.suffix.lower() not in {".mp4", ".mkv"}:
                        continue
                    if entry.stat().st_mtime < cutoff:
                        entry.unlink(missing_ok=True)
                        deleted += 1
                except Exception:
                    logger.exception("Falha ao avaliar/remover ficheiro antigo: %s", entry)
            if deleted:
                logger.info("Cleanup: removidos %s ficheiro(s) antigo(s) (> %ss)", deleted, RETENTION_SECONDS)
        except Exception:
            logger.exception("Cleanup loop falhou (vai tentar de novo)")

        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


def candidate_to_json(candidate: RTCIceCandidate) -> dict:
    return {
        "candidate": candidate.candidate,
        "sdpMid": candidate.sdpMid,
        "sdpMLineIndex": candidate.sdpMLineIndex,
    }


def parse_sdp_candidate(sdp: str) -> Dict[str, Any]:
    parts = sdp.split()
    if len(parts) < 8:
        raise ValueError(f"SDP candidate inválido: {sdp!r}")
    if ":" not in parts[0]:
        raise ValueError(f"SDP candidate inválido (sem prefixo): {sdp!r}")

    foundation = parts[0].split(":", 1)[1]
    component = int(parts[1])
    protocol = parts[2].lower()
    priority = int(parts[3])
    ip = parts[4]
    port = int(parts[5])
    cand_type = parts[7]

    related_address = None
    related_port = None
    tcp_type = None

    if "raddr" in parts:
        related_address = parts[parts.index("raddr") + 1]
    if "rport" in parts:
        related_port = int(parts[parts.index("rport") + 1])
    if "tcptype" in parts:
        tcp_type = parts[parts.index("tcptype") + 1]

    return {
        "foundation": foundation,
        "component": component,
        "protocol": protocol,
        "priority": priority,
        "ip": ip,
        "port": port,
        "type": cand_type,
        "relatedAddress": related_address,
        "relatedPort": related_port,
        "tcpType": tcp_type,
    }


def to_ice_candidate(payload: Dict[str, Any]) -> RTCIceCandidate:
    cand = payload.get("candidate")
    if not isinstance(cand, str):
        raise ValueError("candidate.candidate tem de ser string")

    parsed = parse_sdp_candidate(cand)
    return RTCIceCandidate(
        component=parsed["component"],
        foundation=parsed["foundation"],
        ip=parsed["ip"],
        port=parsed["port"],
        priority=parsed["priority"],
        protocol=parsed["protocol"],
        type=parsed["type"],
        relatedAddress=parsed["relatedAddress"],
        relatedPort=parsed["relatedPort"],
        sdpMid=payload.get("sdpMid"),
        sdpMLineIndex=payload.get("sdpMLineIndex"),
        tcpType=parsed["tcpType"],
    )


# -------------------------
# Sender
# -------------------------
async def handle_sender_offer(ws: Any, data: dict):
    room_id = data.get("room_id", "default")
    sdp = data.get("sdp")
    if not sdp:
        await ws.send(json.dumps({"error": "missing_sdp"}))
        return

    existing = ROOM_SENDERS.get(room_id)
    if existing:
        logger.info("Replacing existing sender for room %s", room_id)
        try:
            rec = existing.get("recorder")
            if rec:
                await rec.stop()
        except Exception:
            logger.exception("Error stopping previous recorder for room %s", room_id)

        try:
            pc_old = existing.get("pc")
            if pc_old:
                await pc_old.close()
        except Exception:
            logger.exception("Error closing previous sender pc for room %s", room_id)

        ROOM_SENDERS.pop(room_id, None)

    pc = RTCPeerConnection()
    pc_id = f"sender-{room_id}-{uuid.uuid4().hex[:8]}"
    logger.info("Created RTCPeerConnection for sender %s (room=%s)", pc_id, room_id)

    @pc.on("track")
    def on_track(track: MediaStreamTrack):
        logger.info("Sender on_track room=%s kind=%s id=%s", room_id, track.kind, track.id)
        if track.kind != "video":
            return

        stamp = utc_stamp()
        ext = ".mkv" if RECORDING_CONTAINER.lower() == "mkv" else ".mp4"
        out_path = RECORDINGS_DIR / f"{room_id}_{stamp}{ext}"

        ROOM_SENDERS[room_id] = {"pc": pc, "track": track, "recorder": None, "stamp": stamp}

        if ext == ".mp4":
            recorder = MediaRecorder(
                str(out_path),
                format="mp4",
                options={"movflags": "frag_keyframe+empty_moov+default_base_moof"},
            )
        else:
            recorder = MediaRecorder(str(out_path), format="matroska")

        recorder.addTrack(track)

        async def start_recorder():
            try:
                await recorder.start()
                ROOM_SENDERS[room_id]["recorder"] = recorder
                logger.info("Recorder started room=%s -> %s", room_id, out_path)
            except Exception:
                logger.exception("Failed to start recorder room=%s", room_id)

        asyncio.create_task(start_recorder())

        @track.on("ended")
        async def on_ended():
            logger.info("Sender track ended room=%s", room_id)
            info = ROOM_SENDERS.pop(room_id, None)
            if not info:
                return

            rec = info.get("recorder")
            pc_local = info.get("pc")

            if rec:
                try:
                    await rec.stop()
                except Exception:
                    logger.exception("Error stopping recorder room=%s", room_id)

            if pc_local:
                try:
                    await pc_local.close()
                except Exception:
                    logger.exception("Error closing sender pc room=%s", room_id)

    @pc.on("icecandidate")
    async def on_icecandidate(candidate: Optional[RTCIceCandidate]):
        if candidate is None:
            return
        try:
            await ws.send(json.dumps({"type": "candidate", "role": "server", "candidate": candidate_to_json(candidate)}))
        except Exception:
            logger.exception("Failed to send ICE candidate to sender")

    offer = RTCSessionDescription(sdp=sdp, type="offer")
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    if room_id not in ROOM_SENDERS:
        ROOM_SENDERS[room_id] = {"pc": pc, "track": None, "recorder": None, "stamp": utc_stamp()}
    else:
        ROOM_SENDERS[room_id]["pc"] = pc

    await ws.send(json.dumps({"type": "answer", "sdp": pc.localDescription.sdp}))

    setattr(ws, "role", "sender")
    setattr(ws, "room_id", room_id)
    setattr(ws, "pc", pc)


# -------------------------
# Viewer
# -------------------------
async def handle_viewer_offer(ws: Any, data: dict):
    room_id = data.get("room_id", "default")
    sdp = data.get("sdp")
    if not sdp:
        await ws.send(json.dumps({"error": "missing_sdp"}))
        return

    sender_info = ROOM_SENDERS.get(room_id)
    sender_track = sender_info.get("track") if sender_info else None
    if not sender_track:
        await ws.send(json.dumps({"error": "no_sender"}))
        return

    pc = RTCPeerConnection()
    viewer_id = f"viewer-{uuid.uuid4().hex[:8]}"

    try:
        relay_track = relay.subscribe(sender_track)
        pc.addTrack(relay_track)
    except Exception:
        logger.exception("Relay subscribe failed room=%s", room_id)
        await ws.send(json.dumps({"error": "relay_failed"}))
        try:
            await pc.close()
        except Exception:
            pass
        return

    @pc.on("icecandidate")
    async def on_icecandidate(candidate: Optional[RTCIceCandidate]):
        if candidate is None:
            return
        try:
            await ws.send(json.dumps({"type": "candidate", "role": "server", "candidate": candidate_to_json(candidate)}))
        except Exception:
            logger.exception("Failed to send ICE candidate to viewer")

    offer = RTCSessionDescription(sdp=sdp, type="offer")
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    await ws.send(json.dumps({"type": "answer", "sdp": pc.localDescription.sdp}))

    VIEWERS[ws] = {"pc": pc, "viewer_id": viewer_id, "room_id": room_id}
    setattr(ws, "role", "viewer")
    setattr(ws, "viewer_id", viewer_id)
    setattr(ws, "room_id", room_id)
    setattr(ws, "pc", pc)


# -------------------------
# Candidate
# -------------------------
async def handle_candidate(ws: Any, data: dict):
    c = data.get("candidate")
    if not isinstance(c, dict):
        return

    pc = getattr(ws, "pc", None)
    if pc is None:
        role = data.get("role")
        if role == "viewer":
            state = VIEWERS.get(ws)
            pc = state["pc"] if state else None
        elif role == "sender":
            room_id = data.get("room_id", getattr(ws, "room_id", None))
            sender_info = ROOM_SENDERS.get(room_id) if room_id else None
            pc = sender_info.get("pc") if sender_info else None

    if pc is None:
        return

    try:
        ice = to_ice_candidate(c)
        await pc.addIceCandidate(ice)
    except Exception:
        logger.exception("Failed to add ICE candidate")


# -------------------------
# WebSocket handler
# -------------------------
async def handler(ws: Any, path: str | None = None):
    peer = getattr(ws, "remote_address", None)
    logger.info("WS ligado: %s path=%s", peer, path)

    try:
        async for message in ws:
            try:
                data = json.loads(message)
            except Exception:
                continue

            mtype = data.get("type")
            role = data.get("role")

            if mtype == "offer" and role == "sender":
                await handle_sender_offer(ws, data)
            elif mtype == "offer" and role == "viewer":
                await handle_viewer_offer(ws, data)
            elif mtype == "candidate":
                await handle_candidate(ws, data)
            elif mtype == "close":
                break
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await cleanup_ws(ws)


async def cleanup_ws(ws: Any):
    role = getattr(ws, "role", None)

    if role == "sender":
        room_id = getattr(ws, "room_id", None)
        if room_id:
            info = ROOM_SENDERS.pop(room_id, None)
            if info:
                rec = info.get("recorder")
                pc = info.get("pc")
                if rec:
                    try:
                        await rec.stop()
                    except Exception:
                        logger.exception("Error stopping recorder during cleanup room=%s", room_id)
                if pc:
                    try:
                        await pc.close()
                    except Exception:
                        logger.exception("Error closing sender pc during cleanup room=%s", room_id)

    elif role == "viewer":
        state = VIEWERS.pop(ws, None)
        if state:
            pc = state.get("pc")
            if pc:
                try:
                    await pc.close()
                except Exception:
                    logger.exception("Error closing viewer pc")

    else:
        pc = getattr(ws, "pc", None)
        if pc:
            try:
                await pc.close()
            except Exception:
                pass


async def main():
    logger.info("Servidor WebRTC a correr em ws://%s:%s (grava em %s)", HOST, PORT, RECORDINGS_DIR)
    cleanup_task = asyncio.create_task(cleanup_old_recordings())
    try:
        async with websockets.serve(handler, HOST, PORT, max_size=2**20 * 16, ping_interval=20, ping_timeout=20):
            await asyncio.Future()
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


def shutdown():
    async def _close_all():
        for _, state in list(VIEWERS.items()):
            pc = state.get("pc")
            if pc:
                try:
                    await pc.close()
                except Exception:
                    pass
        VIEWERS.clear()

        for _, info in list(ROOM_SENDERS.items()):
            rec = info.get("recorder")
            pc = info.get("pc")
            if rec:
                try:
                    await rec.stop()
                except Exception:
                    pass
            if pc:
                try:
                    await pc.close()
                except Exception:
                    pass
        ROOM_SENDERS.clear()

    try:
        asyncio.run(_close_all())
    except Exception:
        logger.exception("Error during shutdown")


if __name__ == "__main__":
    # add_signal_handler nem é fiável no Windows; ok.
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, lambda *_: None)
            except Exception:
                pass
    except Exception:
        pass

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()