#!/usr/bin/env python3
import os
import tempfile
import re
import requests
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

# ---------- Конфигурации ----------
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3

PLATFORM_CONFIGS = {
    "rutube": {"extractor_args": {"rutube": {"player_client": "web"}}, "format": "best[height<=1080]"},
    "vk": {"extractor_args": {"vk": {"player_client": "web"}}, "format": "best[height<=1080]"},
    "ok": {"extractor_args": {"ok": {}}, "format": "best[height<=1080]"},
    "youtube": {"extractor_args": {"youtube": {"player_client": "default,-android_sdkless"}}, "format": "best[height<=1080]"},
    "tiktok": {"extractor_args": {"tiktok": {"webapp": "true"}}, "format": "best"},
}

def detect_platform(url: str) -> str:
    if "rutube.ru" in url:
        return "rutube"
    elif "vk.com/video" in url or "vk.ru/video" in url or "vkvideo.ru" in url or "vkvideo.com" in url:
        return "vk"
    elif "ok.ru" in url:
        return "ok"
    elif "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "tiktok.com" in url or "vm.tiktok.com" in url or "vt.tiktok.com" in url:
        return "tiktok"
    else:
        return "unknown"

def get_direct_url(video_url: str, cookies_path: str = None) -> str | None:
    """Извлекает прямую ссылку на видео (лучшее качество) с помощью yt-dlp."""
    platform = detect_platform(video_url)
    if platform == "unknown":
        return None
    config = PLATFORM_CONFIGS.get(platform, PLATFORM_CONFIGS["youtube"])
    opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": DEFAULT_TIMEOUT,
        "retries": DEFAULT_RETRIES,
        "user_agent": DEFAULT_USER_AGENT,
        "extractor_args": config["extractor_args"],
        "format": config["format"],
        "no_playlist": True,
    }
    if cookies_path and os.path.exists(cookies_path):
        opts["cookiefile"] = cookies_path
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if not info:
                return None
            # Прямая ссылка может быть в info['url'] или в formats
            url = info.get("url")
            if not url and info.get("formats"):
                formats = sorted(info["formats"], key=lambda f: f.get("height") or 0, reverse=True)
                url = formats[0].get("url") if formats else None
            return url
    except Exception as e:
        print(f"Error extracting direct URL: {e}")
        return None

# ---------- НОВЫЙ ЭНДПОИНТ /stream с поддержкой Range ----------
@app.route('/stream')
def stream_video():
    """
    Проксирует видео с YouTube/Rutube и поддерживает частичную загрузку (Range).
    Используется так: /stream?url=ОРИГИНАЛЬНАЯ_ССЫЛКА&cookies=ПУТЬ_К_COOKIES (опционально)
    """
    video_url = request.args.get('url')
    if not video_url:
        return jsonify({'error': 'Missing url parameter'}), 400

    # Опционально: cookies_path можно передать как GET-параметр (для YouTube)
    cookies_path = request.args.get('cookies')
    if cookies_path and not os.path.exists(cookies_path):
        cookies_path = None  # если файла нет, игнорируем

    # 1. Получаем прямую ссылку на видео (или HLS-плейлист)
    direct_url = get_direct_url(video_url, cookies_path)
    if not direct_url:
        return jsonify({'error': 'Could not extract video URL'}), 500

    # 2. Передаём дальше Range-заголовок, если он есть (его присылает mpv)
    headers = {'User-Agent': DEFAULT_USER_AGENT}
    range_header = request.headers.get('Range')
    if range_header:
        headers['Range'] = range_header

    try:
        resp = requests.get(direct_url, headers=headers, stream=True, timeout=30)
        # Создаём потоковый ответ
        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        response = Response(generate(), status=resp.status_code, content_type=resp.headers.get('Content-Type', 'video/mp4'))
        # Проксируем заголовки, необходимые для частичной загрузки
        if 'Content-Range' in resp.headers:
            response.headers['Content-Range'] = resp.headers['Content-Range']
        if 'Content-Length' in resp.headers:
            response.headers['Content-Length'] = resp.headers['Content-Length']
        response.headers['Accept-Ranges'] = 'bytes'
        return response
    except Exception as e:
        return jsonify({'error': f'Proxy error: {str(e)}'}), 500

# ---------- Старые эндпоинты (слегка адаптированы для единообразия) ----------
@app.route('/get_stream_url', methods=['POST'])
def get_stream_url():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'Missing url'}), 400
    url = data['url']
    platform = detect_platform(url)
    if platform == 'unknown':
        return jsonify({'error': 'Unsupported platform'}), 400
    cookies = data.get('cookies_path')
    direct = get_direct_url(url, cookies)
    if not direct:
        return jsonify({'error': 'Failed to extract direct URL'}), 500
    # Дополнительно можно получить метаданные (заголовок и т.д.), но пока просто ссылка
    return jsonify({'stream_url': direct, 'platform': platform, 'title': 'Video'})

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'Missing url'}), 400
    url = data['url']
    platform = detect_platform(url)
    if platform == 'unknown':
        return jsonify({'error': 'Unsupported platform'}), 400
    cookies_path = data.get('cookies_path')
    temp_dir = tempfile.mkdtemp()
    filename = None
    opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": DEFAULT_TIMEOUT,
        "retries": DEFAULT_RETRIES,
        "user_agent": DEFAULT_USER_AGENT,
        "extractor_args": PLATFORM_CONFIGS.get(platform, {}).get("extractor_args", {}),
        "format": PLATFORM_CONFIGS.get(platform, {}).get("format", "best"),
        "no_playlist": True,
        "outtmpl": os.path.join(temp_dir, '%(title)s.%(ext)s'),
        "merge_output_format": "mp4",
    }
    if cookies_path and os.path.exists(cookies_path):
        opts["cookiefile"] = cookies_path
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', info.get('title', 'video'))[:100]
            return send_file(
                filename,
                as_attachment=True,
                download_name=f"{safe_title}.mp4",
                mimetype='video/mp4'
            )
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
