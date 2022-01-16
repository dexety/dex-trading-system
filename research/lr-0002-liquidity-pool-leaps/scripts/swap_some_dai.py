from brownie import interface, network, config, SwapExamples, accounts
from scripts.helpful_scripts import get_account


def main():
    addresses = config["networks"][network.show_active()]
    amountIn = 10 * 10 ** 18  # $10
    dai = interface.ERC20(addresses["dai_token"])
    account = get_account(type="test")

    print("Getting swapper contract...")
    if len(SwapExamples) > 0:
        swap = SwapExamples[-1]
    else:
        print("Swapper has not been deployed yet")
        print("Deploing swapper...")
        swap = SwapExamples.deploy(
            addresses["uniswap_swap_router"], {"from": account}
        )
        print("Done")

    print("Checking allowance...")
    if dai.allowance(account, swap) < amountIn:
        print("Allowance not enough")
        print("Approving spending of $10...")
        dai.approve(swap, amountIn, {"from": account})
        print("Done")

    print("Initiating swap...")
    swap.swapExactInputSingle(amountIn, {"from": account})
    print("Done")
