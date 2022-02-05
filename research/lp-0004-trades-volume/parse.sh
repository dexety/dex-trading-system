python3 src/split_trades_file.py 3

python3 src/parse_trades_data.py 0 &
python3 src/parse_trades_data.py 1 &
python3 src/parse_trades_data.py 2

python3 src/concatenate.py 3