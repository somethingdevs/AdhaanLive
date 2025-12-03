import time
import logging
from typing import Optional
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


# ======================================================
#   DISABLE ALL SELENIUMWIRE + PROXY + CHROME NOISE
# ======================================================
for noisy in [
    "seleniumwire",
    "seleniumwire.handler",
    "seleniumwire.server",
    "seleniumwire.storage",
    "seleniumwire.proxy",
    "urllib3.connectionpool",
    "WDM",
    "undetected_chromedriver",
]:
    logging.getLogger(noisy).setLevel(logging.CRITICAL)

# Also silence Chrome DevTools logs
logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.CRITICAL)


# ======================================================
#   GET M3U8 URL (QUIET MODE)
# ======================================================
def get_m3u8_url(page_url: str) -> Optional[str]:
    """Extract .m3u8 URL with zero noisy logs."""

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--log-level=3")          # Chromium internal silence
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    seleniumwire_options = {
        "exclude_hosts": [
            "google.com",
            "facebook.com",
            "analytics",
            "googletagmanager.com",
            "connect.facebook.net",
        ],
        "verify_ssl": False,
        "request_storage_max_size": 200,      # Keep memory low, less clutter
    }

    driver = webdriver.Chrome(
        options=chrome_options,
        seleniumwire_options=seleniumwire_options
    )

    start_time = time.time()

    try:
        logging.info("[STREAM] Loading livestream page...")
        driver.get(page_url)

        # Try entering iframe silently
        try:
            iframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            driver.switch_to.frame(iframe)
        except:
            pass  # No iframe – quiet fail

        # Try clicking play silently
        try:
            video = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.TAG_NAME, "video"))
            )
            ActionChains(driver).move_to_element(video).click().perform()
        except:
            pass  # also quiet

        # Sniff .m3u8 URL
        timeout = time.time() + 40
        while time.time() < timeout:
            for req in driver.requests:
                if (
                    req.response
                    and "angelcam.com" in req.url
                    and ".m3u8" in req.url
                ):
                    elapsed = time.time() - start_time
                    logging.info(f"[STREAM] Found M3U8 URL ({elapsed:.1f}s)")
                    return req.url

            time.sleep(0.25)

        logging.warning("[STREAM] Timeout — no .m3u8 URL found")
        return None

    except Exception as e:
        logging.error(f"[STREAM] get_m3u8_url error: {e}")
        return None

    finally:
        driver.quit()


# ======================================================
#   RETRY WRAPPER
# ======================================================
def get_new_url_func() -> Optional[str]:
    """Retry wrapper, minimal logging."""
    PAGE_URL = "https://iaccplano.click2stream.com/"
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        url = get_m3u8_url(PAGE_URL)
        if url:
            logging.info(f"[STREAM] New URL acquired (attempt {attempt})")
            return url

        logging.warning(f"[STREAM] Retry {attempt}/{max_retries} failed")
        time.sleep(2)

    logging.error("[STREAM] All retries failed")
    return None


# ======================================================
#   UNMUTE (kept optional, also quiet)
# ======================================================
def unmute_video(livestream_url: str, auto_unmute: bool = True, wait_time: int = 3):
    if not auto_unmute:
        return

    from seleniumwire import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_experimental_option("detach", True)
    driver = webdriver.Chrome(options=options)
    driver.get(livestream_url)

    try:
        iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "iframe"))
        )
        driver.switch_to.frame(iframe)

        video = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "video"))
        )

        actions = ActionChains(driver)

        for _ in range(5):
            actions.move_to_element(video).perform()
            time.sleep(wait_time)
            try:
                mute_btn = driver.find_element(
                    By.CLASS_NAME, "drawer-icon.media-control-icon"
                )
                mute_btn.click()
                logging.info("[STREAM] Stream unmuted")
                break
            except:
                pass

    except Exception:
        pass

    finally:
        logging.info("[STREAM] Browser open for verification")
