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
#        self.cache = NyaaCache(self)
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
        # only poll Nyaa every 10 minutes max
        self.minTime = 10

    ###################################################################################################
    def updateCache(self):
        re_title_url = self.provider.proxy._buildRE(self.provider.re_title_url)
        if not self.shouldUpdate():
            return
        data = self._getData()
        # as long as the http request worked we count this as an update
        if data:
            self.setLastUpdate()
        else:
            return []
        # now that we've loaded the current RSS feed lets delete the old cache
        logger.log(u"Clearing "+self.provider.name+" cache and updating with new information")
        self._clearCache()
        match = re.compile(re_title_url, re.DOTALL).finditer(urllib.unquote(data))
        if not match:
            logger.log(u"The Data returned from the Nyaa is incomplete, this result is unusable", logger.ERROR)
            return []
                
        for torrent in match:
            #accept torrent only from Trusted people
            if sickbeard.Nyaa_TRUSTED and re.search('(VIP|Trusted|Helpers)',torrent.group(0))== None:
                logger.log(u"Nyaa Provider found result "+torrent.group('title')+" but that doesn't seem like a trusted result so I'm ignoring it",logger.DEBUG)
                continue
            
            item = (torrent.group('title').replace('_','.'),torrent.group('url'))
            self._parseItem(item)

    ###################################################################################################
    def _getData(self):
        url = self.provider.proxy._buildURL(self.provider.url + 'tv/latest/') #url for the last 50 tv-show
        logger.log(u"Nyaa cache update URL: "+ url, logger.DEBUG)
        data = self.provider.getURL(url)
        return data

    ###################################################################################################
    def _parseItem(self, item):
        (title, url) = item
        if not title or not url:
            return
        logger.log(u"Adding item to cache: "+title, logger.DEBUG)
        self._addCacheEntry(title, url)

class NyaaWebproxy:
    ###################################################################################################
    def __init__(self):
        self.Type   = 'GlypeProxy'
        self.param  = 'browse.php?u='
        self.option = '&b=32'
        
    ###################################################################################################
    def isEnabled(self):
        """ Return True if we Choose to call TPB via Proxy """ 
        return sickbeard.Nyaa_PROXY
    
    ###################################################################################################
    def getProxyURL(self):
        """ Return the Proxy URL Choosen via Provider Setting """
        return str(sickbeard.Nyaa_PROXY_URL)
    
    ###################################################################################################
    def _buildURL(self,url):
        """ Return the Proxyfied URL of the page """ 
        url = url.replace(provider.url,sickbeard.Nyaa_URL_OVERRIDE) if sickbeard.Nyaa_URL_OVERRIDE else url
        if self.isEnabled():
            url = self.getProxyURL() + self.param + url + self.option   
        return url

    ###################################################################################################
    def _buildRE(self,re):
        """ Return the Proxyfied RE string """
        if self.isEnabled():
            re = re %('&amp;b=32','&amp;b=32')
        else:
            re = re %('','')   
        return re

provider = NyaaProvider()
