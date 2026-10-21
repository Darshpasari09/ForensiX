import csv

source_file = "data/raw/chicago_crimes.csv"
test_file = "data/raw/chicago_test_100.csv"

with open(source_file, "r", encoding="utf-8", newline="") as source:
    reader = csv.reader(source)
    header = next(reader)

    with open(test_file, "w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(header)

        for i, row in enumerate(reader):
            if i >= 100:
                break
            writer.writerow(row)

print("Created 100-row test CSV.")