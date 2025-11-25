from AlgorithmImports import *  # noqa: F401,F403


class EmaCrossAlgorithm(QCAlgorithm):
    def Initialize(self) -> None:
        self.SetStartDate(2023, 1, 1)
        self.SetEndDate(2023, 12, 31)
        self.SetCash(100000)
        self.symbol = self.AddCrypto("BTCUSDT", Resolution.Minute, Market.Binance).Symbol
        fast = ExponentialMovingAverage(10)
        slow = ExponentialMovingAverage(30)
        self.RegisterIndicator(self.symbol, fast, Resolution.Minute)
        self.RegisterIndicator(self.symbol, slow, Resolution.Minute)
        self.fast = fast
        self.slow = slow
        self.SetWarmUp(30)

    def OnData(self, data: Slice) -> None:
        if self.IsWarmingUp:
            return
        if self.fast.Current.Value > self.slow.Current.Value and not self.Portfolio[self.symbol].Invested:
            self.SetHoldings(self.symbol, 1.0)
        elif self.fast.Current.Value < self.slow.Current.Value and self.Portfolio[self.symbol].Invested:
            self.Liquidate(self.symbol)
