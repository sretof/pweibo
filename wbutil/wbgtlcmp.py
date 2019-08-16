#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'
import json
import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup

import conf.db as dbc
import util.caldate as cald
import util.tulog as logger
import wbutil.wbmon as wbmon
from wbutil import TLFeedAly
from wbutil import WbComp


class WbGTlCmp:
    def __init__(self, wbcomp, mlogger=None):
        if mlogger is None:
            mlogger = logger.TuLog('wbgtlcmp', '/log', True, logging.INFO).getlog()
        self.wbcomp = wbcomp
        self.mlogger = mlogger
        self.downfexecutor = ThreadPoolExecutor(max_workers=1)
        self.vdownfexecutor = ThreadPoolExecutor(max_workers=2)

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

    def __fgrouptlpage(self, gtlurl):
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
        return rcode, hemid, hpge, feeds

    def fgroupstl(self):
        gtlmaxmid = wbmon.getgtlmaxmid()
        self.mlogger.info('WbGTlCmp:fgroupstl START=====>gtlmaxmid:{}'.format(gtlmaxmid))
        for gid in dbc.TLGIDS:
            self.mlogger.info('WbGTlCmp:fgroupstl:fgroupstl START=====>gid:{}'.format(gid))
            docct = self.fgrouptl(gid, endsmid=gtlmaxmid.get(gid, ''))
            self.mlogger.info('WbGTlCmp:fgroupstl:fgroupstl END=====>gid:{},ct:{}'.format(gid, docct))
        self.mlogger.info('WbGTlCmp:fgroupstl END=====')

    def fgrouptl(self, gid, stasmid='', endsmid='', endday=''):
        if not endday:
            endday = cald.getdaystr(cald.calmonths(x=12))
        gtlurl = 'https://weibo.com/aj/mblog/fsearch?gid={}&_rnd={}'.format(gid, cald.gettimestamp())
        hemid = '0'
        hpge = '1'
        hmmid = '0'
        docct = 0
        while hemid and hpge and hmmid:
            hsleeptime = random.randint(4, 24)
            hsleeptime = round(hsleeptime * 0.1, 1)
            time.sleep(hsleeptime)
            rcode, hemid, hpge, feeds = self.__fgrouptlpage(gtlurl)
            if not hemid:
                self.mlogger.warning(
                    'WbGTlCmp:fgrouptl:fgrouptlpage EX none hemid;gid:{},rcode:{},feedslen:{},hemid:{},hpage:{},gtlurl:{}'.format(
                        gid, rcode, len(feeds), hemid, hpge, gtlurl))
            else:
                self.mlogger.debug(
                    'WbGTlCmp:fgrouptl:fgrouptlpage;gid:{},rcode:{},feedslen:{},hemid:{},hpage:{},gtlurl:{}'.format(
                        gid, rcode, len(feeds), hemid, hpge, gtlurl))
            hmmid, bkdict, doclist, ctlist, exdoms = TLFeedAly.alygtlfeeds(feeds, stasmid, endsmid, endday)
            if bkdict:
                self.mlogger.debug('WbGTlCmp:fgrouptl:alygtlfeeds END;gid:{},bk:{},url:{}'.format(gid, bkdict, gtlurl))
            if len(exdoms) > 0:
                self.mlogger.warning('WbGTlCmp:fgrouptl:alygtlfeeds EXDOMS;gid:{},exdoms:{},url:{}'.format(gid, exdoms, gtlurl))
            if len(ctlist) > 0:
                self.mlogger.debug('WbGTlCmp:fgrouptl:alygtlfeeds continue;gid:{},ctlist:{},url:{}'.format(gid, ctlist, gtlurl))
            for doc in doclist:
                try:
                    wbmon.savedoc(gid, doc)
                    docct = docct + 1
                    if len(doc['media']) > 0:
                        hasvideo = False
                        for amd in doc['media']:
                            amtype = amd['mtype']
                            if amtype == '22' or amtype == '23':
                                hasvideo = True
                                break
                        if hasvideo:
                            self.vdownfexecutor.submit(self.wbcomp.downmedia, doc['mid'])
                        else:
                            self.downfexecutor.submit(self.wbcomp.downmedia, doc['mid'])
                        # exmedias = self.wbcomp.downmedia(doc['mid'])
                        # if len(exmedias) > 0:
                        #     self.mlogger.error('WbGTlCmp:fgrouptl:downmedia EX;exmedias:{}'.format(exmedias))
                except Exception as ex:
                    self.mlogger.error('WbGTlCmp:fgrouptl:savedoc EX;ex:{},gid{},mid:{},curl:{}'.format(str(ex), gid, doc['mid'], doc['cturl']))
            gtlurl = 'https://weibo.com/aj/mblog/fsearch?{}&end_id={}&min_id={}&gid={}&__rnd={}'.format(
                hpge, hemid, hmmid, gid, cald.gettimestamp())
        return docct


if __name__ == '__main__':
    glogger = logger.TuLog('wbgtlcmp', '/../log', True, logging.DEBUG).getlog()
    wglogger = logger.TuLog('wbcomp', '/../log', True, logging.DEBUG).getlog()
    wbun = 'sretof@live.cn'
    wbpw = '1122aaa'
    owbcomp = WbComp(wbun, wbpw, wglogger)
    owbcomp.login()
    gtlcmp = WbGTlCmp(owbcomp, glogger)
    gtlcmp.fgroupstl()
    # gtlcmp.fgrouptl('3951063348253369', endsmid='201908154405578203590498')
