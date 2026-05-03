"""Tests for src.visualization.charts – chart factories."""

from src.visualization.charts import CHART_REGISTRY
import matplotlib.pyplot as plt
import matplotlib

matplotlib.use("Agg")


class TestChartRegistry:
    def test_all_keys_callable(self):
        for key, factory in CHART_REGISTRY.items():
            assert callable(factory), f"{key} is not callable"

    def test_charts_return_figure(self, sample_dataframe):
        for key, factory in CHART_REGISTRY.items():
            fig = factory(sample_dataframe)
            assert isinstance(fig, plt.Figure), f"{
                key} did not return a Figure"
            plt.close(fig)
