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

from datetime import date
from getpass import getpass

import configparser
import logging
import sys
import sunnyportal.client


def main():
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s", level=logging.DEBUG
    )

    if len(sys.argv) != 2:
        print("Usage: %s <config>" % sys.argv[0])
        sys.exit(1)

    section = "sunnyportal"
    config = configparser.ConfigParser()
    config[section] = {}
    config.read(sys.argv[1])

    if not config[section].get("email"):
        config[section]["email"] = input("E-mail: ")
    if not config[section].get("password"):
        config[section]["password"] = getpass()

    with open(sys.argv[1], "w") as f:
        config.write(f)

    client = sunnyportal.client.Client(
        config[section]["email"], config[section]["password"]
    )

    for plant in client.get_plants():
        logging.info("Found plant %s", plant.name)
        # plant.profile()
        # plant.year_energy_balance(date(2020,4,1))
        # plant.month_energy_balance(date(2020,4,1))
        # plant.last_data_exact(date.today())
        # for device in plant.get_devices():
        #    for name, param in device.get_parameters().parameters.items():
        #        print(f"{name} = {param.value} (changed {param.changed})")
        # plant.all_data('year')
        # plant.all_data('month')
        # plant.day_overview(date(2016, 2, 3))
        # plant.day_overview(date(2016, 2, 3), quarter=False)
        # plant.month_overview(date(2016, 1, 1))
        # plant.year_overview(date(2016, 2, 1))
        # for entry in plant.logbook(date(2016, 2, 1)).entries:
        #    print(f"{entry['date']} | {entry['type']} | {entry['description']}")
    client.logout()


if __name__ == "__main__":
    main()
