import requests
from datetime import datetime


def get_prayer_times(city="Dallas", country="US", method=2):
    """
    Fetches prayer times from Aladhan API and converts them into datetime.time objects.
    """
    api_url = f"https://api.aladhan.com/v1/timingsByCity?city={city}&country={country}&method={method}"

    response = requests.get(api_url, timeout=10000)
    data = response.json()

    if response.status_code == 200:
        return {
            name: datetime.strptime(time_str, "%H:%M").time()
            for name, time_str in data["data"]["timings"].items()
        }
    else:
        print("⚠️ Error fetching prayer times!")
        return None


import logging
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ✅ Set up logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# 🔗 Your livestream page
LIVESTREAM_URL = "https://iaccplano.click2stream.com/"


def unmute_video():
    """Opens the livestream page, switches to the iframe, continuously hovers, and clicks the correct mute button."""

    logging.info("🚀 Starting the Chrome driver...")
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)

    # ✅ Start WebDriver
    driver = webdriver.Chrome(options=options)

    logging.info("🌍 Opening the livestream page...")
    driver.get(LIVESTREAM_URL)

    try:
        # ✅ Step 1: Wait for the iframe to load
        logging.info("⏳ Waiting for the iframe to load...")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        iframe = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe)
        logging.info("📺 Switched to the video iframe.")

        # ✅ Step 2: Wait for the video element
        logging.info("⏳ Waiting for the video element to appear...")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "video")))
        video_element = driver.find_element(By.TAG_NAME, "video")

        # ✅ Step 3: Continuous hover loop (keeps media controls open)
        logging.info("🎥 Starting continuous hover loop...")
        actions = ActionChains(driver)
        hover_attempts = 0

        while hover_attempts < 5:  # Try hovering 5 times
            actions.move_to_element(video_element).perform()
            logging.info(f"🎥 Hover attempt {hover_attempts + 1}...")
            time.sleep(1)  # Short delay between hovers

            try:
                # ✅ Step 4: Locate mute button AFTER hover (prevents stale elements)
                logging.info("🔍 Looking for the mute button...")
                mute_button = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "drawer-icon.media-control-icon"))
                )
                if mute_button:
                    logging.info("✅ Mute button found!")
                    break
            except Exception:
                logging.warning("⚠️ Mute button not found. Retrying hover...")

            hover_attempts += 1

        if hover_attempts == 5:
            logging.error("❌ Mute button was not found after multiple hover attempts.")
            return

        # ✅ Step 5: Click the mute button (SVG inside div)
        logging.info("🔊 Clicking the mute button...")
        mute_svg = mute_button.find_element(By.TAG_NAME, "svg")
        mute_svg.click()

        logging.info("🎉 Stream unmuted successfully!")

    except Exception as e:
        logging.exception("❌ An error occurred during execution.")
        logging.error(driver.page_source)  # Print page source for debugging

    logging.info("🎥 Browser will remain open. Verify if audio is playing.")

# Run the function
unmute_video()
