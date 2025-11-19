const express = require("express");
const cors = require("cors");
const { SerialPort, ReadlineParser } = require("serialport");

const app = express();
app.use(cors());

let latestData = {
  tilt: null,
  temp: null,
  humid: null,
};

// ----------------------
// 1) 시리얼 포트 연결
// ----------------------
const port = new SerialPort(
  {
    path: "COM14",      // 👉 네 PC에서 실제 사용하는 포트
    baudRate: 115200,   // 👉 아두이노(LoRa32)의 BAUD_RATE와 동일하게
  },
  (err) => {
    if (err) {
      console.error("시리얼 포트 열기 실패:", err.message);
      return;
    }
    console.log("✅ 시리얼 포트 연결 성공");
  }
);

const parser = port.pipe(new ReadlineParser({ delimiter: "\n" }));

// ----------------------
// 2) 들어오는 줄 처리
// ----------------------
parser.on("data", (line) => {
  const txt = line.trim();
  console.log("RAW:", txt);

  // JSON 형태("{...}")가 아니면 바로 무시 ([RX] / [DHT] 라인들)
  if (!txt.startsWith("{") || !txt.endsWith("}")) {
    return;
  }

  try {
    const obj = JSON.parse(txt);  // {"tilt":..,"temp":..,"humid":..}
    console.log("파싱 성공:", obj);
    latestData = obj;
  } catch (err) {
    console.log("파싱 오류:", err.message);
  }
});

// ----------------------
// 3) 센서 데이터 API
// ----------------------
app.get("/sensor", (req, res) => {
  res.json(latestData);
});

// ----------------------
// 4) 서버 실행
// ----------------------
app.listen(3000, () => {
  console.log("백엔드 서버 실행 중 (http://localhost:3000)");
});
