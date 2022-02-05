import sys

date_borders = "01-08-2021_22-01-2022"
path_to_output = "../../data/trades/processed"

with open(f"{path_to_output}/indicators_{date_borders}.csv", "w") as output:
    with open(f"{path_to_output}/parts_{date_borders}/0.csv", "r") as part:
        for line in part:
            output.write(line)

    for i in range(1, int(sys.argv[1])):
        with open(f"{path_to_output}/parts_{date_borders}/{i}.csv") as part:
            for line in part.readlines()[1:]:
                output.write(line)
