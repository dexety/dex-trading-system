from utils.helpful_scripts import string_to_datetime
import pandas as pd

with open(
    "../../../data/trades/raw/trades_01-08-2021_22-01-2022.csv", "r"
) as input:
    trades: pd.DataFrame = pd.read_csv(input)
    trades_to_drop = []
    cur_dt = string_to_datetime(trades.iloc[0, 3])
    for i in range(trades.shape[0]):
        new_dt = string_to_datetime(trades.iloc[i, 3])
        if new_dt < cur_dt:
            trades_to_drop.append(i)
        else:
            cur_dt = new_dt
        if i % 100000 == 0:
            print("\r" + str(i * 100 / trades.shape[0]))

    trades = trades.drop(axis=0, index=trades_to_drop)

with open("out.csv", "w") as output:
    trades.to_csv(output, index=False)
