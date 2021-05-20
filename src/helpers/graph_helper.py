import pandas
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from io import BytesIO

matplotlib.use("Agg")


def file_from_timestamps(times, group):
    file = BytesIO()
    series = pandas.Series(times)
    series.index = series.dt.to_period(group)
    series = series.groupby(level=0).size()
    series = series.reindex(pandas.period_range(series.index.min(), series.index.max(), freq=group), fill_value=0)
    bar_chart = series.plot(subplots=False)
    bar_chart.spines['bottom'].set_position('zero')
    figure = bar_chart.get_figure()
    figure.tight_layout()
    figure.savefig(file)
    file.seek(0)
    return file.read()


def pie_chart_from_amount_and_labels(labels, amounts):
    file = BytesIO()
    amounts = np.array(amounts)
    fig = plt.figure()
    axes = fig.add_axes([0, 0, 1, 1])
    axes.axis("equal")
    axes.pie(amounts, labels=labels, autopct='%1.1f%%')
    fig.savefig(file)
    file.seek(0)
    return file.read()


def plot_stats(data):
    file = BytesIO()
    plt.plot(list(range(-len(data), 1)), data)
    plt.savefig(file)
    file.seek(0)
    return file.read()

