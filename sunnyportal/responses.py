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
from xml.sax.saxutils import unescape


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


Yield = namedtuple("Yield", ["timestamp", "absolute", "difference"])
Power = namedtuple("Power", ["timestamp", "power", "min", "max"])
Parameter = namedtuple("Parameter", ["value", "changed"])
Consumption = namedtuple("Consumption", ["external", "internal", "direct"])
Generation = namedtuple("Generation", ["total", "self_consumption", "feed_in"])
Battery = namedtuple("Battery", ["charge", "discharge"])
EnergyBalance = namedtuple(
    "EnergyBalance", ["timestamp", "consumption", "generation", "battery"]
)


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
            raise MalformedResponseError(
                "Missing %s attribute in %s tag" % (attribute, element.tag)
            )
        return value

    def parse(self, data, name=None):
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

        if name is None:
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
            self.plants.append(
                {
                    "oid": self.get_or_raise(p, "oid"),
                    "name": self.get_or_raise(p, "name"),
                }
            )


class PlantProfileResponse(ResponseBase):
    def kwp_to_wp(self, kwp):
        return self.kwh_to_wh(kwp)

    def parse(self, data):
        tag = super().parse(data)

        self.name = tag.find("name").text
        self.peak_power = self.kwp_to_wp(tag.find("peak-power").text)
        self.city_country = tag.find("city-country").text
        self.start_date = datetime.strptime(tag.find("start-date").text, "%d/%m/%Y")

        description = tag.find("description")
        if description is not None:
            self.description = (
                tag.find("description").text.replace("<br />", "").rstrip()
            )
        else:
            self.description = None

        plant_image = tag.find("plant-image")
        if plant_image is not None:
            self.plant_image = {
                "image": plant_image.text,
                "width": int(plant_image.attrib["width"]),
                "height": int(plant_image.attrib["height"]),
            }
        else:
            self.plant_image = None

        def findall(tag, parent, children):
            element = tag.find(parent)
            if element is None:
                return []
            return element.findall(children)

        self.production_data = {}
        for channel in findall(tag, "production-data", "channel"):
            self.production_data[channel.attrib["meta-name"]] = channel.text

        self.inverters = []
        for inverter in findall(tag, "inverters", "inverter"):
            self.inverters.append(
                {
                    "count": int(inverter.attrib["count"]),
                    "deviceIcon": inverter.attrib["deviceIcon"],
                    "text": inverter.text,
                }
            )

        self.communication_products = []
        for product in findall(tag, "communicationProducts", "communicationProduct"):
            self.communication_products.append(
                {
                    "count": int(product.attrib["count"]),
                    "deviceIcon": product.attrib["deviceIcon"],
                    "name": product.text,
                }
            )


class PlantDeviceListResponse(ResponseBase):
    def parse(self, data):
        self.devices = []
        for d in super().parse(data, "devicelist").iterfind("device"):
            startdate = datetime.strptime(
                self.get_or_raise(d, "startdate"), "%m/%d/%Y %I:%M:%S %p"
            )
            self.devices.append(
                {
                    "oid": self.get_or_raise(d, "oid"),
                    "name": self.get_or_raise(d, "name"),
                    "class": self.get_or_raise(d, "class"),
                    "serialnumber": self.get_or_raise(d, "serialnumber"),
                    "type-id": self.get_or_raise(d, "type-id"),
                    "startdate": startdate,
                }
            )


class PlantDeviceParametersResponse(ResponseBase):
    def parse(self, data):
        self.parameters = {}
        for p in super().parse(data, "parameterlist").iterfind("parameter"):
            name = self.get_or_raise(p, "parameter-name")
            value = self.get_or_raise(p, "parameter-value")
            changed = datetime.strptime(
                self.get_or_raise(p, "last-change"), "%m/%d/%Y %I:%M:%S %p"
            )
            self.parameters[name] = Parameter(value, changed)


class DataResponse(ResponseBase):
    def parse_timestamp(self, tag, ts_format):
        return datetime.strptime(self.get_or_raise(tag, "timestamp"), ts_format)

    def parse_abs_diff(self, tag):
        absolute = self.kwh_to_wh(tag.get("absolute"))
        difference = self.kwh_to_wh(tag.get("difference"))
        return (absolute, difference)


class LastDataExactResponse(DataResponse):
    def parse(self, data):
        tag = super().parse(data)
        tag = self.find_or_raise(tag, "./Energy/channel")

        day = self.find_or_raise(tag, "day")
        (absolute, difference) = self.parse_abs_diff(day)
        if absolute is not None and difference is not None:
            date = self.parse_timestamp(day, "%d/%m/%Y")
            self.day = Yield(date, absolute, difference)
        else:
            self.day = None

        hour = self.find_or_raise(tag, "hour")
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
        tag = self.find_or_raise(tag, "./Energy/channel/infinite")
        self.start_timestamp = self.parse_timestamp(tag, "%d/%m/%Y %H:%M")

        fmt = ("year", "%Y")
        if tag.find("month") is not None:
            fmt = ("month", "%m/%Y")

        energy = []
        for entry in tag.iterfind(fmt[0]):
            (absolute, difference) = self.parse_abs_diff(entry)
            if absolute is not None and difference is not None:
                date = self.parse_timestamp(entry, fmt[1])
                energy.append(Yield(date, absolute, difference))
        setattr(self, "%ss" % fmt[0], energy)


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
    def __init__(self, data, quarter, include_all):
        self.quarter = quarter
        self.include_all = include_all
        super().__init__(data)

    def kw_to_w(self, kw):
        return self.kwh_to_wh(kw)

    def parse(self, data):
        tag = super().parse(data)
        tag_type = "day-fifteen" if self.quarter else "day"
        tag = self.find_or_raise(tag, "overview-%s-total" % tag_type)

        self.parse_abs_diff_date(tag, "day", "%d/%m/%Y")

        self.power_measurements = []
        tag_name = "fiveteen" if self.quarter else "hour"
        for entry in tag.iterfind("./channel/day/%s" % tag_name):
            mean = self.kw_to_w(entry.get("mean"))
            if self.include_all or mean is not None:
                time = self.parse_timestamp(entry, "%H:%M")
                time = datetime.combine(self.date, time.time())
                pmin = self.kw_to_w(entry.get("min"))
                pmax = self.kw_to_w(entry.get("max"))
                self.power_measurements.append(Power(time, mean, pmin, pmax))


class MonthOverviewResponse(OverviewResponse):
    def parse(self, data):
        tag = super().parse(data)
        tag = self.find_or_raise(tag, "overview-month-total")

        self.parse_abs_diff_date(tag, "month", "%m/%Y")

        self.days = []
        for entry in tag.iterfind("./channel/month/day"):
            (absolute, difference) = self.parse_abs_diff(entry)
            if absolute is not None and difference is not None:
                date = self.parse_timestamp(entry, "%d/%m/%Y")
                self.days.append(Yield(date, absolute, difference))


class YearOverviewResponse(OverviewResponse):
    def parse(self, data):
        tag = super().parse(data)
        tag = self.find_or_raise(tag, "overview-year-total")

        self.parse_abs_diff_date(tag, "year", "%Y")

        self.months = []
        for entry in tag.iterfind("./channel/year/month"):
            (absolute, difference) = self.parse_abs_diff(entry)
            if absolute is not None and difference is not None:
                date = self.parse_timestamp(entry, "%m/%Y")
                self.months.append(Yield(date, absolute, difference))


class EnergyBalanceResponse(DataResponse):
    def parse(self, data):
        tag = super().parse(data)
        tag = self.find_or_raise(tag, "energybalance")

        if tag.get("unit") == "kWh":
            converter = self.kwh_to_wh
        else:
            assert tag.get("unit") == "Wh"
            converter = lambda wh: None if wh is None else int(float(wh))

        if tag.find("./*/month") is not None:
            self.months = []
            for entry in tag.iterfind("./*/month"):
                date = self.parse_timestamp(entry, "%m/%Y")
                b = self.parse_entry(entry, date, converter)
                if b is not None:
                    self.months.append(b)
            print(self.months)
        elif tag.find("./*/day") is not None:
            self.days = []
            for entry in tag.iterfind("./*/day"):
                date = self.parse_timestamp(entry, "%d/%m/%Y")
                b = self.parse_entry(entry, date, converter)
                if b is not None:
                    self.days.append(b)
        elif tag.find("./day") is not None:
            entry = tag.find("./day")
            date = self.parse_timestamp(entry, "%d/%m/%Y")
            self.day = self.parse_entry(entry, date, converter)
        else:
            raise NotImplementedError("unsupported response")

    def parse_entry(self, entry, timestamp, converter):
        consumption = Consumption(
            converter(entry.get("external-supply")),
            converter(entry.get("self-supply")),
            converter(entry.get("direct-consumption")),
        )
        if any(m is None for m in consumption):
            return None

        generation = Generation(
            converter(entry.get("pv-generation")),
            converter(entry.get("self-consumption")),
            converter(entry.get("feed-in")),
        )
        if any(m is None for m in generation):
            return None

        battery = Battery(
            converter(entry.get("battery-charging")),
            converter(entry.get("battery-discharging")),
        )
        if all(m is None for m in battery):
            battery = None

        return EnergyBalance(timestamp, consumption, generation, battery)


class LogbookResponse(ResponseBase):
    def parse(self, data):
        self.entries = []
        for e in super().parse(data).iterfind("entry"):
            device = self.find_or_raise(e, "device")

            description = self.find_or_raise(e, "description").text
            description = unescape(description, {"&apos;": "'", "&quot;": '"'})

            event_date = self.find_or_raise(e, "date").text
            event_date = datetime.strptime(event_date, "%d/%m/%Y %H:%M:%S")

            self.entries.append(
                {
                    "event_id": self.get_or_raise(e, "event-id"),
                    "date": event_date,
                    "id": self.find_or_raise(e, "id").text,
                    "type": self.find_or_raise(e, "type").text,
                    "status": self.find_or_raise(e, "status").text,
                    "description": description,
                    "device_oid": self.get_or_raise(device, "oid"),
                    "device_name": self.get_or_raise(device, "name"),
                    "device_serial": self.get_or_raise(device, "serialnumber"),
                }
            )
