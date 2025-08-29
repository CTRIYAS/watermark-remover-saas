# AI Video Watermark Remover

This is a simple proof‑of‑concept service for removing watermarks from videos. It exposes a small web API using [FastAPI](https://fastapi.tiangolo.com/) that accepts a video upload, applies an FFmpeg `delogo` filter, and returns the processed file.

> **Disclaimer:** Removing watermarks from copyrighted media may violate the terms of service of streaming providers or local laws. This tool is provided for educational purposes only.

## How it works

1. A client sends a `POST` request to `/remove` with a video file. An optional JSON payload describing the location of the watermark (e.g. `{ "x":1280, "y":0, "w":200, "h":80 }`) can be provided to customise the removal area.
2. The server saves the uploaded file to a temporary directory and then uses FFmpeg's built‑in [`delogo` filter](https://ffmpeg.org/ffmpeg-filters.html#delogo) to blur or mask the specified region.
3. The resulting video is returned to the client as a downloadable file.

The default removal rectangle targets the bottom right corner of a 1920×1080 video (`x=1600, y=900, w=320, h=180`). You can override this by sending a JSON body with your own rectangle.

## Deployment on Render.com

The `render.yaml` blueprint included in this repository defines a simple web service on the free tier:

```yaml
services:
  - type: web
    name: watermark-remover
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT
```

Make sure your account has access to the Render free tier, then commit this repository to GitHub and import it as a new service. When deployed, the API will be accessible at the public URL provided by Render.

## Local development

1. Install the requirements:
   ```bash
   python3 -m venv venv
   . venv/bin/activate
   pip install -r requirements.txt
   ```
2. Ensure FFmpeg is available on your system. On Debian/Ubuntu this can be installed with:
   ```bash
   sudo apt-get update && sudo apt-get install ffmpeg
   ```
3. Start the server:
   ```bash
   uvicorn app:app --reload
   ```
4. Use `curl` or a tool like Postman to upload a video to `http://localhost:8000/remove`. Example:
   ```bash
   curl -X POST -F "file=@input.mp4" -H "Content-Type: multipart/form-data" http://localhost:8000/remove --output output.mp4
   ```

## License

This project is released under the MIT License. See `LICENSE` for details.
