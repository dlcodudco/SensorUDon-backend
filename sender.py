import serial
import time
import json
import re
import requests  # 서버 전송용 라이브러리 (pip install requests 필요)

# -------------------------------
# 설정 (내 컴퓨터 환경)
# -------------------------------
# 아까 장치관리자에서 확인한 포트 번호를 적어주세요.
SERIAL_PORT = "COM5"   
BAUD_RATE = 115200

# 데이터를 보낼 Render 서버 주소
SERVER_URL = "https://sensorudon-backend.onrender.com/update_sensor"

def extract(pattern: str, text: str):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None

def main():
    print(f"[PC] 아두이노 포트({SERIAL_PORT}) 연결 시도 중...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"[PC] 연결 성공! 데이터를 읽어서 {SERVER_URL} 로 전송을 시작합니다.")
    except Exception as e:
        print(f"\n[오류] 아두이노 연결 실패!")
        print(f"에러 내용: {e}")
        return

    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode(errors="ignore").strip()
            else:
                time.sleep(0.1)
                continue

            if not line:
                continue
            
            # [디버깅] 아두이노가 보내는 원본 메시지 확인 (이걸 봐야 수정 가능)
            print(f"[Raw] {line}") 

            # 데이터 파싱 변수 초기화
            temp = None
            hum = None
            tilt = None

            # 1) JSON 파싱 시도
            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    temp = float(data.get("temp")) if "temp" in data else None
                    hum = float(data.get("humid")) if "humid" in data else None
                    # tilt, angle, roll, x 등 다양한 키 시도
                    if "tilt" in data: tilt = float(data["tilt"])
                    elif "angle" in data: tilt = float(data["angle"])
                    elif "roll" in data: tilt = float(data["roll"])
                    elif "x" in data: tilt = float(data["x"])
                except:
                    pass

            # 2) 정규식 파싱 시도 (JSON 실패시)
            # 온도/습도
            if temp is None: temp = extract(r"(?:temp|temperature)[:=\s]+([-+]?\d+\.?\d*)", line)
            if hum is None: hum = extract(r"(?:hum|humid)[:=\s]+([-+]?\d+\.?\d*)", line)
            
            # 기울기 (다양한 이름 패턴 추가)
            if tilt is None: 
                tilt = extract(r"(?:tilt|angle|roll|pitch|x)[:=\s]+([-+]?\d+\.?\d*)", line)

            # 유효한 데이터가 하나라도 있으면 서버로 전송
            if temp is not None or tilt is not None:
                payload = {
                    "temperature": temp,
                    "humidity": hum,
                    "tilt": tilt
                }
                
                try:
                    res = requests.post(SERVER_URL, json=payload, timeout=2)
                    if res.status_code == 200:
                        # 보기 좋게 한 줄로 출력
                        print(f"[전송 성공] T:{temp} H:{hum} Tilt:{tilt}")
                    else:
                        print(f"[서버 오류] {res.status_code}")
                except Exception as req_err:
                    print(f"[전송 실패] {req_err}")

        except Exception as e:
            print(f"[에러] {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()