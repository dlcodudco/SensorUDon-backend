import serial
import time
import json
import re
import requests
import threading  # [핵심] 동시에 여러 일을 하기 위한 라이브러리

# -------------------------------
# 설정
# -------------------------------
SERIAL_PORT = "COM5"   
BAUD_RATE = 115200
SERVER_URL = "https://sensorudon-backend.onrender.com/update_sensor"

# 서버 전송 주기 (초)
# 0.1초 = 1초에 10번 전송 (거의 실시간)
# ※ 주의: 무료 서버가 감당 못하면 약간 버벅일 수 있음
UPLOAD_INTERVAL = 0.1 

# 공유 데이터 (시리얼 스레드 <-> 전송 스레드)
current_data = {
    "temp": None,
    "hum": None,
    "tilt": None
}

# 프로그램 종료 플래그
running = True

def extract(pattern: str, text: str):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None

# [별도 스레드] 서버 전송만 전담하는 함수
def upload_worker():
    global current_data, running
    
    last_sent_time = 0
    
    print("[시스템] 서버 전송 스레드 시작됨 (백그라운드)")
    
    while running:
        # 지정된 주기보다 빠르면 대기
        if time.time() - last_sent_time < UPLOAD_INTERVAL:
            time.sleep(0.01)
            continue
            
        # 보낼 데이터가 유효한지 확인
        # (딕셔너리 복사해서 사용 - 충돌 방지)
        payload = current_data.copy()
        
        if payload["tilt"] is not None:
            try:
                # 보낼 데이터 포맷 맞추기
                json_payload = {
                    "temperature": payload["temp"],
                    "humidity": payload["hum"],
                    "tilt": payload["tilt"]
                }
                
                # 전송 (timeout을 짧게 0.5초로 설정)
                requests.post(SERVER_URL, json=json_payload, timeout=0.5)
                
                # 성공 여부는 출력 안 함 (속도 위해 생략)
                last_sent_time = time.time()
                
            except Exception:
                # 에러 나도 무시하고 다음 턴 진행 (속도가 최우선)
                pass
        
        # CPU 과부하 방지용 미세 대기
        time.sleep(0.01)

def main():
    global running, current_data
    
    print(f"[PC] 포트 {SERIAL_PORT} 연결 중...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"[PC] 연결 성공! 고속 전송 모드 가동")
    except Exception as e:
        print(f"[오류] {e}")
        return

    # [핵심] 전송을 담당할 스레드 시동
    t = threading.Thread(target=upload_worker)
    t.daemon = True # 메인 프로그램 꺼지면 같이 꺼짐
    t.start()

    print("------------------------------------------------")
    print("🚀 실시간 동기화 중... (Ctrl+C로 종료)")
    print("------------------------------------------------")

    try:
        while True:
            # 1. 아두이노 데이터 읽기 (이 루프는 전송 대기 없이 미친듯이 돕니다)
            if ser.in_waiting > 0:
                line = ser.readline().decode(errors="ignore").strip()
            else:
                time.sleep(0.005) # 0.005초 대기 (초고속 읽기)
                continue

            if not line: continue

            # 2. 파싱
            temp = None; hum = None; tilt = None

            # JSON 파싱
            if line.startswith("{") and line.endswith("}"):
                try:
                    d = json.loads(line)
                    temp = float(d.get("temp")) if "temp" in d else None
                    hum = float(d.get("humid")) if "humid" in d else None
                    if "tilt" in d: tilt = float(d["tilt"])
                    elif "roll" in d: tilt = float(d["roll"])
                except: pass

            # 정규식 파싱
            if temp is None: temp = extract(r"(?:temp|temperature)[:=\s]+([-+]?\d+\.?\d*)", line)
            if hum is None: hum = extract(r"(?:hum|humid)[:=\s]+([-+]?\d+\.?\d*)", line)
            if tilt is None: tilt = extract(r"(?:roll|tilt)[:=\s]+([-+]?\d+\.?\d*)", line)

            # 3. 데이터 업데이트 (전송 스레드가 가져가도록 공유 변수에 저장)
            if tilt is not None:
                current_data["tilt"] = tilt
            if temp is not None:
                current_data["temp"] = temp
            if hum is not None:
                current_data["hum"] = hum

            # 4. 화면 출력 (제자리 갱신)
            t_val = current_data["temp"]
            r_val = current_data["tilt"]
            
            if r_val is not None:
                print(f"📡 Sensor: {r_val} deg  |  Temp: {t_val} C      ", end="\r")

    except KeyboardInterrupt:
        print("\n[종료] 프로그램을 끕니다.")
        running = False
        time.sleep(1)

if __name__ == "__main__":
    main()