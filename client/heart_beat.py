import asyncio
import websockets
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SERVER_URI = "ws://8.216.33.92:8001" 

async def run_client():
    """
    主客户端逻辑：连接、保持连接，并实现自动重连。
    """
    while True: 
        try:
            async with websockets.connect(SERVER_URI) as websocket:
                logging.info(f"成功连接到服务器: {SERVER_URI}")
                

                await websocket.wait_closed()

        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as e:
            logging.error(f"连接断开或失败: {e}")
            logging.info("将在 5 秒后尝试重新连接...")
            await asyncio.sleep(5) 
        except Exception as e:
            logging.error(f"发生未知错误: {e}")
            logging.info("将在 5 秒后尝试重新连接...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(run_client())
    except KeyboardInterrupt:
        logging.info("客户端手动关闭。")