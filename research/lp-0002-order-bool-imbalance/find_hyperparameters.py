import os
import numpy as np
from datetime import datetime, timedelta


def main():
    start_time = datetime.now()
    delta_time = timedelta(hours=1)
    while start_time < datetime.now() + delta_time:
        depth = np.random.randint(1, 20)
        dicision_time = np.random.randint(1, 20)
        dicision_threshold = (np.random.rand() + 0.7) / (1 + 0.7)
        cancel_time = np.random.randint(1, 500)
        cancel_threshold = np.random.randint(1, 30) / 1000
        profit_threshold = np.random.randint(3, 100) / 1000
        symbol = "ETH-USD"

        command = "python3 "
        command += "test_hyperparameters.py "
        command += f"--depth={depth} "
        command += f"--dicision_time={dicision_time} "
        command += f"--dicision_threshold={dicision_threshold} "
        command += f"--cancel_time={cancel_time} "
        command += f"--cancel_threshold={cancel_threshold} "
        command += f"--profit_threshold={profit_threshold} "
        command += f"--symbol={symbol} "

        os.system(command)


if __name__ == "__main__":
    main()
