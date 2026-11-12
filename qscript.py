import os
import random
import time
from playwright.sync_api import sync_playwright

PATH_TO_VIDEO_FOLDER = "./video"


def install_fake_cursor(page):
    page.add_init_script("""
        window.addEventListener('DOMContentLoaded', () => {
            const halo = document.createElement('div');
            halo.id = '__cursor_halo__';
            halo.style.cssText = `
                position: fixed; z-index: 2147483645; pointer-events: none;
                width: 32px; height: 32px;
                background: #FFD700;
                border-radius: 50%;
                top: 0; left: 0;
                opacity: 0.55;
                transition: transform 0.05s linear;
                box-shadow: 0 0 8px rgba(255, 215, 0, 0.7);
            `;
            document.body.appendChild(halo);
            const c = document.createElement('div');
            c.id = '__fake_cursor__';
            c.style.cssText = `
                position: fixed; z-index: 2147483647; pointer-events: none;
                width: 24px; height: 24px; top: 0; left: 0;
                transition: transform 0.05s linear;
                background: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="M3 2 L3 20 L8 15 L11 22 L14 20 L11 13 L19 13 Z" fill="white" stroke="black" stroke-width="1.5"/></svg>') no-repeat;
                filter: drop-shadow(0 0 2px rgba(0,0,0,.4));
            `;
            document.body.appendChild(c);

            const pulse = document.createElement('div');
            pulse.id = '__pulse__';
            pulse.style.cssText = `
                position: fixed; z-index: 2147483646; pointer-events: none;
                width: 40px; height: 40px; border-radius: 50%;
                border: 3px solid #FFD700; opacity: 0;
                background: transparent;
                top: 0; left: 0; transform: translate(-50%, -50%);
            `;
            document.body.appendChild(pulse);

            window.__moveCursor = (x, y) => {
                c.style.transform = `translate(${x}px, ${y}px)`;
                halo.style.transform = `translate(${x - 16}px, ${y - 16}px)`;
            };

            window.__pulseAt = (x, y) => {
                pulse.style.left = x + 'px';
                pulse.style.top = y + 'px';
                pulse.style.animation = 'none';
                void pulse.offsetWidth;
                pulse.style.animation = 'pulseAnim 0.4s ease-out';
            };

            const style = document.createElement('style');
            style.innerHTML = `
                @keyframes pulseAnim {
                    0%   { transform: translate(-50%, -50%) scale(0.5); opacity: 1; }
                    100% { transform: translate(-50%, -50%) scale(2);   opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        });
    """)


def move_and_click(page, locator, steps=40):
    box = locator.bounding_box()
    if not box:
        raise Exception("Элемент не найден для клика")

    tx = box["x"] + box["width"] / 3
    ty = box["y"] + box["height"] / 2
    sx, sy = 50, 50

    for i in range(steps + 1):
        t = i / steps
        cx = sx + (tx - sx) * t
        cy = sy + (ty - sy) * t
        page.mouse.move(cx, cy)
        page.evaluate("([x,y]) => window.__moveCursor?.(x,y)", [cx, cy])
        page.wait_for_timeout(8)

    page.evaluate("([x,y]) => window.__pulseAt?.(x,y)", [tx, ty])
    page.wait_for_timeout(150)

    page.mouse.click(tx, ty)
    page.wait_for_timeout(300)


def CaptureVideo_Magento(url, company_name, language, country, postcode, city, street, house_no):
    try:
        os.makedirs(PATH_TO_VIDEO_FOLDER, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="Europe/London",
                viewport={"width": 1280, "height": 720},
                record_video_dir=PATH_TO_VIDEO_FOLDER,
                record_video_size={"width": 1280, "height": 720},
            )

            page = context.new_page()
            install_fake_cursor(page)

            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            search = page.locator("textarea[name='q']")
            search.wait_for(state="visible", timeout=15000)
            page.wait_for_timeout(500)

            move_and_click(page, search)
            for ch in company_name:
                search.press(ch)
                page.wait_for_timeout(int(random.uniform(50, 200)))
            search.press("Enter")

            first_result_link = page.locator("a[data-testid='result-title-a']").first
            first_result_link.wait_for(state="visible", timeout=15000)
            page.wait_for_timeout(500) 

            move_and_click(page, first_result_link)

            page.wait_for_timeout(2000)

            video_path = page.video.path()
            context.close()
            browser.close()

            final_path = os.path.join(PATH_TO_VIDEO_FOLDER, f"{company_name}.webm")
            os.rename(video_path, final_path)

            return os.path.abspath(final_path)

    except Exception as e:
        print(f"Error: {e}")
        return None