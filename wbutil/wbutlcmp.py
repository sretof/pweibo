#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'
import json
import logging
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup

import conf.db as dbc
import util.caldate as cald
import util.tulog as logger
import wbutil.wbmon as wbmon
from wbutil import TLFeedAly
from wbutil import TLDetailAly
from wbutil import WbComp
from wbutil import WbPageCmp


class WbUTlCmp:
    def __init__(self, wbcomp, pagecmp=None, mlogger=None):
        if mlogger is None:
            mlogger = logger.TuLog('wbutlcmp', '/log', True, logging.INFO).getlog()
        self.wbcomp = wbcomp
        self.mlogger = mlogger
        self.fguexecutor = ThreadPoolExecutor(max_workers=1)
        self.gudictlock = threading.Lock()
        self.gudict = {}
        self.uidunamedict = {}
        if pagecmp is None:
            pagecmp = WbPageCmp(wbcomp, mlogger)
        self.pagecmp = pagecmp

    # def fgumidexist(self, gid, muid):
    #     for cgid in dbc.TLGIDS:
    #         if cgid == gid:
    #             break
    #         if cgid in self.gudict and muid in self.gudict[cgid]:
    #             return True
    #     return False

    def fmembertl(self, gid, uid, stasmid='', endsmid='', endday=''):
        if not endday:
            endday = cald.getdaystr(cald.calmonths(x=150))
        gtlurl = 'https://weibo.com/aj/mblog/fsearch?gid={}&_rnd={}'.format(gid, cald.gettimestamp())
        hemid = '0'
        hpge = '1'
        hmmid = '0'
        docct = 0
        rcnt = 0
        while hemid and hpge and hmmid:
            hsleeptime = random.randint(4, 24)
            hsleeptime = round(hsleeptime * 0.1, 1)
            time.sleep(hsleeptime)
            rcode, hemid, hpge, feeds = self.__fgrouptlpage(gtlurl)
            if not hemid:
                if len(feeds) == 0:
                    self.mlogger.warning('WbGTlCmp:fgrouptl:fgrouptlpage EX none hemid;gid:{},rcode:{},feedslen:{},hemid:{},hpage:{},rcnt:{},gtlurl:{}'.format(
                        gid, rcode, len(feeds), hemid, hpge, rcnt, gtlurl))
                else:
                    self.mlogger.error('WbGTlCmp:fgrouptl:fgrouptlpage EX none hemid;gid:{},rcode:{},feedslen:{},hemid:{},hpage:{},rcnt:{},gtlurl:{}'.format(
                        gid, rcode, len(feeds), hemid, hpge, rcnt, gtlurl))
                if rcnt < 2:
                    time.sleep(60)
                    hemid = '0'
                    hpge = '1'
                    hmmid = '0'
                elif 2 <= rcnt < 4:
                    hemid = '0'
                    hpge = '1'
                    hmmid = '0'
                    self.wbcomp.refresh(self.wbcomp.wbuuid, (rcnt - 1) * 10 * 60, True)
                else:
                    raise Exception('fgrouptl EX:gtlurl:{}'.format(gtlurl))
                rcnt = rcnt + 1
            else:
                self.mlogger.debug(
                    'WbGTlCmp:fgrouptl:fgrouptlpage;gid:{},rcode:{},feedslen:{},hemid:{},hpage:{},gtlurl:{}'.format(
                        gid, rcode, len(feeds), hemid, hpge, gtlurl))
                rcnt = 0
            if len(feeds) > 0:
                hmmid, bkdict, doclist, ctlist, exdoms = TLFeedAly.alygtlfeeds(feeds, stasmid, endsmid, endday)
                if bkdict:
                    self.mlogger.debug('WbGTlCmp:fgrouptl:alygtlfeeds END;gid:{},bk:{},url:{}'.format(gid, bkdict, gtlurl))
                if len(exdoms) > 0:
                    self.mlogger.warning('WbGTlCmp:fgrouptl:alygtlfeeds EXDOMS;gid:{},exdoms:{},url:{}'.format(gid, exdoms, gtlurl))
                if len(ctlist) > 0:
                    self.mlogger.debug('WbGTlCmp:fgrouptl:alygtlfeeds continue;gid:{},ctlist:{},url:{}'.format(gid, ctlist, gtlurl))
                for doc in doclist:
                    try:
                        hasvideo = TLDetailAly.chkandudpmediamtype(gid, doc['media'])
                        if 'fwddoc' in doc and doc['fwddoc'] is not None and doc['fwddoc'] and 'media' in doc['fwddoc'] and doc['fwddoc']['media'] is not None:
                            TLDetailAly.chkandudpmediamtype(gid, doc['fwddoc']['media'])
                        wbmon.savedoc(gid, doc)
                        docct = docct + 1
                        if len(doc['media']) > 0:
                            if hasvideo:
                                self.vdownfexecutor.submit(self.pagecmp.downmedia, doc['mid'])
                            else:
                                self.downfexecutor.submit(self.pagecmp.downmedia, doc['mid'])
                            # exmedias = self.wbcomp.downmedia(doc['mid'])
                            # if len(exmedias) > 0:
                            #     self.mlogger.error('WbGTlCmp:fgrouptl:downmedia EX;exmedias:{}'.format(exmedias))
                    except Exception as ex:
                        self.mlogger.exception(ex)
                        self.mlogger.error('WbGTlCmp:fgrouptl:savedoc EX;ex:{},gid{},mid:{},curl:{}'.format(str(ex), gid, doc['mid'], doc['cturl']))
                gtlurl = 'https://weibo.com/aj/mblog/fsearch?{}&end_id={}&min_id={}&gid={}&__rnd={}'.format(
                    hpge, hemid, hmmid, gid, cald.gettimestamp())
        return docct

    def __fgroupuids(self, gid):
        href = 'https://weibo.com/1795005665/myfollow?gid={}'.format(gid)
        while href:
            self.mlogger.debug('WbUTlCmp:__fgroupuids gid:{},href:{}'.format(gid, href))
            text = self.wbcomp.gethtml(href)[1]
            rpg = r'<script>FM\.view\({"ns":"pl\.relation\.myFollow\.index",(.*?)\)</script>'
            jtext = re.findall(rpg, text, re.S)
            jtext = '{' + jtext[0]
            ptext = json.loads(jtext)
            thtml = ptext['html']
            soup = BeautifulSoup(thtml, 'lxml')
            uidlis = soup.select('div.member_box > ul.member_ul > li.member_li[action-data]')
            for uidli in uidlis:
                acd = uidli['action-data']
                mumap = WbComp.splitacd(acd, 'uid', 'screen_name')
                if 'uid' not in mumap:
                    self.mlogger.warning('WbUTlCmp:__fgroupuids uid none uidli:{}'.format(str(uidli)))
                    continue
                elif mumap['uid'] in self.gudict:
                    self.mlogger.warning('WbUTlCmp:__fgroupuids uid exist uid:{},uname:{}'.format(mumap['uid'], mumap['screen_name']))
                    continue
                else:
                    self.gudict[mumap['uid']] = gid
                    self.uidunamedict[mumap['uid']] = mumap.get('screen_name', '')
            npa = soup.select_one('div.WB_cardpage > div.W_pages a.page.next')
            if npa is not None and npa.get('href', ''):
                href = WbComp.fillwbhref(npa['href'])
            else:
                href = ''

    def fgroupsuids(self):
        self.mlogger.debug('WbUTlCmp:fgroupsuids START')
        self.gudictlock.acquire()
        try:
            self.gudict = {}
            self.uidunamedict = {}
            for gid in dbc.TLGIDS:
                self.mlogger.debug('WbUTlCmp:fgroupsuids START=====>gid:{}'.format(gid))
                try:
                    self.__fgroupuids(gid)
                    self.mlogger.debug('WbUTlCmp:fgroupsuids END=====>gid:{}'.format(gid))
                except Exception as guex:
                    self.mlogger.error('WbUTlCmp:fgroupsuids EX=====>gid:{},ex:{}'.format(gid, str(guex)))
            pusers = wbmon.getflwusers()
            pusersdict = {}
            for puser in pusers:
                pusersdict[puser['uid']] = puser
            for uid in self.gudict:
                if uid in pusersdict:
                    wbmon.updateflwuser({'uid': uid, 'gid': self.gudict[uid], 'uname': self.uidunamedict[uid]})
                    del pusersdict[uid]
                else:
                    wbmon.updateflwuser({'uid': uid, 'gid': self.gudict[uid], 'uname': self.uidunamedict[uid]})
            for puser in pusersdict:
                wbmon.updateflwuser({'uid': puser}, 1)
        finally:
            self.gudictlock.release()
        self.mlogger.debug('WbUTlCmp:fgroupsuids END=====>gudict:{}'.format(self.gudict))

    def fgroupsuidsl(self):
        while 1:
            self.fgroupsuids()
            ih = random.randint(4, 48)
            time.sleep(3600 * ih)

    def fgroupsuidsex(self):
        self.fguexecutor.submit(self.fgroupsuidsl)
        #self.fgroupsuidsl()
        time.sleep(60*5)

    def getgudict(self):
        self.gudictlock.acquire()
        rdict = self.gudict
        self.gudictlock.release()
        return rdict

    def hasuid(self, uid):
        rgid = self.getgudict().get(uid, '')
        return rgid


if __name__ == '__main__':
    glogger = logger.TuLog('wbutlcmptest', '/log', True, logging.DEBUG).getlog()
    wglogger = logger.TuLog('wbutlwbcomptest', '/log', True, logging.DEBUG).getlog()
    wbun = 'sretof@live.cn'
    wbpw = '1122aaa'
    owbcomp = WbComp(wbun, wbpw, wglogger)
    owbcomp.login()
    outlcmp = WbUTlCmp(owbcomp, glogger)
    outlcmp.fgroupsuidsex()
    time.sleep(1)
    print(len(outlcmp.getgudict()))
    # gtlcmp.fgrouptl('3951063348253369', endsmid='201908154405578203590498')
