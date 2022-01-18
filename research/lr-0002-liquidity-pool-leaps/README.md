# This is a research for flashloans.

The idea of falshloans is to borrow a lot of money in crypto, then make some trades on layer 1 of ethereum network so that you will have more than you started with, and repay everything that you borrowed with some interest. All this should be executed in 1 transaction, because this is the way flashloans work. To understand if the strategy is even possible, we need to make sure that we can buy/sell a lot of money in L1 exchanges with profit.

Currently there is a script, that allows you to swap 10 DAI to WETH using Uniswap. It uses our contract, called SwapExamples. To run the script use command `brownie run scripts/swap_some_dai.py --network ropsten`