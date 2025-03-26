import os
import threading
import time
import logging
from web_app import app as web_app
from bot import run_bot
from keep_alive import start_ping_thread

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Định nghĩa app cho Gunicorn sử dụng
app = web_app

def run_bot_safely():
    """Chạy bot và tự động khởi động lại nếu bị gián đoạn."""
    while True:
        try:
            run_bot()
        except Exception as e:
            logger.error(f"Bot bị lỗi và sẽ được khởi động lại sau 10 giây: {e}")
            time.sleep(10)

# Khởi động thread bot khi module được import (cho Gunicorn)
bot_thread = threading.Thread(target=run_bot_safely)
bot_thread.daemon = True
bot_thread.start()
logger.info("Bot Discord đã được khởi động trong một thread riêng")

# Khởi động thread ping để giữ kết nối
ping_thread = threading.Thread(target=start_ping_thread)
ping_thread.daemon = True
ping_thread.start()
logger.info("Thread ping định kỳ đã được khởi động")

if __name__ == "__main__":
    try:
        # Nếu chạy trực tiếp (không qua Gunicorn), chạy app tại đây
        # Chú ý sử dụng cổng 8080 thay vì 5000 để tránh xung đột với Gunicorn
        web_app.run(host='0.0.0.0', port=9000)
    except KeyboardInterrupt:
        logger.info("Ứng dụng đang dừng...")
    except Exception as e:
        logger.error(f"Lỗi không mong muốn: {e}")