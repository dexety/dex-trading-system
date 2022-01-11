# Hypothesis
## Market-Making strategy
1. Take 2 mirror orders of size `v` with a spread `s` around the index price.
2. If one order was realized, cancel the second order. Let the order `SELL` was realized at a price of `p1`.
3. Make only `BUY` order with price `p2 = p1 * (1 - d)`, `p2 < p1`.
4. When the `BUY` order is realized, repeat step (1).
5. If index price in step (3) is less than p1 * (1 - c), cancel it

Let the commission equal to `c`. In one cycle your profit will be `v * (p1 - p2) - 2 * c * v * (p1 + p2)`.

## Parameters
- `s` -- spread of mirror orders
- `d` -- delta between the price of orders, the coefficient of profit
- `e` -- cancel ratio
- `v` -- the size of the currency we are buying
- `c` -- commission

## Disadvantages.
- The period between steps can be very long, which means a small profit.

# Implementation

## Алгоритм

В словаре `our_orders` находятся две зеркальные заявки со спредом `spread_pc`. Как только одну сторону пробивают, вторая заявка остается на том же месте, но ту, которую пробили, мы не восстанавливаем. После пробития второй заявки, повторяем все заново.

В итоге наш профит равен `v * abs(p1 - p2) - 2 * c * v * (p1 + p2)` , где `abs(1 - p1 / p2) = spread_pc`

## Реализация

Пусть уже задан словарь `our_orders`. Тогда на каждой итерации будем смотреть на трейды, совершенные за `stock_delay_ms` после самой поздней нашей заявки. Смотрим, пробили ли нас или нет. Если не пробили, то мы успеем переставить заявки. Если пробили, то ждем, когда пробьют вторую заявку.

## Результаты

Гипотеза о недостатках подтвердилась. За день в среднем совершалось 5-8 прибыльных пар сделок.

`Your profit is 124.41112500001034 $ using market-making strategy with 1 ETH` при `spread_pc = 1.5 * commision` 

Соответственно прибыль за неделю при курсе 4000$/ETH составила 3,110278125 % при нулевом плече, то есть надо иметь 1 ETH, и эквивалент в долларах.

Результаты согласуются с моей предыдущей работой `lp-0001-momental-leaps`, вот график

[картинка есть в ноушене]

Вертикальные линии —  скачки больше, чем на комиссию. В те же моменты срабатывала `market-making` стратегия. Так как в этой стратегии прибыль всегда фиксирована, равна `(p1 - p2) * v - 2 * c`, где `p1/p2` задано условиями стратегии, то суммарная прибыль равна количеству скачков, умноженное на эту величину.