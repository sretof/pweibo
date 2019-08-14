#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'
import json
import logging
import re

from bs4 import BeautifulSoup

import conf.db as dbc
import util.caldate as cald
import util.tulog as logger
import wbutil.wbmon as wbmon
from wbutil import TLFeedAly
from wbutil import WbComp


class WbGTlCmp:
    GLOGGER = logger.TuLog('wbgtlcmp', '/../log', True, logging.WARNING).getlog()

    def __init__(self, wbcomp):
        self.wbcomp = wbcomp
        self.mlogger = WbGTlCmp.GLOGGER

    @staticmethod
    def alygtlpageinfo(paged):
        hemid = ''
        hpge = ''
        sem = paged.select_one('em[node-type="feedsincemaxid"]')
        if sem is not None:
            semad = sem.get('action-data', '')
            psemad = r'since_id=(\d+)'
            rtext = re.findall(psemad, semad, re.S)
            if len(rtext) > 0:
                hemid = rtext[0]
        lazyd = paged.select_one('div.WB_cardwrap.S_bg2[node-type="lazyload"]')
        if lazyd is not None:
            hpge = lazyd.get('action-data', '')
        feeds = paged.select('div.WB_cardwrap[tbinfo]')
        return hemid, hpge, feeds

    def __fgrouptlpage(self, gid, gtlurl):
        rcode = ''
        hemid = ''
        hpge = {}
        feeds = []
        try:
            rcode, text = self.wbcomp.gethtml(gtlurl)
            if rcode == 200:
                tjson = json.loads(text)
                gpsoup = BeautifulSoup(tjson['data'], 'lxml')
                hemid, hpge, feeds = WbGTlCmp.alygtlpageinfo(gpsoup)
        except Exception as fpex:
            self.mlogger.exception(fpex)
        if not hemid:
            self.mlogger.warning('WbGTlCmp fgrouptlpage EEEEE not hemid=====>gid:{},rcode:{},feedslen:{},hemid:{},page:{},gtlurl:{}'.format(
                gid, rcode, len(feeds), hemid, hpge, gtlurl))
        else:
            self.mlogger.debug('WbGTlCmp fgrouptlpage=====>gid:{},rcode:{},feedslen:{},hemid:{},page:{},gtlurl:{}'.format(
                gid, rcode, len(feeds), hemid, hpge, gtlurl))
        return hemid, hpge, feeds

    def fgroupstl(self):
        gtlmaxmid = wbmon.getgtlmaxmid()
        for gid in dbc.TLGIDS:
            print(gid, '==', gtlmaxmid.get(gid, ''))
            # fgweibo.fgrouptl(gid, maxmid=int(gsmmid.get(gid, '0')))

    def fgrouptl(self, gid, stasmid='', endsmid='', endday=''):
        if not endday:
            endday = cald.getdaystr(cald.calmonths(x=12))
        gtlurl = 'https://weibo.com/aj/mblog/fsearch?gid={}&_rnd={}'.format(gid, cald.gettimestamp())
        # if hisp:
        #     gtlurl = 'https://weibo.com/aj/mblog/fsearch?{}&end_id={}&min_id={}&gid={}&__rnd={}'.format(
        #         hisp['page'], hisp['emid'], hisp['mmid'], gid, cald.gettimestamp())
        hemid, hpge, feeds = self.__fgrouptlpage(gid, gtlurl)
        hmmid = TLFeedAly.alygtlfeeds(feeds, stasmid, endsmid, endday)


if __name__ == '__main__':
    wbun = 'sretof@live.cn'
    wbpw = '1122aaa'
    owbcomp = WbComp(wbun, wbpw)
    owbcomp.login()
    gtlcmp = WbGTlCmp(owbcomp)
    # gtlcmp.fgroupstl()
    gtlcmp.fgrouptl('3909747545351455')
