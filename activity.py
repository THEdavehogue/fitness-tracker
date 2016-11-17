import os
import pytz
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from time import sleep, localtime
from bs4 import BeautifulSoup
from tzwhere import tzwhere
from datetime import datetime, timedelta

FTP = 210
plt.style.use('fivethirtyeight')


class Activity(object):

    def __init__(self, filename):
        self.filename = filename
        self.time = np.array([])
        self.lat = np.array([])
        self.lon = np.array([])
        self.alt = np.array([])
        self.dist = np.array([])
        self.hr = np.array([])
        self.cad = np.array([])
        self.spd = np.array([])
        self.pwr = np.array([])

    def analyze(self):
        self._parse_tcx()
        self._calculate_avgs()
        self._print_avgs()

    def _parse_tcx(self):
        lines = []
        with open(self.filename) as f:
            for line in f:
                lines.append(line)
        raw = ''.join(lines)
        soup = BeautifulSoup(raw, 'xml')
        trackpoints = soup.findAll('Trackpoint')
        offset = self._utc_offset(trackpoints[0])
        dst = timedelta(0, -3600)
        for tp in trackpoints:
            time = datetime.strptime(tp.find('Time').text, '%Y-%m-%dT%H:%M:%S.%fZ') + offset
            self.time = np.append(self.time, time)
            self.lat = np.append(self.lat, float(tp.find('LatitudeDegrees').text))
            self.lon = np.append(self.lon, float(tp.find('LongitudeDegrees').text))
            self.alt = np.append(self.alt, float(tp.find('AltitudeMeters').text))
            self.dist = np.append(self.dist, float(tp.find('DistanceMeters').text))
            self.hr = np.append(self.hr, int(tp.find('HeartRateBpm').text))
            self.cad = np.append(self.cad, int(tp.find('Cadence').text))
            self.spd = np.append(self.spd, float(tp.find('Speed').text))
            self.pwr = np.append(self.pwr, int(tp.find('Watts').text))
        self._convert_units()
        # self._calc_climb_descent()

    def _calc_climb_descent(self):
        self.climb = 0
        self.descent = 0
        for i in range(1, len(self.alt)):
            delta = self.alt[i] - self.alt[i - 1]
            if delta >= 0:
                self.climb += delta
            else:
                self.descent -= delta

    def _convert_units(self):
        self.alt *= 3.28084 # convert m to ft
        self.spd *= 2.23694 # convert m/s to mph
        self.dist *= 0.0006213712 # convert meters to mi

    def _utc_offset(self, tp):
        tzw = tzwhere.tzwhere()
        lat = float(tp.find('LatitudeDegrees').text)
        lon = float(tp.find('LongitudeDegrees').text)
        timezone_str = tzw.tzNameAt(lat, lon)
        timezone = pytz.timezone(timezone_str)
        dt = datetime.now()
        offset = timezone.utcoffset(dt)
        dst = localtime().tm_isdst
        if dst == 0:
            offset += timedelta(0, -3600)
        return offset

    def _calculate_avgs(self):
        self.avg_pwr = int(self.pwr.mean())
        self.avg_spd = round(self.spd.mean(), 2)
        self.avg_cad = int(self.cad.mean())
        self.avg_hr = int(self.hr.mean())
        self.ride_time = str(self.time.max() - self.time.min())
        self._calc_normalized_pwr()

    def _print_avgs(self):
        print 'Distance: {} mi'.format(round(self.dist.max(), 2))
        print 'Average Speed: {} mph'.format(self.avg_spd)
        print 'Average Cadence: {}'.format(self.avg_cad)
        print 'Average Power: {}W'.format(self.avg_pwr)
        print 'Normalized Power: {}W'.format(self.norm_pwr)
        print 'FTP Setting: {}W'.format(FTP)
        print 'Intensity Factor: {}'.format(self.IF)
        print 'Training Stress Score: {}'.format(self.TSS)
        # print 'Total Ascent: {} ft'.format(self.climb)

    def _calc_normalized_pwr(self):
        np_len = len(self.pwr) - 29
        roll_avgs = np.array([self.pwr[i:i+30].mean() for i in range(np_len)])
        pwr_4_avg = (roll_avgs**4).mean()
        self.norm_pwr = int(pwr_4_avg**(0.25))
        self._calc_if_tss()

    def _calc_if_tss(self):
        self.IF = round(self.norm_pwr/float(FTP), 2)
        sec = len(self.time)
        np = self.norm_pwr
        IF = self.IF
        self.TSS = int((sec * np * IF)/(FTP * 3600) * 100)

    def plot_key_measurements(self):
        fig = plt.figure(figsize=(12,10))
        incr = len(self.time) / 4
        xticks = []
        for i in range(4):
            xticks.append(str(self.time[i * incr]))
        xticks.append(str(self.time[-1]))
        ax1 = self._plot_measurement(fig, 511, xticks, self.alt,
                                     '#006700', 'Elevation (ft)')
        ax2 = self._plot_measurement(fig, 512, xticks, self.spd,
                                     '#0077B9', 'Speed (mph)')
        ax3 = self._plot_measurement(fig, 513, xticks, self.hr,
                                     '#EB0039', 'Heart Rate (bpm)')
        ax4 = self._plot_measurement(fig, 514, xticks, self.pwr,
                                     '#9F00BD', 'Power (Watts)')
        ax5 = self._plot_measurement(fig, 515, xticks, self.cad,
                                     '#D46800', 'Bike Cadence (rpm)')
        plt.tight_layout()
        plt.show()

    def _plot_measurement(self, fig, pos, xticks, measurement, color, title):
        ax = fig.add_subplot(pos)
        dt_format = mdates.DateFormatter('%T')
        ax.xaxis.set_major_formatter(dt_format)
        incr = len(self.time) / 4
        ax.plot(self.time, measurement, lw = 1.25, color=color, alpha=0.8)
        ax.set_xticks(xticks)
        ax.set_yticks(self._calc_y_ticks(measurement))
        ax.set_ylim(measurement.min() - 10)
        ax.fill_between(self.time, measurement,
                        where=measurement > measurement.min() - 10,
                        color=color, alpha=0.9)
        ax.grid(False, which='both', axis='x')
        ax.set_title(title)
        return ax

    def _calc_y_ticks(self, measurement):
        yticks = np.linspace(measurement.min(), measurement.max() + 10, 4)
        yticks = yticks.astype(int)
        return yticks


if __name__ == '__main__':
    act = Activity(os.path.join('data', 'activity_1449026316.tcx'))
    act.analyze()
    act.plot_key_measurements()
