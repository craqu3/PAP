from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaRecorder

import httpx # Precisas de instalar: pip install httpx

FASTAPI_URL = "http://10.222.248.231:8000/video/upload" # Ajusta a porta se necessário

async def send_to_fastapi(file_path: Path):
    try:
        # Converte para caminho absoluto do Windows de forma segura
        absolute_path = file_path.resolve()
        
        async with httpx.AsyncClient() as client:
            # Usar o 'with' aqui garante que o ficheiro fecha mesmo se o upload falhar
            with open(str(absolute_path), "rb") as f:
                files = {"file": (absolute_path.name, f, "video/mp4")}
                params = {"user_id": 123}
                
                response = await client.post(
                    FASTAPI_URL, 
                    params=params, 
                    files=files, 
                    timeout=120.0 # Aumentado para vídeos grandes
                )
                
                if response.status_code == 200:
                    logger.info(f"Sucesso! API respondeu: {response.json()}")
                else:
                    logger.error(f"Falha na API ({response.status_code}): {response.text}")
    except Exception as e:
        logger.exception(f"Erro crítico no upload: {e}")
# -----------------------
# Configuração de Logging
# -----------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc-signaling")
# Reduzir ruído de bibliotecas externas
logging.getLogger("aioice").setLevel(logging.WARNING)
logging.getLogger("aiortc").setLevel(logging.INFO)

# Configurações de Gravação
RECORDINGS_DIR = Path(r"C:\Users\Public\Recordings")
RETENTION_HOURS = 4

@dataclass
class SessionRecording:
    path: Path
    recorder: MediaRecorder
    started_at: datetime
    cleanup_task: Optional[asyncio.Task] = None

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

# -----------------------
# Estado Global
# -----------------------
sender_state: Optional[PeerState] = None
sender_video_track = None
sender_ws: Optional[websockets.WebSocketServerProtocol] = None
sender_recording: Optional[SessionRecording] = None

# Mapeamento de Visualizadores (WS -> PeerState)
viewer_states: Dict[websockets.WebSocketServerProtocol, PeerState] = {}

# -----------------------
# Funções Auxiliares (Gravação e ICE)
# -----------------------

async def delete_recording_after_retention(path: Path, delay_seconds: float) -> None:
    try:
        await asyncio.sleep(delay_seconds)
        if path.exists():
            path.unlink()
            logger.info("Gravação removida após período de retenção: %s", path)
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Erro ao remover gravação expirada: %s", path)

def build_recording_path() -> Path:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    # Correção Python 3.13: datetime.now(timezone.utc)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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
        started_at=datetime.now(timezone.utc),
    )

async def stop_recording(recording: Optional[SessionRecording]) -> None:
    if recording is None:
        return

    try:
        # 1. Para o recorder
        await recording.recorder.stop()
        logger.info("Recorder parado. A aguardar libertação do ficheiro...")
        
        # 2. Pequena pausa para garantir que o Windows libertou o lock do ficheiro
        await asyncio.sleep(1) 
        
        # 3. Tenta o upload
        if recording.path.exists():
            logger.info(f"A iniciar upload de: {recording.path}")
            await send_to_fastapi(recording.path)
        else:
            logger.error("Ficheiro de gravação não encontrado após paragem.")
            
    except Exception as e:
        logger.error(f"Erro ao parar gravação ou enviar para API: {e}")
    finally:
        # Lógica de expiração/limpeza
        now = datetime.now(timezone.utc)
        delay_seconds = RETENTION_HOURS * 3600
        recording.cleanup_task = asyncio.create_task(
            delete_recording_after_retention(recording.path, delay_seconds)
        )
        logger.info("Sessão de gravação encerrada.")

def parse_sdp_candidate(sdp: str) -> Dict[str, Any]:
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

    related_address = parts[parts.index("raddr") + 1] if "raddr" in parts else None
    related_port = int(parts[parts.index("rport") + 1]) if "rport" in parts else None
    tcp_type = parts[parts.index("tcptype") + 1] if "tcptype" in parts else None

    return {
        "foundation": foundation, "component": component, "protocol": protocol,
        "priority": priority, "ip": ip, "port": port, "type": cand_type,
        "relatedAddress": related_address, "relatedPort": related_port, "tcpType": tcp_type,
    }

def to_ice_candidate(candidate_payload: Dict[str, Any]) -> RTCIceCandidate:
    cand = candidate_payload.get("candidate")
    if not isinstance(cand, str):
        raise ValueError("O campo candidate tem de ser uma string")

    parsed = parse_sdp_candidate(cand)
    return RTCIceCandidate(
        component=parsed["component"], foundation=parsed["foundation"],
        ip=parsed["ip"], port=parsed["port"], priority=parsed["priority"],
        protocol=parsed["protocol"], type=parsed["type"],
        relatedAddress=parsed["relatedAddress"], relatedPort=parsed["relatedPort"],
        sdpMid=candidate_payload.get("sdpMid"),
        sdpMLineIndex=candidate_payload.get("sdpMLineIndex"),
        tcpType=parsed["tcpType"],
    )

# -----------------------
# Gestão de Peer Connections
# -----------------------

async def close_sender() -> None:
    global sender_state, sender_video_track, sender_ws, sender_recording
    if sender_state:
        try:
            await sender_state.pc.close()
        except Exception:
            logger.exception("Erro ao fechar PeerConnection do Sender")
    
    if sender_recording:
        await stop_recording(sender_recording)
    
    sender_state = None
    sender_video_track = None
    sender_ws = None
    sender_recording = None
    logger.info("Sessão do Sender terminada e limpa.")

async def close_viewer(ws: websockets.WebSocketServerProtocol) -> None:
    st = viewer_states.pop(ws, None)
    if st:
        try:
            await st.pc.close()
            logger.info("PeerConnection do Viewer fechada.")
        except Exception:
            logger.exception("Erro ao fechar PeerConnection do Viewer")

# -----------------------
# Handlers de Mensagens
# -----------------------

async def handle_sender_offer(ws: websockets.WebSocketServerProtocol, data: Dict[str, Any]) -> None:
    global sender_state, sender_video_track, sender_ws, sender_recording

    if sender_state:
        logger.info("Novo sender detetado. A fechar a sessão anterior...")
        await close_sender()

    pc = RTCPeerConnection()
    st = PeerState(pc=pc)
    sender_state = st
    sender_ws = ws

    @pc.on("track")
    def on_track(track):
        global sender_video_track, sender_recording
        if track.kind == "video":
            logger.info("Track de vídeo recebida do sender.")
            sender_video_track = track
            
            # Inicia gravação
            if sender_recording is None:
                asyncio.create_task(_start_sender_recording(track))
            
            @track.on("ended")
            async def on_ended():
                logger.info("Track de vídeo finalizada pelo emissor.")
                await stop_recording(sender_recording)

    @pc.on("connectionstatechange")
    def on_connectionstatechange():
        logger.info("Estado da ligação do Sender: %s", pc.connectionState)
        if pc.connectionState in ("closed", "failed", "disconnected"):
            asyncio.create_task(close_sender())

    offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
    await pc.setRemoteDescription(offer)
    st.remote_description_set = True
    await st.flush_ice()

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    await ws.send(json.dumps({"type": pc.localDescription.type, "sdp": pc.localDescription.sdp}))

async def _start_sender_recording(track) -> None:
    global sender_recording
    try:
        sender_recording = await start_recording(track)
    except Exception:
        logger.exception("Falha ao iniciar a gravação do stream")

async def handle_viewer_offer(ws: websockets.WebSocketServerProtocol, data: Dict[str, Any]) -> None:
    global sender_video_track
    if sender_video_track is None:
        await ws.send(json.dumps({"error": "no_active_sender"}))
        return

    await close_viewer(ws)
    pc = RTCPeerConnection()
    st = PeerState(pc=pc)
    viewer_states[ws] = st

    # Adiciona a track do sender para este viewer
    pc.addTrack(sender_video_track)

    offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
    await pc.setRemoteDescription(offer)
    st.remote_description_set = True
    await st.flush_ice()

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    await ws.send(json.dumps({"type": pc.localDescription.type, "sdp": pc.localDescription.sdp}))

# -----------------------
# Handler Principal WebSocket
# -----------------------

async def handler(ws: websockets.WebSocketServerProtocol) -> None:
    logger.info("Novo cliente conectado: %s", ws.remote_address)
    try:
        async for message in ws:
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                role = data.get("role")
                
                if msg_type == "offer":
                    if role == "sender":
                        await handle_sender_offer(ws, data)
                    else:
                        await handle_viewer_offer(ws, data)
                
                elif msg_type == "candidate":
                    ice_data = data.get("candidate")
                    if role == "sender" and sender_state:
                        await sender_state.add_ice_or_queue(to_ice_candidate(ice_data))
                    elif role == "viewer" and ws in viewer_states:
                        await viewer_states[ws].add_ice_or_queue(to_ice_candidate(ice_data))
            
            except Exception as e:
                logger.error("Erro ao processar mensagem: %s", e)
    finally:
        await close_viewer(ws)
        if sender_ws == ws:
            await close_sender()
        logger.info("Cliente desconectado: %s", ws.remote_address)

async def main() -> None:
    host, port = "0.0.0.0", 9000
    async with websockets.serve(handler, host, port, ping_interval=20, ping_timeout=20):
        logger.info("Servidor WebRTC ativo em ws://%s:%s", host, port)
        await asyncio.Future()  # Corre para sempre

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass