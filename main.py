# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import serial
import threading
import time
import json
import re
import os
from datetime import datetime
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

latest_temp: Optional[float] = None
latest_hum: Optional[float] = None
latest_tilt: Optional[float] = None

# ====== 최신 카메라 프레임(메모리) ======
latest_jpg: Optional[bytes] = None
latest_jpg_ts: Optional[str] = None
latest_jpg_name: Optional[str] = None

SERIAL_PORT = os.getenv("SERIAL_PORT", "COM14")
BAUD_RATE = int(os.getenv("BAUD_RATE", "115200"))
USE_SERIAL = os.getenv("USE_SERIAL", "0") == "1"

CAMERA_DIR = os.getenv("CAMERA_DIR", "camera_images")
os.makedirs(CAMERA_DIR, exist_ok=True)

app.mount("/camera_images", StaticFiles(directory=CAMERA_DIR), name="camera_images")


def extract(pattern: str, text: str):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def serial_reader():
    global latest_temp, latest_hum, latest_tilt

    ser = None
    if USE_SERIAL:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"[SERIAL] Connected on {SERIAL_PORT} @ {BAUD_RATE}")
        except Exception as e:
            print("[SERIAL] Open failed:", e)
            print("[SERIAL] → dummy 값으로 동작합니다.")
            ser = None
    else:
        print("[SERIAL] USE_SERIAL=0 → dummy 값으로 동작합니다.")

    while True:
        try:
            if ser:
                line = ser.readline().decode(errors="ignore").strip()
            else:
                line = '{"tilt": 3.2, "temp": 25.4, "humid": 41.2}'
                time.sleep(1)

            if not line:
                continue

            print("[SERIAL LINE]", line)

            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    if "temp" in data and data["temp"] is not None:
                        latest_temp = float(data["temp"])
                    if "humid" in data and data["humid"] is not None:
                        latest_hum = float(data["humid"])
                    if "tilt" in data and data["tilt"] is not None:
                        latest_tilt = float(data["tilt"])
                    continue
                except Exception as e:
                    print("[JSON ERROR]", e)

            t = extract(r"(?:temp|temperature)[:=\s]+([-+]?\d+\.?\d*)", line)
            h = extract(r"(?:hum|humid|humidity)[:=\s]+([-+]?\d+\.?\d*)", line)
            tilt = extract(r"(?:tilt|roll|angle)[:=\s]+([-+]?\d+\.?\d*)", line)

            if t is not None:
                latest_temp = t
            if h is not None:
                latest_hum = h
            if tilt is not None:
                latest_tilt = tilt

        except Exception as e:
            print("[SERIAL LOOP ERROR]", e)
            time.sleep(0.1)


threading.Thread(target=serial_reader, daemon=True).start()


@app.get("/")
def root():
    return {
        "status": "SensorUDon backend running",
        "camera_gallery": "/camera",
        "camera_live": "/camera/live",
        "camera_latest": "/camera/latest.jpg",
        "camera_upload": "/upload_camera",
        "sensor_endpoint": "/sensor",
    }


@app.get("/sensor")
def get_sensor():
    return JSONResponse(
        {"temperature": latest_temp, "humidity": latest_hum, "tilt": latest_tilt}
    )


# ====== 카메라 갤러리(저장된 파일들) ======
@app.get("/camera", response_class=HTMLResponse)
def camera_page():
    files = sorted(
        [f for f in os.listdir(CAMERA_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))],
        reverse=True
    )[:50]

    items = "\n".join(
        [
            f"""
            <div style="margin:12px 0;">
              <div style="font-size:12px;color:#444;margin-bottom:6px;">{f}</div>
              <img src="/camera_images/{f}" style="max-width:720px;width:100%;border:1px solid #ddd;border-radius:10px;">
            </div>
            """
            for f in files
        ]
    ) or "<p>No images yet.</p>"

    return f"""
    <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>SensorUDon Camera</title>
      </head>
      <body style="font-family:Arial, sans-serif; padding:16px; max-width:900px; margin:0 auto;">
        <h2>📷 Camera uploads</h2>
        <p>
          Upload endpoint: <code>/upload_camera</code><br/>
          Live page: <a href="/camera/live">/camera/live</a><br/>
          Latest frame: <a href="/camera/latest.jpg">/camera/latest.jpg</a>
        </p>
        <hr/>
        {items}
      </body>
    </html>
    """


def _latest_file_path() -> Optional[str]:
    try:
        files = sorted(
            [f for f in os.listdir(CAMERA_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))],
            reverse=True
        )
        if not files:
            return None
        return os.path.join(CAMERA_DIR, files[0])
    except Exception:
        return None


# ====== 최신 프레임(1장)만 바로 제공 ======
@app.get("/camera/latest.jpg")
def camera_latest():
    if latest_jpg:
        return Response(latest_jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    # 서버 재시작 등으로 메모리가 비었으면 파일에서 fallback
    path = _latest_file_path()
    if not path:
        raise HTTPException(404, "아직 업로드된 이미지가 없습니다.")
    with open(path, "rb") as f:
        data = f.read()
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


# ====== 라이브 페이지(최신 1장을 주기적으로 새로고침) ======
@app.get("/camera/live", response_class=HTMLResponse)
def camera_live():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Live Camera</title>
  <style>
    body{font-family:Arial, sans-serif; padding:16px; max-width:900px; margin:0 auto;}
    img{max-width:100%; border:1px solid #ddd; border-radius:12px;}
    .meta{font-size:12px; color:#555; margin:8px 0 12px;}
    code{background:#f3f3f3; padding:2px 6px; border-radius:6px;}
  </style>
</head>
<body>
  <h2>🎥 Live Camera</h2>
  <div class="meta">
    최신 프레임: <code>/camera/latest.jpg</code> (300ms마다 갱신)
  </div>
  <img id="cam" src="/camera/latest.jpg" />
  <script>
    const img = document.getElementById("cam");
    setInterval(() => {
      img.src = "/camera/latest.jpg?t=" + Date.now(); // 캐시 방지
    }, 300);
  </script>
</body>
</html>
"""


# ====== ESP32가 JPEG 바이트를 그대로 POST ======
@app.post("/upload_camera")
async def upload_camera(request: Request):
    global latest_jpg, latest_jpg_ts, latest_jpg_name

    body: bytes = await request.body()
    if not body:
        return JSONResponse({"status": "error", "detail": "empty body"}, status_code=400)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"camera_{ts}.jpg"
    filepath = os.path.join(CAMERA_DIR, filename)

    try:
        with open(filepath, "wb") as f:
            f.write(body)

        # 최신 프레임 메모리에도 저장(라이브용)
        latest_jpg = body
        latest_jpg_ts = ts
        latest_jpg_name = filename

        print(f"[CAMERA] Saved image: {filepath} ({len(body)} bytes)")

        return JSONResponse(
            {
                "status": "ok",
                "filename": filename,
                "size": len(body),
                "view_url": f"/camera_images/{filename}",
                "gallery": "/camera",
                "live": "/camera/live",
                "latest": "/camera/latest.jpg",
            }
        )
    except Exception as e:
        print("[CAMERA SAVE ERROR]", e)
        return JSONResponse({"status": "error", "detail": "save_failed"}, status_code=500)
