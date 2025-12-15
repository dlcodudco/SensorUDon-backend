SensorUdon-backend 📦
-
IoT 기반 스마트 배달 박스(Safe Food) 프로젝트의 백엔드 서버입니다. 하드웨어 센서(ESP32, Arduino)로부터 수집된 Raw 데이터를 정제(Parsing)하고, 프론트엔드 애플리케이션에 실시간 데이터를 제공하는 데이터 파이프라인의 허브 역할을 수행합니다.

📋 프로젝트 개요
-
이 프로젝트는 배달 중 음식의 상태(온도, 습도, 기울기)를 실시간으로 모니터링하여 배달 사고를 예방하는 시스템입니다. 본 백엔드 리포지토리는 LoRa 통신을 통해 수신된 시리얼 데이터를 읽어들여 웹 애플리케이션에서 사용할 수 있는 표준 JSON 포맷으로 변환하고 API를 제공합니다.

🏗️ System Architecture & Data Flow
-
지원하신 직무와 관련하여 가장 중요한 **데이터 흐름도**입니다.

코드 스니펫

graph LR

    A[Sensors (Tilt/Temp/Humid)] -->|LoRa Wireless| B[Receiver (Arduino)]
    
    B -->|Serial Comm (UART)| C[SensorUdon-backend]
    
    C -->|Data Parsing & Log| C
    
    C -->|REST API (JSON)| D[Safe Food Web App]
    
1. Data Acquisition: 기울기, 온습도 센서 데이터 수집 및 LoRa 무선 송신
   
2. Serial Communication: 수신 모듈과 백엔드 서버 간 시리얼(USB) 통신 연결
   
3. Data Processing: b'Temp:25,Tilt:0' 형태의 비정형 Raw Data를 파싱하여 구조화된 객체로 변환
   
4. API Serving: 프론트엔드 요청에 따라 실시간 상태 데이터 응답
   

🛠️ Tech Stack
-
• Language: Python 3.x

• Framework: FastAPI (비동기 처리를 통한 빠른 응답 속도 확보)

• Library:

     • pyserial: 아두이노 시리얼 통신 데이터 수신
  
     • uvicorn: ASGI 서버 실행
  
     • pydantic: 데이터 유효성 검사 및 스키마 정의

✨ Key Features
-
• Real-time Serial Monitoring: 시리얼 포트를 통해 들어오는 하드웨어 로그를 실시간으로 리스닝

• Data Normalization: 바이트 스트림(Byte Stream) 형태의 로그를 분석하여 백엔드 표준 스키마로 정규화

• Exception Handling: 하드웨어 통신 중 발생하는 노이즈 데이터 및 연결 끊김 예외 처리

• RESTful API: 클라이언트(Web)를 위한 상태 조회 API 엔드포인트 제공
