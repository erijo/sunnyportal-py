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


class ResponseBase(object):
    def __init__(self, data):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.parse(data)

    def log_response(self, data):
        self.log.debug("Response: %s", data)

    def get_creation_date(self):
        return datetime.strptime(self.creation_date, "%m/%d/%Y %I:%M:%S %p")

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
        for p in super().parse(data).findall("plant"):
            self.plants.append({
                'oid': self.get_or_raise(p, 'oid'),
                'name': self.get_or_raise(p, 'name')
            })


class PlantProfileResponse(ResponseBase):
    def parse(self, data):
        tag = super().parse(data)
        # TODO: parse into something meaningful


class LastDataExactResponse(ResponseBase):
    def parse(self, data):
        tag = super().parse(data)
        # TODO: parse into something meaningful


class AllDataResponse(ResponseBase):
    def parse(self, data):
        tag = super().parse(data)
        # TODO: parse into something meaningful


class OverviewResponse(ResponseBase):
    def kwh_to_wh(self, kwh):
        if kwh is not None:
            return int(float(kwh) * 1000)
        else:
            return kwh

    def parse_timestamp(self, tag, ts_format):
        return datetime.strptime(
            self.get_or_raise(tag, 'timestamp'), ts_format)

    def parse_abs_diff(self, tag, period, date_format):
        summary = tag.find("./channel/%s[@absolute]" % period)
        if summary is not None:
            self.absolute = self.kwh_to_wh(summary.get('absolute'))
            self.difference = self.kwh_to_wh(summary.get('difference'))
            self.date = summary
        else:
            self.absolute = None
            self.difference = None
            self.date = self.find_or_raise(tag, "./channel/%s" % period)
        self.date = self.parse_timestamp(self.date, date_format).date()


class DayOverviewResponse(OverviewResponse):
    def kw_to_w(self, kw):
        return self.kwh_to_wh(kw)

    def parse(self, data):
        tag = super().parse(data)
        tag = self.find_or_raise(tag, 'overview-day-fifteen-total')

        self.parse_abs_diff(tag, "day", "%d/%m/%Y")

        self.power = []
        for entry in tag.findall('./channel/day/fiveteen'):
            mean = self.kw_to_w(entry.get('mean'))
            if mean is not None:
                time = self.parse_timestamp(entry, "%H:%M").time()
                self.power.append((time, mean))


class MonthOverviewResponse(OverviewResponse):
    def parse(self, data):
        tag = super().parse(data)
        tag = self.find_or_raise(tag, 'overview-month-total')

        self.parse_abs_diff(tag, "month", "%m/%Y")

        self.energy = []
        for entry in tag.findall('./channel/month/day'):
            absolute = self.kwh_to_wh(entry.get('absolute'))
            difference = self.kwh_to_wh(entry.get('difference'))
            if absolute is not None and difference is not None:
                date = self.parse_timestamp(entry, "%d/%m/%Y").date()
                self.energy.append((date, absolute, difference))


class YearOverviewResponse(OverviewResponse):
    def parse(self, data):
        tag = super().parse(data)
        tag = self.find_or_raise(tag, 'overview-year-total')

        self.parse_abs_diff(tag, "year", "%Y")

        self.energy = []
        for entry in tag.findall('./channel/year/month'):
            absolute = self.kwh_to_wh(entry.get('absolute'))
            difference = self.kwh_to_wh(entry.get('difference'))
            if absolute is not None and difference is not None:
                date = self.parse_timestamp(entry, "%m/%Y").date()
                self.energy.append((date, absolute, difference))
