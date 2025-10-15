import time
import logging
from typing import Optional
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import warnings


def get_m3u8_url(page_url: str) -> Optional[str]:
    """
    Faster extractor that filters only Angelcam .m3u8 requests.
    Expected runtime: 3–5 seconds max.
    """
    warnings.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    # Limit SeleniumWire capture scope for speed
    seleniumwire_options = {
        'exclude_hosts': ['google.com', 'facebook.com', 'analytics', 'googletagmanager.com'],
        'verify_ssl': False
    }

    driver = webdriver.Chrome(options=chrome_options, seleniumwire_options=seleniumwire_options)
    try:
        driver.get(page_url)
        timeout = time.time() + 12  # give max 12 sec to find it
        while time.time() < timeout:
            for request in driver.requests:
                if request.response and "angelcam.com" in request.url and ".m3u8" in request.url:
                    logging.info(f"🎯 Found M3U8 URL: {request.url}")
                    return request.url
            time.sleep(0.5)
        logging.warning("⚠️ Timed out waiting for .m3u8 request.")
        return None
    finally:
        driver.quit()


def get_new_url_func() -> Optional[str]:
    """
    Wrapper for the refresher loop.
    This will call get_m3u8_url() for the IACC livestream.
    """
    PAGE_URL = "https://iaccplano.click2stream.com/"
    url = get_m3u8_url(PAGE_URL)
    if url:
        logging.info(f"✅ New stream URL obtained: {url}")
    else:
        logging.warning("⚠️ Failed to get new stream URL.")
    return url


def unmute_video(livestream_url: str, auto_unmute: bool = True, wait_time: int = 3):
    """
    Opens the livestream and clicks the mute/unmute button if needed.
    Keeps browser open for manual verification.
    """
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
