import sys

input = open('../../data/trades/raw/trades_01-08-2021_22-01-2022.csv', 'r')
lines = input.readlines()
fieldnames = lines[0]
trades = lines[1:]
input.close()

parts_amount = int(sys.argv[1])

for i in range(parts_amount):
    output = open(f'../../data/trades/raw/parts_01-08-2021_22-01-2022/{i}.csv', 'w')
    ind_from = i * (len(trades) // parts_amount)
    if (i == parts_amount - 1):
        ind_to = len(trades)
    else:
        ind_to = (i + 1) * (len(trades) // parts_amount)
    print(fieldnames, file=output, end='')
    for line in trades[ind_from:ind_to]:
        print(line, file=output, end='')
    output.close()
