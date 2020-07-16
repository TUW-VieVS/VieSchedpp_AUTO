import itertools
import math
import os

import matplotlib.pyplot as plt
import numpy as np


def summary(df, output):
    """
    generate summary plot with four fields: #obs, #scans, #sources and sky-coverage score

    :param df: DateFrame with summary statistics
    :param output: output directory path
    :return: None
    """
    codes = df.index.tolist()
    n = len(codes)
    networks = df["stations"].tolist()
    df = df.drop(columns=["stations"])

    unique_networks = set(networks)
    cat = []
    for net in unique_networks:
        cat.append([i for i, x in enumerate(networks) if x == net])

    n_col = df.columns.size
    fig_r = math.floor(math.sqrt(n_col))
    fig_c = math.ceil(n_col / fig_r)

    fig, axes = plt.subplots(fig_r, fig_c, figsize=(fig_c * 3, fig_r * 3), sharex='all')

    plt.xticks(range(n), codes)
    hs = []
    first_empty = 0;
    for i, field in itertools.zip_longest(range(0, fig_r * fig_c), df):
        if field is None:
            hs.append(plot_summary(axes.flat[i], None, cat, field))
            axes.flat[i].get_yaxis().set_visible(False)

            if first_empty == 0:
                first_empty = i
        else:
            hs.append(plot_summary(axes.flat[i], df[field], cat, field))
        for tick in axes.flat[i].get_xticklabels():
            tick.set_rotation(90)

    labels = []
    for net in unique_networks:
        n = len(net) / 2
        if (n > 6):
            labels.append("({:.0f}) {:12.12}...".format(n, net))
        else:
            labels.append("({:.0f}) {}".format(n, net))

    axes.flat[first_empty].legend(hs[first_empty], labels, loc='lower left')
    fig.subplots_adjust(left=0.1, right=0.975, bottom=0.15, top=0.95, wspace=0.2, hspace=0.15)
    plt.savefig(os.path.join(output, "summary.png"), dpi=150)


def plot_summary(ax, data, cat, title):
    """
    generate one summary plot in axes

    :param ax: axes
    :param data: values
    :param cat: categories for color-coding
    :param title: title for axes
    :return: list of plot handles
    """
    colors = ["#1f78b4",
              "#33a02c",
              "#e31a1c",
              "#ff7f00",
              "#6a3d9a",
              "#a6cee3",
              "#b2df8a",
              "#fb9a99",
              "#fdbf6f",
              "#cab2d6"]

    hs = []
    for x, c in zip(cat, colors):
        if data is None:
            d = np.full(len(x), np.nan)
        else:
            d = data[x]
        hs.append(ax.bar(x, d, color=c))
    ax.set_title(title)
    return hs


def polar_plots(skd, output, attribute_name):
    """
    generate sky-coverage plot with color-coded duration or scan start time

    :param skd: parsed sked file
    :param output: output directory path
    :param attribute_name: "duration" or "start_time"
    :return: None
    """
    stations = [sta.name for sta in skd.stations]
    n = len(stations)
    r = math.floor(math.sqrt(n))
    c = math.ceil(n / r)

    all_obs = [o for scan in skd.getScanList() for o in scan.observations]
    start_times = [o.scan.start_time for o in all_obs]

    fig, axes = plt.subplots(r, c, figsize=(c * 4, r * 4), subplot_kw={"projection": "polar"})
    h = []
    for sta, ax in zip(stations, axes.flat):
        h.append(polar_plot_per_station(all_obs, sta, ax, attribute_name))

    if n <= 3:
        fig.subplots_adjust(left=0.05, right=0.95, bottom=0.225, top=0.9, wspace=0.2, hspace=0.25)
        cbar_ax = fig.add_axes([0.05, 0.125, 0.9, 0.025])
    else:
        fig.subplots_adjust(left=0.05, right=0.95, bottom=0.15, top=0.95, wspace=0.2, hspace=0.25)
        cbar_ax = fig.add_axes([0.05, 0.07, 0.9, 0.025])

    fig.colorbar(h[0], cax=cbar_ax, orientation="horizontal")
    vmin = min([o.duration for o in all_obs])
    vmax = max([o.duration for o in all_obs])
    for this_h in h:
        this_h.set_clim(vmin, vmax)

    if attribute_name == "duration":
        cbar_ax.set_xlabel("duration [sec]")
    elif attribute_name == "start_time":
        cbar_ax.set_xlabel("time since observation start [h]")

    plt.savefig(os.path.join(output, "{:s}.png".format(attribute_name)), dpi=150)


def polar_plot_per_station(all_obs, station, ax, attribute_name):
    """
    generate one sky-coverage plot in axes

    :param all_obs: list of all observations
    :param station: station name
    :param ax: axes
    :param attribute_name: "duration" or "start_time"
    :return:
    """
    if attribute_name == "duration":
        vmin = min([o.duration for o in all_obs])
        vmax = max([o.duration for o in all_obs])
    elif attribute_name == "start_time":
        vmin = min([o.scan.start_time for o in all_obs])
        vmax = max([o.scan.start_time for o in all_obs])
    else:
        vmin = 0
        vmax = 1

    obs = [o for o in all_obs if o.station.name == station]
    az = np.array([o.az_start for o in obs])
    el = np.array([o.el_start for o in obs])
    zd = 90 - np.degrees(el)
    if attribute_name == "duration":
        target = np.array([o.duration for o in obs])
        cmap = "RdYlGn_r"
    elif attribute_name == "start_time":
        target = np.array([(o.scan.start_time - vmin).total_seconds() / 3600. for o in obs])
        vmax = (vmax - vmin).total_seconds() / 3600.
        vmin = 0.0
        cmap = "gist_rainbow"
    else:
        target = np.full(az.shape, 0.0)
        cmap = "Greys"

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim([0, 90])

    ax.set_yticks(np.arange(15, 91, 15))
    labels = ["", "NE", "E", "SE", "S", "SW", "W", "NW"]
    ax.set_xticklabels(labels)

    ax.set_title(station)
    h = ax.scatter(az, zd, c=target, cmap=cmap, alpha=0.75, vmin=vmin, vmax=vmax, edgecolors='k')
    return h


def close_all():
    """
    close all figures

    Returns
    -------

    """
    plt.close('all')
