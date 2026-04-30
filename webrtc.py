import asyncio
import json
import logging
import os
from datetime import datetime

import httpx
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRecorder
from aiortc.sdp import candidate_from_sdp
from websockets.server import serve

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc")

RECORDINGS_DIR = "recordings_temp"
os.makedirs(RECORDINGS_DIR, exist_ok=True)

pcs = {}


# 🚀 Upload FastAPI
async def upload_to_fastapi(path, user_id="1"):
    url = "http://127.0.0.1:8000/video/upload"

    try:
        if not os.path.exists(path) or os.path.getsize(path) < 2000:
            logger.error("❌ Ficheiro inválido")
            return

        async with httpx.AsyncClient() as client:
            with open(path, "rb") as f:
                files = {"file": (os.path.basename(path), f, "video/mp4")}

                r = await client.post(
                    url,
                    params={"user_id": user_id},
                    files=files,
                    timeout=120
                )

                logger.info(f"✅ Upload OK: {r.text}")

        os.remove(path)

    except Exception as e:
        logger.error(f"❌ Upload error: {e}")


# 🎥 STOP seguro
async def safe_stop(pc, path):
    try:
        await asyncio.sleep(1.5)

        if hasattr(pc, "recorder") and pc.recorder:
            await pc.recorder.stop()
            logger.info(f"💾 Guardado: {path}")

            asyncio.create_task(upload_to_fastapi(path))

    except Exception as e:
        logger.error(f"❌ stop error: {e}")


# 📡 OFFER handler
async def handle_offer(data, ws):
    room = data.get("room_id", "default")

    pc = RTCPeerConnection()
    pcs[ws] = pc

    filename = f"{room}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    path = os.path.join(RECORDINGS_DIR, filename)

    recorder = MediaRecorder(path)
    pc.recorder = recorder
    pc.recorder_path = path

    recorder_started = False

    @pc.on("track")
    def on_track(track):
        nonlocal recorder_started

        logger.info(f"📺 track: {track.kind}")

        if track.kind == "video":
            recorder.addTrack(track)

            if not recorder_started:
                recorder_started = True

                async def start_rec():
                    await recorder.start()
                    logger.info("🎥 recorder started")

                asyncio.create_task(start_rec())

    @pc.on("connectionstatechange")
    async def on_state():
        state = pc.connectionState if pc else None
        logger.info(f"🔄 state: {state}")

        if state in ["closed", "failed", "disconnected"]:
            logger.info("🔌 closing")
            asyncio.create_task(safe_stop(pc, pc.recorder_path))

    # SDP
    await pc.setRemoteDescription(
        RTCSessionDescription(sdp=data["sdp"], type=data["type"])
    )

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    await ws.send(json.dumps({
        "type": "answer",
        "sdp": pc.localDescription.sdp
    }))

    # ICE send
    @pc.on("icecandidate")
    async def on_ice(candidate):
        if candidate:
            await ws.send(json.dumps({
                "type": "candidate",
                "candidate": {
                    "candidate": candidate.to_sdp(),
                    "sdpMid": candidate.sdpMid,
                    "sdpMLineIndex": candidate.sdpMLineIndex
                }
            }))


# 🌐 WS handler
async def handler(ws):
    try:
        async for msg in ws:
            data = json.loads(msg)

            if data["type"] == "offer":
                await handle_offer(data, ws)

            elif data["type"] == "candidate":
                pc = pcs.get(ws)

                if pc:
                    try:
                        cand = data["candidate"]

                        ice = candidate_from_sdp(cand["candidate"])
                        ice.sdpMid = cand["sdpMid"]
                        ice.sdpMLineIndex = cand["sdpMLineIndex"]

                        await pc.addIceCandidate(ice)

                    except Exception as e:
                        logger.error(f"ICE error: {e}")

    except Exception as e:
        logger.error(e)

    finally:
        pc = pcs.pop(ws, None)
        if pc:
            await pc.close()


# 🚀 RUN
async def main():
    async with serve(handler, "0.0.0.0", 9000):
        logger.info("🚀 WebRTC running ws://0.0.0.0:9000")
        await asyncio.Future()


asyncio.run(main())