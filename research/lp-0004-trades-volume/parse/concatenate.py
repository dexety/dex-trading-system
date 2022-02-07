import sys
import pandas as pd

date_borders = "01-08-2021_22-01-2022"
path_to_output = "../../data/trades/processed"

filenames = [
    f"{path_to_output}/parts_{date_borders}/{i}.csv"
    for i in range(int(sys.argv[1]))
]
concatenated_csv:pd.DataFrame = pd.concat(
    [pd.read_csv(filename) for filename in filenames]
)
concatenated_csv.to_csv(
    f"{path_to_output}/indicators_{date_borders}.csv", index=False
)
