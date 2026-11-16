import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
import uvicorn

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "videos.db"

UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI()


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=3.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=3000")
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    try:
        conn.execute("PRAGMA busy_timeout=3000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL UNIQUE,
                file_path TEXT NOT NULL,        -- absolute path to the file on disk
                video_url TEXT NOT NULL,        -- public URL to the video
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
    finally:
        conn.close()


def safe_filename(company_name: str) -> str:
    stem = re.sub(r"[^\w-]+", "_", company_name.strip()).strip("_")
    return f"{stem or 'video'}.webm"


@app.post("/upload")
async def upload_video(
    request: Request,
    file: Optional[UploadFile] = File(None),
    company_name: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    if file is None or not company_name or not company_name.strip():
        raise HTTPException(
            status_code=400,
            detail="Both 'file' and 'company_name' form fields are required",
        )

    company_name = company_name.strip()
    file_path = UPLOAD_DIR / safe_filename(company_name)

    with file_path.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)

    video_url = str(request.base_url).rstrip("/") + f"/media/{file_path.name}"

    db.execute(
        """
        INSERT INTO videos (company_name, file_path, video_url)
        VALUES (?, ?, ?)
        ON CONFLICT(company_name) DO UPDATE SET
            file_path = excluded.file_path,
            video_url = excluded.video_url,
            updated_at = datetime('now')
        """,
        (company_name, str(file_path.resolve()), video_url),
    )
    db.commit()

    return {"company_name": company_name, "video_url": video_url}


@app.get("/get_video_url")
def get_video_url(company_name: str, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT company_name, video_url FROM videos WHERE company_name = ?",
        (company_name,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"No video found for company '{company_name}'"
        )
    return {"company_name": row["company_name"], "video_url": row["video_url"]}


@app.get("/media/{filename}")
def media(filename: str):
    path = (UPLOAD_DIR / filename).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="video/webm")


@app.get("/videos")
def list_videos(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        """
        SELECT id, company_name, file_path, video_url, created_at, updated_at
        FROM videos ORDER BY id
        """
    ).fetchall()
    return [dict(row) for row in rows]


init_db()


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
