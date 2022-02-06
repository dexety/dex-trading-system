import pandas as pd
import numpy as np
import json
from catboost import CatBoostClassifier, Pool, metrics
from sklearn.metrics import accuracy_score
import random
from utils.logger.logger import Logger


class TrainModel:
    commision = 0.0005
    punch = commision * 4
    buckets_num = 200

    def __init__(self, data_path: str) -> None:
        self.data_path = data_path
        self.read_data()
        self.decrease_null_numbers()
        self.split_data_to_train_validation_test()

    def read_data(self) -> None:
        Logger.debug("Reading data")
        self.df = pd.read_csv(self.data_path)
        Logger.debug("Prepare data")
        self.x_columns = list(
            filter(lambda column: not "punch" in column, self.df.columns)
        )
        self.y_columns = list(
            filter(lambda column: "punch" in column, self.df.columns)
        )
        self.df["target"] = self.df[self.y_columns].apply(
            lambda row: 1
            if max(list(row.to_numpy()), key=abs) > self.punch
            else -1
            if max(list(row.to_numpy()), key=abs) < -self.punch
            else 0,
            axis=1,
        )
        self.df = self.df.drop(self.y_columns, axis=1)

    def decrease_null_numbers(self) -> None:
        lines_to_drop = []

        for index, line in self.df.iterrows():
            if np.random.rand() < 0.9 and line["target"] == 0:
                lines_to_drop.append(index)

        self.df = self.df.drop(lines_to_drop)
        self.X = self.df[self.x_columns]
        self.y = self.df["target"]

    def split_data_to_train_validation_test(self) -> None:
        Logger.debug("Split data to train, validation and test")
        buckets = [
            self.df[
                len(self.df)
                // self.buckets_num
                * i : len(self.df)
                // self.buckets_num
                * (i + 1)
            ]
            for i in range(self.buckets_num)
        ]
        random.shuffle(buckets)
        df_train = pd.concat(
            buckets[: int(self.buckets_num * 0.70)], ignore_index=True
        )
        df_validate = pd.concat(
            buckets[
                int(self.buckets_num * 0.70) : int(self.buckets_num * 0.85)
            ],
            ignore_index=True,
        )
        df_test = pd.concat(
            buckets[int(self.buckets_num * 0.85) :], ignore_index=True
        )

        self.X_train = df_train[self.x_columns]
        self.y_train = df_train["target"]

        self.X_validation = df_validate[self.x_columns]
        self.y_validation = df_validate["target"]

        self.X_test = df_test[self.x_columns]
        self.y_test = df_test["target"]

    def train(self) -> None:
        Logger.debug("Start model training")
        params = {
            "iterations": 1500,
            "l2_leaf_reg": 2,
            "learning_rate": 0.2,
            "custom_loss": [metrics.Accuracy()],
            "eval_metric": metrics.Accuracy(),
            "random_seed": 42,
            "depth": 5,
            "logging_level": "Silent",
            "loss_function": "MultiClass",
        }
        train_pool = Pool(self.X_train, self.y_train)
        validate_pool = Pool(self.X_validation, self.y_validation)

        self.model = CatBoostClassifier(**params)
        self.model.fit(
            train_pool,
            eval_set=validate_pool,
            plot=False,
        )
        self.model.save_model("punch_predictor_model.dump")
        self.predictions_probs = self.model.predict_proba(self.X_test)

        Logger.debug(
            "Model validation accuracy: {:.4}".format(
                accuracy_score(self.y_test, self.model.predict(self.X_test))
            )
        )

    def _get_predictions(
        self,
        prob_threshold: float,
        diff_threshold: float,
        null_threshold: float,
    ) -> np.ndarray:
        return np.array(
            (
                list(
                    map(
                        lambda row: 1
                        if row[2] > prob_threshold
                        and row[2] > row[0]
                        and row[1] < null_threshold
                        and abs(row[2] - row[0]) > diff_threshold
                        and abs(row[2] - row[1]) > diff_threshold
                        else -1
                        if row[0] > prob_threshold
                        and row[0] > row[2]
                        and row[1] < null_threshold
                        and abs(row[0] - row[2]) > diff_threshold
                        and abs(row[0] - row[1]) > diff_threshold
                        else 0,
                        self.predictions_probs,
                    )
                )
            )
        )

    def _get_predictions_quality(
        self,
        prob_threshold: float,
        diff_threshold: float,
        null_threshold: float,
    ) -> None:
        predictions = self._get_predictions(
            prob_threshold, diff_threshold, null_threshold
        )
        quality = {
            "correct_predictions": 0,
            "false_positive": 0,
            "false_negative": 0,
            "wrong_side": 0,
        }
        for i in range(len(predictions)):
            answer = int(self.y_test[i : i + 1])
            if predictions[i] == answer != 0:
                quality["correct_predictions"] += 1
            elif (
                predictions[i] != answer and answer != 0 and predictions[i] != 0
            ):
                quality["wrong_side"] += 1
            elif predictions[i] != 0 and answer == 0:
                quality["false_positive"] += 1
            elif predictions[i] == 0 and answer != 0:
                quality["false_negative"] += 1

        quality["correct_predictions_pc"] = quality[
            "correct_predictions"
        ] / len(self.y_test)
        quality["false_positive_pc"] = quality["false_positive"] / len(
            self.y_test
        )
        quality["false_negative_pc"] = quality["false_negative"] / len(
            self.y_test
        )
        quality["wrong_side_pc"] = quality["wrong_side"] / len(self.y_test)
        quality["prob_threshold"] = prob_threshold
        quality["diff_threshold"] = diff_threshold
        quality["null_threshold"] = null_threshold
        return quality

    def _get_profit(
        self,
        prob_threshold: float,
        diff_threshold: float,
        null_threshold: float,
    ) -> float:
        predictions = self._get_predictions(
            prob_threshold, diff_threshold, null_threshold
        )
        quality = self._get_predictions_quality(
            prob_threshold, diff_threshold, null_threshold
        )
        return (
            len(self.y)
            * quality["correct_predictions_pc"]
            * (self.punch - 2 * self.commision)
            - len(self.y) * quality["false_positive_pc"] * 2 * self.commision
            - len(self.y)
            * quality["wrong_side_pc"]
            * (self.punch + 2 * self.commision)
        )

    def find_predict_thresholds(self):
        Logger.debug("Find predic threshold")
        qualities = []
        for null_threshold in np.arange(0.3, 0.8, 0.05):
            for prob_threshold in np.arange(0.3, 0.7, 0.05):
                for diff_threshold in np.arange(0.00, 0.20, 0.05):
                    qualities.append(
                        self._get_predictions_quality(
                            prob_threshold, diff_threshold, null_threshold
                        )
                    )
        qualities = list(
            sorted(
                qualities,
                key=lambda quality: -self._get_profit(
                    quality["prob_threshold"],
                    quality["diff_threshold"],
                    quality["null_threshold"],
                ),
            )
        )
        self.prob_threshold = qualities[0]["prob_threshold"]
        self.diff_threshold = qualities[0]["diff_threshold"]
        self.null_threshold = qualities[0]["null_threshold"]

        print(
            f"Prob_threshold {self.prob_threshold}, diff_threshold {self.diff_threshold}, null_threshold {self.null_threshold}"
        )
        with open(
            "punch_predictor_thresholds.dump", "w", encoding="utf-8"
        ) as out_file:
            json.dump(
                {
                    "prob_threshold": self.prob_threshold,
                    "diff_threshold": self.diff_threshold,
                    "null_threshold": self.null_threshold,
                },
                out_file,
            )
        predictions = self._get_predictions(
            self.prob_threshold, self.diff_threshold, self.null_threshold
        )
        print("Accuracy", accuracy_score(predictions, self.y_test))
        profit = self._get_profit(
            self.prob_threshold, self.diff_threshold, self.null_threshold
        )
        print(
            "Profit from 3000$ fot 6 months",
            profit * 3000,
            "$",
            profit * 100,
            "%",
        )
        print()

    def _print_feature_importance(self) -> None:
        train_pool = Pool(self.X_train, self.y_train)
        feature_importances = self.model.get_feature_importance(train_pool)
        feature_names = self.X_train.columns
        print("Top-15 feature importance")
        for score, name in sorted(
            zip(feature_importances, feature_names), reverse=True
        )[:15]:
            print("{}: {}".format(name, score))
        print()

    def print_model_info(self) -> None:
        self._print_feature_importance()
        quality = self._get_predictions_quality(
            self.prob_threshold, self.diff_threshold, self.null_threshold
        )
        print(quality)
        print()
        correct_accuracy = quality["correct_predictions"] / len(
            self.y_test[self.y_test != 0]
        )
        print(
            f"Correct accuracy = correct prediction / total positive num = {correct_accuracy}"
        )
        FPR = quality["false_positive"] / len(self.y_test[self.y_test == 0])
        print(f"FPR = false positive / total negative num = {FPR}")
        FNR = quality["false_negative"] / len(self.y_test[self.y_test != 0])
        print(f"FNR = false negative / total positive num = {FNR}")
        cases_pc = (
            (
                quality["correct_predictions"]
                + quality["false_positive"]
                + quality["wrong_side"]
            )
            / len(self.y_test[self.y_test != 0])
            * 100
        )
        probability_pc = (
            quality["correct_predictions"]
            / (
                quality["correct_predictions"]
                + quality["false_positive"]
                + quality["wrong_side"]
            )
            * 100
        )
        print(
            f"Model in {cases_pc}% of cases with probability {probability_pc}% predict a correct market jump"
        )


def main():
    tm = TrainModel(
        "../../data/trades/processed/trades-df-2021_8_1_0_0_0-2022_1_22_0_0_0.csv"
    )
    tm.train()
    tm.find_predict_thresholds()
    tm.print_model_info()


if __name__ == "__main__":
    main()
