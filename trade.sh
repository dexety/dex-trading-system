mv debug.log old_debug.log

export PYTHONPATH="${PYTHONPATH}:./"

strategy_name=$1
python3 strategy/$strategy_name/trade.py
