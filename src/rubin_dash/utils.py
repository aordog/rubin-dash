"""
utils.py
========

**Author:** Anna Ordog

**Description:**

"""

import numpy as np
import random # only needed for making fake bands and camera angles for now
import healpy as hp
from datetime import datetime

BANDS = ('u', 'g', 'r', 'i', 'z', 'y')
MASK_COLS = [f'{b}mask' for b in BANDS]
VISIT_COLS = [f'{b}visits' for b in BANDS]


def remove_high_dec(ra_in, dec_in, dec_lim):
    return ra_in[dec_in<dec_lim], dec_in[dec_in<dec_lim]

def make_fake_src_list(nside, declim):

    idx_list = np.arange(0,hp.nside2npix(nside))

    ra, dec = hp.pix2ang(nside, idx_list, lonlat=True)

    return remove_high_dec(ra.astype(float), 
                           dec.astype(float), declim)

def make_fake_bands(nvisits):

    bands = ['u','g','r','i','z','y']

    return random.choices(bands, k=nvisits)

def make_fake_rot(nvisits):

    return [random.uniform(0, 90) for _ in range(nvisits)]

def write(destinations, msg, at_line_start):
    lines = msg.split("\n")

    for i, line in enumerate(lines):
        if i > 0:
            for dest in destinations:
                dest.write("\n")
            at_line_start = True

        if line:
            if at_line_start:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                line = f"[{timestamp}] {line}"
                at_line_start = False
            for dest in destinations:
                dest.write(line)
                dest.flush()

    return at_line_start




