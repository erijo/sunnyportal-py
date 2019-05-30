# Copyright (c) 2016 Erik Johansson <erik@ejohansson.se>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

from collections import namedtuple
from datetime import datetime

import logging
import xml.etree.ElementTree as ET


class Error(Exception):
    pass


class MalformedResponseError(Error):
    pass


class ResponseError(Error):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code

    def __str__(self):
        s = super().__str__()
        if self.code:
            s = "%s: %s" % (self.code, s)
        return s


Yield = namedtuple('Yield', ['timestamp', 'absolute', 'difference'])
Power = namedtuple('Power', ['timestamp', 'power'])


class ResponseBase(object):
    def __init__(self, data):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.parse(data)

    def log_response(self, data):
        self.log.debug("Response: %s", data)

    def get_creation_date(self):
        return datetime.strptime(self.creation_date, "%m/%d/%Y %I:%M:%S %p")

    def kwh_to_wh(self, kwh):
        if kwh is None:
            return None
        return int(float(kwh) * 1000)

    def find_or_raise(self, element, tag):
        child = element.find(tag)
        if child is None:
            raise MalformedResponseError("Missing %s tag" % tag)
        return child

    def get_or_raise(self, element, attribute):
        value = element.get(attribute)
        if value is None:
            raise MalformedResponseError("Missing %s attribute in %s tag"
                                         % (attribute, element.tag))
        return value

    def parse(self, data):
        self.log_response(data)

        root = ET.fromstring(data)
        if root.tag != "sma.sunnyportal.services":
            raise MalformedResponseError("Unknown root tag")

        service = self.find_or_raise(root, "service")

        error = service.find("error")
        if error is not None:
            msg = error.findtext("message")
            if not msg:
                msg = "Invalid response error"

            raise ResponseError(msg, error.findtext("code"))

        self.creation_date = self.get_or_raise(service, "creation-date")
        self.method = self.get_or_raise(service, "method").upper()

        name = self.get_or_raise(service, "name")
        return self.find_or_raise(service, name)


class AuthenticationResponse(ResponseBase):
    def parse(self, data):
        tag = super().parse(data)

        if tag.text != "OK":
            raise ResponseError("Authentication failed")

        self.server_offset = datetime.now() - self.get_creation_date()
        self.identifier = self.get_or_raise(tag, "identifier")
        if self.method != "DELETE":
            self.key = self.get_or_raise(tag, "key")


class PlantListResponse(ResponseBase):
    def parse(self, data):
        self.plants = []
        for p in super().parse(data).iterfind("plant"):
            self.plants.append({
                'oid': self.get_or_raise(p, 'oid'),
                'name': self.get_or_raise(p, 'name')
            })


class PlantProfileResponse(ResponseBase):
    def kwp_to_wp(self, kwp):
        return self.kwh_to_wh(kwp)

    def parse(self, data):
        tag = super().parse(data)

        self.name = tag.find('name').text
        self.peak_power = self.kwp_to_wp(tag.find('peak-power').text)
        self.city_country = tag.find('city-country').text
        self.start_date = datetime.strptime(
            tag.find('start-date').text, "%d/%m/%Y")

        description = tag.find('description')
        if description is not None:
            self.description = \
                tag.find('description').text.replace("<br />", "").rstrip()
        else:
            self.description = None

        plant_image = tag.find('plant-image')
        if plant_image is not None:
            self.plant_image = {'image': plant_image.text,
                                'width': int(plant_image.attrib['width']),
                                'height': int(plant_image.attrib['height'])}
        else:
            self.plant_image = None

        self.production_data = {}
        for channel in tag.find('production-data').findall('channel'):
            self.production_data[channel.attrib['meta-name']] = channel.text

        self.inverters = []
        inverters = tag.find('inverters')
        for inverter in inverters.findall('inverter'):
            self.inverters.append({'count': int(inverter.attrib['count']),
                                   'deviceIcon': inverter.attrib['deviceIcon'],
                                   'text': inverter.text})

        self.communication_products = []
        communication_products = tag.find('communicationProducts')
        for product in communication_products.findall('communicationProduct'):
            self.communication_products.append(
                {'count': int(product.attrib['count']),
                 'deviceIcon': product.attrib['deviceIcon'],
                 'name': product.text})


class DataResponse(ResponseBase):
    def parse_timestamp(self, tag, ts_format):
        return datetime.strptime(
            self.get_or_raise(tag, 'timestamp'), ts_format)

    def parse_abs_diff(self, tag):
        absolute = self.kwh_to_wh(tag.get('absolute'))
        difference = self.kwh_to_wh(tag.get('difference'))
        return (absolute, difference)


class LastDataExactResponse(DataResponse):
    def parse(self, data):
        tag = super().parse(data)
        tag = self.find_or_raise(tag, './Energy/channel')

        day = self.find_or_raise(tag, 'day')
        (absolute, difference) = self.parse_abs_diff(day)
        if absolute is not None and difference is not None:
            date = self.parse_timestamp(day, "%d/%m/%Y")
            self.day = Yield(date, absolute, difference)
        else:
            self.day = None

        hour = self.find_or_raise(tag, 'hour')
        (absolute, difference) = self.parse_abs_diff(hour)
        if absolute is not None and difference is not None:
            time = self.parse_timestamp(hour, "%H:%M")
            time = datetime.combine(self.day.timestamp, time.time())
            self.hour = Yield(time, absolute, difference)
        else:
            self.hour = None


class AllDataResponse(DataResponse):
    def parse(self, data):
        tag = super().parse(data)
        tag = self.find_or_raise(tag, './Energy/channel/infinite')
        self.start_timestamp = self.parse_timestamp(tag, "%d/%m/%Y %H:%M")

        fmt = ('year', "%Y")
        if tag.find('month') is not None:
            fmt = ('month', '%m/%Y')

        energy = []
        for entry in tag.iterfind(fmt[0]):
            (absolute, difference) = self.parse_abs_diff(entry)
            if absolute is not None and difference is not None:
                date = self.parse_timestamp(entry, fmt[1])
                energy.append(Yield(date, absolute, difference))
        setattr(self, '%ss' % fmt[0], energy)


class OverviewResponse(DataResponse):
    def parse_abs_diff_date(self, tag, period, date_format):
        summary = tag.find("./channel/%s[@absolute]" % period)
        if summary is not None:
            (self.absolute, self.difference) = self.parse_abs_diff(summary)
        else:
            (self.absolute, self.difference) = (None, None)
            summary = self.find_or_raise(tag, "./channel/%s" % period)
        self.date = self.parse_timestamp(summary, date_format).date()


class DayOverviewResponse(OverviewResponse):
    def kw_to_w(self, kw):
        return self.kwh_to_wh(kw)

    def parse(self, data):
        tag = super().parse(data)
        tag = self.find_or_raise(tag, 'overview-day-fifteen-total')

        self.parse_abs_diff_date(tag, "day", "%d/%m/%Y")

        self.power_measurements = []
        for entry in tag.iterfind('./channel/day/fiveteen'):
            mean = self.kw_to_w(entry.get('mean'))
            if mean is not None:
                time = self.parse_timestamp(entry, "%H:%M")
                time = datetime.combine(self.date, time.time())
                self.power_measurements.append(Power(time, mean))


class MonthOverviewResponse(OverviewResponse):
    def parse(self, data):
        tag = super().parse(data)
        tag = self.find_or_raise(tag, 'overview-month-total')

        self.parse_abs_diff_date(tag, "month", "%m/%Y")

        self.days = []
        for entry in tag.iterfind('./channel/month/day'):
            (absolute, difference) = self.parse_abs_diff(entry)
            if absolute is not None and difference is not None:
                date = self.parse_timestamp(entry, "%d/%m/%Y")
                self.days.append(Yield(date, absolute, difference))


class YearOverviewResponse(OverviewResponse):
    def parse(self, data):
        tag = super().parse(data)
        tag = self.find_or_raise(tag, 'overview-year-total')

        self.parse_abs_diff_date(tag, "year", "%Y")

        self.months = []
        for entry in tag.iterfind('./channel/year/month'):
            (absolute, difference) = self.parse_abs_diff(entry)
            if absolute is not None and difference is not None:
                date = self.parse_timestamp(entry, "%m/%Y")
                self.months.append(Yield(date, absolute, difference))
