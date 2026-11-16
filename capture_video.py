import argparse
import csv

from qscript import CaptureVideo_Magento


def preview_in_browser(url: str, view_seconds: float) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url)
        if view_seconds > 0:
            page.wait_for_timeout(int(view_seconds * 1000))
        else:
            input("Press Enter to close the preview...")
        browser.close()


def process_row(row: dict, server_url: str | None, view_seconds: float) -> None:
    video_path = CaptureVideo_Magento(
        url=row['URL'],
        company_name=row['Company Name'],
        language=row['Language'],
        country=row['Country'],
        postcode=row['Postcode'],
        city=row['City'],
        street=row['Street'],
        house_no=row['HouseNo']
    )
    if not video_path:
        print(f"[{row['Company Name']}] Recording failed, skipping row.")
        return

    print(f"Saved: {video_path}")

    if not server_url:
        return

    try:
        from video_client import UploadVideo

        video_url = UploadVideo(server_url, video_path, row['Company Name'])
        print(f"Uploaded: {video_url}")
        preview_in_browser(video_url, view_seconds)
    except Exception as e:
        print(f"[{row['Company Name']}] Upload/preview failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Record videos for every input.csv row")
    parser.add_argument(
        "--server",
        default=None,
        help="video service URL, e.g. http://127.0.0.1:8000 (upload + preview after recording)",
    )
    parser.add_argument(
        "--view-seconds",
        type=float,
        default=5.0,
        help="seconds to keep the preview browser open; 0 = wait for Enter",
    )
    args = parser.parse_args()

    with open('input.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=";", quotechar='"')
        for row in reader:
            process_row(row, args.server, args.view_seconds)


if __name__ == "__main__":
    main()
