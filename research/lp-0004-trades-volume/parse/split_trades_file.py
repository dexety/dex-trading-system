import sys
import os

date_borders = "01-08-2021_22-01-2022"

raw_parts_dir_path = f"../../data/trades/raw/parts_{date_borders}"
if not os.path.isdir(raw_parts_dir_path):
    os.makedirs(raw_parts_dir_path)

parts_amount = int(sys.argv[1])

with open(f"../../data/trades/raw/trades_{date_borders}.csv", "r") as input:
    trades = input.readlines()
    fieldnames = trades[0]
    del trades[0]


for i in range(parts_amount):
    with open(
        f"../../data/trades/raw/parts_{date_borders}/{i}.csv", "w"
    ) as output:
        ind_from = i * (len(trades) // parts_amount)
        if i == parts_amount - 1:
            ind_to = len(trades)
        else:
            ind_to = (i + 1) * (len(trades) // parts_amount)
        print(fieldnames, file=output, end="")
        for line in trades[ind_from:ind_to]:
            print(line, file=output, end="")
