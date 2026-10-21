import csv

FILE = "data/raw/chicago_crimes.csv"

bad_rows = 0
total_rows = 0

with open(FILE, "r", encoding="utf-8", newline="") as file:
    reader = csv.reader(file)

    header = next(reader)

    print("Number of columns in header:", len(header))

    for line_number, row in enumerate(reader, start=2):
        total_rows += 1

        if len(row) != 22:
            print("BAD ROW FOUND")
            print("CSV line:", line_number)
            print("Number of columns:", len(row))
            print(row)
            bad_rows += 1

            if bad_rows >= 5:
                break

print()
print("Rows checked:", total_rows)
print("Bad rows found:", bad_rows)