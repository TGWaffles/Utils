import pandas
import matplotlib.pyplot as plt
import numpy as np
import PIL
import PIL.Image

from io import BytesIO


def file_from_timestamps(times, group):
    file = BytesIO()
    series = pandas.Series(times)
    series.index = series.dt.to_period(group)
    series = series.groupby(level=0).size()
    series = series.reindex(pandas.period_range(series.index.min(), series.index.max(), freq=group), fill_value=0)
    bar_chart = series.plot.bar(subplots=False)
    figure = bar_chart.get_figure()
    figure.tight_layout()
    figure.savefig(file)
    file.seek(0)
    return file.read()


def pie_chart_from_amount_and_labels(labels, amounts):
    file = BytesIO()
    smaller_amounts = amounts[15:]
    labels = labels[:15]
    amounts = amounts[:15]
    amounts.append(sum(smaller_amounts))
    labels.append("Other")
    amounts = np.array(amounts)
    fig = plt.figure()
    axes = fig.add_axes([0, 0, 1, 1])
    axes.axis("equal")
    axes.pie(amounts, labels=labels, autopct='%1.3f%%')
    fig.savefig(file)
    file.seek(0)
    return file.read()
