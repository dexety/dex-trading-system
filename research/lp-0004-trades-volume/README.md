# CatBoost. Предсказание скачков цены по размерам сделок.

# TLDR

Есть моделька, которая в 9.78% случаев с вероятностью 69.63% правильно предсказывает скачок рынка.

# Данные

Из предыдущей таски есть обработанные данные трейдов. По столбцам записано значение индикаторов по каждой из сторон за последние `n/c, 2n/c, ..., n` секунд.

Я их распарсил так что по столбцам данные за промежутки `[0, n/c], [n/c, 2n/c], ..., [(c - 1)n/c, n]` секунд. Я выбрал параметры `n = 60, c = 10`.

В качестве вектора ответов у нас единица, если рынок отклонился более, чем на `delta` вверх, -1, если вниз, и 0 иначе. `delta` я экспериментально выбрал как `5 * commision`, `commision = 0.02%`.

## Индикаторы

- Объем торгов
    - Сумма объема всех сделок
- Скользящее среднее
    - Сумма цен сделок, поделенная на их количество
- Экспоненциальное скользящее среднее
    - Сумма цен сделок, где более старая идет с меньшим весом
- Взвешенное скользящее среднее
    - Сумма цен сделок, умноженных на их объем, поделенная на общий объем
- Стохастический осцилятор
    - Разница цен последней сделки и самой дешевой, поделенной на максимум из единицы и разницы цен максимальной и минимальной сделки

# CatBoost

Я использовал библиотеку `CatBoost` для `Python`. Она очень простая, там почти все делать по фит-предикт. Даже настройку гипер-параметров можно сделать автоматической.

## Фит-Предикт

```python
params = {
    'iterations': 300,
    'l2_leaf_reg': int(best['l2_leaf_reg']),
    'learning_rate': best['learning_rate'],
    'custom_loss': [metrics.Accuracy()],
    'eval_metric': metrics.Accuracy(),
    'random_seed': 42,
    'logging_level': 'Silent',
    'loss_function': 'Logloss',
}
train_pool = Pool(X_train, y_train)
validate_pool = Pool(X_validation, y_validation)
model = CatBoostClassifier(**params)
model.fit(
    train_pool,
    eval_set=validate_pool,
    plot=True,
)

print('Model validation accuracy: {:.4}'.format(
    accuracy_score(y_test, model.predict(X_test))
))
# Output:
# Model validation accuracy: 0.8387

predictions = model.predict(X_test)
predictions = predictions.reshape(predictions.shape[0], 1)
predictions_probs = model.predict_proba(X_test)
print(predictions[10:20])
print(predictions_probs[10:20])
print(y_test[10:20])
# Output:
# [[0]
#  [0]
#  [1]
#  [0]
#  [0]
#  [0]
#  [0]
#  [0]
#  [0]
#  [0]]
# [[0.90951818 0.09048182]
#  [0.90500857 0.09499143]
#  [0.10940416 0.89059584]
#  [0.769889   0.230111  ]
#  [0.89437084 0.10562916]
#  [0.74706247 0.25293753]
#  [0.92070772 0.07929228]
#  [0.92894806 0.07105194]
#  [0.82551112 0.17448888]
#  [0.84077802 0.15922198]]
#        target
# 11825       0
# 16429       0
# 37912       1
# 18177       0
# 17451       0
# 21036       0
# 3300        0
# 6366        1
# 1772        0
# 13051       0
```

## Подбор гипер-параметров

```python
def hyperopt_objective(params):
    model = CatBoostClassifier(
        l2_leaf_reg=int(params['l2_leaf_reg']),
        learning_rate=params['learning_rate'],
        iterations=300,
        eval_metric=metrics.Accuracy(),
        random_seed=126,
        verbose=False,
        loss_function=metrics.Logloss(),
    )
    cv_data = cv(
        Pool(X, y),
        model.get_params(),
        fold_count=5,
        shuffle=True,
        logging_level='Silent',
    )
    best_accuracy = np.max(cv_data['test-Accuracy-mean'])
    return 1 - best_accuracy

params_space = {
    'l2_leaf_reg': hyperopt.hp.qloguniform('l2_leaf_reg', 0, 2, 1),
    'learning_rate': hyperopt.hp.uniform('learning_rate', 1e-3, 5e-1),
}
trials = hyperopt.Trials()
best = hyperopt.fmin(
    hyperopt_objective,
    space=params_space,
    algo=hyperopt.tpe.suggest,
    max_evals=50,
    trials=trials,
    rstate=RandomState(42)
)
```

В `best` у нас будут лучшие гипер-параметры

# Предсказание

Есть понятия `False Positive Ratio` и  `False Negative Ratio`. Из названия легко понять, за что они отвечают. Первое считается, как отношение того, когда мы предсказали 1 к тому, когда правильным ответом было ноль. Второе наоборот. Мы хотим сделать эти значения как можно меньше. В нашем случае оптимизировать лучше первую метрику, потому что лучше, если наш алгоритм скажет, что ничего делать не надо, когда рынок будет колебаться, чем наоборот, потому что в первом случае мы ничего не потерями, а во втором да. Параметр `delta` подобран так, что

```python
FPR = false positive / total negative num = 0.010005175090564086
FNR = false negative / total positive num = 0.8827444956477215
```

Эксперимент показал, что такие значения достигаются при плече принятия решений `omega = 34%`. То есть если модель предсказывает `+-1` с такой вероятностью или больше, то мы считаем, что ее прогноз верный. Причем мы не хотим оказаться в ситуации, когда модель выдает `P(1) = 45%, P(-1) = 45.1%` , порог в `34%` пройден, значит надо выбирать -1. Но мы хотим выбрать -1 только тогда, когда `P(-1) >= omega and P(-1) > (P(1) + epsilon) and P(-1) > (P(0) + epsilon)`. Эксперимент выдал, что `epsilon = 1%` оптимальнее всего.

# Результат

При таких параметрах получается, что моделька в 9.78% случаев с вероятностью 69.63% правильно предсказывает скачок рынка. То есть из всех скачков она ловит только 9.78%. И среди них с вероятностью 69.63% угадывает, куда пойдет рынок.