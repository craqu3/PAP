"""
Servidor WebRTC (sinalização via WebSocket) — versão melhorada.

Compatível com o protocolo do teu colega:
  - Mensagens JSON via WebSocket
  - type: "offer" | "candidate"
  - role: "sender" | "viewer"

O servidor:
  - Recebe 1 emissor (sender) com um track de vídeo.
  - Permite N viewers, reencaminhando o vídeo do sender para cada viewer.

Melhorias vs. versão original:
  - Corrige o fluxo SDP: cria answer sempre após setRemoteDescription
  - Fila de ICE candidates recebidos antes do PC estar pronto
  - Limpeza/fecho correto de PCs quando sockets fecham
  - Tratamento de erros e validação de mensagens
  - Logs mais claros
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaRecorder


# -----------------------
# Logging configuration
# -----------------------
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("webrtc-signaling")
# reduzir ruído de libs específicas
logging.getLogger("aioice").setLevel(logging.INFO)
logging.getLogger("aiortc").setLevel(logging.INFO)


RECORDINGS_DIR = Path(r"C:\Users\Public\Recordings")
RETENTION_HOURS = 4


@dataclass
class SessionRecording:
    path: Path
    recorder: MediaRecorder
    started_at: datetime
    cleanup_task: Optional[asyncio.Task] = None


async def delete_recording_after_retention(path: Path, delay_seconds: float) -> None:
    try:
        await asyncio.sleep(delay_seconds)
        if path.exists():
            path.unlink()
            logger.info("Gravação removida após retenção: %s", path)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Erro a remover gravação expirada: %s", path)


def build_recording_path() -> Path:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return RECORDINGS_DIR / f"stablepack_box_{stamp}.mp4"


async def start_recording(track) -> SessionRecording:
    output_path = build_recording_path()
    recorder = MediaRecorder(str(output_path))
    recorder.addTrack(track)
    await recorder.start()
    logger.info("Gravação iniciada em %s", output_path)
    return SessionRecording(
        path=output_path,
        recorder=recorder,
        started_at=datetime.utcnow(),
    )


async def stop_recording(recording: Optional[SessionRecording]) -> None:
    if recording is None:
        return

    try:
        await recording.recorder.stop()
        expires_at = datetime.utcnow() + timedelta(hours=RETENTION_HOURS)
        delay_seconds = max((expires_at - datetime.utcnow()).total_seconds(), 0)
        recording.cleanup_task = asyncio.create_task(
            delete_recording_after_retention(recording.path, delay_seconds)
        )
        logger.info(
            "Gravação finalizada: %s (expira em %s)",
            recording.path,
            expires_at.isoformat() + "Z",
        )
    except Exception:
        logger.exception("Erro ao finalizar gravação: %s", recording.path)


def parse_sdp_candidate(sdp: str) -> Dict[str, Any]:
    """
    Parser simples de SDP 'candidate:' (compatível com versões antigas).
    Exemplo (sem 'candidate:' no início):
      "candidate:842163049 1 udp 1677729535 192.168.1.10 54400 typ srflx raddr 0.0.0.0 rport 0 ..."
    """
    parts = sdp.split()
    if len(parts) < 8:
        raise ValueError(f"SDP candidate inválido: {sdp!r}")

    foundation = parts[0].split(":")[1]
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


def to_ice_candidate(candidate_payload: Dict[str, Any]) -> RTCIceCandidate:
    """
    Converte o payload enviado pelo cliente (formato WebRTC) num RTCIceCandidate do aiortc.
    Espera:
      {
        "candidate": "candidate:....",
        "sdpMid": "0",
        "sdpMLineIndex": 0
      }
    """
    cand = candidate_payload.get("candidate")
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
        sdpMid=candidate_payload.get("sdpMid"),
        sdpMLineIndex=candidate_payload.get("sdpMLineIndex"),
        tcpType=parsed["tcpType"],
    )


@dataclass
class PeerState:
    pc: RTCPeerConnection
    pending_ice: list[RTCIceCandidate] = field(default_factory=list)
    remote_description_set: bool = False

    async def add_ice_or_queue(self, ice: RTCIceCandidate) -> None:
        if self.remote_description_set:
            await self.pc.addIceCandidate(ice)
        else:
            self.pending_ice.append(ice)

    async def flush_ice(self) -> None:
        if not self.remote_description_set:
            return
        while self.pending_ice:
            ice = self.pending_ice.pop(0)
            await self.pc.addIceCandidate(ice)


sender_state: Optional[PeerState] = None
sender_video_track = None
sender_ws: Optional[websockets.WebSocketServerProtocol] = None
sender_recording: Optional[SessionRecording] = None

# Cada websocket viewer tem o seu PeerState
viewer_states: Dict[websockets.WebSocketServerProtocol, PeerState] = {}


async def close_sender() -> None:
    global sender_state, sender_video_track, sender_ws, sender_recording
    if sender_state is not None:
        try:
            await sender_state.pc.close()
        except Exception:
            logger.exception("Erro a fechar sender PC")
    await stop_recording(sender_recording)
    sender_state = None
    sender_video_track = None
    sender_ws = None
    sender_recording = None


async def close_viewer(ws: websockets.WebSocketServerProtocol) -> None:
    st = viewer_states.pop(ws, None)
    if st is None:
        return
    try:
        await st.pc.close()
    except Exception:
        logger.exception("Erro a fechar viewer PC")


async def handle_sender_offer(ws: websockets.WebSocketServerProtocol, data: Dict[str, Any]) -> None:
    global sender_state, sender_video_track, sender_ws, sender_recording

    # Garante que só existe 1 sender de cada vez
    if sender_state is not None:
        logger.info("Novo sender ligado — a fechar sender anterior.")
        await close_sender()

    pc = RTCPeerConnection()
    st = PeerState(pc=pc)
    sender_state = st
    sender_ws = ws

    @pc.on("track")
    def on_track(track) -> None:
        global sender_video_track, sender_recording
        logger.info("on_track chamado: kind=%s id=%s readyState=%s", track.kind, getattr(track, "id", None), getattr(track, "readyState", None))
        if track.kind == "video":
            logger.info("Track de vídeo recebida do sender (on_track).")
            sender_video_track = track
            if sender_recording is None:
                asyncio.create_task(_start_sender_recording(track))

    @pc.on("connectionstatechange")
    def on_connectionstatechange() -> None:
        logger.info("Sender connection state: %s", pc.connectionState)
        if pc.connectionState in ("closed", "failed", "disconnected"):
            asyncio.create_task(close_sender())

    # --- LOGS ADICIONADOS PARA DEBUG ---
    offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
    logger.info("OFFER recebido do sender: len(sdp)=%d", len(data.get("sdp", "")))
    has_video = "m=video" in data.get("sdp", "")
    logger.info("OFFER contém m=video: %s", has_video)
    rtpmaps = [line for line in data["sdp"].splitlines() if "a=rtpmap" in line]
    logger.info("OFFER rtpmap lines: %r", rtpmaps)
    logger.info("Transceivers antes de setRemoteDescription: %r", pc.getTransceivers())
    # ------------------------------------

    await pc.setRemoteDescription(offer)
    st.remote_description_set = True
    await st.flush_ice()

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    await ws.send(
        json.dumps(
            {
                "type": pc.localDescription.type,
                "sdp": pc.localDescription.sdp,
            }
        )
    )


async def handle_sender_candidate(data: Dict[str, Any]) -> None:
    global sender_state
    logger.info("candidate recebido do sender: %r", data.get("candidate"))
    if sender_state is None:
        logger.info("sender_state é None ao receber candidate")
        return
    ice = to_ice_candidate(data["candidate"])
    await sender_state.add_ice_or_queue(ice)


async def _start_sender_recording(track) -> None:
    global sender_recording
    try:
        sender_recording = await start_recording(track)
    except Exception:
        logger.exception("Erro a iniciar gravação da transmissão")


async def handle_viewer_offer(ws: websockets.WebSocketServerProtocol, data: Dict[str, Any]) -> None:
    global sender_video_track

    if sender_video_track is None:
        await ws.send(json.dumps({"error": "no_sender"}))
        return

    # Se este ws já tinha PC, fecha e recria (renegociação simples)
    await close_viewer(ws)

    pc = RTCPeerConnection()
    st = PeerState(pc=pc)
    viewer_states[ws] = st

    @pc.on("connectionstatechange")
    def on_connectionstatechange() -> None:
        logger.info("Viewer connection state: %s", pc.connectionState)

    # Envia o vídeo do sender para o viewer (sendonly)
    transceiver = pc.addTransceiver("video", direction="sendonly")
    replace_track = getattr(transceiver.sender, "replaceTrack", None)
    if replace_track is not None:
        maybe_coro = replace_track(sender_video_track)
        if asyncio.iscoroutine(maybe_coro):
            await maybe_coro
    else:
        # Fallback (raro): adiciona como track
        pc.addTrack(sender_video_track)

    # --- LOGS ADICIONADOS PARA DEBUG (viewer) ---
    offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
    logger.info("OFFER recebido do viewer: len(sdp)=%d", len(data.get("sdp", "")))
    logger.info("OFFER contém m=video: %s", "m=video" in data.get("sdp", ""))
    logger.info("Transceivers antes de setRemoteDescription (viewer): %r", pc.getTransceivers())
    # ------------------------------------

    await pc.setRemoteDescription(offer)
    st.remote_description_set = True
    await st.flush_ice()

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    await ws.send(
        json.dumps(
            {
                "type": pc.localDescription.type,
                "sdp": pc.localDescription.sdp,
            }
        )
    )


async def handle_viewer_candidate(ws: websockets.WebSocketServerProtocol, data: Dict[str, Any]) -> None:
    logger.info("candidate recebido do viewer: %r", data.get("candidate"))
    st = viewer_states.get(ws)
    if st is None:
        logger.info("viewer_state é None ao receber candidate")
        return
    ice = to_ice_candidate(data["candidate"])
    await st.add_ice_or_queue(ice)


def validate_message(data: Dict[str, Any]) -> None:
    if data.get("type") not in ("offer", "candidate"):
        raise ValueError("type inválido")
    role = data.get("role")
    if role not in ("sender", "viewer"):
        raise ValueError("role inválido")

    if data["type"] == "offer":
        if not isinstance(data.get("sdp"), str):
            raise ValueError("sdp em falta")
        if data.get("type") not in ("offer",):
            raise ValueError("type inválido para offer")
    else:
        cand = data.get("candidate")
        if not isinstance(cand, dict):
            raise ValueError("candidate em falta")
        if not isinstance(cand.get("candidate"), str):
            raise ValueError("candidate.candidate em falta")


async def handler(ws: websockets.WebSocketServerProtocol) -> None:
    logger.info("WS ligado: %s", getattr(ws, "remote_address", None))
    try:
        async for message in ws:
            try:
                data = json.loads(message)
                if not isinstance(data, dict):
                    raise ValueError("JSON tem de ser objecto")
                validate_message(data)
            except Exception as e:
                logger.warning("Mensagem inválida: %s (%r)", message, e)
                await ws.send(json.dumps({"error": "bad_message"}))
                continue

            msg_type = data["type"]
            role = data["role"]

            try:
                if msg_type == "offer":
                    if role == "sender":
                        await handle_sender_offer(ws, data)
                    else:
                        await handle_viewer_offer(ws, data)

                elif msg_type == "candidate":
                    if role == "sender":
                        await handle_sender_candidate(data)
                    else:
                        await handle_viewer_candidate(ws, data)
            except Exception:
                logger.exception("Erro a processar mensagem (%s/%s)", role, msg_type)
                await ws.send(json.dumps({"error": "internal"}))

    finally:
        await close_viewer(ws)
        # Se este websocket pertencia ao sender, terminamos também a sessão/gravação.
        global sender_state, sender_ws
        if sender_ws is ws:
            await close_sender()
        elif sender_state is not None and sender_state.pc.connectionState in ("closed", "failed", "disconnected"):
            await close_sender()
        logger.info("WS desligado: %s", getattr(ws, "remote_address", None))


async def main() -> None:
    host = "0.0.0.0"
    port = 9000
    async with websockets.serve(handler, host, port, ping_interval=20, ping_timeout=20):
        logger.info("Servidor WebRTC (sinalização) aberto em ws://%s:%s", host, port)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())