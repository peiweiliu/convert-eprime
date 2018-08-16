# emacs: -*- mode: python-mode; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 et:
"""
Three functions for converting data generated by E-Prime experiment to more
useable csv format.
1.  etext_to_rcsv: Converts exported 'E-Prime text' file to reduced csv based
    on desired column headers. Make sure, when exporting the edat file as
    'E-Prime text', that Unicode is turned off.
2.  text_to_csv: Converts text file produced by successful completion of
    E-Prime experiment to csv. Output from text_to_csv can be used to deduce
    information necessary for text_to_rcsv (e.g. columns to merge, columns to
    rename, etc.). These variables would then be saved in the task-specific json
    file.
3.  text_to_rcsv: Converts text file produced by successful completion of
    E-Prime experiment to reduced csv, using information from the variables
    contained in headers.pickle. The output from this should be
    indistinguishable from the output of etext_to_rcsv, only without the tedious
    step of exporting the 'E-Prime text' file by hand.

command line usage: python convert_eprime.py [function_name] [inputs]
"""
from __future__ import print_function
from builtins import range
import os
import sys
import json
import inspect
from collections import OrderedDict

import numpy as np
import pandas as pd

from .utils import remove_unicode


def etext_to_rcsv(in_file, param_file, out_file=None):
    """
    Reads exported 'E-Prime text' file, reduces columns based on tasks-specific
    list of headers, and writes out reduced csv.

    Converts exported 'E-Prime text' file to reduced csv based on desired column
    headers. Make sure, when exporting the edat file as 'E-Prime text', that
    Unicode is turned off.

    Parameters
    ----------
    in_file : str
        Exported E-Prime text file to convert and reduce.

    param_file : str
        A json file with relevant task-specific parameters.

    out_file : str
        Name of output file (csv format) to generate. If not set, then a file
        will be written out with the same name as the input file, but with a csv
        suffix instead of txt.

    Examples
    ----------
    >>> from convert_eprime.convert import etext_to_rcsv
    >>> etext_file = 'subj0001_stop_signal_task-0.txt'
    >>> param_file = '../config_files/nac_stopsignal.json'
    >>> etext_to_rcsv(etext_file, param_file)  # doctest: +ALLOW_UNICODE
    'Output file successfully created- subj0001_stop_signal_task-0.csv'

    """
    with open(param_file, 'r') as file_object:
        param_dict = json.load(file_object)

    filename, suffix = os.path.splitext(in_file)
    if suffix == '.txt':
        # Remove first three lines of exported E-Prime tab-delimited text file.
        rem_lines = list(range(3))
        delimiter_ = '\t'
    elif suffix == '.csv':
        # Remove no lines of comma-delimited csv file.
        rem_lines = []
        delimiter_ = ','
    else:
        raise Exception('File not txt or csv: {0}'.format(in_file))

    df = pd.read_csv(in_file, skiprows=rem_lines, sep=delimiter_)

    header_list = param_dict.get('headers')
    df = df[header_list]

    if param_dict['rem_nulls']:
        df = df.dropna(axis=0, how='all')

    if out_file is None:
        out_file = filename + '.csv'

    df.to_csv(out_file, index=False)
    print('Output file successfully created- {0}'.format(out_file))


def text_to_csv(text_file, out_file):
    """
    Converts text file produced by successful completion of E-Prime experiment
    to csv. Output from text_to_csv can be used to determine information
    necessary for text_to_rcsv (e.g. columns to merge, columns to rename,
    etc.).

    Parameters
    ----------
    text_file : str
        Raw E-Prime text file to convert.

    out_file : str
        Name of output file (csv format) to generate.

    Examples
    ----------
    >>> from convert_eprime.convert import text_to_csv
    >>> in_file = 'subj0001_stop_signal_task-0.txt'
    >>> out_file = 'subj0001_0.csv'
    >>> text_to_csv(in_file, out_file)  # doctest: +ALLOW_UNICODE
    'Output file successfully created- subj0001_0.csv'

    """
    df = _text_to_df(text_file)

    df.to_csv(out_file, index=False)
    print('Output file successfully created- {0}'.format(out_file))


def text_to_rcsv(text_file, edat_file, param_file, out_file):
    """
    Converts text file produced by successful completion of E-Prime experiment
    to reduced csv. Considerably more complex than text_to_csv.

    Parameters
    ----------
    text_file : str
        Raw E-Prime text file to convert.

    edat_file : str
        Raw E-Prime edat file paired with text_file. Only used for its file
        type, because sometimes files will differ between version of E-Prime
        (edat vs. edat2 suffix).

    param_file : str
        A json file with relevant task-specific parameters.

    out_file : str
        Name of output file (csv format) to generate.

    Examples
    ----------
    >>> from convert_eprime.convert import text_to_rcsv
    >>> in_file = 'subj0001_stop_signal_task-0.txt'
    >>> edat_file = 'subj0001_stop_signal_task-0.edat2'
    >>> out_file = 'subj0001_0.csv'
    >>> param_file = '../config_files/nac_stopsignal.json'
    >>> text_to_rcsv(in_file, edat_file, out_file, param_file)  # doctest: +ALLOW_UNICODE
    'Output file successfully created- subj0001_0.csv'

    """
    with open(param_file, 'r') as file_object:
        param_dict = json.load(file_object)

    df = _text_to_df(text_file)

    # Rename columns
    _, edat_suffix = os.path.splitext(edat_file)
    replace_dict = param_dict.get('replace_dict')
    if replace_dict:
        replacements = replace_dict.get(edat_suffix)
        df = df.rename(columns=replacements)

    # Merge columns
    merge_cols = param_dict.get('merge_cols')
    for col in list(merge_cols.keys()):
        df[col] = df[merge_cols[col]].fillna('').sum(axis=1)

    # Drop NaNs based on specific columns
    if param_dict.get('rem_nulls', False):
        df = df.dropna(subset=param_dict.get('null_cols'), how='all')

    # Reduce DataFrame to desired columns
    header_list = param_dict.get('headers')
    df = df[header_list]

    # Write out reduced csv
    df.to_csv(out_file, index=False)
    print('Output file successfully created- {0}'.format(out_file))


def _text_to_df(text_file):
    """
    Convert a raw E-Prime output text file into a pandas DataFrame.
    """
    # Load the text file as a list.
    with open(text_file, 'rb') as fo:
        text_data = list(fo)

    # Remove unicode characters.
    filtered_data = [remove_unicode(row.decode('utf-8', 'ignore')) for row in text_data]

    # Determine where rows begin and end.
    start_index = [i for i, row in enumerate(filtered_data) if row == '*** LogFrame Start ***']
    end_index = [i for i, row in enumerate(filtered_data) if row == '*** LogFrame End ***']
    if len(start_index) != len(end_index) or start_index[0] >= end_index[0]:
        print('Warning: LogFrame Starts and Ends do not match up.')
    n_rows = min(len(start_index), len(end_index))

    # Find column headers and remove duplicates.
    headers = []
    data_by_rows = []
    for i in range(n_rows):
        one_row = filtered_data[start_index[i]+1:end_index[i]]
        data_by_rows.append(one_row)
        for col_val in one_row:
            split_header_idx = col_val.index(':')
            headers.append(col_val[:split_header_idx])

    headers = list(OrderedDict.fromkeys(headers))

    # Preallocate list of lists composed of NULLs.
    data_matrix = np.empty((n_rows, len(headers)), dtype=object)
    data_matrix[:] = np.nan

    # Fill list of lists with relevant data from data_by_rows and headers.
    for i in range(n_rows):
        for cell_data in data_by_rows[i]:
            split_header_idx = cell_data.index(':')
            for k_header, header in enumerate(headers):
                if cell_data[:split_header_idx] == header:
                    data_matrix[i, k_header] = cell_data[split_header_idx+1:].lstrip()

    df = pd.DataFrame(columns=headers, data=data_matrix)

    # Columns with one value at the beginning, the end, or end - 1 should be
    # filled with that value.
    for col in df.columns:
        non_nan_idx = np.where(df[col].values == df[col].values)[0]
        if len(non_nan_idx) == 1 and non_nan_idx[0] in [0, df.shape[0]-1,
                                                        df.shape[0]-2]:
            df.loc[:, col] = df.loc[non_nan_idx[0], col]
    return df


if __name__ == '__main__':
    """
    If called from the command line, the desired function should be the first
    argument.
    """
    function_name = sys.argv[1]
    MODULE_FUNCTIONS = [name for name, obj in inspect.getmembers(sys.modules[__name__])
                        if inspect.isfunction(obj) and not name.startswith('_')]

    if function_name not in MODULE_FUNCTIONS:
        raise IOError('Function {0} not in convert_eprime.'.format(function_name))

    function = globals()[function_name]
    n_args = len(inspect.getargspec(function).args)

    if n_args != len(sys.argv) - 2:
        raise IOError('Function {0} takes {1} args, not {2}.'.format(function_name,
                                                                     n_args, len(sys.argv)-2))

    function(*sys.argv[2:])
