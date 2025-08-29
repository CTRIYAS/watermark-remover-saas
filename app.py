from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

app = FastAPI(title="Video Watermark Remover", version="0.1.0")

def ffmpeg_has_delogo() -> bool:
    try:
        result = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True, check=True)
        return "delogo" in result.stdout
    except Exception:
        return False

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/remove")
async def remove_watermark(file: UploadFile = File(...), params: Optional[str] = Form(None)):
    if not ffmpeg_has_delogo():
        raise HTTPException(status_code=500, detail="FFmpeg with delogo filter is required.")

    rect = {"x": 1600, "y": 900, "w": 320, "h": 180}
    if params:
        try:
            user_rect = json.loads(params)
            for k in ("x", "y", "w", "h"):
                if k in user_rect and isinstance(user_rect[k], (int, float)):
                    rect[k] = int(user_rect[k])
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in params")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / file.filename
        content = await file.read()
        with open(input_path, "wb") as f:
            f.write(content)
        output_path = Path(tmpdir) / f"cleaned_{file.filename}"
        delogo_filter = f"delogo=x={rect['x']}:y={rect['y']}:w={rect['w']}:h={rect['h']}:show=0"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            delogo_filter,
            "-c:a",
            "copy",
            str(output_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e)
            raise HTTPException(status_code=500, detail=f"FFmpeg processing failed: {error_msg}")
        return FileResponse(
            path=str(output_path),
            filename=f"cleaned_{file.filename}",
            media_type="video/mp4",
        )


from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Mount static directory for serving HTML and other assets
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def frontend():
    with open("static/index.html", "r") as f:
        return HTMLResponse(f.read())
