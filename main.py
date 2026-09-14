import asyncio
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.webtransport.server import WebTransportServer

# Global list to hold active browser sessions
active_browsers = set()

# --- PART A: Handle Incoming Sensor Data (Raw UDP) ---
class SensorUDPServerProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        # 'data' contains the raw CSI bytes from your ESP32/sensor
        if not active_browsers:
            return
            
        # Broadcast the raw bytes directly to all connected web dashboards
        for session in list(active_browsers):
            try:
                session.send_datagram(data)
            except Exception:
                active_browsers.remove(session)

# --- PART B: WebTransport Server for the Browser Dashboard ---
class CSIDashboardServer(WebTransportServer):
    def webtransport_session_established(self, session):
        print("Browser dashboard connected via WebTransport!")
        active_browsers.add(session)

    def webtransport_session_closed(self, session):
        print("Browser dashboard disconnected.")
        if session in active_browsers:
            active_browsers.remove(session)

    def datagram_received(self, data, session):
        # If the dashboard needs to send commands back to the server, handle here
        pass

async def main():
    # 1. Configure QUIC Profile (Requires SSL certificates for browser security)
    configuration = QuicConfiguration(is_client=False)
    configuration.load_cert_chain(certfile="ssl_cert.pem", keyfile="ssl_key.pem")
    
    # 2. Start WebTransport endpoint for Browser (Port 4433)
    loop = asyncio.get_running_loop()
    await serve(
        host="0.0.0.0",
        port=4433,
        configuration=configuration,
        create_protocol=CSIDashboardServer
    )
    print("WebTransport server listening on port 4433...")

    # 3. Start local UDP listener for Sensors (Port 5555)
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: SensorUDPServerProtocol(),
        local_addr=('0.0.0.0', 5555)
    )
    print("Sensor UDP listener active on port 5555...")
    
    # Keep server running perpetually
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())


asyncio.
