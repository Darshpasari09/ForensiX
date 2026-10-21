import csv

FILE = "data/raw/chicago_crimes.csv"

with open(FILE, "r", encoding="utf-8", newline="") as file:

    reader = csv.reader(file)

    # Subtract header
    row_count = sum(1 for _ in reader) - 1

print(f"Rows in dataset: {row_count:,}")