# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
from catboost import CatBoostClassifier, Pool, metrics, cv
from sklearn.metrics import accuracy_score
import random

csv_path = (
    "../../data/trades/precessed/trades-df-2021_8_1_0_0_0-2022_1_22_0_0_0.csv"
)
df = pd.read_csv(csv_path)
x_columns = list(filter(lambda column: not "punch" in column, df.columns))
y_columns = list(filter(lambda column: "punch" in column, df.columns))

commision = 0.0005
punch = commision * 4

df["target"] = df[y_columns].apply(
    lambda row: 1
    if max(list(row.to_numpy()), key=abs) > punch
    else -1
    if max(list(row.to_numpy()), key=abs) < -punch
    else 0,
    axis=1,
)
df = df.drop(y_columns, axis=1)

lines_to_drop = []

for index, line in df.iterrows():
    if np.random.rand() < 0.9 and line["target"] == 0:
        lines_to_drop.append(index)

df = df.drop(lines_to_drop)

X = df[x_columns]
y = df["target"]

print(y.value_counts())

buckets_num = 50
buckets = [
    df[len(df) // buckets_num * i : len(df) // buckets_num * (i + 1)]
    for i in range(buckets_num)
]
random.shuffle(buckets)
df_train = pd.concat(buckets[: int(buckets_num * 0.75)], ignore_index=True)
df_validate = pd.concat(
    buckets[int(buckets_num * 0.75) : int(buckets_num * 0.90)],
    ignore_index=True,
)
df_test = pd.concat(buckets[int(buckets_num * 0.90) :], ignore_index=True)

X_train = df_train[x_columns]
y_train = df_train["target"]

X_validation = df_validate[x_columns]
y_validation = df_validate["target"]

X_test = df_test[x_columns]
y_test = df_test["target"]

params = {
    "iterations": 1000,
    "l2_leaf_reg": 2,
    "learning_rate": 0.2,
    "custom_loss": [metrics.Accuracy()],
    "eval_metric": metrics.Accuracy(),
    "random_seed": 42,
    "depth": 5,
    "logging_level": "Silent",
    "loss_function": "MultiClass",
}
train_pool = Pool(X_train, y_train)
validate_pool = Pool(X_validation, y_validation)

model = CatBoostClassifier(**params)
model.fit(
    train_pool,
    eval_set=validate_pool,
    plot=True,
)
model.save_model("catboost_model.dump")

print(
    "Model validation accuracy: {:.4}".format(
        accuracy_score(y_test, model.predict(X_test))
    )
)
predictions = model.predict(X_test)
predictions = predictions.reshape(predictions.shape[0], 1)
predictions_probs = model.predict_proba(X_test)
print(predictions[90:100])
print(predictions_probs[90:100])
print(y_test[90:100])
feature_importances = model.get_feature_importance(train_pool)
feature_names = X_train.columns
for score, name in sorted(
    zip(feature_importances, feature_names), reverse=True
):
    print("{}: {}".format(name, score))


def calculate_profit(prob_threshold, diff_threshold, null_threshold):
    p = f(prob_threshold, diff_threshold, null_threshold)
    result = {
        "correct_predictions": 0,
        "false_positive": 0,
        "false_negative": 0,
        "wrong_side": 0,
    }
    for i in range(len(p)):
        t = int(y_test[i : i + 1])
        if p[i] == t != 0:
            result["correct_predictions"] += 1
        elif p[i] != t and t != 0 and p[i] != 0:
            result["wrong_side"] += 1
        elif p[i] != 0 and t == 0:
            result["false_positive"] += 1
        elif p[i] == 0 and t != 0:
            result["false_negative"] += 1

    result["correct_predictions_pc"] = result["correct_predictions"] / len(
        y_test
    )
    result["false_positive_pc"] = result["false_positive"] / len(y_test)
    result["false_negative_pc"] = result["false_negative"] / len(y_test)
    result["wrong_side_pc"] = result["wrong_side"] / len(y_test)

    return (
        len(y) * result["correct_predictions_pc"] * (punch - 2 * commision)
        - len(y) * result["false_positive_pc"] * 2 * commision
        - len(y) * result["wrong_side_pc"] * (punch + 2 * commision)
    )


results = []


def f(prob_threshold, diff_threshold, null_threshold):
    p = np.array(
        (
            list(
                map(
                    lambda row: 1 if row[2] > prob_threshold
                    # and row[2] == max(row)
                    and row[2] > row[0]
                    and row[1] < null_threshold
                    and abs(row[2] - row[0]) > diff_threshold
                    and abs(row[2] - row[1]) > diff_threshold
                    else -1
                    if row[0] > prob_threshold
                    # and row[0] == max(row)
                    and row[0] > row[2]
                    and row[1] < null_threshold
                    and abs(row[0] - row[2]) > diff_threshold
                    and abs(row[0] - row[1]) > diff_threshold
                    else 0,
                    predictions_probs,
                )
            )
        )
    )
    result = {
        "correct_predictions": 0,
        "false_positive": 0,
        "false_negative": 0,
        "wrong_side": 0,
    }
    for i in range(len(p)):
        t = int(y_test[i : i + 1])
        if p[i] == t != 0:
            result["correct_predictions"] += 1
        elif p[i] != t and t != 0 and p[i] != 0:
            result["wrong_side"] += 1
        elif p[i] != 0 and t == 0:
            result["false_positive"] += 1
        elif p[i] == 0 and t != 0:
            result["false_negative"] += 1

    result["correct_predictions"] /= len(y_test)
    result["false_positive"] /= len(y_test)
    result["false_negative"] /= len(y_test)
    result["wrong_side"] /= len(y_test)
    result["prob_threshold"] = prob_threshold
    result["diff_threshold"] = diff_threshold
    result["null_threshold"] = null_threshold
    results.append(result)
    return p


for null_threshold in np.arange(0.3, 0.8, 0.05):
    for prob_threshold in np.arange(0.3, 0.7, 0.05):
        for diff_threshold in np.arange(0.00, 0.20, 0.05):
            f(prob_threshold, diff_threshold, null_threshold)

results = list(
    sorted(
        results,
        key=lambda result: -calculate_profit(
            result["prob_threshold"],
            result["diff_threshold"],
            result["null_threshold"],
        ),
    )
)
print(results[0])

prob_threshold = results[0]["prob_threshold"]
diff_threshold = results[0]["diff_threshold"]
null_threshold = results[0]["null_threshold"]

print(
    f"prob_threshold {prob_threshold}, diff_threshold {diff_threshold}, null_threshold {null_threshold}"
)
p = f(prob_threshold, diff_threshold, null_threshold)
print("accuracy", accuracy_score(p, y_test))
result = {
    "correct_predictions": 0,
    "false_positive": 0,
    "false_negative": 0,
    "wrong_side": 0,
}
for i in range(len(p)):
    t = int(y_test[i : i + 1])
    if p[i] == t != 0:
        result["correct_predictions"] += 1
    elif p[i] != t and t != 0 and p[i] != 0:
        result["wrong_side"] += 1
    elif p[i] != 0 and t == 0:
        result["false_positive"] += 1
    elif p[i] == 0 and t != 0:
        result["false_negative"] += 1

result["correct_predictions_pc"] = result["correct_predictions"] / len(y_test)
result["false_positive_pc"] = result["false_positive"] / len(y_test)
result["false_negative_pc"] = result["false_negative"] / len(y_test)
result["wrong_side_pc"] = result["wrong_side"] / len(y_test)
print(result)

profit = calculate_profit(prob_threshold, diff_threshold, null_threshold)
print("profit from 3000$ fot 6 months", profit * 3000, "$", profit * 100, "%")

correct_accuracy = result["correct_predictions"] / len(y_test[y_test != 0])
print(
    f"Correct accuracy = correct prediction / total positive num = {correct_accuracy}"
)
FPR = result["false_positive"] / len(y_test[y_test == 0])
print(f"FPR = false positive / total negative num = {FPR}")
FNR = result["false_negative"] / len(y_test[y_test != 0])
print(f"FNR = false negative / total positive num = {FNR}")
cases_pc = (
    (
        result["correct_predictions"]
        + result["false_positive"]
        + result["wrong_side"]
    )
    / len(y_test[y_test != 0])
    * 100
)
probability_pc = (
    result["correct_predictions"]
    / (
        result["correct_predictions"]
        + result["false_positive"]
        + result["wrong_side"]
    )
    * 100
)
print(
    f"Model in {cases_pc}% of cases with probability {probability_pc}% predict a correct market jump"
)
