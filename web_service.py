import asyncio
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import psycopg2
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from psycopg2.extras import RealDictCursor
import uvicorn


BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

DB_CONFIG = {
    "dbname": os.getenv("POSTGRES_DB", "qsolution_db"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
    "host": os.getenv("POSTGRES_HOST", "postgres"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
}


def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id SERIAL PRIMARY KEY,
                    company_name TEXT NOT NULL UNIQUE,
                    file_path TEXT NOT NULL,
                    video_url TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(1, 11):
        try:
            init_db()
            break
        except psycopg2.OperationalError:
            if attempt == 10:
                raise
            await asyncio.sleep(2)
    yield


app = FastAPI(lifespan=lifespan)


def safe_filename(company_name: str) -> str:
    stem = re.sub(r"[^\w-]+", "_", company_name.strip()).strip("_")
    return f"{stem or 'video'}.webm"


def upsert_video(db, company_name: str, file_path: str, video_url: str) -> None:
    with db, db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO videos (company_name, file_path, video_url)
            VALUES (%s, %s, %s)
            ON CONFLICT (company_name) DO UPDATE SET
                file_path = EXCLUDED.file_path,
                video_url = EXCLUDED.video_url,
                updated_at = now()
            """,
            (company_name, file_path, video_url),
        )


@app.post("/upload")
async def upload_video(
    request: Request,
    file: Optional[UploadFile] = File(None),
    company_name: Optional[str] = Form(None),
    db: psycopg2.extensions.connection = Depends(get_db),
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

    base_url = PUBLIC_BASE_URL or str(request.base_url).rstrip("/")
    video_url = f"{base_url}/media/{quote(file_path.name)}"

    await run_in_threadpool(
        upsert_video, db, company_name, str(file_path.resolve()), video_url
    )

    return {"company_name": company_name, "video_url": video_url}


@app.get("/get_video_url")
def get_video_url(company_name: str, db: psycopg2.extensions.connection = Depends(get_db)):
    with db.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT company_name, video_url FROM videos WHERE company_name = %s",
            (company_name,),
        )
        row = cur.fetchone()
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
def list_videos(db: psycopg2.extensions.connection = Depends(get_db)):
    with db.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, company_name, file_path, video_url, created_at, updated_at
            FROM videos ORDER BY id
            """
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "4002"))
    uvicorn.run(app, host=host, port=port)