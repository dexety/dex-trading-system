# Crypto trading system
This is a trading system for the DyDx decentralized exchange

# Project structure

## Collect data
Scripts for data collection

*Example:* `collect_trades.py`

## Connectors
Interface for connecting and working with exchanges

## Data
Data from exchanges

*Example:* `trades/trades_ETH-USD.py`

## Research
Research on any topic that MAY NOT be compatible with updates. It's best to have a `README.md` file with research results. Inside your folder you can do whatever you want, but it will be good if others can easily understand what you have done.

### Structure
**Research folder name:** `[short_name]-[research_number]-[research_name]/...`

Reserved short names:
- lp -- Leo Proko
- lr -- Lev Rybakov
- ib -- Ivan Bondyrev

*Folder name example:* `lp-0001-momental-leaps/...`

## Strategy
Trading strategies that have already passed the research stage

# Тесты

## Как добавить новый тест?

- В папке `tests` создайте `.py` файл. В названии обязательно должно быть слово `test`.
- В этом файле создайте класс, который будет обязательно начинаться с `Test`. В классе не должно быть конструктора, то есть метода `__init__`. Все переменные, которые вам нужны, объявляйте статическими. [https://radek.io/2011/07/21/static-variables-and-methods-in-python/](https://radek.io/2011/07/21/static-variables-and-methods-in-python/)
- Каждый юнит-тест — это метод класса. Все методы, которые надо протестировать, должны обязательно начинаться c `test`.

### Пример

[https://github.com/dexety/dex-trading-system/blob/main/tests/test_client_api.py](https://github.com/dexety/dex-trading-system/blob/main/tests/test_client_api.py)

## Как запустить тесты

- В корне есть файл `lint_and_test.sh`, он запускает линтер и тестер с нужными параметрами
- Чтобы все это запустить отдельно, есть соответствующие команды в папке `tests`