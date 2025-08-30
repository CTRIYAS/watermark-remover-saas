from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
from pathlib import Path
import subprocess, json, tempfile, os

app = FastAPI(title="Watermark Remover Service", version="1.0")

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
def health():
    return {"status":"ok"}

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = Path("static/upload.html")
    if not html_path.exists():
        return HTMLResponse("<h1>Upload page missing</h1>", status_code=500)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))

@app.get("/remove", response_class=HTMLResponse)
def remove_get():
    return HTMLResponse("""
        <h2>Upload a video</h2>
        <form action="/remove" method="post" enctype="multipart/form-data">
            <label>Video: <input type="file" name="file" required></label><br>
            <label>Params JSON (optional):
                <input type="text" name="params" placeholder='{"x":1600,"y":900,"w":320,"h":180}'>
            </label><br>
            <button type="submit">Process</button>
        </form>
    """)

def ffmpeg_has(filter_name: str) -> bool:
    try:
        output = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, check=True)
        return filter_name in output.stdout
    except Exception:
        return False

def run_ffmpeg(cmd: list):
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        msg = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e)
        raise HTTPException(status_code=500, detail=f"FFmpeg failed: {msg[:2000]}")

@app.post("/remove")
async def remove_watermark(file: UploadFile = File(...), params: Optional[str] = Form(None)):
    if not ffmpeg_has("delogo"):
        raise HTTPException(status_code=500, detail="FFmpeg delogo filter not available.")
    rect = {"x": 1600, "y": 900, "w": 320, "h": 180}
    if params:
        try:
            user_params = json.loads(params)
            for k in ("x", "y", "w", "h"):
                if k in user_params:
                    rect[k] = int(user_params[k])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON for params")
    with tempfile.TemporaryDirectory() as td:
        input_path = Path(td) / file.filename
        input_path.write_bytes(await file.read())
        output_path = Path(td) / f"cleaned_{file.filename}"
        delogo_filter = f"delogo=x={rect['x']}:y={rect['y']}:w={rect['w']}:h={rect['h']}:show=0"
        cmd = ["ffmpeg", "-hide_banner", "-y", "-i", str(input_path), "-vf", delogo_filter, "-c:a", "copy", str(output_path)]
        run_ffmpeg(cmd)
        return FileResponse(str(output_path), filename=output_path.name, media_type="video/mp4")

@app.post("/add_text")
async def add_text_watermark(
    file: UploadFile = File(...),
    text: str = Form(...),
    x: str = Form("w-tw-20"),
    y: str = Form("h-th-20"),
    fontsize: int = Form(36),
    color: str = Form("white@0.7"),
    box: bool = Form(True),
    boxcolor: str = Form("black@0.4"),
    boxborderw: int = Form(10),
    fontfile: Optional[str] = Form(None),
):
    fontfile = fontfile or os.getenv("FONTFILE") or "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    with tempfile.TemporaryDirectory() as td:
        in_path = Path(td) / file.filename
        in_path.write_bytes(await file.read())
        out_path = Path(td) / f"textwm_{file.filename}"
        drawtext = (
            f"drawtext=fontfile='{fontfile}':text='{text}':"
            f"x={x}:y={y}:fontsize={fontsize}:fontcolor={color}"
            + (f":box=1:boxcolor={boxcolor}:boxborderw={boxborderw}" if box else "")
        )
        cmd = ["ffmpeg", "-hide_banner", "-y", "-i", str(in_path), "-vf", drawtext, "-c:a", "copy", str(out_path)]
        run_ffmpeg(cmd)
        return FileResponse(str(out_path), filename=out_path.name, media_type="video/mp4")

@app.post("/add_image")
async def add_image_watermark(
    file: UploadFile = File(...),
    watermark: UploadFile = File(...),
    x: str = Form("W-w-20"),
    y: str = Form("H-h-20"),
    scale_w: Optional[int] = Form(None),
    scale_h: Optional[int] = Form(None),
    opacity: float = Form(0.8),
):
    with tempfile.TemporaryDirectory() as td:
        vid_path = Path(td) / file.filename
        wm_path = Path(td) / watermark.filename
        vid_path.write_bytes(await file.read())
        wm_path.write_bytes(await watermark.read())
        out_path = Path(td) / f"imgwm_{file.filename}"
        wm_input = "[1:v]"
        if scale_w or scale_h:
            sw = scale_w if scale_w else -1
            sh = scale_h if scale_h else -1
            wm_input = f"[1:v]scale={sw}:{sh}[wm];[wm]"
        alpha = max(0.0, min(1.0, opacity))
        filter_complex = (
            f"{wm_input}format=rgba,colorchannelmixer=aa={alpha}[wma];"
            f"[0:v][wma]overlay=x={x}:y={y}[v]"
        )
        cmd = [
            "ffmpeg", "-hide_banner", "-y",
            "-i", str(vid_path),
            "-i", str(wm_path),
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "0:a?", "-c:a", "copy",
            str(out_path),
        ]
        run_ffmpeg(cmd)
        return FileResponse(str(out_path), filename=out_path.name, media_type="video/mp4")
