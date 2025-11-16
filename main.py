# main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.responses import Response
import serial
import threading
import time
import re
import base64
import requests

app = FastAPI()

# -------------------------------
# 전역 변수 (센서 최신 값 저장)
# -------------------------------
latest_temp = None
latest_hum = None
latest_tilt = None
latest_image_base64 = None


# -------------------------------
# 시리얼 센서 읽기 (백그라운드 스레드)
# -------------------------------
def extract(pattern, text):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def serial_reader():
    global latest_temp, latest_hum, latest_tilt
    try:
        ser = serial.Serial("COM5", 115200, timeout=1)
        print("Serial Connected")
    except:
        print("Serial not found → Running dummy values")
        ser = None

    while True:
        try:
            if ser:
                line = ser.readline().decode(errors="ignore").strip()
            else:
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


# -------------------------------
# 카메라 이미지 가져오기 (백그라운드 스레드)
# -------------------------------
def camera_reader():
    global latest_image_base64
    ESP32_URL = "http://172.20.10.4/capture"

    while True:
        try:
            img = requests.get(ESP32_URL, timeout=1).content
            latest_image_base64 = base64.b64encode(img).decode()
        except:
            pass

        time.sleep(0.2)


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


@app.get("/camera")
def get_camera():
    if latest_image_base64 is None:
        return JSONResponse({"error": "no image"}, status_code=404)

    return JSONResponse({
        "image": latest_image_base64
    })


# -------------------------------
# 백그라운드 스레드 실행
# -------------------------------
threading.Thread(target=serial_reader, daemon=True).start()
threading.Thread(target=camera_reader, daemon=True).start()
