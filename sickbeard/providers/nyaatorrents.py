###################################################################################################
# Author: Bryan Ching
# Based on work by: Mr_Orange <mr_orange@hotmail.it>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of Sick Beard.
#
# Sick Beard is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Sick Beard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.
###################################################################################################

import re
import urllib, urllib2
import sys
import datetime
import os
import time

import sickbeard
import generic
from sickbeard.common import Quality
from sickbeard import logger
from sickbeard import tvcache
from sickbeard import helpers
from sickbeard import show_name_helpers
from sickbeard import db
from sickbeard.common import Overview
from sickbeard.exceptions import ex
from sickbeard import encodingKludge as ek

from xml.dom.minidom import parseString

from sickbeard import classes

from sickbeard import exceptions, logger, db
from sickbeard.common import *
from sickbeard import tvcache
from lib.dateutil.parser import parse as parseDate

class NyaaProvider(generic.TorrentProvider):
    ###################################################################################################
    def __init__(self):
        generic.TorrentProvider.__init__(self, "nyaatorrents")
        self.supportsBacklog = True
        self.supportsAbsoluteNumbering = True
        self.cache = NyaaCache(self)
        self.url = 'http://nyaa.eu/?'
 
    ###################################################################################################
    def isEnabled(self):
        return sickbeard.NYAATORRENTS
    
    ###################################################################################################
    def imageName(self):
        return 'nyaa.png'
    
    ###################################################################################################
    def getQuality(self, item):
        
        quality = Quality.nameQuality(item[0])
        return quality    
    
    ###################################################################################################
    def _get_airbydate_season_range(self, season):
            if season == None:
                return ()
        
            year, month = map(int, season.split('-'))
            min_date = datetime.date(year, month, 1)
            if month == 12:
                max_date = datetime.date(year, month, 31)
            else:    
                max_date = datetime.date(year, month+1, 1) -  datetime.timedelta(days=1)

            return (min_date, max_date)    
      
    def _get_season_search_strings(self, show, season, scene=False):
        names = []
        if season is -1:
            names = [show.name.encode('utf-8')]
        names.extend(show_name_helpers.makeSceneSeasonSearchString(show, season, scene=scene))
        return names

    def _get_episode_search_strings(self, ep_obj):
        # names = [(ep_obj.show.name + " " + str(ep_obj.absolute_number)).encode('utf-8')]
        names = show_name_helpers.makeSceneSearchString(ep_obj)
        return names

    def _doSearch(self, search_string, show=None):
        if show and not show.is_anime:
            logger.log(u"" + str(show.name) + " is not an anime skiping " + str(self.name))
            return []

        params = {
            "page": "rss",
            "term": search_string.encode('utf-8'),
            "sort": "2"
        }

        searchURL = self.url + urllib.urlencode(params)

        logger.log(u"Search string: " + searchURL, logger.DEBUG)

        searchResult = self.getURL(searchURL)

        # Pause to avoid 503's
        time.sleep(5)

        if searchResult == None:
            return []

        try:
            parsedXML = parseString(searchResult)
            items = parsedXML.getElementsByTagName('item')
        except Exception, e:
            logger.log(u"Error trying to load NYAA RSS feed: " + str(e).decode('utf-8'), logger.ERROR)
            return []

        results = []

        for curItem in items:
            (title, url) = self._get_title_and_url(curItem)

            if not title or not url:
                logger.log(u"The XML returned from the NYAA RSS feed is incomplete, this result is unusable: " + searchResult, logger.ERROR)
                continue

            url = url.replace('&amp;', '&')

            results.append(curItem)

        return results
   
   ###################################################################################################
    def downloadResult(self, result):
        """
        Save the result to disk.
        """
        
        #Hack for rtorrent user (it will not work for other torrent client)
        if sickbeard.TORRENT_METHOD == "blackhole" and result.url.startswith('magnet'): 
            magnetFileName = ek.ek(os.path.join, sickbeard.TORRENT_DIR, helpers.sanitizeFileName(result.name) + '.' + self.providerType)
            magnetFileContent = 'd10:magnet-uri' + `len(result.url)` + ':' + result.url + 'e'

            try:
                fileOut = open(magnetFileName, 'wb')
                fileOut.write(magnetFileContent)
                fileOut.close()
                helpers.chmodAsParent(magnetFileName)
            except IOError, e:
                logger.log("Unable to save the file: "+ex(e), logger.ERROR)
                return False
            logger.log(u"Saved magnet link to "+magnetFileName+" ", logger.MESSAGE)
            return True

class NyaaCache(tvcache.TVCache):
    ###################################################################################################
    def __init__(self, provider):
        tvcache.TVCache.__init__(self, provider)
        self.url = 'http://nyaa.eu/?'
        self.minTime = 1 

    def _getRSSData(self):
        params = {
            "page": "rss",
        }

        url = self.url + urllib.urlencode(params)

        logger.log(u"FANZUB cache update URL: " + url, logger.DEBUG)

        data = self.provider.getURL(url)

        return data

    def _checkItemAuth(self, title, url):
        return True

provider = NyaaProvider()
