#! /usr/bin/env python
"""
Reads in IMU data from a static thermal calibration test and performs
a curve fit of gyro, accel and baro bias vs temperature
Data can be gathered using the following sequence:

1) Set the TC_A_ENABLE, TC_B_ENABLE and TC_G_ENABLE parameters to 0 to
    thermal compensation and reboot
2) Perform a gyro and accel cal
2) Set the SYS_LOGGER parameter to 1 to use the new system logger
3) Set the SDLOG_MODE parameter to 3 to enable logging of sensor data
    for calibration and power off
4) Cold soak the board for 30 minutes
5) Move to a warm dry environment.
6) Apply power for 45 minutes, keeping the board still.
7) Remove power and extract the .ulog file
8) Open a terminal window in the script file directory
9) Run the script file 'python process_sensor_caldata.py
    <full path name to .ulog file>

Outputs thermal compensation parameters in a file named
    <inputfilename>.params which can be loaded onto the
    board using QGroundControl
Outputs summary plots in a pdf file named <inputfilename>.pdf

"""

from __future__ import print_function

import argparse
import os
import matplotlib.pyplot as plt
import numpy as np

from jinja2 import Environment, FileSystemLoader
import pyulog

class Param(dict):
    def __init__(self, name, val):
        """
        Initialize a param dict
        """
        self.name = name
        self.val = val

def temp_calibration(data, topic, fields, units, label):
    """
    Performe a temperature calibration on a sensor.
    """

    # pylint: disable=no-member
    params = {}

    int_params = ['ID']
    float_params = [
        'TMIN', 'TMAX', 'TREF',
        'X0_0', 'X1_0', 'X2_0', 'X3_0',
        'X0_1', 'X1_1', 'X2_1', 'X3_1',
        'X0_2', 'X1_2', 'X2_2', 'X3_2',
        'SCL_0', 'SCL_1', 'SCL_2'
    ]

    # define data dictionary of thermal correction  parameters
    for field in int_params:
        params[field] = {
            'val': 0,
            'type': 'INT',
        }

    for field in float_params: params[field] = {
            'val': 0,
            'type': 'FLOAT',
        }

    # curve fit the data for corrections - note
    #   corrections have oppsite sign to sensor bias
    try:
        params['ID']['val'] = int(np.median(data['device_id']))
    except:
        print('no device id')
        pass

    # find the min, max and reference temperature
    params['TMIN']['val'] = float(np.amin(data['temperature']))
    params['TMAX']['val'] = float(np.amax(data['temperature']))
    params['TREF']['val'] = float(0.5 * (params['TMIN']['val'] + params['TMAX']['val']))
    temp_rel = data['temperature'] - params['TREF']['val']
    temp_rel_resample = np.linspace(
        float(params['TMIN']['val'] - params['TREF']['val']),
        float(params['TMAX']['val'] - params['TREF']['val']), 100)
    temp_resample = temp_rel_resample + params['TREF']['val']

    for i, field in enumerate(fields):
        coef = np.polyfit(temp_rel, -data[field], 3)
        for j in range(3):
            params['X{:d}_{:d}'.format(3-j, i)]['val'] = float(coef[j])
        fit_coef = np.poly1d(coef)
        resample = fit_coef(temp_rel_resample)

        # draw plots
        plt.subplot(len(fields), 1, i + 1)
        plt.plot(data['temperature'], data[field], 'b')
        plt.plot(temp_resample, -resample, 'r')
        plt.title('{:s} Bias vs Temperature'.format(topic))
        plt.ylabel('{:s} bias {:s}'.format(field, units))
        plt.xlabel('temperature (degC)')
        plt.grid()

    return params


def process_file(log_path, out_path, template_path):
    """
    Command line interface to temperature calibration.
    """
    log = pyulog.ULog(log_path, 'sensor_gyro, sensor_accel, sensor_baro')
    data = {}
    for d in log.data_list:
        data['{:s}_{:d}'.format(d.name, d.multi_id)] = d.data

    print(data.keys())

    params = {}

    # open file to save plots to PDF
    # from matplotlib.backends.backend_pdf import PdfPages
    # output_plot_filename = ulog_file_name + ".pdf"
    # pp = PdfPages(output_plot_filename)

    # process gyro data
    plt.figure(figsize=(20, 13))
    for d in log.data_list:
        if d.name == 'sensor_gyro':
            topic = '{:s}_{:d}'.format(d.name, d.multi_id)
            print('found {:s} data'.format(topic))
            fields = ['x', 'y', 'z']
            units = 'rad/s'
            label = 'TC_G{:d}'.format(d.multi_id)
            params[topic] = {
                'params': temp_calibration(
                    data=d.data, topic=topic,
                    fields=fields, units=units, label=label),
                'label': label
            }
    plt.savefig('gyro_cal.pdf')

    # process accel data
    plt.figure(figsize=(20, 13))
    for d in log.data_list:
        if d.name == 'sensor_accel':
            topic = '{:s}_{:d}'.format(d.name, d.multi_id)
            print('found {:s} data'.format(topic))
            fields = ['x', 'y', 'z']
            units = 'rad/s'
            label = 'TC_G{:d}'.format(d.multi_id)
            params[topic] = {
                'params': temp_calibration(
                    data=d.data, topic=topic,
                    fields=fields, units=units, label=label),
                'label': label
            }
    plt.savefig('accel_cal.pdf')

    # process baro data
    plt.figure(figsize=(20, 13))
    for d in log.data_list:
        if d.name == 'sensor_baro':
            topic = '{:s}_{:d}'.format(d.name, d.multi_id)
            print('found {:s} data'.format(topic))
            fields = ['altitude']
            units = 'm'
            label = 'TC_B{:d}'.format(d.multi_id)
            params[topic] = {
                'params': temp_calibration(
                    data=d.data, topic=topic,
                    fields=fields, units=units, label=label),
                'label': label
            }
    plt.savefig('baro_cal.pdf')

    # import json
    # print(json.dumps(params, indent=2))

    # for jinja docs see: http://jinja.pocoo.org/docs/2.9/api/
    env = Environment(
        loader=FileSystemLoader(template_path))
    template = env.get_template('sensor_cal.params.jinja')
    with open(out_path, 'w') as fid:
        fid.write(template.render(params=params))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
    description='Analyse the sensor_gyro  message data')
    parser.add_argument('filename', metavar='file.ulg', help='ULog input file')
    args = parser.parse_args()
    ulog_file_name = args.filename
    template_path = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), 'templates')
    process_file(log_path=args.filename, out_path=ulog_file_name.replace('ulg', 'params'),
            template_path=template_path)
    plt.show()

#  vim: set et fenc=utf-8 ff=unix sts=0 sw=4 ts=4 : 
