import logging
import threading
import time

logger = logging.getLogger(__name__)

def periodic_ping():
    """
    Gửi ping định kỳ để giữ bot luôn hoạt động.
    """
    while True:
        logger.debug("Bot vẫn đang hoạt động...")
        time.sleep(300)  # Ping mỗi 5 phút

def start_ping_thread():
    """
    Bắt đầu thread gửi ping định kỳ.
    """
    ping_thread = threading.Thread(target=periodic_ping)
    ping_thread.daemon = True
    ping_thread.start()
    logger.info("Đã bắt đầu thread ping định kỳ")