"""
Chart builder - specialized for Excel chart operations
"""

from typing import List, Optional, Union
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.chart import (
    BarChart,
    LineChart,
    PieChart,
    AreaChart,
    ScatterChart,
    DoughnutChart,
    RadarChart,
    Reference,
)

from .configs import ChartConfig, ComboChartConfig


class ChartBuilder:
    """Specialized builder for Excel charts"""

    def __init__(self):
        self.chart_types = {
            "bar": BarChart,
            "column": BarChart,
            "line": LineChart,
            "pie": PieChart,
            "area": AreaChart,
            "scatter": ScatterChart,
            "doughnut": DoughnutChart,
            "radar": RadarChart,
        }

    def create_chart(self, worksheet: Worksheet, config: ChartConfig) -> None:
        """Create and add a chart to the worksheet"""
        ChartClass = self.chart_types.get(config.chart_type.lower(), BarChart)
        chart = ChartClass()

        # Set title
        if config.title:
            chart.title = config.title

        # Configure chart based on type
        if config.chart_type.lower() == "column":
            chart.type = "col"
        elif config.chart_type.lower() == "bar":
            chart.type = "bar"

        # Add data and categories
        chart.add_data(config.data_range, titles_from_data=True)
        if config.categories and config.chart_type.lower() not in ["pie", "doughnut"]:
            chart.set_categories(config.categories)

        # Set dimensions
        chart.width = config.width
        chart.height = config.height

        # Add to worksheet
        worksheet.add_chart(chart, config.position)
        return chart

    def create_chart_legacy(
        self,
        worksheet: Worksheet,
        chart_type: str,
        data_range: Reference,
        categories: Optional[Reference] = None,
        title: str = "",
        position: str = "E5",
    ) -> None:
        """Legacy method for backward compatibility"""
        config = ChartConfig(
            chart_type=chart_type,
            data_range=data_range,
            categories=categories,
            title=title,
            position=position,
        )
        return self.create_chart(worksheet, config)

    def create_combo_chart(
        self, worksheet: Worksheet, config: ComboChartConfig
    ) -> None:
        """Create a combination chart with two data series"""
        # Create primary chart
        primary_chart = self._create_base_chart(config.primary_type)
        primary_chart.title = config.title
        primary_chart.add_data(config.primary_data, titles_from_data=True)
        primary_chart.set_categories(config.categories)

        # Create secondary chart
        secondary_chart = self._create_base_chart(config.secondary_type)
        secondary_chart.add_data(config.secondary_data, titles_from_data=True)
        secondary_chart.set_categories(config.categories)

        # Combine charts
        primary_chart += secondary_chart

        # Add to worksheet
        worksheet.add_chart(primary_chart, config.position)

    def style_chart(
        self,
        chart: Union[BarChart, LineChart, PieChart, AreaChart],
        style_id: int = 2,
        colors: Optional[List[str]] = None,
    ) -> None:
        """Apply styling to a chart"""
        # Apply built-in style
        chart.style = style_id

        # Apply custom colors if provided
        if colors and hasattr(chart, "series"):
            for i, series in enumerate(chart.series):
                if i < len(colors):
                    series.graphicalProperties.solidFill = colors[i]

    def add_data_labels(
        self,
        chart: Union[BarChart, LineChart, PieChart, AreaChart],
        show_value: bool = True,
        show_percentage: bool = False,
        position: str = "center",
    ) -> None:
        """Add data labels to chart"""
        from openpyxl.chart.label import DataLabelList

        chart.dataLabels = DataLabelList()
        chart.dataLabels.showVal = show_value

        if isinstance(chart, (PieChart, DoughnutChart)):
            chart.dataLabels.showPercent = show_percentage

    def set_axis_titles(
        self,
        chart: Union[BarChart, LineChart, AreaChart],
        x_title: str = "",
        y_title: str = "",
    ) -> None:
        """Set axis titles for charts that support them"""
        if hasattr(chart, "x_axis") and x_title:
            chart.x_axis.title = x_title

        if hasattr(chart, "y_axis") and y_title:
            chart.y_axis.title = y_title

    def _create_base_chart(self, chart_type: str):
        """Create a base chart instance"""
        ChartClass = self.chart_types.get(chart_type.lower(), BarChart)
        chart = ChartClass()

        if chart_type.lower() == "column":
            chart.type = "col"
        elif chart_type.lower() == "bar":
            chart.type = "bar"

        return chart
