# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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

# ====== 최신 센서 값 ======
latest_temp: Optional[float] = None
latest_hum: Optional[float] = None
latest_tilt: Optional[float] = None

class SensorData(BaseModel):
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    tilt: Optional[float] = None

# ====== 카메라 저장 폴더/정적 서빙 ======
CAMERA_DIR = os.getenv("CAMERA_DIR", "camera_images")
os.makedirs(CAMERA_DIR, exist_ok=True)
app.mount("/camera_images", StaticFiles(directory=CAMERA_DIR), name="camera_images")

# ====== 최신 카메라 프레임(메모리) ======
latest_jpg: Optional[bytes] = None
latest_jpg_ts: Optional[str] = None
latest_jpg_name: Optional[str] = None


@app.get("/")
def root():
    return {
        "status": "SensorUDon backend running",
        "sensor_endpoint": "/sensor",
        "update_endpoint": "/update_sensor",
        "camera_upload": "/upload_camera",
        "camera_gallery": "/camera",
        "camera_live": "/camera/live",
        "camera_latest": "/camera/latest.jpg",
    }


@app.get("/sensor")
def get_sensor():
    return JSONResponse(
        {"temperature": latest_temp, "humidity": latest_hum, "tilt": latest_tilt}
    )


@app.post("/update_sensor")
def update_sensor(data: SensorData):
    global latest_temp, latest_hum, latest_tilt
    if data.temperature is not None:
        latest_temp = float(data.temperature)
    if data.humidity is not None:
        latest_hum = float(data.humidity)
    if data.tilt is not None:
        latest_tilt = float(data.tilt)
    return {"status": "ok", "temperature": latest_temp, "humidity": latest_hum, "tilt": latest_tilt}


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


@app.get("/camera/latest.jpg")
def camera_latest():
    if latest_jpg:
        return Response(latest_jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    path = _latest_file_path()
    if not path:
        raise HTTPException(404, "아직 업로드된 이미지가 없습니다.")
    with open(path, "rb") as f:
        data = f.read()
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


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
  <div class="meta">최신 프레임: <code>/camera/latest.jpg</code> (300ms마다 갱신)</div>
  <img id="cam" src="/camera/latest.jpg" />
  <script>
    const img = document.getElementById("cam");
    setInterval(() => {
      img.src = "/camera/latest.jpg?t=" + Date.now();
    }, 300);
  </script>
</body>
</html>
"""


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

        latest_jpg = body
        latest_jpg_ts = ts
        latest_jpg_name = filename

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
    except Exception:
        return JSONResponse({"status": "error", "detail": "save_failed"}, status_code=500)
