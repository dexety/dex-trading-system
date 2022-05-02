import csv

with open("/home/ivan/dex-data/dydx/ETH-USD_dydx_2022-02.csv", "r", encoding="utf-8") as signal_file:
    csv_reader = csv.reader(signal_file, delimiter=",")
    for line in csv_reader:
        print(csv_reader.line_num)
