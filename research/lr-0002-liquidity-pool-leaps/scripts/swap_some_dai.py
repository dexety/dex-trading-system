from brownie import interface, network, config, SwapExamples
from scripts.helpful_scripts import get_account


def main():
    addresses = config["networks"][network.show_active()]
    amountIn = 10 * 10 ** 18  # $10
    dai = interface.ERC20(addresses["dai_token"])
    account = get_account(type="test")

    print("Deploing swapper...")
    swap = SwapExamples.deploy(
        addresses["uniswap_swap_router"], {"from": account}
    )
    print("Done")

    print("Approving...")
    dai.approve(swap, amountIn, {"from": account})
    print("Done")

    print("Swap initiated...")
    swap.swapExactInputSingle(amountIn)
    print("Done")
