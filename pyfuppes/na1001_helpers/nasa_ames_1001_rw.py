# -*- coding: utf-8 -*-
r"""
Created on Mon Feb 12 09:32:32 2018

@author: F. Obersteiner, florian\obersteiner\\kit\edu

more info on NASA AMES file format:
    https://espoarchive.nasa.gov/content/Ames_Format_Specification_v20
"""
import os
from datetime import date
from pathlib import Path

# from pyfuppes.misc import checkbytes_lt128


###############################################################################


def na1001_cls_read(file_path, sep=" ", sep_com=";", sep_data="\t",
                    auto_nncoml=True,
                    strip_lines=True,
                    remove_doubleseps=False,
                    vscale_vmiss_vertical=False,
                    vmiss_to_None=False,
                    ensure_ascii=True):
    """
    read NASA AMES 1001 formatted text file. expected encoding is ASCII.
    args:
        file_path: path to file
    kwargs:
        sep=" ": general string separator, e.g. space
        sep_com=";": string separator used exclusively in comment block
        sep_data="\t": string separator used exclusively in data block
        auto_nncoml=True: automatically determine number of lines in normal
                          comment block
        strip_lines=True: remove whitespaces from all file lines
        remove_doubleseps=False: remove repeated occurrences of general
                                 separator
        vscale_vmiss_vertical=False: set to True if VSCALE and VMISS parameters
                                     are arranged vertically over multiple
                                     lines (1 entry per line) instead of in one
                                     line each (e.g. for DLR Bahamas files)
        vmiss_to_None: set True if missing values should be replaced with None.
        ensure_ascii: set True to allow only ASCII encoding (default).

    returns:
        na_1001: dictionary with keys according to na1001 class.
    """
    try:
        file_path.is_file()
    except AttributeError: # file path is not provided as path object; convert
        file_path = Path(file_path)

    if not os.path.isfile(file_path): # check if file exists
        raise FileExistsError(str(file_path) + "\n    does not exist.")
    else:
        # by definition, nasa ames 1001 is pure ascii. the following lines allow
        # to read files with other encodings; use with caution
        encodings = ('ascii',) if ensure_ascii else ('ascii', 'utf-8', 'cp1252', 'latin-1')
        data = None
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as file_obj:
                    data = file_obj.readlines() # read file content to string list
            except ValueError: # invalid encoding, try next
                pass
            else:
                if enc != 'ascii':
                    print(f"warning: using non-ascii encoding {enc} for file {file_path.name}")
                break # found a working encoding
        if not data:
            raise ValueError(f"could not decode {file_path.name} (ASCII-only: {ensure_ascii}")
        # done with encoding


        if strip_lines:
            for i, line in enumerate(data):
                data[i] = line.strip()

        if remove_doubleseps:
            for i, line in enumerate(data):
                while sep+sep in line:
                    line = line.replace(sep+sep, sep)
                data[i] = line

        na_1001 = {'SRC': str(file_path)}

        tmp = list(map(int, data[0].split()))
        assert len(tmp) == 2, f"invalid format in {data[0]} (line 1)"
        assert tmp[1] == 1001, f"invalid FFI in {data[0]} (line 1)"

        nlhead = tmp[0]
        na_1001['NLHEAD'] = nlhead
        na_1001['_FFI'] = tmp[1]

        header = data[0:nlhead]
        data = data[nlhead:]

        # test case: no data ->
        assert data, "no data found."

        na_1001['ONAME'] = header[1]
        na_1001['ORG'] = header[2]
        na_1001['SNAME'] = header[3]
        na_1001['MNAME'] = header[4]

        tmp = list(map(int, header[5].split()))
        assert len(tmp) == 2, f"invalid format {header[5]} (line 6)"
        na_1001['IVOL'], na_1001['NVOL'] = tmp[0], tmp[1]

        tmp = list(map(int, header[6].split()))
        assert len(tmp) == 6, f"invalid format {header[6]} (line 7)"
        # check for valid date in line 7 (yyyy mm dd)
        date(*tmp[:3]), date(*tmp[3:6])
        na_1001['DATE'], na_1001['RDATE'] = tmp[:3], tmp[3:6]

        # DX check if the line contains a decimal separator; if so use float else int
        na_1001['DX'] = float(header[7]) if '.' in header[7] else int(header[7])
        na_1001['XNAME'] = header[8].rsplit(sep=sep_com)
        # CARIBIC: [0] is type, [1] is description, [2] is unit.

        n_vars = int(header[9])
        na_1001['NV'] = n_vars

        if vscale_vmiss_vertical:
            offset = n_vars*2
            na_1001['VSCAL'] = header[10:10+n_vars]
            na_1001['VMISS'] = header[10+n_vars:10+n_vars*2]
        else:
            offset = 2
            na_1001['VSCAL'] = header[10].split()
            na_1001['VMISS'] = header[11].split()
        # test case:
        msg = "vscal, vmiss and vname must have equal number of elements"
        assert n_vars == len(na_1001['VSCAL']) == len(na_1001['VMISS']), msg

        na_1001['_VNAME'] = header[10+offset:10+n_vars+offset]

        nscoml = int(header[10+n_vars+offset])
        na_1001['NSCOML'] = nscoml
        if nscoml > 0: # read special comment if nscoml>0
            na_1001['_SCOM'] = header[n_vars+11+offset:n_vars+nscoml+11+offset]
        else:
            na_1001['_SCOM'] = ""
        # test case:
        msg = "nscoml not equal n elements in list na_1001['_SCOM']"
        assert nscoml == len(na_1001['_SCOM']), msg

        # read normal comment if nncoml>0
        if auto_nncoml is True:
            nncoml = nlhead-(n_vars+nscoml+12+offset)
        else:
            nncoml = int(header[n_vars+nscoml+11+offset])
        na_1001['NNCOML'] = nncoml

        if nncoml > 0:
            na_1001['_NCOM'] = header[n_vars+nscoml+12+offset:n_vars+nscoml+nncoml+12+offset]
        else:
            na_1001['_NCOM'] = ""
        # test case:
        msg = "nncoml not equal n elements in list na_1001['_NCOM']"
        assert nncoml == len(na_1001['_NCOM']), msg
        # test case
        msg = "nlhead must be equal to nncoml + nscoml + n_vars + 14"
        assert nncoml+nscoml+n_vars+14 == nlhead, msg

        # done with header, continue with variables.
        na_1001['_X'] = [] # holds independent variable
        na_1001['V'] = [[] for _ in range(n_vars)] # list for each dependent variable

        for ix, line in enumerate(data):
            l = line.rsplit(sep=sep_data)
            msg = f'{file_path.name}: invalid number of parameters in line {ix+nlhead}, have {len(l)}, want {n_vars+1}'
            assert len(l) == n_vars+1, msg
            na_1001['_X'].append(l[0].strip())
            if vmiss_to_None:
                for j in range(n_vars):
                    na_1001['V'][j].append(l[j+1].strip() if l[j+1].strip() != na_1001['VMISS'][j] else None)
            else:
                for j in range(n_vars):
                    na_1001['V'][j].append(l[j+1].strip())

    return na_1001


###############################################################################


def na1001_cls_write(file_path, na_1001,
                     sep=" ", sep_com=";", sep_data="\t",
                     crlf="\n", overwrite=False,
                     verbose=False):
    """
    write content of na1001 class instance to file in NASA AMES 1001 format.
    encoding is ASCII.
    inputs:
        file_path - file path, string or pathlib.Path
        na_1001 - dict containing parameters according to NASA AMES 1001 spec.
    keywords:
        sep - separator (general)
        sep_com - separator used in comment section
        sep_data - separator used in data section
        crlf - newline character(s)
        overwrite - set to True to overwrite if file exists
        verbose - print info to the console
    returns:
        (int) 0 -> failed, 1 -> normal write, 2 -> overwrite
    """
    verboseprint = print if verbose else lambda *a, **k: None

    # check if directory exists, create if not.
    if not os.path.isdir(os.path.dirname(file_path)):
        os.mkdir(os.path.dirname(file_path))

    # check if file exists, act according to overwrite keyword
    if os.path.isfile(file_path):
        if not overwrite:
            verboseprint(f"write failed: {file_path} already exists.\n"
                          "set overwrite keyword to overwrite.")
            return 0 # write failed / forbidden
        write = 2 # overwriting
    write = 1 # normal writing

    # check n variables and comment lines; adjust values if incorrect
    n_vars_named = len(na_1001['_VNAME'])
    n_vars_data = len(na_1001['V'])
    if n_vars_named != n_vars_data:
        raise ValueError("NA error: n vars in V and VNAME not equal, "
                        f"{n_vars_data} vs. {n_vars_named}!")

    if n_vars_named-na_1001['NV'] != 0:
        verboseprint("NA output: NV corrected!")
        na_1001['NV'] = n_vars_named

    nscoml_is = len(na_1001['_SCOM'])
    if (nscoml_is - na_1001['NSCOML']) != 0:
        verboseprint("NA output: NSCOML corrected!")
        na_1001['NSCOML'] = nscoml_is

    nncoml_is = len(na_1001['_NCOM'])
    if (nncoml_is - na_1001['NNCOML']) != 0:
        verboseprint("NA output: NNCOML corrected!")
        na_1001['NNCOML'] = nncoml_is

    nlhead_is = 14 + n_vars_named + nscoml_is + nncoml_is
    if (nlhead_is - na_1001['NLHEAD']) != 0:
        verboseprint("NA output: NLHEAD corrected!")
        na_1001['NLHEAD'] = nlhead_is

    # begin the actual writing process
    with open(file_path, "w", encoding="ascii") as file_obj:
        block = str(na_1001['NLHEAD']) + sep + str(na_1001['_FFI']) + crlf
        file_obj.write(block)

        block = str(na_1001['ONAME']) + crlf
        file_obj.write(block)

        block = str(na_1001['ORG']) + crlf
        file_obj.write(block)

        block = str(na_1001['SNAME']) + crlf
        file_obj.write(block)

        block = str(na_1001['MNAME']) + crlf
        file_obj.write(block)

        block = str(na_1001['IVOL']) + sep + str(na_1001['NVOL']) + crlf
        file_obj.write(block)

        # dates: assume "yyyy m d" in tuple
        block = ('%4.4u' % na_1001['DATE'][0] + sep +
                 '%2.2u' % na_1001['DATE'][1] + sep +
                 '%2.2u' % na_1001['DATE'][2] + sep +
                 '%4.4u' % na_1001['RDATE'][0] + sep +
                 '%2.2u' % na_1001['RDATE'][1] + sep +
                 '%2.2u' % na_1001['RDATE'][2] + crlf)
        file_obj.write(block)

        file_obj.write(f"{na_1001['DX']}{crlf}")

        file_obj.write(sep_com.join(na_1001['XNAME']) + crlf)

        n_vars = na_1001['NV'] # get number of variables
        block = str(n_vars) + crlf
        file_obj.write(block)

        line = ""
        for i in range(n_vars):
            line += str(na_1001['VSCAL'][i]) + sep
        if line.endswith("\n"):
            line = line[0:-1]
        else:
            line = line[0:-1] + crlf
        file_obj.write(line)

        line = ""
        for i in range(n_vars):
            line += str(na_1001['VMISS'][i]) + sep
        if line.endswith("\n"):
            line = line[0:-1]
        else:
            line = line[0:-1] + crlf
        file_obj.write(line)

        block = na_1001['_VNAME']
        for i in range(n_vars):
            file_obj.write(block[i] + crlf)

        nscoml = na_1001['NSCOML'] # get number of special comment lines
        line = str(nscoml) + crlf
        file_obj.write(line)

        block = na_1001['_SCOM']
        for i in range(nscoml):
            file_obj.write(block[i] + crlf)

        nncoml = na_1001['NNCOML'] # get number of normal comment lines
        line = str(nncoml) + crlf
        file_obj.write(line)

        block = na_1001['_NCOM']
        for i in range(nncoml):
            file_obj.write(block[i] + crlf)

        for i, x in enumerate(na_1001['_X']):
            line = str(x) + sep_data
            for j in range(n_vars):
                line += str(na_1001['V'][j][i]) + sep_data
            file_obj.write(line[0:-1] + crlf)

    return write


###############################################################################