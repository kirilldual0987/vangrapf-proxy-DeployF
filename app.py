#!/usr/bin/env python3
import os
import tempfile
import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

# ---------- Конфигурация ----------
DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
DEFAULT_TIMEOUT = 30
COOKIE_ENV = os.environ.get("YOUTUBE_COOKIES")  # переменная окружения с содержимым cookies.txt

def get_cookies_file():
    """Создаёт временный файл из переменной окружения YOUTUBE_COOKIES"""
    if not COOKIE_ENV:
        return None
    fd, path = tempfile.mkstemp(suffix=".txt", text=True)
    with os.fdopen(fd, 'w') as f:
        f.write(COOKIE_ENV)
    return path

def get_direct_url(video_url):
    """Извлекает прямую ссылку на видео через yt-dlp"""
    cookie_file = get_cookies_file()
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": DEFAULT_TIMEOUT,
        "retries": 5,
        "user_agent": DEFAULT_USER_AGENT,
        "format": "best[height<=1080]",
        "no_playlist": True,
        "merge_output_format": "mp4",
    }
    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if not info:
                return None
            # Прямая ссылка
            direct = info.get("url")
            if not direct and info.get("formats"):
                formats = sorted(info["formats"], key=lambda f: f.get("height") or 0, reverse=True)
                direct = formats[0].get("url") if formats else None
            return direct
    except Exception as e:
        print(f"Extract error: {e}")
        return None
    finally:
        if cookie_file and os.path.exists(cookie_file):
            os.remove(cookie_file)

# ---------- API ----------
@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/stream')
def stream():
    video_url = request.args.get('url')
    if not video_url:
        return jsonify({"error": "Missing url"}), 400

    direct_url = get_direct_url(video_url)
    if not direct_url:
        return jsonify({"error": "Failed to extract video URL"}), 500

    headers = {"User-Agent": DEFAULT_USER_AGENT}
    range_header = request.headers.get('Range')
    if range_header:
        headers['Range'] = range_header

    try:
        resp = requests.get(direct_url, headers=headers, stream=True, timeout=DEFAULT_TIMEOUT)
        response = Response(resp.iter_content(chunk_size=8192),
                            status=resp.status_code,
                            content_type=resp.headers.get('Content-Type', 'video/mp4'))
        if 'Content-Range' in resp.headers:
            response.headers['Content-Range'] = resp.headers['Content-Range']
        if 'Content-Length' in resp.headers:
            response.headers['Content-Length'] = resp.headers['Content-Length']
        response.headers['Accept-Ranges'] = 'bytes'
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Missing url"}), 400
    video_url = data['url']

    direct_url = get_direct_url(video_url)
    if not direct_url:
        return jsonify({"error": "Failed to extract video URL"}), 500

    try:
        resp = requests.get(direct_url, stream=True)
        return Response(resp.iter_content(chunk_size=8192),
                        headers={"Content-Disposition": "attachment; filename=video.mp4"},
                        content_type="video/mp4")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
