# core/parser.py
from obspy import read_inventory
from obspy.io.xseed import Parser as XSeedParser
import os


def parse_response(path):

    try:
        return read_inventory(path)
    except Exception as e:
        return None


def combine_resp(sensor_resp, recorder_resp):
    recorder_resp.response_stages.pop(0)
    sensor_stage0 = sensor_resp.response_stages[0]
    recorder_resp.response_stages.insert(0, sensor_stage0)
    recorder_resp.instrument_sensitivity.input_units = sensor_stage0.input_units
    recorder_resp.instrument_sensitivity.input_units_description = \
        sensor_stage0.input_units_description
    try:
        recorder_resp.recalculate_overall_sensitivity()
    except ValueError:
        msg = "Failed to recalculate overall sensitivity."
        print(msg)
    return recorder_resp

