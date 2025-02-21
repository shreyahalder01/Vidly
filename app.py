from flask import Flask, request, render_template, send_file, jsonify
import yt_dlp
import os
import threading

app = Flask(__name__)
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Global variable to hold download progress and status.
download_status = {
    "progress": 0,
    "filename": None,
    "status": "idle"  # Possible values: idle, starting, downloading, finished, error
}


def progress_hook(d):
    global download_status
    if d['status'] == 'downloading':
        total = d.get('total_bytes', 0)
        downloaded = d.get('downloaded_bytes', 0)
        if total > 0:
            download_status["progress"] = round((downloaded / total) * 100, 2)
        else:
            download_status["progress"] = 0
        download_status["status"] = "downloading"
    elif d['status'] == 'finished':
        download_status["progress"] = 100
        download_status["status"] = "finished"
        download_status["filename"] = d.get('filename')




def download_video(video_url, chosen_format):
    global download_status
    ydl_opts = {
        'format': chosen_format,
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
            download_status["filename"] = filename
    except Exception as e:
        download_status["status"] = "error"
        print("Download error:", e)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        video_url = request.form.get('video_url')
        if video_url:
            # Extract video info without downloading.
            ydl_opts = {'skip_download': True}
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                    formats = info.get('formats', [])

                    # Build list of available formats with extra details.
                    format_options = []
                    for f in formats:
                        if f.get('vcodec') != 'none':
                            height = f.get('height') or 0
                            file_size = f.get('filesize') or f.get('filesize_approx')
                            file_size_mb = round(file_size / (1024 * 1024), 2) if file_size else None
                            format_options.append({
                                'format_id': f.get('format_id'),
                                'format': f.get('format'),
                                'resolution': height,
                                'filesize': file_size_mb
                            })
                    # Sort options by resolution (highest first).
                    format_options = sorted(format_options, key=lambda x: x['resolution'], reverse=True)
                return render_template('quality.html', video_url=video_url, format_options=format_options)
            except Exception as e:
                return f"An error occurred while extracting video info: {e}"
    return render_template('index.html')


@app.route('/start_download', methods=['POST'])
def start_download():
    global download_status
    video_url = request.form.get('video_url')
    chosen_format = request.form.get('format')
    if video_url and chosen_format:
        # Reset progress.
        download_status = {"progress": 0, "filename": None, "status": "starting"}
        # Start download in a background thread.
        thread = threading.Thread(target=download_video, args=(video_url, chosen_format))
        thread.start()
        return jsonify({"status": "started"})
    return jsonify({"status": "error", "message": "Missing parameters"})


@app.route('/progress')
def progress():
    return jsonify(download_status)


@app.route('/download_file')
def download_file():
    global download_status
    if download_status.get("filename") and download_status.get("status") == "finished":
        return send_file(download_status["filename"], as_attachment=True)
    return "File not ready", 404


if __name__ == '__main__':
    app.run(debug=True)
