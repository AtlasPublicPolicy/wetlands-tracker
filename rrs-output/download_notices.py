import os
import time
import base64
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# -----------------------------------------------------------------------------
#  Sync download worker
# -----------------------------------------------------------------------------
def _sync_download_url(url, output_folder, sleep_time=10):
    print(f"[START] {url}")
    os.makedirs(output_folder, exist_ok=True)
    prefs = {
        "download.default_directory": os.path.abspath(output_folder),
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
    }
    chrome_options = Options()
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options,
    )
    driver.set_page_load_timeout(20)
    try:
        driver.get(url)
        time.sleep(sleep_time)
        print(f"[DONE]  {url}")
    except TimeoutException:
        print(f"[TIMEOUT] {url}")
    except Exception as e:
        print(f"[ERROR]   {url}  →  {e}")
    finally:
        driver.quit()

# -----------------------------------------------------------------------------
#  Async download for list‐columns
# -----------------------------------------------------------------------------
async def download_links_async(df, link_col, output_folder, max_workers=4):
    print(f"Downloading {link_col} → {output_folder}")
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=max_workers)
    tasks = []

    for _, row in df.iterrows():
        urls = row[link_col]
        if pd.isna(urls):
            continue

        # Normalize to list
        if isinstance(urls, str):
            if urls.startswith('[') and urls.endswith(']'):
                try:
                    import ast
                    parsed = ast.literal_eval(urls)
                    urls = parsed if isinstance(parsed, list) else [urls]
                except:
                    urls = [urls]
            else:
                urls = [urls]
        elif not isinstance(urls, list):
            print(f"[SKIP] Unknown format: {type(urls)}")
            continue

        for url in urls:
            if isinstance(url, str) and url.strip():
                tasks.append(
                    loop.run_in_executor(executor, _sync_download_url, url.strip(), output_folder)
                )

    await asyncio.gather(*tasks)
    executor.shutdown(wait=True)
    print(f"Finished {link_col}")

# -----------------------------------------------------------------------------
#  Async “print‐to‐PDF” downloader
# -----------------------------------------------------------------------------
async def download_print_links_async(urls, output_folder, max_workers=8, sleep_time=10):
    os.makedirs(output_folder, exist_ok=True)
    loop = asyncio.get_event_loop()
    semaphore = asyncio.Semaphore(max_workers)

    async def _download_one(url):
        async with semaphore:
            def _sync_print_to_pdf():
                opts = Options()
                opts.add_argument("--headless")
                opts.add_argument("--disable-gpu")
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")

                driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=opts
                )
                driver.set_page_load_timeout(30)
                try:
                    driver.get(url)
                    time.sleep(sleep_time)
                    res = driver.execute_cdp_cmd("Page.printToPDF", {"printBackground": True})
                    pdf = base64.b64decode(res["data"])

                    raw = url.rstrip("/").split("/")[-1] or "print_page"
                    fname = re.sub(r"[^0-9A-Za-z_-]", "_", raw) + ".pdf"
                    path = os.path.join(output_folder, fname)
                    with open(path, "wb") as f:
                        f.write(pdf)
                    print(f"[SAVED] {path}")

                except TimeoutException:
                    print(f"[TIMEOUT] {url}")
                except Exception as e:
                    print(f"[ERROR]   {url}  →  {e}")
                finally:
                    driver.quit()

            await loop.run_in_executor(None, _sync_print_to_pdf)

    tasks = [asyncio.create_task(_download_one(u)) for u in urls]
    await asyncio.gather(*tasks)
    print("All print links processed")

# -----------------------------------------------------------------------------
#  Optional: a main() so you can `python download_utils.py`
# -----------------------------------------------------------------------------
async def main():
    # Example: load dataframes and call the above functions
    df_pdf    = pd.read_csv("pdf_links.csv")
    df_cdm    = pd.read_csv("cdm_links.csv")
    df_other  = pd.read_csv("other_links.csv")

    await download_links_async(df_pdf,   'PDF_URLs',       "download_notices", max_workers=8)
    await download_links_async(df_cdm,   'ContentDM_URLs', "download_contentdm", max_workers=4)
    await download_print_links_async(df_other['PRINT_URLs'].tolist(), "download_other", max_workers=4)

if __name__ == "__main__":
    asyncio.run(main())
