"""Download and unpack Spider 1.0 dataset."""

import os
import sys
import zipfile
from pathlib import Path

import requests

HF_SPIDER_URL = (
    "https://huggingface.co/datasets/HAL-9001/spider-databases/resolve/main/spider_data.zip"
)
SPIDER_GDRIVE_ID = "1_ackp_xPqzzzp7bFlv8ySARr82q2a4p8"


def download_and_extract_spider(raw_dir: str = "data/raw") -> None:
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    spider_dir = raw_path / "spider"
    zip_path = raw_path / "spider.zip"

    # Check if already extracted
    expected_files = [
        spider_dir / "train_spider.json",
        spider_dir / "dev.json",
        spider_dir / "tables.json",
    ]
    if all(f.exists() for f in expected_files):
        print(f"Spider dataset already exists at {spider_dir}")
        return

    # Try direct mirror first (Hugging Face)
    download_success = False
    print("Downloading Spider 1.0 dataset from mirror...")
    try:
        response = requests.get(HF_SPIDER_URL, stream=True, timeout=60)
        if response.status_code == 200:
            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            download_success = True
            print("Download completed successfully!")
    except Exception as e:
        print(f"Mirror download failed: {e}")

    # Fallback to gdown if mirror failed
    if not download_success:
        print("Attempting download via gdown...")
        try:
            import gdown

            url = f"https://drive.google.com/uc?id={SPIDER_GDRIVE_ID}"
            gdown.download(url, str(zip_path), quiet=False)
            if zip_path.exists():
                download_success = True
        except Exception as e:
            print(f"gdown download failed: {e}")

    if not download_success or not zip_path.exists():
        print("\n=== MANUAL DOWNLOAD INSTRUCTIONS ===")
        print("1. Download Spider 1.0 zip from: https://yale-lily.github.io/spider")
        print(f"2. Save the zip file to: {zip_path.resolve()}")
        print("3. Re-run this script to unpack it.")
        print("=====================================\n")
        sys.exit(1)

    print(f"Unzipping {zip_path} into {raw_path}...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(raw_path)

    # Check extracted folder name (could be spider or spider_data or spider/...)
    extracted_spider = raw_path / "spider"
    extracted_spider_data = raw_path / "spider_data"

    if not extracted_spider.exists() and extracted_spider_data.exists():
        extracted_spider_data.rename(extracted_spider)

    if extracted_spider.exists():
        print(f"Extraction complete! Spider dataset ready at {extracted_spider}")
        if zip_path.exists():
            os.remove(zip_path)
    else:
        print(f"Warning: Extracted content did not result in expected {extracted_spider}")


if __name__ == "__main__":
    download_and_extract_spider()
