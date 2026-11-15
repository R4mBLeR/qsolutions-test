import sqlite3
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "videos.db"

UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI()


connection = sqlite3.connect('my_database.db')
cursor = connection.cursor()


def init_db() -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL UNIQUE,
            file_path TEXT NOT NULL,
            video_url TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)


init_db()


@app.post("/upload")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    company_name: str = Form(...),
):
    file_path = (UPLOAD_DIR / company_name).resolve()

    with open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    video_url = str(request.base_url).rstrip("/") + f"/media/{company_name}"

    cursor.execute(
        """
        INSERT INTO videos (company_name, file_path, video_url)
        VALUES (?, ?, ?)
        ON CONFLICT(company_name) DO UPDATE SET
            file_path  = excluded.file_path,
            video_url  = excluded.video_url,
            updated_at = datetime('now')
        """,
        (company_name, str(file_path), video_url),
    )

    return {"company_name": company_name, "video_url": video_url}

@app.get("/get_video_url")
def get_video_url(company_name: str):
    row = cursor.execute(
        "SELECT company_name, video_url FROM videos WHERE company_name = ?",
        (company_name,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"video with name: {company_name} not found")
    return {"company_name": row["company_name"], "video_url": row["video_url"]}

@app.get("/media/{filename}")
def media(filename: str):
    path = (UPLOAD_DIR / filename).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path)