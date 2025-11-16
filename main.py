# # main.py
# from fastapi import FastAPI, UploadFile, File
# from fastapi.responses import JSONResponse
# from fastapi.middleware.cors import CORSMiddleware
# import serial
# import threading
# import time
# import re
# import base64
# from typing import Optional

# app = FastAPI()

# # CORS 허용 (Vercel에서 호출하기 위해)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],   # 데모용: 모두 허용
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # -------------------------------
# # 전역 변수 (센서 최신 값 + 카메라 이미지)
# # -------------------------------
# latest_temp: Optional[float] = None
# latest_hum: Optional[float] = None
# latest_tilt: Optional[float] = None
# latest_image_bytes: Optional[bytes] = None


# # -------------------------------
# # 시리얼 센서 읽기 (백그라운드 스레드)
# # -------------------------------
# def extract(pattern, text: str):
#     m = re.search(pattern, text)
#     return float(m.group(1)) if m else None


# def serial_reader():
#     global latest_temp, latest_hum, latest_tilt
#     try:
#         ser = serial.Serial("COM5", 115200, timeout=1)
#         print("Serial Connected")
#     except:
#         print("Serial not found → Running dummy values")
#         ser = None

#     while True:
#         try:
#             if ser:
#                 line = ser.readline().decode(errors="ignore").strip()
#             else:
#                 line = "temp=25.4 hum=41.2 tilt=3.2"
#                 time.sleep(1)

#             t = extract(r"temp[:=\s]+([-+]?\d+\.?\d*)", line)
#             h = extract(r"hum[:=\s]+([-+]?\d+\.?\d*)", line)
#             tilt = extract(r"(?:tilt|angle|roll)[\s:=]+([-+]?\d+\.?\d*)", line)

#             if t is not None:
#                 latest_temp = t
#             if h is not None:
#                 latest_hum = h
#             if tilt is not None:
#                 latest_tilt = tilt

#         except Exception as e:
#             print("Serial Error:", e)
#             time.sleep(0.1)


# # -------------------------------
# # API 라우트
# # -------------------------------
# @app.get("/")
# def root():
#     return {"status": "SensorUDon backend running"}


# @app.get("/sensor")
# def get_sensor():
#     return JSONResponse({
#         "temperature": latest_temp,
#         "humidity": latest_hum,
#         "tilt": latest_tilt
#     })


# # ✅ ESP32가 이미지를 업로드하는 엔드포인트
# @app.post("/upload_camera")
# async def upload_camera(file: UploadFile = File(...)):
#     global latest_image_bytes
#     latest_image_bytes = await file.read()
#     print(f"Uploaded image: {len(latest_image_bytes)} bytes")
#     return {"status": "ok"}


# # ✅ 프론트(Vercel)가 이미지를 가져가는 엔드포인트
# @app.get("/camera")
# def get_camera():
#     if latest_image_bytes is None:
#         return JSONResponse({"error": "no image"}, status_code=404)

#     image_b64 = base64.b64encode(latest_image_bytes).decode()
#     return {"image": image_b64}


# # -------------------------------
# # 백그라운드 스레드 실행
# # -------------------------------
# threading.Thread(target=serial_reader, daemon=True).start()



# main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import serial
import threading
import time
import re
import requests  # ⭐ ESP32에서 이미지 가져올 때 사용

app = FastAPI()

# CORS 허용 (Vercel에서 호출하기 위해)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 데모용: 모두 허용
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# 전역 변수 (센서 최신 값 저장)
# -------------------------------
latest_temp = None
latest_hum = None
latest_tilt = None

# ESP32 카메라 주소 (현재 시리얼에서 본 IP 사용)
ESP32_CAMERA_URL = "http://172.20.10.4/capture"  # ⭐ IP 바뀌면 여기만 수정

# -------------------------------
# 시리얼 센서 읽기 (백그라운드 스레드)
# -------------------------------
def extract(pattern, text):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def serial_reader():
    global latest_temp, latest_hum, latest_tilt
    try:
        ser = serial.Serial("COM5", 115200, timeout=1)  # ⭐ PC에서 센서 연결된 포트
        print("Serial Connected")
    except:
        print("Serial not found → Running dummy values")
        ser = None

    while True:
        try:
            if ser:
                line = ser.readline().decode(errors="ignore").strip()
            else:
                # 더미 데이터
                line = "temp=25.4 hum=41.2 tilt=3.2"
                time.sleep(1)

            t = extract(r"temp[:=\s]+([-+]?\d+\.?\d*)", line)
            h = extract(r"hum[:=\s]+([-+]?\d+\.?\d*)", line)
            tilt = extract(r"(?:tilt|angle|roll)[\s:=]+([-+]?\d+\.?\d*)", line)

            if t is not None:
                latest_temp = t
            if h is not None:
                latest_hum = h
            if tilt is not None:
                latest_tilt = tilt

        except Exception as e:
            print("Serial Error:", e)
            time.sleep(0.1)

# 백그라운드에서 센서 읽기 시작
threading.Thread(target=serial_reader, daemon=True).start()

# -------------------------------
# API 라우트
# -------------------------------
@app.get("/")
def root():
    return {"status": "SensorUDon backend running"}

@app.get("/sensor")
def get_sensor():
    return JSONResponse({
        "temperature": latest_temp,
        "humidity": latest_hum,
        "tilt": latest_tilt
    })

# ⭐ ESP32 카메라에서 이미지를 바로 가져와서 JPEG로 반환
@app.get("/camera")
def get_camera():
    try:
        r = requests.get(ESP32_CAMERA_URL, timeout=5)
        if r.status_code != 200:
            return JSONResponse(
                {"error": f"ESP32 returned status {r.status_code}"},
                status_code=502
            )
        # 브라우저/프론트에서 바로 <img src="...">로 볼 수 있도록 JPEG로 리턴
        return Response(content=r.content, media_type="image/jpeg")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
