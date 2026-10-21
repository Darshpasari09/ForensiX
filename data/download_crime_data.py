import csv
import os
import time
import requests

API_URL = "https://data.cityofchicago.org/resource/ijzp-q8t2.json"

TARGET_ROWS = 2_162_217
CHUNK_SIZE = 50_000

OUTPUT_FILE = "data/raw/chicago_crimes.csv"

FIELDS = [
    "id",
    "case_number",
    "date",
    "block",
    "iucr",
    "primary_type",
    "description",
    "location_description",
    "arrest",
    "domestic",
    "beat",
    "district",
    "ward",
    "community_area",
    "fbi_code",
    "x_coordinate",
    "y_coordinate",
    "year",
    "updated_on",
    "latitude",
    "longitude",
    "location"
]


def download_data():

    os.makedirs("data/raw", exist_ok=True)

    total_downloaded = 0
    last_id = 0
    first_request = True

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as output_file:

        writer = csv.DictWriter(
            output_file,
            fieldnames=FIELDS,
            extrasaction="ignore"
        )

        writer.writeheader()

        while total_downloaded < TARGET_ROWS:

            remaining = TARGET_ROWS - total_downloaded
            limit = min(CHUNK_SIZE, remaining)

            params = {
                "$limit": limit,
                "$where": f"id > {last_id}",
                "$order": "id ASC"
            }

            print()
            print(
                f"Requesting up to {limit:,} records..."
            )
            print(
                f"Current progress: "
                f"{total_downloaded:,} / "
                f"{TARGET_ROWS:,}"
            )

            success = False

            for attempt in range(1, 6):

                try:
                    response = requests.get(
                        API_URL,
                        params=params,
                        timeout=180
                    )

                    response.raise_for_status()

                    rows = response.json()

                    success = True
                    break

                except requests.RequestException as error:

                    print(
                        f"Request failed "
                        f"(attempt {attempt}/5): {error}"
                    )

                    if attempt < 5:
                        time.sleep(5)

            if not success:
                print("Download failed after 5 attempts.")
                break

            if not rows:
                print("No more records returned.")
                break

            for row in rows:
                writer.writerow(row)

            output_file.flush()

            total_downloaded += len(rows)

            last_id = int(rows[-1]["id"])

            print(
                f"Downloaded so far: "
                f"{total_downloaded:,}"
            )

            print(
                f"Last source ID: {last_id}"
            )

            time.sleep(1)

    print()
    print("=" * 50)
    print("DOWNLOAD COMPLETE")
    print("=" * 50)
    print(f"Rows downloaded: {total_downloaded:,}")
    print(f"Last source ID: {last_id}")
    print(f"File: {OUTPUT_FILE}")


if __name__ == "__main__":
    download_data()