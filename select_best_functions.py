from pathlib import Path
import numpy as np
import pandas as pd

import Helper


def select_best_intensives(df, **kwargs):
    """
    logic to select best schedule for intensive sessions

    :param df: DataFrame of statistics.csv file
    :return: version number of best schedule
    """

    if df.shape[0] == 1:
        return df.index[0]

    nobs = df["n_observations"]
    sky_cov = df["sky-coverage_average_37_areas_60_min"]
    dut1_mfe = df["sim_mean_formal_error_dUT1_[mus]"]
    dut1_rep = df["sim_repeatability_dUT1_[mus]"]
    # data = pd.concat([nobs, sky_cov, dut1_mfe, dut1_rep], axis=1)

    s_nobs = Helper.scale(nobs, minIsGood=False)
    s_sky_cov = Helper.scale(sky_cov, minIsGood=False)
    s_dut1_mfe = Helper.scale(dut1_mfe)
    s_dut1_rep = Helper.scale(dut1_rep)
    # scores = pd.concat([s_nobs, s_sky_cov, s_dut1_mfe, s_dut1_rep], axis=1)

    score = 1 * s_nobs + .25 * s_sky_cov + .8 * s_dut1_mfe + .8 * s_dut1_rep
    best = score.idxmax()
    return best


def select_best_ohg(df):
    """
    logic to select best schedule for OHG sessions

    :param df: DataFrame of statistics.csv file
    :return: version number of best schedule
    """

    if df.shape[0] == 1:
        return df.index[0]

    nobs = df["n_observations"]
    sky_cov = df["sky-coverage_average_25_areas_60_min"]
    avg_rep = df["sim_repeatability_average_3d_coordinates_[mm]"]
    ohg_rep = df["sim_repeatability_OHIGGINS"]
    avg_mfe = df["sim_mean_formal_error_average_3d_coordinates_[mm]"]
    ohg_mfe = df["sim_mean_formal_error_OHIGGINS"]
    # data = pd.concat([nobs, sky_cov, avg_rep, ohg_rep, avg_mfe, ohg_mfe], axis=1)

    s_nobs = Helper.scale(nobs, minIsGood=False)
    s_sky_cov = Helper.scale(sky_cov, minIsGood=False)
    s_rep_avg_sta = Helper.scale(avg_rep)
    s_rep_ohg = Helper.scale(ohg_rep)
    s_mfe_avg_sta = Helper.scale(avg_mfe)
    s_mfe_ohg = Helper.scale(ohg_mfe)
    # scores = pd.concat([s_nobs, s_sky_cov, s_rep_avg_sta, s_rep_ohg, s_mfe_avg_sta, s_mfe_ohg], axis=1)

    score = 1 * s_nobs + .25 * s_sky_cov + 1.5 * s_rep_ohg + 1 * s_mfe_ohg + .75 * s_rep_avg_sta + .5 * s_mfe_avg_sta
    best = score.idxmax()
    return best


def select_best_24h(df, **kwargs):
    """
    logic to select best schedule for OHG sessions

    :param df: DataFrame of statistics.csv file
    :return: version number of best schedule
    """

    if df.shape[0] == 1:
        return df.index[0]

    mfe = 0.3
    rep = 0.7
    nobs = df["n_observations"]
    # sky_cov = df["sky-coverage_average_25_areas_60_min"]

    avg_rep = df["sim_repeatability_average_3d_coordinates_[mm]"]
    avg_mfe = df["sim_mean_formal_error_average_3d_coordinates_[mm]"]

    dut1_rep = df["sim_repeatability_dUT1_[mus]"]
    dut1_mfe = df["sim_mean_formal_error_dUT1_[mus]"]
    xpo_rep = df["sim_repeatability_x_pol_[muas]"]
    xpo_mfe = df["sim_mean_formal_error_x_pol_[muas]"]
    ypo_rep = df["sim_repeatability_y_pol_[muas]"]
    ypo_mfe = df["sim_mean_formal_error_y_pol_[muas]"]
    nutx_rep = df["sim_repeatability_x_nut_[muas]"]
    nutx_mfe = df["sim_mean_formal_error_x_nut_[muas]"]
    nuty_rep = df["sim_repeatability_y_pol_[muas]"]
    nuty_mfe = df["sim_mean_formal_error_y_pol_[muas]"]

    # data = pd.concat([nobs, sky_cov, avg_rep, ohg_rep, avg_mfe, ohg_mfe], axis=1)

    s_nobs = Helper.scale(nobs, minIsGood=False)
    # s_sky_cov = Helper.scale(sky_cov, minIsGood=False)
    s_rep_avg_sta = Helper.scale(avg_rep)
    s_mfe_avg_sta = Helper.scale(avg_mfe)

    s_dut1_rep = Helper.scale(dut1_rep)
    s_dut1_mfe = Helper.scale(dut1_mfe)
    s_xpo_rep = Helper.scale(xpo_rep)
    s_xpo_mfe = Helper.scale(xpo_mfe)
    s_ypo_rep = Helper.scale(ypo_rep)
    s_ypo_mfe = Helper.scale(ypo_mfe)
    s_nutx_rep = Helper.scale(nutx_rep)
    s_nutx_mfe = Helper.scale(nutx_mfe)
    s_nuty_rep = Helper.scale(nuty_rep)
    s_nuty_mfe = Helper.scale(nuty_mfe)
    # scores = pd.concat([s_nobs, s_sky_cov, s_rep_avg_sta, s_rep_ohg, s_mfe_avg_sta, s_mfe_ohg], axis=1)

    score = 1 * s_nobs + \
            rep * 1 * s_rep_avg_sta + \
            mfe * 1 * s_mfe_avg_sta + \
            rep * 0.2 * s_dut1_rep + \
            mfe * 0.2 * s_dut1_mfe + \
            rep * 0.2 * s_xpo_rep + \
            mfe * 0.2 * s_xpo_mfe + \
            rep * 0.2 * s_ypo_rep + \
            mfe * 0.2 * s_ypo_mfe + \
            rep * 0.2 * s_nutx_rep + \
            mfe * 0.2 * s_nutx_mfe + \
            rep * 0.2 * s_nuty_rep + \
            mfe * 0.2 * s_nuty_mfe
    best = score.idxmax()
    return best


def select_best_24h_focus_EOP(df, **kwargs):
    """
    logic to select best schedule for OHG sessions

    :param df: DataFrame of statistics.csv file
    :return: version number of best schedule
    """

    if df.shape[0] == 1:
        return df.index[0]

    mfe = 0.3
    rep = 0.7
    nobs = df["n_observations"]
    # sky_cov = df["sky-coverage_average_25_areas_60_min"]

    avg_rep = df["sim_repeatability_average_3d_coordinates_[mm]"]
    avg_mfe = df["sim_mean_formal_error_average_3d_coordinates_[mm]"]

    dut1_rep = df["sim_repeatability_dUT1_[mus]"]
    dut1_mfe = df["sim_mean_formal_error_dUT1_[mus]"]
    xpo_rep = df["sim_repeatability_x_pol_[muas]"]
    xpo_mfe = df["sim_mean_formal_error_x_pol_[muas]"]
    ypo_rep = df["sim_repeatability_y_pol_[muas]"]
    ypo_mfe = df["sim_mean_formal_error_y_pol_[muas]"]
    nutx_rep = df["sim_repeatability_x_nut_[muas]"]
    nutx_mfe = df["sim_mean_formal_error_x_nut_[muas]"]
    nuty_rep = df["sim_repeatability_y_pol_[muas]"]
    nuty_mfe = df["sim_mean_formal_error_y_pol_[muas]"]

    # data = pd.concat([nobs, sky_cov, avg_rep, ohg_rep, avg_mfe, ohg_mfe], axis=1)

    s_nobs = Helper.scale(nobs, minIsGood=False)
    # s_sky_cov = Helper.scale(sky_cov, minIsGood=False)
    s_rep_avg_sta = Helper.scale(avg_rep)
    s_mfe_avg_sta = Helper.scale(avg_mfe)

    s_dut1_rep = Helper.scale(dut1_rep)
    s_dut1_mfe = Helper.scale(dut1_mfe)
    s_xpo_rep = Helper.scale(xpo_rep)
    s_xpo_mfe = Helper.scale(xpo_mfe)
    s_ypo_rep = Helper.scale(ypo_rep)
    s_ypo_mfe = Helper.scale(ypo_mfe)
    s_nutx_rep = Helper.scale(nutx_rep)
    s_nutx_mfe = Helper.scale(nutx_mfe)
    s_nuty_rep = Helper.scale(nuty_rep)
    s_nuty_mfe = Helper.scale(nuty_mfe)
    # scores = pd.concat([s_nobs, s_sky_cov, s_rep_avg_sta, s_rep_ohg, s_mfe_avg_sta, s_mfe_ohg], axis=1)

    score = 0.75 * s_nobs + \
            rep * 0.5 * s_rep_avg_sta + \
            mfe * 0.5 * s_mfe_avg_sta + \
            rep * 0.3 * s_dut1_rep + \
            mfe * 0.3 * s_dut1_mfe + \
            rep * 0.1 * s_xpo_rep + \
            mfe * 0.1 * s_xpo_mfe + \
            rep * 0.1 * s_ypo_rep + \
            mfe * 0.1 * s_ypo_mfe + \
            rep * 0.3 * s_nutx_rep + \
            mfe * 0.3 * s_nutx_mfe + \
            rep * 0.3 * s_nuty_rep + \
            mfe * 0.3 * s_nuty_mfe
    best = score.idxmax()
    return best


def select_best_CRF(df, **kwargs):
    if df.shape[0] == 1:
        return df.index[0]

    template_path = kwargs["template_path"]
    target = Helper.read_sources(Path(template_path) / "source.cat.target")[0]
    calib = Helper.read_sources(Path(template_path) / "source.cat.calib")[0]

    df_src = df.filter(like='n_src_scans_', axis=1)

    targets = [c for c in df.columns if c[12:] in target]
    df_target = df_src.loc[:, df_src.columns.isin(targets)]
    df_target = df_target > 4

    calibs = [c for c in df.columns if c[12:] in calib]
    df_calib = df_src.loc[:, df_src.columns.isin(calibs)]
    df_calib = df_calib > 4

    target_source_good = df_target.sum(axis=1)
    calib_source_good = df_calib.sum(axis=1)
    source_good = target_source_good + calib_source_good

    fraction = abs(target_source_good / calib_source_good)
    fraction = fraction.replace([np.inf, -np.inf], np.nan)
    fraction = fraction.replace(np.nan, fraction.max())

    nobs = df["n_observations"]
    obs_time = df["time_average_observation"]
    idle_time = df["time_average_idle"]

    s_source_good = Helper.scale(source_good, minIsGood=False)
    s_nobs = Helper.scale(nobs, minIsGood=False)
    s_obs_time = Helper.scale(obs_time, minIsGood=False)
    s_idle_time = Helper.scale(idle_time)

    # scale fraction between target and calibrator scans. Target fraction is 4
    s_fraction = pd.Series(data=0, index=fraction.index)
    s_fraction[abs(fraction - 4) < 1.5] = 1
    s_fraction[abs(fraction - 4) < .75] = 2

    score = 0.5 * s_nobs + \
            2 * s_source_good + \
            s_fraction + \
            0.2 * s_obs_time + \
            0.2 * s_idle_time

    best = score.idxmax()

    return best
