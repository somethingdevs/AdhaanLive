import time
import logging
from typing import Optional
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


def get_m3u8_url(page_url: str) -> Optional[str]:
    """Extract Angelcam .m3u8 URL by sniffing network traffic via SeleniumWire."""

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    seleniumwire_options = {
        'exclude_hosts': [
            'google.com', 'facebook.com',
            'analytics', 'googletagmanager.com'
        ],
        'verify_ssl': False
    }

    driver = webdriver.Chrome(
        options=chrome_options,
        seleniumwire_options=seleniumwire_options
    )

    start_time = time.time()

    try:
        logging.info(f"[STREAM] Loading page: {page_url}")
        driver.get(page_url)

        # Try entering iframe
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            iframe = driver.find_element(By.TAG_NAME, "iframe")
            driver.switch_to.frame(iframe)
            logging.debug("[STREAM] Switched to iframe")
        except Exception:
            logging.debug("[STREAM] No iframe found; continuing")

        # Try clicking video element
        try:
            video = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "video"))
            )
            actions = ActionChains(driver)
            actions.move_to_element(video).click().perform()
            logging.debug("[STREAM] Clicked <video> element to trigger playback")
        except Exception:
            logging.debug("[STREAM] Could not click video element")

        # Sniff network traffic
        timeout = time.time() + 40
        while time.time() < timeout:
            for req in driver.requests:
                if req.response and "angelcam.com" in req.url and ".m3u8" in req.url:
                    elapsed = time.time() - start_time
                    logging.info(f"[STREAM] Found M3U8 URL ({elapsed:.1f}s)")
                    return req.url
            time.sleep(0.3)

        logging.warning("[STREAM] Timeout waiting for .m3u8 URL")
        return None

    except Exception as e:
        logging.error(f"[STREAM] Failure: {e}")
        return None

    finally:
        driver.quit()


def get_new_url_func() -> Optional[str]:
    """Retry wrapper for getting M3U8 URL."""
    PAGE_URL = "https://iaccplano.click2stream.com/"
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        logging.info(f"[STREAM] Fetch attempt {attempt}/{max_retries}")
        url = get_m3u8_url(PAGE_URL)
        if url:
            logging.info(f"[STREAM] Got stream URL (attempt {attempt})")
            return url

        logging.warning(f"[STREAM] Attempt {attempt} failed; retrying...")
        time.sleep(2)

    logging.error("[STREAM] Unable to obtain M3U8 URL after retries")
    return None


def unmute_video(livestream_url: str, auto_unmute: bool = True, wait_time: int = 3):
    """Click unmute button on livestream if present."""
    if not auto_unmute:
        logging.info("[UNMUTE] Auto-unmute disabled")
        return

    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)

    driver = webdriver.Chrome(options=options)
    driver.get(livestream_url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "iframe"))
        )
        iframe = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "video"))
        )
        video = driver.find_element(By.TAG_NAME, "video")

        actions = ActionChains(driver)

        for _ in range(5):
            actions.move_to_element(video).perform()
            time.sleep(wait_time)

            try:
                mute_btn = driver.find_element(By.CLASS_NAME, "drawer-icon.media-control-icon")
                mute_btn.click()
                logging.info("[UNMUTE] Stream unmuted successfully")
                return
            except Exception:
                logging.debug("[UNMUTE] Mute button not found; retrying")

    except Exception as e:
        logging.error(f"[UNMUTE] Error: {e}")

    finally:
        logging.info("[UNMUTE] Browser left open for verification")
