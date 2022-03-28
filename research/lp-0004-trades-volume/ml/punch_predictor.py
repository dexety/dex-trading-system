import json
from catboost import CatBoostClassifier
import pandas as pd
import numpy as np


class PunchPredictor:
    def __init__(self):
        self.model = CatBoostClassifier()
        self.model.load_model("punch_predictor_model.dump")
        with open(
            "punch_predictor_thresholds.dump", "r", encoding="utf8"
        ) as in_file:
            thresholds = json.load(in_file)
            self.prob_threshold = thresholds["prob_threshold"]
            self.diff_threshold = thresholds["diff_threshold"]
            self.null_threshold = thresholds["null_threshold"]

    def _get_predictions(self, predictions_probs: list) -> np.ndarray:
        return np.array(
            (
                list(
                    map(
                        lambda row: 1
                        if row[2] > self.prob_threshold
                        and row[2] > row[0]
                        and row[1] < self.null_threshold
                        and abs(row[2] - row[0]) > self.diff_threshold
                        and abs(row[2] - row[1]) > self.diff_threshold
                        else -1
                        if row[0] > self.prob_threshold
                        and row[0] > row[2]
                        and row[1] < self.null_threshold
                        and abs(row[0] - row[2]) > self.diff_threshold
                        and abs(row[0] - row[1]) > self.diff_threshold
                        else 0,
                        predictions_probs,
                    )
                )
            )
        )

    def predict(self, indicators) -> int:
        indicators = dict(
            map(
                lambda indicator: (indicator[0], [indicator[1]]),
                indicators.items(),
            )
        )
        indicators_df = pd.DataFrame.from_dict(indicators)
        predictions_probs = self.model.predict_proba(indicators_df)
        print(predictions_probs)
        return self._get_predictions(predictions_probs)[0]


pp = PunchPredictor()
print(
    pp.predict(
        {
            "seconds-since-midnight": 54659,
            "seconds-since-1-trades-ago-BUY": 0.809,
            "seconds-since-10-trades-ago-BUY": 10.421,
            "seconds-since-50-trades-ago-BUY": 20.194,
            "seconds-since-100-trades-ago-BUY": 29.513,
            "seconds-since-1000-trades-ago-BUY": 689.953,
            "trade-amount-BUY-600-sec": 380,
            "trade-volume-BUY-600-sec": 956.8720000000004,
            "open-close-diff-BUY-600-sec": 1.00022343040143,
            "moving-average-BUY-600-sec": 4024.2560526315815,
            "weighted-moving-average-BUY-600-sec": 4023.112731901441,
            "exp-moving-average-BUY-600-sec": 4028.624987660779,
            "stochastic-oscillator-BUY-600-sec": 0.6733668341708557,
            "trade-amount-BUY-60-sec": 83,
            "trade-volume-BUY-60-sec": 193.42000000000002,
            "open-close-diff-BUY-60-sec": 1.0009440524694426,
            "moving-average-BUY-60-sec": 4022.574698795179,
            "weighted-moving-average-BUY-60-sec": 4021.7628838796395,
            "exp-moving-average-BUY-60-sec": 4028.624987660779,
            "stochastic-oscillator-BUY-60-sec": 1.0,
            "trade-amount-BUY-30-sec": 77,
            "trade-volume-BUY-30-sec": 191.71800000000002,
            "open-close-diff-BUY-30-sec": 1.0021141649048626,
            "moving-average-BUY-30-sec": 4022.5584415584394,
            "weighted-moving-average-BUY-30-sec": 4021.7504553563044,
            "exp-moving-average-BUY-30-sec": 4028.624987660779,
            "stochastic-oscillator-BUY-30-sec": 1.0,
            "trade-amount-BUY-10-sec": 50,
            "trade-volume-BUY-10-sec": 112.70700000000001,
            "open-close-diff-BUY-10-sec": 1.0021889458235909,
            "moving-average-BUY-10-sec": 4024.28,
            "weighted-moving-average-BUY-10-sec": 4023.6603751319794,
            "exp-moving-average-BUY-10-sec": 4028.624987660779,
            "stochastic-oscillator-BUY-10-sec": 1.0,
            "trade-amount-BUY-5-sec": 25,
            "trade-volume-BUY-5-sec": 62.00300000000002,
            "open-close-diff-BUY-5-sec": 1.001018658848667,
            "moving-average-BUY-5-sec": 4026.1000000000004,
            "weighted-moving-average-BUY-5-sec": 4025.5875651178153,
            "exp-moving-average-BUY-5-sec": 4028.6249876618385,
            "stochastic-oscillator-BUY-5-sec": 1.0,
            "trade-amount-BUY-1-sec": 1,
            "trade-volume-BUY-1-sec": 0.2,
            "open-close-diff-BUY-1-sec": 1.0,
            "moving-average-BUY-1-sec": 4029.0,
            "weighted-moving-average-BUY-1-sec": 4029.0,
            "exp-moving-average-BUY-1-sec": 4029.0,
            "stochastic-oscillator-BUY-1-sec": 0.0,
            "seconds-since-1-trades-ago-SELL": 0.809,
            "seconds-since-10-trades-ago-SELL": 10.421,
            "seconds-since-50-trades-ago-SELL": 20.194,
            "seconds-since-100-trades-ago-SELL": 29.513,
            "seconds-since-1000-trades-ago-SELL": 689.953,
            "trade-amount-SELL-600-sec": 384,
            "trade-volume-SELL-600-sec": 996.9000000000001,
            "open-close-diff-SELL-600-sec": 0.9994530220531563,
            "moving-average-SELL-600-sec": 4024.9132812499897,
            "weighted-moving-average-SELL-600-sec": 4025.3575618417112,
            "exp-moving-average-SELL-600-sec": 4019.465001567546,
            "stochastic-oscillator-SELL-600-sec": 0.225,
            "trade-amount-SELL-60-sec": 43,
            "trade-volume-SELL-60-sec": 97.05499999999999,
            "open-close-diff-SELL-60-sec": 0.9982864805801133,
            "moving-average-SELL-60-sec": 4022.0418604651168,
            "weighted-moving-average-SELL-60-sec": 4022.0389274122917,
            "exp-moving-average-SELL-60-sec": 4019.465001567546,
            "stochastic-oscillator-SELL-60-sec": 0.2500000000000124,
            "trade-amount-SELL-30-sec": 30,
            "trade-volume-SELL-30-sec": 65.97299999999998,
            "open-close-diff-SELL-30-sec": 0.9991549225759948,
            "moving-average-SELL-30-sec": 4020.8799999999997,
            "weighted-moving-average-SELL-30-sec": 4020.0183211313724,
            "exp-moving-average-SELL-30-sec": 4019.4650015674533,
            "stochastic-oscillator-SELL-30-sec": 0.40350877192983714,
            "trade-amount-SELL-10-sec": 5,
            "trade-volume-SELL-10-sec": 27.675,
            "open-close-diff-SELL-10-sec": 1.0003483887022522,
            "moving-average-SELL-10-sec": 4018.88,
            "weighted-moving-average-SELL-10-sec": 4019.7574525745254,
            "exp-moving-average-SELL-10-sec": 4019.4375,
            "stochastic-oscillator-SELL-10-sec": 1.0,
            "trade-amount-SELL-5-sec": 3,
            "trade-volume-SELL-5-sec": 26.5,
            "open-close-diff-SELL-5-sec": 1.0005724810832337,
            "moving-average-SELL-5-sec": 4019.133333333333,
            "weighted-moving-average-SELL-5-sec": 4019.81320754717,
            "exp-moving-average-SELL-5-sec": 4019.325,
            "stochastic-oscillator-SELL-5-sec": 1.0,
            "trade-amount-SELL-1-sec": 2,
            "trade-volume-SELL-1-sec": 25.5,
            "open-close-diff-SELL-1-sec": 1.0,
            "moving-average-SELL-1-sec": 4019.9,
            "weighted-moving-average-SELL-1-sec": 4019.9,
            "exp-moving-average-SELL-1-sec": 4019.9,
            "stochastic-oscillator-SELL-1-sec": 0.0,
        }
    )
)
