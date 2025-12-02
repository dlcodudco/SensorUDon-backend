from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel  # 데이터 형식을 정의하기 위해 추가
import serial
import threading
import time
import json
import re
import os
from datetime import datetime

app = FastAPI()

# -------------------------------
# CORS 설정
# -------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# 전역 변수: 센서 최신 값
# -------------------------------
latest_temp: float | None = None   # ℃
latest_hum: float | None = None    # %RH
latest_tilt: float | None = None   # deg

# [참고] Render 서버에서는 COM 포트가 없으므로 이 설정은 무시됩니다.
SERIAL_PORT = "COM5"
BAUD_RATE = 115200

# 카메라 이미지 저장 폴더
CAMERA_DIR = "camera_images"

# -------------------------------
# [추가됨] 데이터 전송 형식 정의
# -------------------------------
class SensorData(BaseModel):
    temperature: float | None = None
    humidity: float | None = None
    tilt: float | None = None

# -------------------------------
# [추가됨] PC(중계기)에서 보낸 센서 값을 받는 우체통
# -------------------------------
@app.post("/update_sensor")
def update_sensor(data: SensorData):
    global latest_temp, latest_hum, latest_tilt
    
    # PC에서 보내준 값이 있으면 전역 변수 업데이트
    if data.temperature is not None:
        latest_temp = data.temperature
    if data.humidity is not None:
        latest_hum = data.humidity
    if data.tilt is not None:
        latest_tilt = data.tilt
        
    # print(f"[SERVER] Updated: Temp={latest_temp}, Hum={latest_hum}, Tilt={latest_tilt}")
    return {"status": "success", "data": data}

# -------------------------------
# 시리얼 리더 스레드 (서버용으로 수정됨)
# -------------------------------
def serial_reader():
    global latest_temp, latest_hum, latest_tilt

    ser = None
    try:
        # Render 서버에서는 여기서 무조건 실패합니다 (정상)
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"[SERIAL] Connected on {SERIAL_PORT}")
    except Exception as e:
        print("[SERIAL] 하드웨어 연결 실패 (Render 환경 예상). 외부 데이터 수신 대기 중...")
        ser = None

    while True:
        # [중요 수정] 
        # Render 서버에서는 시리얼 연결이 안 되므로 그냥 대기만 합니다.
        # 기존의 '더미 데이터 생성' 로직을 삭제했습니다. 
        # (PC에서 오는 실제 데이터를 덮어쓰지 않기 위함)
        if ser:
            try:
                line = ser.readline().decode(errors="ignore").strip()
                # (여기는 로컬 테스트용 로직, Render에서는 실행 안 됨)
                if not line: continue
                # ... 기존 파싱 로직 ...
            except:
                pass
        
        # CPU 과부하 방지
        time.sleep(1)

# 서버 시작 시 스레드 실행
threading.Thread(target=serial_reader, daemon=True).start()


# -------------------------------
# API 라우트
# -------------------------------
@app.get("/")
def root():
    return {
        "status": "SensorUdon Backend Running on Render",
        "camera_upload": "/upload_camera",
        "sensor_endpoint": "/sensor",
        "update_endpoint": "/update_sensor" # 확인용
    }

@app.get("/sensor")
def get_sensor():
    return JSONResponse(
        {
            "temperature": latest_temp,
            "humidity": latest_hum,
            "tilt": latest_tilt,
        }
    )

# -------------------------------
# 카메라 업로드 엔드포인트
# -------------------------------
@app.post("/upload_camera")
async def upload_camera(request: Request):
    body: bytes = await request.body()
    if not body:
        return JSONResponse({"status": "error", "detail": "empty body"}, status_code=400)

    # Render 무료 버전은 15분 뒤 파일이 삭제되지만, 데모 시연용으로는 충분합니다.
    os.makedirs(CAMERA_DIR, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"camera_{ts}.jpg"
    filepath = os.path.join(CAMERA_DIR, filename)

    try:
        with open(filepath, "wb") as f:
            f.write(body)
        print(f"[CAMERA] Saved image: {filepath}")
        return JSONResponse({"status": "ok", "filename": filename})
    except Exception as e:
        print("[CAMERA SAVE ERROR]", e)
        return JSONResponse({"status": "error"}, status_code=500)