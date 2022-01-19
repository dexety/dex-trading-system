import pandas as pd


def main():
    csv_path = "trades-df-2021_11_1_0_0_0-2021_12_21_0_0_0.csv"
    df = pd.read_csv(csv_path)
    print(df.dtypes)


if __name__ == "__main__":
    main()
