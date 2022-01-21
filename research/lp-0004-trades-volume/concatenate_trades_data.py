import sys
import pandas as pd
import os


def main():
    filenames = [
        f"trades-df-2021_11_1_0_0_0-2021_12_21_0_0_0-{i}.csv"
        for i in range(int(sys.argv[1]))
    ]
    concatenated_csv = pd.concat(
        [pd.read_csv(filename) for filename in filenames]
    )
    concatenated_csv.to_csv(
        "trades-df-2021_11_1_0_0_0-2021_12_21_0_0_0.csv", index=False
    )
    for filename in filenames:
        os.remove(filename)


if __name__ == "__main__":
    main()
