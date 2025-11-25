import matplotlib.pyplot as plt


def equity_curve(values):
    fig, ax = plt.subplots()
    ax.plot(values)
    return fig
