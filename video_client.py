"""HTTP client for the video web service."""

import os

import requests


def UploadVideo(server_url: str, video_path: str, company_name: str) -> str:
    video_path = os.path.abspath(video_path)
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    url = server_url.rstrip("/") + "/upload"
    with open(video_path, "rb") as fh:
        response = requests.post(
            url,
            files={"file": (os.path.basename(video_path), fh)},
            data={"company_name": company_name},
            timeout=300,
        )
    response.raise_for_status()
    return response.json()["video_url"]


def GetVideoURL(server_url: str, company_name: str) -> str:
    url = server_url.rstrip("/") + "/get_video_url"
    response = requests.get(
        url, params={"company_name": company_name}, timeout=30
    )
    response.raise_for_status()
    return response.json()["video_url"]
