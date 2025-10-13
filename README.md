# 🕌 Adhaan Streamer

**Adhaan Streamer** is an open-source Python application that detects and streams the **live Adhaan (call to prayer)**
from mosque livestreams directly to homes or connected speakers.  
The goal is to build a community-driven platform where masjids can easily expose their Adhaan livestream via a simple
API, and users can experience it automatically at prayer times.

---

## 🌍 Project Overview

The Adhaan Streamer connects to a mosque’s 24/7 livestream (e.g., Click2Stream, Angelcam, YouTube Live, etc.)  
It uses **audio detection and prayer-time scheduling** to:

- Listen for Adhaan automatically at the correct times
- Stream the live audio/video when Adhaan begins
- Detect when the Adhaan ends and stop playback

It can be run locally on a computer, Raspberry Pi, or small IoT device, and can later integrate into home automation
systems.

---

## 🧩 Features

- 🕓 Fetches **accurate prayer times** from a public API
- 🎙️ Detects **live Adhaan start** based on loudness thresholds
- 🔇 Detects **Adhaan end** automatically via silence detection
- 🎥 Streams **real-time mosque audio/video**
- 🔁 Refreshes livestream URLs automatically (avoiding token expiry)
- 🧠 Modular code — easy to integrate with APIs, GUIs, or dashboards

---

## 🛠️ Tech Stack

| Category | Technology |
|-----------|-------------|
| Language | Python 3.9 |
| Audio/Video | FFmpeg, PyAudio, SoundDevice |
| Data Processing | NumPy |
| Scheduling | `datetime`, prayer time API |
| API | FastAPI *(planned)* |
| UI *(optional)* | Streamlit *(future)* |

---

## ⚙️ Installation

### 1️⃣ Clone this repository

```bash
git clone https://github.com/<your-username>/adhaan-streamer.git
cd adhaan-streamer
```

### 2️⃣ Create and activate a Conda environment

```bash
conda env create -f environment.yml
conda activate adhaan_streamer
```

(If you prefer pip, you can also run pip install -r requirements.txt.)

### 3️⃣ Verify installation

Run this command to make sure everything is installed correctly:

```bash
python -m sounddevice
```

You should see a list of available audio devices.

## ▶️ Usage

Run the main script:

```bash
python adhaan_streamer.py
```

The program will:

- Fetch today’s prayer times

- Display them in a table

- Continuously listen for Adhaan start

- Automatically play the livestream when detected

Example console output:

```bash
🎙️ Listening for Adhaan in livestream audio...
🔊 Adhaan detected in livestream! Playing video...
🔇 Adhaan ended. Stopping livestream.
```

## ⚡ Configuration

You can update the livestream URL or location by modifying this in your code:

```python
LIVESTREAM_URL = "https://iaccplano.click2stream.com/"
```

Or extend util.py to:

Support different mosque livestreams

Use alternative prayer time APIs

Store API keys or tokens securely

## 📁 Project Structure

```bash
adhaan_streamer/
│
├── adhaan_streamer.py # Main application logic
├── util.py # Helper functions (API calls, URL refresh, etc.)
├── environment.yml # Conda environment file
├── requirements.txt # Pip dependencies (optional)
├── README.md # Documentation
└── .gitignore # Ignore build and cache files
```

## 🧱 Future Roadmap

- ✅ **Phase 1:** CLI version (local streaming)
- 🧭 **Phase 2:** REST API backend (FastAPI) for public access
- 💻 **Phase 3:** Web UI (Streamlit dashboard) for setup & status
- ☁️ **Phase 4:** Cloud-hosted Adhaan aggregator (multi-masjid support)
- 🕋 **Phase 5:** Integration with IoT devices / smart speakers

## 🤝 Contributing

We welcome contributions from the community!

1. Fork the repository
2. Create a new branch (`feature/new-feature`)
3. Commit your changes
4. Push to your branch and open a pull request

Please test your changes locally before submitting.


---

## 🧾 License

This project is licensed under the **MIT License** — feel free to use, modify, and distribute it.

---

## 💬 Acknowledgements

- **Click2Stream / Angelcam** for livestream access
- **Aladhan API** for global prayer time data
- **Community masjids** for inspiring this project
- Everyone working to make Adhaan accessible to all 💚

> _"And who is better in speech than one who calls to Allah, does righteous deeds, and says,  
> 'Indeed, I am of the Muslims.'"_ — **Qur’an 41:33**

## 🚀 Quick Start Preview

Here’s how the Adhaan Streamer works conceptually:

```bash
            ┌────────────────────────────────────────┐
            │          Mosque Livestream             │
            │ (e.g., Click2Stream / Angelcam / YT)   │
            └────────────────────────────────────────┘
                            │
                            ▼
              ┌────────────────────────┐
              │  Stream URL Fetcher     │
              │ (auto-refresh tokenized)│
              └────────────────────────┘
                            │
                            ▼
          ┌──────────────────────────────────┐
          │    Audio Detection Engine        │
          │  - monitors sound intensity      │
          │  - detects Adhaan start & end    │
          └──────────────────────────────────┘
                            │
                            ▼
      ┌─────────────────────────────────────┐
      │     Player (FFmpeg + FFplay)        │
      │ Streams live video + audio to home  │
      └─────────────────────────────────────┘
                            │
                            ▼
         ┌─────────────────────────────────┐
         │  Logs + Notifications (Planned) │
         │  e.g., mobile alerts / webhooks │
         └─────────────────────────────────┘
```

### 🧭 Typical Workflow

1. `util.py` fetches prayer times via API.
2. Main script listens for Adhaan near each prayer time.
3. When Adhaan starts → plays the livestream automatically.
4. When silence is detected → stops playback.
5. Stream URL refreshes every 10 minutes to avoid expiry.

---

### 🌐 Future Integration Ideas

- REST API for remote access (`/play_adhaan`, `/get_prayer_times`)
- Streamlit or React dashboard for live status
- Integration with **Angelcam**, **Click2Stream**, and **YouTube Live** APIs
- Smart home integration (Google Home, Alexa, etc.)

---

## 🧡 Built for communities, masjids, and families who want to hear the Adhaan echo in every home.
