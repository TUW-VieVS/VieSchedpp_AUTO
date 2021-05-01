import itertools
import math
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def summary(df, fields, output):
    """
    generate summary plot with four fields: #obs, #scans, #sources and sky-coverage score

    :param df: DateFrame with summary statistics
    :param fields: list of fields
    :param output: output directory path
    :return: None
    """
    codes = df.index.tolist()
    networks = df["stations"].tolist()
    networks_s = []
    for n in networks:
        tmp = [n[i:i+2] for i in range(0, len(n), 2)]
        tmp.sort()
        networks_s.append("".join(tmp))
    networks = networks_s

    n = len(codes)

    unique_networks = [*set(networks)]
    cat = [ unique_networks.index(net) for net in networks ]

    n_col = len(fields)
    fig_r = math.floor(math.sqrt(n_col))
    fig_c = math.ceil(n_col / fig_r)

    fig, axes = plt.subplots(fig_r, fig_c, figsize=(fig_c * 3.5, fig_r * 4), sharex='all')

    plt.xticks(range(n), codes)
    first_empty = 0
    hs = None
    for i, field in itertools.zip_longest(range(0, fig_r * fig_c), fields):
        ax = axes.flat[i]
        hs = plot_summary_background(ax, cat)
        if field is None:
            ax.get_yaxis().set_visible(False)
            if first_empty == 0:
                first_empty = i
        elif field in df:
            data = df[field]
            ax.bar(range(len(data)), data, width=.6, ec='#252525', fc='#969696')
            if field.startswith("n_"):
                field = "#" + field[2:]
            ax.set_title(field)

        else:
            plot_special_stats(ax, df, field)
            pass

        for tick in ax.get_xticklabels():
            tick.set_rotation(90)

    labels = []
    for net in unique_networks:
        n = len(net) / 2
        if (n > 6):
            labels.append("({:.0f}) {:12.12}...".format(n, net))
        else:
            labels.append("({:.0f}) {}".format(n, net))

    axes.flat[first_empty].legend(hs, labels, loc='lower left')
    plt.tight_layout()
    # fig.subplots_adjust(left=0.1, right=0.975, bottom=0.15, top=0.95, wspace=0.2, hspace=0.15)
    plt.savefig(os.path.join(output, "summary.png"), dpi=150)


def plot_summary_background(ax, cats):
    colors = ["#1f78b4",
              "#33a02c",
              "#e31a1c",
              "#ff7f00",
              "#6a3d9a",
              "#a6cee3",
              "#b2df8a",
              "#fb9a99",
              "#fdbf6f",
              "#cab2d6",
              ]

    painted = []

    hs = []
    for i in range(10):
        for x in range(len(cats)):
            if cats[x] == i:
                c = colors[i]
                h = ax.axvspan(x-.5, x+.5, alpha=0.25, color=c)
                if c not in painted:
                    painted.append(c)
                    hs.append(h)
    return hs


def plot_special_stats(ax, df, field):
    """
    generate one summary plot in axes

    :param ax: axes
    :param data: dataframe
    :param field: field
    """
    x = np.arange(df.shape[0])

    ecs = [
        '#1f77b4',
        '#ff7f0e',
        '#2ca02c',
        '#d62728',
        '#9467bd',
        '#8c564b',
        '#e377c2',
        '#7f7f7f',
        '#bcbd22',
        '#17becf',
    ]

    fcs = [
        '#51A9E6',
        '#FFB140',
        '#5ED25E',
        '#FF595A',
        '#C699EF',
        '#BE887D',
        '#FFA9F4',
        '#B1B1B1',
        '#EEEF54',
        '#49F0FF',
    ]

    if field == "n_scans_per_sta":
        storage = np.zeros((df.shape[0]))
        df_src_scans = df[[c for c in df.columns if c.endswith("station_scans")]].copy()
        df_src_scans.fillna(0,inplace=True)

        n = df_src_scans.shape[1]
        groupby = int(n/10)+1
        if groupby > 1:
            xx = np.arange(len(df_src_scans.columns)) // groupby
            cols = []
            for i in set(xx):
                c = df_src_scans.columns[xx == i]
                start = c[0].split("-")[0]
                end = c[-1].split("-")[0]
                if start == end:
                    cols.append("{}-station_scans".format(start))
                else:
                    cols.append("{}-{}-station_scans".format(start,end))
            df_src_scans = df_src_scans.groupby(xx, axis=1).sum()
            df_src_scans.columns = cols

        for c, ec, fc in zip(df_src_scans.columns[::-1], ecs, fcs):
            s = df_src_scans[c]
            l = "-".join(c.split("-")[:-1])
            ax.bar(x, s, label=l, bottom=storage, width=.6, ec=ec, fc=fc)
            storage += s
        undef_x = np.where((df_src_scans.sum(axis=1) == 0).values)[0]
        undef_y = df.loc[df_src_scans.sum(axis=1) == 0,"n_scans"].values
        if len(undef_x)>0:
            ax.bar(undef_x, undef_y, label='undef', width=.6, ec='#252525', fc='#969696')

        handles, labels = ax.get_legend_handles_labels()
        legend = ax.legend(reversed(handles), reversed(labels), title='stations', loc='lower left')
        legend.get_frame().set_alpha(None)
        legend.get_frame().set_facecolor((1, 1, 1, 0.45))
        ax.set_title("#scans per #stations")

    elif field == "n_scans_per_type":
        ax.bar(x, df["n_single_source_scans"], label="standard", width=.6, ec=ecs[0], fc=fcs[0])
        ax.bar(x, df["n_fillin-mode_scans"], label="fillin-mode", width=.6, hatch='//', ec=ecs[0], fc=fcs[0])
        ax.bar(x, df["n_subnetting_scans"], bottom=df["n_single_source_scans"], label="subnetting", width=.6, ec=ecs[1], fc=fcs[1])
        handles, labels = ax.get_legend_handles_labels()
        legend = ax.legend(reversed(handles), reversed(labels), title='type', loc='lower left')
        legend.get_frame().set_alpha(None)
        legend.get_frame().set_facecolor((1, 1, 1, 0.45))
        ax.set_title("#scans per type")

    elif field == "sky-coverage_37_areas_60_min":
        df_sky = df[[c for c in df.columns if c.startswith('sky-coverage_') and c.endswith("37_areas_60_min")]].copy()
        df_sky.drop("sky-coverage_average_37_areas_60_min", axis=1, inplace=True)
        sky = df_sky.mean(axis=1)
        sky_std = df_sky.std(axis=1)
        ax.bar(x, sky, yerr=sky_std, width=.6, ec='#252525', fc='#969696')
        ax.set_title("sky-coverage score 37/60 ")

    elif field == "sky-coverage_25_areas_60_min":
        df_sky = df[[c for c in df.columns if c.startswith('sky-coverage_') and c.endswith("25_areas_60_min")]].copy()
        df_sky.drop("sky-coverage_average_25_areas_60_min", axis=1, inplace=True)
        sky = df_sky.mean(axis=1)
        sky_std = df_sky.std(axis=1)
        ax.bar(x, sky, yerr=sky_std, width=.6, ec='#252525', fc='#969696')
        ax.set_title("sky-coverage score 25/60 ")

    elif field == "sky-coverage_13_areas_60_min":
        df_sky = df[[c for c in df.columns if c.startswith('sky-coverage_') and c.endswith("13_areas_60_min")]].copy()
        df_sky.drop("sky-coverage_average_13_areas_60_min", axis=1, inplace=True)
        sky = df_sky.mean(axis=1)
        sky_std = df_sky.std(axis=1)
        ax.bar(x, sky, yerr=sky_std, width=.6, ec='#252525', fc='#969696')
        ax.set_title("sky-coverage score 13/60 ")

    elif field == "sky-coverage_37_areas_30_min":
        df_sky = df[[c for c in df.columns if c.startswith('sky-coverage_') and c.endswith("37_areas_30_min")]].copy()
        df_sky.drop("sky-coverage_average_37_areas_30_min", axis=1, inplace=True)
        sky = df_sky.mean(axis=1)
        sky_std = df_sky.std(axis=1)
        ax.bar(x, sky, yerr=sky_std, width=.6, ec='#252525', fc='#969696')
        ax.set_title("sky-coverage score 37/30 ")

    elif field == "sky-coverage_25_areas_30_min":
        df_sky = df[[c for c in df.columns if c.startswith('sky-coverage_') and c.endswith("25_areas_30_min")]].copy()
        df_sky.drop("sky-coverage_average_25_areas_30_min", axis=1, inplace=True)
        sky = df_sky.mean(axis=1)
        sky_std = df_sky.std(axis=1)
        ax.bar(x, sky, yerr=sky_std, width=.6, ec='#252525', fc='#969696')
        ax.set_title("sky-coverage score 25/30 ")

    elif field == "sky-coverage_13_areas_30_min":
        df_sky = df[[c for c in df.columns if c.startswith('sky-coverage_') and c.endswith("13_areas_30_min")]].copy()
        df_sky.drop("sky-coverage_average_13_areas_30_min", axis=1, inplace=True)
        sky = df_sky.mean(axis=1)
        sky_std = df_sky.std(axis=1)
        ax.bar(x, sky, yerr=sky_std, width=.6, ec='#252525', fc='#969696')
        ax.set_title("sky-coverage score 13/30 ")

    elif field == "time":

        storage = np.zeros((df.shape[0]))
        df_obs = df[[c for c in df.columns if c.startswith('time_') and c.endswith("_observation")]].copy()
        df_obs.drop("time_average_observation", axis=1, inplace=True)
        obs = df_obs.mean(axis=1)
        std_obs = df_obs.std(axis=1)

        df_preob = df[[c for c in df.columns if c.startswith('time_') and c.endswith("_preob")]].copy()
        df_preob.drop("time_average_preob", axis=1, inplace=True)
        preob = df_preob.mean(axis=1)
        std_preob = df_preob.std(axis=1)

        df_idle = df[[c for c in df.columns if c.startswith('time_') and c.endswith("_idle")]].copy()
        df_idle.drop("time_average_idle", axis=1, inplace=True)
        idle = df_idle.mean(axis=1)
        std_idle = df_idle.std(axis=1)

        df_slew = df[[c for c in df.columns if c.startswith('time_') and c.endswith("_slew")]].copy()
        df_slew.drop("time_average_slew", axis=1, inplace=True)
        slew = df_slew.mean(axis=1)
        std_slew = df_slew.std(axis=1)

        df_field_system = df[[c for c in df.columns if c.startswith('time_') and c.endswith("_field_system")]].copy()
        df_field_system.drop("time_average_field_system", axis=1, inplace=True)
        field_system = df_field_system.mean(axis=1)
        std_field_system = df_field_system.std(axis=1)

        ax.bar(x, obs, label='obs', bottom=storage, width=.6, yerr=std_obs, ec='#1F77B4', fc='#51A9E6', error_kw=dict(ecolor='#1F77B4',capsize=3))
        storage += obs
        ax.bar(x, slew, label='slew', bottom=storage, width=.6, yerr=std_slew, ec='#FF7F0E', fc='#FFB140', error_kw=dict(ecolor='#FF7F0E',capsize=3))
        storage += slew
        ax.bar(x, preob, label='preob', bottom=storage, width=.6, yerr=std_preob, ec='#2CA02C', fc='#5ED25E', error_kw=dict(ecolor='#2CA02C',capsize=3))
        storage += preob
        ax.bar(x, field_system, label='field system', bottom=storage, width=.6, yerr=std_field_system, ec='#D62728', fc='#FF595A', error_kw=dict(ecolor='#D62728',capsize=3))
        storage += field_system
        ax.bar(x, idle, label='idle', bottom=storage, width=.6, yerr=std_idle, ec='#9467BD', fc='#C699EF', error_kw=dict(ecolor='#9467BD',capsize=3))
        storage += idle

        handles, labels = ax.get_legend_handles_labels()
        legend = ax.legend(reversed(handles), reversed(labels), loc='lower left')
        legend.get_frame().set_alpha(None)
        legend.get_frame().set_facecolor((1, 1, 1, 0.45))
        ax.set_title("spent time")
        ax.set_ylabel("[%]")


        pass
    elif field == "dUT1":
        ax.plot(x, df["sim_repeatability_dUT1_[mus]"], label="rep", marker='o')
        ax.plot(x, df["sim_mean_formal_error_dUT1_[mus]"], label="mfe", marker='o')
        ax.set_title("dUT1")
        ax.set_ylabel("$\mu$s")
        ax.legend(loc='best')

    elif field == "POL":
        ax.plot(x, df["sim_repeatability_x_pol_[muas]"], marker='^', label="X rep")
        ax.plot(x, df["sim_mean_formal_error_x_pol_[muas]"], marker='^', label="X mfe")
        ax.plot(x, df["sim_repeatability_y_pol_[muas]"], marker='v', label="Y rep", linestyle="dashed")
        ax.plot(x, df["sim_mean_formal_error_y_pol_[muas]"], marker='v', label="Y mfe", linestyle="dashed")
        ax.legend(loc='best')
        ax.set_title("POL")
        ax.set_ylabel("$\mu$as")

    elif field == "NUT":
        ax.plot(x, df["sim_repeatability_x_nut_[muas]"], marker='^', label="X rep")
        ax.plot(x, df["sim_mean_formal_error_x_nut_[muas]"], marker='^', label="X mfe")
        ax.plot(x, df["sim_repeatability_y_nut_[muas]"], marker='v', label="Y rep", linestyle="dashed")
        ax.plot(x, df["sim_mean_formal_error_y_nut_[muas]"], marker='v', label="Y mfe", linestyle="dashed")
        ax.legend(loc='best')
        ax.set_title("NUT")
        ax.set_ylabel("$\mu$as")

    elif field == "COORD":
        df_rep_sta = df[[c for c in df.columns if c.startswith('sim_repeatability_') and not c.endswith("]")]].copy()
        df_rep_sta.drop("sim_repeatability_n_sim", axis=1, inplace=True)
        rep_sta = df_rep_sta.mean(axis=1)
        rep_sta_std = df_rep_sta.std(axis=1)

        df_mfe_sta = df[[c for c in df.columns if c.startswith('sim_mean_formal_error_') and not c.endswith("]")]].copy()
        df_mfe_sta.drop("sim_mean_formal_error_n_sim", axis=1, inplace=True)
        mfe_sta = df_mfe_sta.mean(axis=1)
        mfe_sta_std = df_mfe_sta.std(axis=1)

        ax.errorbar(x, rep_sta, yerr=rep_sta_std, marker='o', label="rep")
        ax.errorbar(x, mfe_sta, yerr=mfe_sta_std, marker='o', label="mfe")
        ax.legend(loc='best')
        ax.set_title("3d sta-coordinates")
        ax.set_ylabel("mm")

    elif field == "sources_per_obs":
        n_src_obs = [c for c in df.columns if c.startswith('n_src_obs_')]
        df_src_obs = df[n_src_obs]
        maxmax = df_src_obs.max().max()
        if maxmax < 100:
            step = int(maxmax/10)+1
            bins = np.arange(1,maxmax+step,step,dtype=int).tolist()
        else:
            bins = [1, 34, 68, 101, 201, 301, 501, 701, 1301, float('inf')]
        s_obs = []
        header = []
        for s, e in zip(bins[0:-1], bins[1:]):
            s_obs.append(((df_src_obs >= s) & (df_src_obs < e)).sum(axis=1))
            if s == e-1:
                header.append(f"{s} obs")
            else:
                header.append(f"{s}-{e - 1} obs")
        df_sources_obs = pd.concat(s_obs, axis=1)
        df_sources_obs.columns = header

        ax.set_title("#sources per #obs")
        storage = np.zeros((df_sources_obs.shape[0]))
        for c, ec, fc in zip(df_sources_obs.columns[::-1], ecs, fcs):
            s = df_sources_obs[c]
            l = c[:-4]
            l = l.replace("-inf","+")
            ax.bar(x, s, label=l, bottom=storage, width=.6, ec=ec, fc=fc)
            storage += s
        handles, labels = ax.get_legend_handles_labels()
        legend = ax.legend(reversed(handles), reversed(labels), title='obs', loc='lower left')
        legend.get_frame().set_alpha(None)
        legend.get_frame().set_facecolor((1, 1, 1, 0.45))

    elif field == "sources_per_scans":
        ax.set_title("#sources per #scans")
        n_src_scans = [c for c in df.columns if c.startswith('n_src_scans_')]
        df_src = df[n_src_scans]
        maxmax = df_src.max().max()
        if maxmax < 100:
            step = int(maxmax/10)+1
            bins = np.arange(1,maxmax+step,step,dtype=int).tolist()
        else:
            bins = [1,5,10,15,20,30,40, float('inf')]

        s_scans = []
        header = []
        for s, e in zip(bins[0:-1], bins[1:]):
            s_scans.append(((df_src >= s) & (df_src < e)).sum(axis=1))
            if s == e-1:
                header.append(f"{s} obs")
            else:
                header.append(f"{s}-{e - 1} obs")
        df_src_scans = pd.concat(s_scans, axis=1)
        df_src_scans.columns = header


        storage = np.zeros((df.shape[0]))
        for c, ec, fc in zip(df_src_scans.columns[::-1], ecs, fcs):
            s = df_src_scans[c]
            l = c[:-4]
            l = l.replace("-inf","+")
            ax.bar(x, s, label=l, bottom=storage, width=.6, ec=ec, fc=fc)
            storage += s
        handles, labels = ax.get_legend_handles_labels()
        legend = ax.legend(reversed(handles), reversed(labels), title='scans', loc='lower left')
        legend.get_frame().set_alpha(None)
        legend.get_frame().set_facecolor((1, 1, 1, 0.45))


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

    if attribute_name == "duration":
        cbar_ax.set_xlabel("duration [sec]")
        vmin = min([o.duration for o in all_obs])
        vmax = max([o.duration for o in all_obs])
        for this_h in h:
            this_h.set_clim(vmin, vmax)
        cbar_ax.set_xlabel("integration time [sec]")

    elif attribute_name == "start_time":
        vmin = min([o.scan.start_time for o in all_obs])
        vmax = max([o.scan.start_time for o in all_obs])
        vmax = (vmax - vmin).total_seconds() / 3600.
        vmin = 0.0
        for this_h in h:
            this_h.set_clim(vmin, vmax)
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

if __name__ == "__main__":
    import skd_parser.skd as skd_parser
    skd = skd_parser.skdParser(r'C:/programming/q20348.skd')
    skd.parse()
    polar_plots(skd, 'C:/programming/', "duration")

    # import pandas as pd
    # df = pd.read_csv(r'C:\Users\Matthias Schartner\Desktop\Neuer Ordner\summary.txt',index_col=0)
    # df = df.tail(10)
    # summary(df, 'C:/programming/')