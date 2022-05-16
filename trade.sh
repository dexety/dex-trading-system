export PYTHONPATH=`pwd`

strategy_name=$1
if [[ $strategy_name == "" ]]
then
    strategy_name="arbitrage"
fi
python3 strategy/$strategy_name/run_trader.py
