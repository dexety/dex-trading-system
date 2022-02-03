success_shorts = 0
bad_shorts = 0
total_shorts = 0
success_longs = 0
bad_longs = 0
total_longs = 0

usd = 100
with open("trades.txt") as f:
    for line in f.readlines():
        line = list(line.split())
        usd *= (1 - 0.0005)**2
        if line[0] == "SHORT":
            total_shorts += 1
            sell = float(line[4][0:len(line[4])-1])
            buy = float(line[-1])
            if sell / buy >= (1 + 0.00101):
                success_shorts += 1
            else:
                bad_shorts += 1
            usd *= sell / buy
        else:
            total_longs += 1
            buy = float(line[4][0:len(line[4])-1])
            sell = float(line[-1])
            if sell / buy >= (1 + 0.00101):
                success_longs += 1
            else:
                bad_longs += 1
            usd *= sell / buy

print(f"PROFIT: {usd - 100}")
print(f"TOTAL LONGS: {total_longs}\tSUCCESS LONGS: {success_longs}\tBAD_LONGS: {bad_longs}")
print(f"TOTAL SHORTS: {total_shorts}\tSUCCESS SHORTS: {success_shorts}\tBAD_SHORTS: {bad_shorts}")
