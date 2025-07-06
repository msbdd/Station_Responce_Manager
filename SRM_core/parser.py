# core/parser.py
from obspy import read_inventory
from obspy.io.xseed import Parser as XSeedParser
import os

def parse_response(path):

    try:
        return read_inventory(path)
    except Exception as e:
        return None
