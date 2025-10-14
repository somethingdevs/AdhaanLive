import time
import logging
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from typing import Optional


def get_m3u8_url(page_url: str) -> Optional[str]:
    """Extract .m3u8 stream URL from a livestream page."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.get(page_url)
        time.sleep(10)
        for request in driver.requests:
            if request.response and ".m3u8" in request.url:
                logging.info(f"🎯 Found M3U8 URL: {request.url}")
                return request.url
        logging.warning("⚠️ No .m3u8 URL found on this page.")
        return None
    finally:
        driver.quit()


def unmute_video(livestream_url: str, auto_unmute: bool = True, wait_time: int = 3):
    """Unmute livestream video via Selenium interaction."""
    if not auto_unmute:
        logging.info("🔕 Auto-unmute disabled in config.")
        return
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)
    driver = webdriver.Chrome(options=options)
    driver.get(livestream_url)
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        iframe = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "video")))
        video = driver.find_element(By.TAG_NAME, "video")
        actions = ActionChains(driver)
        for _ in range(5):
            actions.move_to_element(video).perform()
            time.sleep(wait_time)
            try:
                mute_btn = driver.find_element(By.CLASS_NAME, "drawer-icon.media-control-icon")
                mute_btn.click()
                logging.info("🎉 Stream unmuted successfully!")
                break
            except Exception:
                logging.debug("Mute button not found, retrying...")
    except Exception as e:
        logging.exception(f"❌ Unmute error: {e}")
    finally:
        logging.info("🎥 Browser will remain open for verification.")
