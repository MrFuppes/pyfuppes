# -*- coding: utf-8 -*-
r"""
Created on Thu Aug  9 09:46:55 2018

@author: F. Obersteiner, florian\obersteiner\\kit\edu
"""

from cmath import rect, phase
from math import radians, degrees
from datetime import timedelta
from copy import deepcopy

import numpy as np
import pandas as pd
from numba import njit
from scipy.interpolate import interp1d
from scipy.ndimage.filters import uniform_filter1d


###############################################################################


def mean_angle(deg):
    """
    Calculate a mean angle.
    input:
        deg - (list or array) values to average
    returns:
        mean of deg (float)
    notes:
    - if input parameter deg contains NaN or is a numpy masked array, missing
      values will be removed before the calculation.
    - result is degrees between -180 and +180
    """
    if np.ma.isMaskedArray(deg):
        deg = deg.data
    elif isinstance(deg, np.ndarray):
        deg = deg[np.isfinite(deg)]

    if len(deg) == 0:
        return np.nan
    elif len(deg) == 1:
        return deg[0]

    return degrees(phase(sum(rect(1, radians(d)) for d in deg)/len(deg)))


###############################################################################


@njit
def mean_angle_numba(deg):
    """
    - numba compatible version of mean_angle()
    - input must be numpy array of type float!
    """
    deg = deg[np.isfinite(deg)]
    if len(deg) == 0:
        return np.nan
    elif len(deg) == 1:
        return deg[0]

    result = 0
    for d in deg:
        result += rect(1, radians(d))

    return degrees(phase(result/len(deg)))


###############################################################################


def mean_day_frac(dfr, use_numba=True):
    """
    use the mean_angle function to calculate a mean day fraction (0-1).
    the conversion to angle is necessary since day changes cannot be
      calculated as arithmetic mean.
    - dfr: day fraction, 0-1
    - if input parameter dfr contains NaN or is a numpy masked array, missing
      values will be removed before the calculation.
    """
    if np.ma.isMaskedArray(dfr):
        dfr = dfr.data
    elif isinstance(dfr, np.ndarray):
        dfr = dfr[np.isfinite(dfr)]
    else:
        dfr = np.array(dfr, dtype='float64')
        dfr = dfr[np.isfinite(dfr)]

    if len(dfr) == 0:
        return np.nan
    elif len(dfr) == 1:
        return dfr[0]

    deg_mean = mean_angle_numba(dfr*360) if use_numba else mean_angle(dfr*360)

    if deg_mean < 0: # account for mean degree between -180 and +180
        deg_mean += 360

    return deg_mean/360


###############################################################################


def bin_t_10s(t,
              force_t_range=True,
              drop_empty=True):
    """
    bin a time axis to 10 s intervals around 5;
        lower boundary included, upper boundary excluded (0. <= 5. < 10.)
    input:
        t - np.ndarray (time vector, unit=second, increasing monotonically)
    returns:
        dict with binned time axis and bins, as returned by np.searchsorted()

    keywords:
        force_t_range (bool) - True enforces bins to fall within range of t
        drop_empty (bool) - False keeps empty bins alive
    """
    if not isinstance(t, np.ndarray):
        raise TypeError('Please pass np.ndarray to function.')

    if t.ndim != 1:
        raise TypeError('Please pass 1D array to function.')

    from pyfuppes.monotonicity import strict_inc_np
    if not strict_inc_np(t):
        raise ValueError('Input must be strictly increasing.')

    tmin, tmax = np.floor(t[0]), np.floor(t[-1])
    t_binned = np.arange((tmin-tmin%10)+5, (tmax-tmax%10)+6, 10)

    # if all values of t should fall WITHIN the range of t_binned:
    vmask = None
    if force_t_range:
        if t_binned[0] < t[0]:
            t_binned = t_binned[1:]
        if t_binned[-1] > t[-1]:
            t_binned = t_binned[:-1]
        # check if values should be masked, e.g. if an element in t does not
        # fall into the bins
        vmask = ((t < t_binned[0]-5) | (t >= t_binned[-1]+5))
        t = t[~vmask]

    bins = np.searchsorted(t_binned-5, t, side='right')

    # if empty bins should be created, mask all bins that would have no
    # corresponding value in the dependent variable's data
    bmask = None
    if drop_empty:
        t_binned = t_binned[np.bincount(bins-1).astype(np.bool_)]
    else:
        bmask = np.ones(t_binned.shape).astype(np.bool_)
        bmask[bins-1] = False

    return {'t_binned': t_binned, 'bins': bins,
            'masked_bins': bmask, 'masked_vals': vmask}


###############################################################################


@njit
def get_npnanmean(v):
    return np.nanmean(v)

def bin_y_of_t(v, bin_info,
                  vmiss=np.nan,
                  return_type='arit_mean',
                  use_numba=True):
    """
    use the output of function "bin_time" or "bin_time_10s" to bin
        a variable 'v' that depends on a variable t.
    input:
        v - np.ndarray to be binned
        bin_info - config dict returned by bin_time() or bin_time_10s()
    returns:
        v binned according to parameters in bin_info
    keywords:
        vmiss (numeric) - missing value identifier, defaults to np.NaN
        return_type (str) - how to bin, defaults to 'arit_mean'
        use_numba (bool) - use njit'ed binning functions or not
    """
    if not isinstance(v, np.ndarray):
        raise TypeError('Please pass np.ndarray to function.')

    if not any([v.dtype == np.dtype(t) for t in ('int16', 'int32', 'int64',
                                                 'float16', 'float32', 'float64')]):
        raise TypeError('Please pass valid dtype, int or float.')

    # make a deep copy so that v is not modified on the way
    _v = deepcopy(v)

    # change dtype to float so we can use NaN
    if any([_v.dtype == np.dtype(t) for t in ('int16', 'int32', 'int64')]):
        _v = _v.astype(np.float)

    _v[_v==vmiss] = np.nan

    # remove values that were masked (out of bin range)
    _v = _v[~bin_info['masked_vals']]

    v_binned = []
    vd_bins = bin_info['bins']

    if return_type == 'arit_mean':
        if use_numba:
            v_binned = [get_npnanmean(_v[vd_bins == bin_no]) for bin_no in np.unique(vd_bins)]
        else:
            v_binned = [np.nanmean(_v[vd_bins == bin_no]) for bin_no in np.unique(vd_bins)]
    elif return_type == 'mean_day_frac':
        if use_numba:
            v_binned = [mean_day_frac(_v[vd_bins == bin_no]) for bin_no in np.unique(vd_bins)]
        else:
            v_binned = [mean_day_frac(_v[vd_bins == bin_no], use_numba=False) for bin_no in np.unique(vd_bins)]
    elif return_type == 'mean_angle':
        if use_numba:
            v_binned = [mean_angle_numba(_v[vd_bins == bin_no]) for bin_no in np.unique(vd_bins)]
        else:
            v_binned = [mean_angle(_v[vd_bins == bin_no]) for bin_no in np.unique(vd_bins)]

    result = np.array(v_binned)

    # check if there are masked bins, i.e. empty bins. add them to the output if so.
    if bin_info['masked_bins'] is not None:
        tmp = np.ones(bin_info['masked_bins'].shape)
        tmp[bin_info['masked_bins']] = vmiss
        tmp[~bin_info['masked_bins']] = result
        result = tmp

    # round to integers if input type was integer
    if any([v.dtype == np.dtype(t) for t in ('int16', 'int32', 'int64')]):
        result =  np.rint(result).astype(v.dtype)

    return result


###############################################################################


def bin_by_pdresample(t, v,
                      rule='10S',
                      offset=timedelta(seconds=5),
                      force_t_range=True,
                      drop_empty=True):
    """
    use pandas DataFrame method "resample" for binning along a time axis.

    Parameters
    ----------
    t : 1d array of float or int
        time axis / independent variable.
    v : 1d or 2d array corresponding to t
        dependent variable(s).
    rule : string, optional
        rule for resample method. The default is '10S'.
    offset : datetime.timedelta, optional
        offset to apply to the starting value.
        The default is timedelta(seconds=5).
    force_t_range : boolean, optional
        truncate new time axis to min/max of t. The default is True.
    drop_empty : boolean, optional
        drop empty bins that otherwise hold NaN. The default is True.

    Returns
    -------
    df1 : pandas DataFrame
        data binned (arithmetic mean) to resampled time axis.

    """

    if isinstance(v, list):
        d = {f"v_{i}": y for i, y in enumerate(v)}
    else:
        d = {'v_0': v}

    df = pd.DataFrame(d, index=pd.to_datetime(t*1e9))
    df1 = df.resample(rule, loffset=offset).mean()
    df1['t_binned'] = df1.index.astype(np.int64) // 10**9

    if force_t_range:
        if df1['t_binned'].iloc[0] < t[0]:
            df1 = df1.drop(df1.index[0])
        if df1['t_binned'].iloc[-1] > t[-1]:
            df1 = df1.drop(df1.index[-1])

    df1 = df1.drop(columns=['t_binned']).set_index(df1['t_binned'])

    if drop_empty:
        df1 = df1.dropna(how='all')

    return df1


###############################################################################


def bin_by_npreduceat(v: np.ndarray, nbins: int,
                      ignore_nan=True):
    """
    1D binning with numpy.add.reduceat.
    ignores NaN or INF by default (finite elements only).
    if ignore_nan is set to False, the whole bin will be NaN if 1 or more NaNs
        fall within the bin.
    on SO:
        https://stackoverflow.com/questions/57160558/how-to-handle-nans-in-binning-with-numpy-add-reduceat
    """
    if not isinstance(v, np.ndarray):
        v = np.array(v)

    bins = np.linspace(0, v.size, nbins+1, True).astype(np.int)

    if ignore_nan:
        mask = np.isfinite(v)
        vn = np.where(~mask, 0, v)
        with np.errstate(invalid='ignore'):
            out = np.add.reduceat(vn, bins[:-1])/np.add.reduceat(mask, bins[:-1])
    else:
        out = np.add.reduceat(v, bins[:-1])/np.diff(bins)

    return out


###############################################################################


def moving_avg(v, N):
    """
    simple moving average.

    Parameters
    ----------
    v : list
        data ta to average
    N : integer
        number of samples per average.

    Returns
    -------
    m_avg : list
        averaged data.

    """
    s, m_avg = [0], []
    for i, x in enumerate(v, 1):
        s.append(s[i-1] + x)
        if i >= N:
            avg = (s[i] - s[i-N])/N
            m_avg.append(avg)
    return m_avg


###############################################################################


def np_mvg_avg(v, N, ip_ovr_nan=False, mode='same', edges='expand'):
    """
    moving average based on numpy convolution function.

    Parameters
    ----------
    v : 1d array
        data to average.
    N : integer
        number of samples per average.
    ip_ovr_nan : boolean, optional
        interpolate linearly using finite elements of v. The default is False.
    mode : string, optional
        config for np.convolve. The default is 'same'.
    edges : string, optional
        config for output. The default is 'expand'.
            in case of mode='same', convolution gives false results
            ("running-in effect") at edges. account for this by
            simply expanding the Nth value to the edges.

    Returns
    -------
    m_avg : 1d array
        averaged data.
    """
    N = int(N)

    if ip_ovr_nan:
        x = np.linspace(0, len(v)-1, num=len(v))
        fip = interp1d(x[np.isfinite(v)], v[np.isfinite(v)], kind='linear',
                       bounds_error=False, fill_value='extrapolate')
        v = fip(x)

    m_avg = np.convolve(v, np.ones((N,))/N, mode=mode)

    if edges=='expand':
        m_avg[:N-1], m_avg[-N-1:] = m_avg[N], m_avg[-N]

    return m_avg


###############################################################################


def pd_mvg_avg(v, N, ip_ovr_nan=False, min_periods=1):
    """
    moving average based on pandas dataframe rolling function.

    Parameters
    ----------
    v : 1d array
        data to average.
    N : integer
        number of samples per average.
    ip_ovr_nan : boolean, optional
        interpolate linearly using finite elements of v. The default is False.
    min_periods : TYPE, optional
        minimum number of values in averaging window. The default is 1.

    Returns
    -------
    1d array
        averaged data.

    NOTE: automatically skips NaN (forms averages over windows with <N),
          unless minimum number of values in window is exceeded.
    """
    N, min_periods = int(N), int(min_periods)

    min_periods = 1 if min_periods < 1 else min_periods

    df = pd.DataFrame({ 'v' : v })
    df['rollmean'] = df['v'].rolling(int(N), center=True,
                                     min_periods=min_periods).mean()
    if ip_ovr_nan:
        df['ip']  = df['rollmean'].interpolate()
        return df['ip'].values

    return df['rollmean'].values


###############################################################################


def sp_mvg_avg(v, N, edges='nearest'):
    """
    Use scipy's uniform_filter1d to calculate a moving average, see the docs at
    https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.uniform_filter1d.html
    Handles NaNs by removing them before interpolation.

    Parameters
    ----------
    v : np.ndarray
        data to average.
    N : int
        number of samples per average.
    edges : str, optional
        mode of uniform_filter1d (see docs). The default is 'nearest'.

    Returns
    -------
    avg : np.ndarray
        averaged data.

    """
    m = np.isfinite(v)
    avg = np.empty(v.shape)
    avg[~m] = np.nan
    avg[m] = uniform_filter1d(v[m], size=N, mode=edges)
    return avg


###############################################################################


def map_dependent(xref, xcmp, vcmp, vmiss=np.nan):
    """
    Map a variable "vcmp" depending on variable "xcmp" to an independent
        variable "xref".

    Parameters
    ----------
    xref : np.ndarray, 1D
        reference / independent variable.
    xcmp : np.ndarray, 1D
        independent variable of vcmp.
    vcmp : np.ndarray, 1D
        dependent variable of xcmp.
    vmiss : int or float
        what should be inserted to specify missing values.
    Returns
    -------
    vmap : np.ndarray, 1D
        vcmp mapped to xref.

    """
    # which element of xref has a corresponding element in xcmp?
    m = np.in1d(xref, xcmp)

    # prepare output
    vmap = np.empty(xref.shape, dtype=vcmp.dtype)
    # insert VMISS where xref has NO corresponding element
    vmap[~m] = vmiss

    # where corresponding elements exist, insert those from vcmp
    vmap[m] = np.take(vcmp, np.nonzero(np.in1d(xcmp, xref)))[0]

    return vmap


###############################################################################
