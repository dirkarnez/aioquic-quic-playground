import asyncio
import os
from typing import Dict, Optional
from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3_ALPN, H3Connection
# 修正 1：導入正確的 aioquic WebTransport 相關事件
from aioquic.h3.events import DatagramReceived, H3Event, HeadersReceived, WebTransportStreamDataReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import ProtocolNegotiated, QuicEvent

# 全局字典，用於追蹤瀏覽器連線：{session_id: protocol_instance}
active_browsers: Dict[int, 'WebTransportServerProtocol'] = {}

# --- PART A: 處理感測器傳入的原始 UDP 數據 ---
class SensorUDPServerProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data: bytes, addr):
        if not active_browsers:
            return
            
        # 廣播原始數據給所有已連線的 WebTransport 瀏覽器
        for session_id, protocol in list(active_browsers.items()):
            try:
                # 根據 WebTransport 標準，Datagram 傳輸需自帶 Flow ID 前綴（單純傳輸時通常為 0 號 varint，即 b'\x00'）
                payload = b"\x00" + data
                protocol._http.send_datagram(stream_id=session_id, data=payload)
                protocol.transmit()  # 立即清空快取發送
            except Exception as e:
                print(f"Error broadcasting to session {session_id}: {e}")
                active_browsers.pop(session_id, None)

# --- PART B: 網頁 Dashboard 的 WebTransport 協定處理器 ---
class WebTransportServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._http: Optional[H3Connection] = None
        self._session_id: Optional[int] = None

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, ProtocolNegotiated):
            # QUIC 握手成功，初始化 HTTP/3 連線並啟用 WebTransport 支援
            self._http = H3Connection(self._quic, enable_webtransport=True)

        if self._http is not None:
            # 將底層 QUIC 事件交由 HTTP/3 引擎解析，並遞迴處理產生的 H3 事件
            for h3_event in self._http.handle_event(event):
                self._h3_event_received(h3_event)

    def _h3_event_received(self, event: H3Event) -> None:
        # 1. 攔截瀏覽器的 WebTransport CONNECT 握手請求
        if isinstance(event, HeadersReceived):
            headers = dict(event.headers)
            method = headers.get(b":method")
            path = headers.get(b":path", b"/")
            if method == b"CONNECT" and headers.get(b":protocol") == b"webtransport":
                print(f"Browser WebTransport connection approved! Session ID: {event.stream_id}")
                
                # 回應狀態碼 200 完成握手
                self._http.send_headers(
                    stream_id=event.stream_id,
                    headers=[
                        (b":status", b"200"),
                        (b"sec-webtransport-http3-draft", b"draft02"),
                    ],
                )
                self._session_id = event.stream_id
                active_browsers[self._session_id] = self
                self.transmit()
            elif method == b"GET":
                print(f"Browser HTTP/3 Request for SPA Page: {path.decode()}")
                
                # 讀取本地的 index.html 檔案
                html_path = "index.html"
                if os.path.exists(html_path):
                    with open(html_path, "rb") as f:
                        body = f.read()
                    status = b"200"
                else:
                    body = b"SPA index.html not found on server root."
                    status = b"404"

                # 1. 先發送 HTTP 響應頭 (Response Headers)
                self._http.send_headers(
                    stream_id=event.stream_id,
                    headers=[
                        (b":status", status),
                        (b"content-type", b"text/html; charset=utf-8"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                )
                # 2. 隨後發送 HTML 網頁主體內容並標記 Stream 結束 (end_stream=True)
                self._http.send_data(stream_id=event.stream_id, data=body, end_stream=True)
                self.transmit()

        # 2. 接收來自瀏覽器的 Datagram 數據 (選填：如果前端有回傳控制指令)
        elif isinstance(event, DatagramReceived):
            # 這裡可以處理來自網頁端 dashboard 的資料
            pass
            
        # 修正 2：使用正確的 WebTransport 數據流事件
        elif isinstance(event, WebTransportStreamDataReceived):
            # 當瀏覽器建立可靠數據流 (Stream) 並發送資料時會觸發此處
            pass

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if self._session_id in active_browsers:
            print(f"Browser dashboard session {self._session_id} disconnected.")
            active_browsers.pop(self._session_id, None)
        super().connection_lost(exc)


async def main():
    # 1. 配置 QUIC 設定 (瀏覽器安全性要求必須附帶憑證)
    configuration = QuicConfiguration(is_client=False, alpn_protocols=H3_ALPN)
    configuration.load_cert_chain(certfile="ssl_cert.pem", keyfile="ssl_key.pem")
    
    # 2. 啟動供瀏覽器連線的 WebTransport 端點 (Port 4433)
    loop = asyncio.get_running_loop()
    await serve(
        host="0.0.0.0",
        port=4433,
        configuration=configuration,
        create_protocol=WebTransportServerProtocol
    )
    print("WebTransport server listening on port 4433...")

    # 3. 啟動供硬體感測器連線的本地 UDP 監聽器 (Port 5555)
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: SensorUDPServerProtocol(),
        local_addr=('0.0.0.0', 5555)
    )
    print("Sensor UDP listener active on port 5555...")
    
    # 保持伺服器永久運行
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
