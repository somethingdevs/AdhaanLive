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
    """
    Extracts Angelcam .m3u8 livestream URL by sniffing network requests.
    Simulates a user click so the player starts streaming in headless mode.
    """

    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    seleniumwire_options = {
        'exclude_hosts': ['google.com', 'facebook.com', 'analytics', 'googletagmanager.com'],
        'verify_ssl': False
    }

    driver = webdriver.Chrome(options=chrome_options, seleniumwire_options=seleniumwire_options)
    start_time = time.time()

    try:
        driver.get(page_url)

        # --- Wait for iframe and switch into it ---
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
            iframe = driver.find_element(By.TAG_NAME, "iframe")
            driver.switch_to.frame(iframe)
            logging.info("🪟 Switched to Angelcam iframe.")
        except Exception:
            logging.warning("⚠️ No iframe found — continuing without switch.")

        # --- Try to click play button (if present) ---
        try:
            video = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "video")))
            actions = ActionChains(driver)
            actions.move_to_element(video).click().perform()
            logging.info("▶️ Clicked on video element to trigger playback.")
        except Exception as e:
            logging.debug(f"Could not click video: {e}")

        # --- Now sniff for .m3u8 requests ---
        timeout = time.time() + 40
        while time.time() < timeout:
            for request in driver.requests:
                if request.response and "angelcam.com" in request.url and ".m3u8" in request.url:
                    elapsed = time.time() - start_time
                    logging.info(f"🎯 Found M3U8 URL in {elapsed:.1f}s: {request.url}")
                    return request.url
            time.sleep(0.3)

        logging.warning("⚠️ Timed out waiting for .m3u8 request.")
        return None

    except Exception as e:
        logging.error(f"❌ get_m3u8_url() failed: {e}")
        return None

    finally:
        driver.quit()


def get_new_url_func() -> Optional[str]:
    """
    Wrapper with retries for robustness.
    Retries up to 3 times to fetch a valid M3U8 livestream URL.
    """
    PAGE_URL = "https://iaccplano.click2stream.com/"
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        url = get_m3u8_url(PAGE_URL)
        if url:
            logging.info(f"✅ New stream URL obtained on attempt {attempt}.")
            return url
        logging.warning(f"⚠️ Attempt {attempt} failed to fetch stream URL, retrying...")
        time.sleep(2)

    logging.error("❌ All attempts to fetch M3U8 URL failed.")
    return None


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
