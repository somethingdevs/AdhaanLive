import base64
import json
import urllib.parse

token_url = "https://e1-na3.angelcam.com/cameras/1223/streams/hls/playlist.m3u8?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9%2EeyJpYXQiOjE3NjA0ODIzNTksIm5iZiI6MTc2MDQ4MjIzOSwiZXhwIjoxNzYwNDg5NTU5LCJkaWQiOiIxMjIzIn0%2E0P1QwGijLJjI%2DmRhIR9WbvJW%2DX5c%2DYwJxrKh%5FEkStJQ"

# Extract the token and URL-decode it
token = urllib.parse.unquote(token_url.split("token=")[1])

# Split JWT into parts
header_b64, payload_b64, signature = token.split(".")

# Decode payload
payload_json = base64.urlsafe_b64decode(payload_b64 + "==").decode("utf-8")
payload = json.loads(payload_json)

print(payload)
