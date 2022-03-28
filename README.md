# Crypto trading system
This is a trading system for the DyDx decentralized exchange

# Configuration

## Python modules

Из-за того, что некоторые пайтон-модули используют разные версии одних и тех же библиотек, возникаются конфиликты, если все скачивать просто через `pip3 install -r requirements.txt`.

Поэтому скачайте все модули через `pip3 -r install -r requirements.txt --no-deps`, а то, что не скачается из-за опции `--no-deps`, придется докачивать руками.

## Python env

Добавьте корень проекта в окружение, чтобы из любого места проекта можно было импортить любое другое.
```bash
export PYTHONPATH=`/path/to/dex-trading-system`
```

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
- В этом файлы вы может создавать свои юнит-тесты.
- Все функции, которые надо протестировать, должны обязательно начинаться c `test`.

### Пример

[https://github.com/dexety/dex-trading-system/blob/main/tests/test_client_api.py](https://github.com/dexety/dex-trading-system/blob/main/tests/test_client_api.py)

## Как запустить тесты

- В корне есть файл `run_tests.sh`, он запускает тестер с нужными параметрами

# Линтер

## Параметры

Параметры линтера находятся в файлике `pyproject.toml`

## Как запустить линтер

- В корне есть файл `lint.sh`, он запускает линтер с нужными параметрами
