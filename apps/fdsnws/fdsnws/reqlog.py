#!/usr/bin/python3

# was working with py3.8 originally
# now running python3.12 and it's ...working! if you're downloading fresh from maxmind whatever and get a "bytes error" or see "xrange", that's python2 still. 


##edited version by RCP to help send logs to IRIS


from __future__ import absolute_import, division, print_function

import os
import datetime
import json
import hashlib
import subprocess
import logging
import logging.handlers
import threading

#removed this
#from .utils import py3bstr


mutex = threading.Lock()


class MyFileHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, filename):
        super(MyFileHandler, self).__init__(
            filename, when="midnight", utc=True)

    def rotate(self, source, dest):
        super(MyFileHandler, self).rotate(source, dest)

        if os.path.exists(dest):
            subprocess.Popen(["bzip2", dest])


class Tracker(object):
    def __init__(self, logger, geoip, service, userName, userIP, clientID, userSalt):
        self.__logger = logger
        self.__userName = userName
        self.__userSalt = userSalt
        self.__logged = False

        #if userName:
        #    userID = int(hashlib.md5(py3bstr(userSalt + userName.lower())).hexdigest()[:8], 16)
        #else:
        #    userID = int(hashlib.md5(py3bstr(userSalt + userIP)).hexdigest()[:8], 16)


        self.__data = {
            'service': service,
            #'userID': userID,
            'IP': userIP,
            'clientID': clientID,
            #'userEmail': None,
            'auth': not not userName,
            'userLocation': {'country':{},'continent':{},'region':{},'latlon':{}},
            'created': datetime.datetime.utcnow().isoformat() + 'Z'
        }

        if geoip:
            try: #whole thing is very precarious
                from geoip import geolite2
                ip_loc_data = geolite2.lookup(userIP)
                if ip_loc_data : #sometimes doesn't return anything... 
                    self.__data['userLocation']['country'] = ip_loc_data.country
                    self.__data['userLocation']['continent'] = ip_loc_data.continent
                    region = list(ip_loc_data.subdivisions) #converts from a frozenset back to a string
                    if len(region) > 0:
                        self.__data['userLocation']['region'] = region[0]
                    else:
                        self.__data['userLocation']['region'] = '' 
                    self.__data['userLocation']['latlon'] = ip_loc_data.location
                else:
                    self.__data['userLocation'] = None
            except: pass


        #if (userName and userName.lower().endswith("@gfz-potsdam.de")) or \
        #   userIP.startswith("139.17."):
        #    self.__data['userLocation']['institution'] = "GFZ"

    #pylint: disable=W0613
    def line_status(self, start_time, end_time, network, station, channel,
                    location, restricted, net_class, shared, constraints,
                    volume, status, size, message):

        try:
            trace = self.__data['trace']

        except KeyError:
            trace = []
            self.__data['trace'] = trace

        trace.append({
            'net': network,
            'sta': station,
            'loc': location,
            'cha': channel,
            'start': start_time.iso(),
            'end': end_time.iso(),
            'restricted': restricted,
            'status': status,
            'bytes': size
        })

        #if restricted and status == 'OK':
        #    self.__data['userEmail'] = self.__userName

    # FDSNWS requests have one volume, so volume_status() is called once per request
    def volume_status(self, volume, status, size, message):
        self.__data['status'] = status
        self.__data['bytes'] = size
        self.__data['finished'] = datetime.datetime.utcnow().isoformat() + 'Z'

    def request_status(self, status, message):
        with mutex:
            if not self.__logged:
                if self.__data['clientID'][0:7] not in ["IRISDMC","Health "] and self.__data['status'] != "NODATA":
                    self.__logger.info(json.dumps(self.__data))
                    self.__logged = True


class RequestLog(object):
    def __init__(self, filename, userSalt):
        self.__logger = logging.getLogger("seiscomp.fdsnws.reqlog")
        self.__logger.addHandler(MyFileHandler(filename))
        self.__logger.setLevel(logging.INFO)
        self.__userSalt = userSalt

        try:
            #import GeoIP
            #self.__geoip = GeoIP.new(GeoIP.GEOIP_MEMORY_CACHE) #original version, we're adding the dictionary ourselves
            from geoip import geolite2  #this is a single file we had to copy over from 3.6, then, 3.8, then 3.12
            self.__geoip = 1
            

        except ImportError:
            self.__geoip = None

    def tracker(self, service, userName, userIP, clientID):
        return Tracker(self.__logger, self.__geoip, service, userName, userIP, clientID, self.__userSalt)
