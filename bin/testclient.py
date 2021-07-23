#!/usr/bin/env python3

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

"""A simple client using the sunnyportal-py library."""

from datetime import date, timedelta
from getpass import getpass

import configparser
import logging
import sys
import time
import sunnyportal.client


def main():
    """Main."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO
    )

    if len(sys.argv) != 2:
        print("Usage: %s <config>" % sys.argv[0])
        sys.exit(1)

    section = "sunnyportal"
    config = configparser.ConfigParser()
    config[section] = {}
    config.read(sys.argv[1])

    if not config[section].get('plant'):
        config[section]['plant'] = input("Plant: ")
    if not config[section].get("email"):
        config[section]["email"] = input("E-mail: ")
    if not config[section].get("password"):
        config[section]["password"] = getpass()

    with open(sys.argv[1], "w") as file:
        config.write(file)

    client = sunnyportal.client.Client(
        config[section]["email"], config[section]["password"]
    )

    for plant in client.get_plants():
        if plant.name == config[section]['plant']:
            logging.debug("Found plant %s", plant.name)

            # Fetch all generation data for 2020, for example
            start_date = date(2020, 1, 1)
            end_date = date(2020, 12, 31)
            delta = timedelta(days=1)
            # Be a good client
            time.sleep(5)

            while start_date <= end_date:
                day = plant.day_overview(start_date)
                for power in day.power_measurements:
                    print(power.timestamp, power.power)
                start_date += delta

    client.logout()


if __name__ == "__main__":
    main()
