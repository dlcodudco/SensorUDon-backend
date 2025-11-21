# main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import serial
import threading
import time
import json
import re
import os
from datetime import datetime

app = FastAPI()

# -------------------------------
# CORS 설정 (앱/웹에서 호출 가능하게)
# -------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 데모용: 모두 허용 (나중에 도메인 제한 가능)
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# 전역 변수: 센서 최신 값
# -------------------------------
latest_temp: float | None = None   # ℃
latest_hum: float | None = None    # %RH
latest_tilt: float | None = None   # deg

# LoRa 수신기 포트 (나중에 실제 포트 번호로 바꾸면 됨)
SERIAL_PORT = "COM14"
BAUD_RATE = 115200

# 카메라 이미지 저장 폴더
CAMERA_DIR = "camera_images"


# -------------------------------
# 보조 함수: 텍스트에서 숫자 뽑기 (백업용)
# -------------------------------
def extract(pattern: str, text: str):
    """
    pattern 에서 캡처 그룹 1개로 숫자를 뽑아 float로 변환
    """
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


# -------------------------------
# 시리얼 리더 스레드
# -------------------------------
def serial_reader():
    global latest_temp, latest_hum, latest_tilt

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"[SERIAL] Connected on {SERIAL_PORT}")
    except Exception as e:
        print("[SERIAL] Open failed:", e)
        print("[SERIAL] → 실제 하드웨어 대신 dummy 값으로 동작합니다.")
        ser = None

    while True:
        try:
            if ser:
                line = ser.readline().decode(errors="ignore").strip()
            else:
                # 하드웨어 없을 때 테스트용
                line = '{"tilt": 3.2, "temp": 25.4, "humid": 41.2}'
                time.sleep(1)

            if not line:
                continue

            print("[SERIAL LINE]", line)

            # 1) 아두이노가 출력하는 JSON ({...}) 라인 우선 처리
            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)

                    # 아두이노 JSON 키: tilt, temp, humid
                    if "temp" in data:
                        latest_temp = float(data["temp"])
                    if "humid" in data:
                        latest_hum = float(data["humid"])
                    if "tilt" in data:
                        latest_tilt = float(data["tilt"])

                    continue  # 이 줄은 여기서 끝
                except Exception as e:
                    print("[JSON ERROR]", e)

            # 2) JSON이 아닌 경우(디버그 텍스트 등) 대비: 정규식으로 숫자 뽑기
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


# 서버 시작 시 시리얼 리더 스레드 실행
threading.Thread(target=serial_reader, daemon=True).start()


# -------------------------------
# API 라우트
# -------------------------------
@app.get("/")
def root():
    return {
        "status": "SensorUDon backend running (LoRa RX / COM14)",
        "camera_upload": "/upload_camera",
        "sensor_endpoint": "/sensor",
    }


@app.get("/sensor")
def get_sensor():
    """
    프론트/앱에서 주기적으로 호출하면 되는 엔드포인트.
    반환 형식:
    {
      "temperature": float | null,
      "humidity": float | null,
      "tilt": float | null
    }
    """
    return JSONResponse(
        {
            "temperature": latest_temp,
            "humidity": latest_hum,
            "tilt": latest_tilt,
        }
    )


# -------------------------------
# 카메라 업로드 엔드포인트
# ESP32가 JPEG 바디를 그대로 POST
# -------------------------------
@app.post("/upload_camera")
async def upload_camera(request: Request):
    """
    ESP32-S3 카메라가 JPEG 바이트를 그대로 POST하는 엔드포인트.

    - Content-Type: image/jpeg
    - Body: JPEG 바이너리
    """
    body: bytes = await request.body()

    if not body:
        return JSONResponse(
            {"status": "error", "detail": "empty body"},
            status_code=400,
        )

    # 저장 폴더 생성
    os.makedirs(CAMERA_DIR, exist_ok=True)

    # 파일 이름: camera_YYYYMMDD_HHMMSS_mmm.jpg
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"camera_{ts}.jpg"
    filepath = os.path.join(CAMERA_DIR, filename)

    try:
        with open(filepath, "wb") as f:
            f.write(body)

        print(f"[CAMERA] Saved image: {filepath} ({len(body)} bytes)")

        return JSONResponse(
            {
                "status": "ok",
                "filename": filename,
                "size": len(body),
            }
        )
    except Exception as e:
        print("[CAMERA SAVE ERROR]", e)
        return JSONResponse(
            {"status": "error", "detail": "save_failed"},
            status_code=500,
        )
