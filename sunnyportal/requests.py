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

import base64
import hashlib
import hmac
import http.client as http
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET


class RequestError(Exception):
    CODE_TAG = "code"
    MESSAGE_TAG = "message"

    def __init__(self, tag):
        super().__init__()
        code = tag.find(RequestError.CODE_TAG)
        if code is not None and code.text:
            self.code = code.text
        else:
            self.code = "unknown-error"

        msg = tag.find(RequestError.MESSAGE_TAG)
        if msg is not None and msg.text:
            self.msg = msg.text
        else:
            self.msg = "Invalid request error"

    def __str__(self):
        return "%s (%s)" % (self.msg, self.code)


class RequestBase(object):
    ROOT_TAG = "sma.sunnyportal.services"
    SERVICE_TAG = "service"
    ERROR_TAG = "error"

    def __init__(self, service, token=None, method='GET'):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.service = service
        self.token = token
        self.method = method
        self.version = 100
        self.base_path = '/services'
        self.url = None

    def get_timestamp(self, offset):
        timestamp = datetime.now() - offset
        return timestamp.strftime("%Y-%m-%dT%H:%M:%S")

    def prepare_url(self, path, params={}):
        if self.token is not None:
            sig = hmac.new(self.token['key'].encode(), digestmod=hashlib.sha1)
            sig.update(self.method.lower().encode())
            sig.update(self.service.lower().encode())

            ts = self.get_timestamp(self.token['server_offset'])
            sig.update(ts.encode())
            params['timestamp'] = ts

            sig.update(self.token['identifier'].lower().encode())

            params['signature-method'] = 'auth'
            params['signature-version'] = self.version
            params['signature'] = base64.standard_b64encode(sig.digest())

        self.url = "%s/%s/%d/%s" % (
            self.base_path, self.service, self.version,
            urllib.parse.quote(path))
        if params:
            self.url += "?%s" % urllib.parse.urlencode(params)

    def log_request(self, method, url):
        self.log.debug("%s %s", method, url)

    def log_response(self, data):
        self.log.debug("Response: %s", data)

    def perform(self, connection):
        assert(self.url is not None)

        self.log_request(self.method, self.url)
        connection.request(self.method, self.url)

        response = connection.getresponse()
        if response.status != http.OK:
            raise RuntimeError(
                "HTTP error performing {} request: {} {}".format(
                    self.service, response.status, response.reason))

        data = response.read().decode("utf-8")
        self.log_response(data)

        root = ET.fromstring(data)
        if root.tag != RequestBase.ROOT_TAG:
            raise RuntimeError("Unknown root tag in XML")

        xpath = "./%s[@name='%s']" % (RequestBase.SERVICE_TAG, self.service)
        tags = root.findall(xpath)
        if len(tags) != 1:
            raise RuntimeError("Unexpected number of children in XML")

        error = tags[0].find(RequestBase.ERROR_TAG)
        if error is not None:
            raise RequestError(error)

        self.parse_response(tags[0])

    def parse_response(self, tag):
        pass


class AuthenticationRequest(RequestBase):
    def __init__(self, username, password):
        super().__init__(service='authentication')
        self.password = password
        self.prepare_url(username, {'password': password})

    def log_request(self, method, url):
        password = urllib.parse.quote_plus(self.password)
        super().log_request(method, url.replace(password, '<password>'))

    def parse_response(self, tag):
        d = datetime.strptime(tag.get("creation-date"), "%m/%d/%Y %I:%M:%S %p")
        self.server_offset = datetime.now() - d

        child = tag.find(self.service)
        self.identifier = child.get("identifier")
        self.key = child.get("key")

    def get_token(self):
        return {'identifier': self.identifier, 'key': self.key,
                'server_offset': self.server_offset}


class LogoutRequest(RequestBase):
    def __init__(self, token):
        super().__init__(service='authentication', token=token,
                         method='DELETE')
        self.prepare_url(token['identifier'])


class PlantListRequest(RequestBase):
    def __init__(self, token):
        super().__init__(service='plantlist', token=token)
        self.prepare_url(token['identifier'])
