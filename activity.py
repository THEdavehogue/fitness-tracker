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

    def __init__(self, tcx_file, gpx_file):
        self.tcx_file = tcx_file
        self.gpx_file = gpx_file
        self.time = np.array([])
        self.lat = np.array([])
        self.lon = np.array([])
        self.ele = np.array([])
        self.dist = np.array([])
        self.hr = np.array([])
        self.cad = np.array([])
        self.spd = np.array([])
        self.pwr = np.array([])
        self.temp = np.array([])

    def analyze(self):
        self._parse_tcx()
        self._parse_gpx()
        self._convert_units()
        self._calc_climb_descent()
        self._calculate_avgs()
        self._print_avgs()

    def _soupify(self, filename):
        lines = []
        with open(filename) as f:
            for line in f:
                lines.append(line)
        raw = ''.join(lines)
        soup = BeautifulSoup(raw, 'xml')
        return soup

    def _parse_gpx(self):
        soup = self._soupify(self.gpx_file)
        trackpoints = soup.findAll('trkpt')
        for tp in trackpoints:
            self.lat = np.append(self.lat, float(tp.attrs['lat']))
            self.lon = np.append(self.lon, float(tp.attrs['lon']))
            self.ele = np.append(self.ele, float(tp.contents[1].text))
            self.temp = np.append(self.temp,
                            float(tp.contents[5].contents[1].contents[1].text))

    def _parse_tcx(self):
        soup = self._soupify(self.tcx_file)
        self.calories = int(soup.find('Calories').text)
        trackpoints = soup.findAll('Trackpoint')
        offset = self._utc_offset(trackpoints[0])
        dst = timedelta(0, -3600)
        for tp in trackpoints:
            time = datetime.strptime(tp.find('Time').text, '%Y-%m-%dT%H:%M:%S.%fZ') + offset
            self.time = np.append(self.time, time)
            self.dist = np.append(self.dist, float(tp.find('DistanceMeters').text))
            # self.ele = np.append(self.ele, float(tp.find('AltitudeMeters').text))
            self.cad = np.append(self.cad, int(tp.find('Cadence').text))
            self.hr = np.append(self.hr, int(tp.find('HeartRateBpm').text))
            self.spd = np.append(self.spd, float(tp.find('Speed').text))
            self.pwr = np.append(self.pwr, int(tp.find('Watts').text))

    def _calc_climb_descent(self):
        self.climb = 0
        self.descent = 0
        cd_len = len(self.ele) - 24
        roll_avgs = np.array([self.ele[i:i+25].mean() for i in range(cd_len)])
        for i in range(1, len(roll_avgs)):
            delta = roll_avgs[i] - roll_avgs[i - 1]
            if delta >= 0:
                self.climb += delta
            else:
                self.descent -= delta
        self.climb = int(round(self.climb, 0))
        self.descent = int(round(self.descent, 0))

    def _convert_units(self):
        self.ele *= 3.28084 # convert m to ft
        self.spd *= 2.23694 # convert m/s to mph
        self.dist *= 0.0006213712 # convert meters to mi
        self.temp = self.temp * (9./5) + 32 # convert deg C to deg F

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
        self.avg_pwr = int(round(self.pwr.mean(), 0))
        self.avg_spd = round(self.spd.mean(), 1)
        cad_vect = self.cad[np.where(self.cad != 0)[0]]
        self.avg_cad = int(round(cad_vect.mean(), 0))
        self.avg_hr = int(round(self.hr.mean(), 0))
        self.ride_time = str(self.time.max() - self.time.min())
        self._calc_normalized_pwr()

    def _print_avgs(self):
        print 'Distance: {} mi'.format(round(self.dist.max(), 2))
        print 'Average Speed: {} mph'.format(self.avg_spd)
        print 'Average Cadence: {} rpm'.format(self.avg_cad)
        print 'Average Heart Rate: {} bpm'.format(self.avg_hr)
        print 'Average Power: {} W'.format(self.avg_pwr)
        print 'Normalized Power: {} W'.format(self.norm_pwr)
        print 'FTP Setting: {} W'.format(FTP)
        print 'Calories: {}'.format(self.calories)
        print 'Intensity Factor: {}'.format(self.IF)
        print 'Training Stress Score: {}'.format(self.TSS)
        print 'Total Ascent: {} ft'.format(self.climb)

    def _calc_normalized_pwr(self):
        np_len = len(self.pwr) - 29
        roll_avgs = np.array([self.pwr[i:i+30].mean() for i in range(np_len)])
        pwr_4_avg = (roll_avgs**4).mean()
        self.norm_pwr = int(round(pwr_4_avg**(0.25), 0))
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
            xticks.append(self.time[i * incr])
        xticks.append(self.time[-1])
        ax1 = self._plot_measurement(fig, 611, xticks, self.ele,
                                     '#50B012', 'Elevation (ft)')
        ax2 = self._plot_measurement(fig, 612, xticks, self.spd,
                                     '#11A9ED', 'Speed (mph)')
        ax3 = self._plot_measurement(fig, 613, xticks, self.hr,
                                     '#FF0035', 'Heart Rate (bpm)')
        ax4 = self._plot_measurement(fig, 614, xticks, self.pwr,
                                     '#CF23B8', 'Power (Watts)')
        ax5 = self._plot_measurement(fig, 615, xticks, self.cad,
                                     '#ED7E00', 'Bike Cadence (rpm)')
        ax6 = self._plot_measurement(fig, 616, xticks, self.temp,
                                     '#888888', 'Temperature (F)')
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
    tcx = os.path.join('data', 'activity_1449026316.tcx')
    gpx = os.path.join('data', 'activity_1449026316.gpx')
    act = Activity(tcx, gpx)
    act.analyze()
    act.plot_key_measurements()
