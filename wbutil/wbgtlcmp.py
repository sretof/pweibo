# -*- coding:utf-8 -*-
import json
import logging
import re

from bs4 import BeautifulSoup

import conf.db as dbc
import util.caldate as cald
import util.tulog as logger
import wbutil.wbmon as wbmon
from wbutil import TLFeedInf
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

    def __fgrouptlpage(self, gid, hisp={}):
        gtlurl = 'https://weibo.com/aj/mblog/fsearch?gid={}&_rnd={}'.format(gid, cald.gettimestamp())
        if hisp:
            gtlurl = 'https://weibo.com/aj/mblog/fsearch?{}&end_id={}&min_id={}&gid={}&__rnd={}'.format(
                hisp['page'], hisp['emid'], hisp['mmid'], gid, cald.gettimestamp())
        rcode, text, ghex = self.wbcomp.gethtml(gtlurl)
        hemid = ''
        hpge = {}
        feeds = []
        if rcode == 200:
            try:
                tjson = json.loads(text)
                gpsoup = BeautifulSoup(tjson['data'], 'lxml')
                hemid, hpge, feeds = WbGTlCmp.alygtlpageinfo(gpsoup)
            except Exception as fgex:
                self.mlogger.error('fgrouptlpage load and soup error,text:{}'.format(text))
        self.mlogger.info('fgrouptlpage==========>rcode:{},feedslen:{},HEMID:{},page:{},gtlurl:{}'.format(rcode, len(feeds), hemid, hpge, gtlurl))
        return gtlurl, hemid, hpge, feeds

    def __alygtlfeeds(self, gid, gtlurl, feeds):
        for feed in feeds:
            mid, uid, ruid, detail = TLFeedInf.alytlfeedinfo(feed)
            if detail is None or not mid or not uid:
                self.mlogger.warning('fgroupct maxmid continue...gid:{},mid:{},uid:{},url:{}'.format(gid, mid, uid, gtlurl))
                continue
            print(mid)
            # if mid <= maxmid:
            #     hmmid = '-1'
            #     break
            #
            # curl, uname, ctime = WbComp.alydetailinfo(feed)
            # if not curl or not ctime:
            #     self.mlogger.warning('fgroupct maxmid continue...gid:{},mid:{},uid:{},curl:{},ctime:{},url:{}'.format(gid, mid, uid, curl, ctime, gcturl))
            #     continue
            # isad = False
            # for adurl in dbc.ADURL:
            #     if adurl in curl:
            #         isad = True
            #         break
            # if isad:
            #     continue
            #
            # if cald.now().year - int(ctime[0:4]) > maxy:
            #     self.mlogger.info('fgroupct maxy stop....gid:{},mid:{},ctime:{},url:{}'.format(gid, mid, ctime, gcturl))
            #     hmmid = '-2'
            #     break
            #
            # if not hemid:
            #     hemid = mid
            #     hpge = hpge or hisp.get('page', '') or 'pre_page=1&page=1'
            #
            # self.mlogger.info('SSSSSSSSSS-CURL====================>fgroupct url:{}'.format(curl))
            # # 0 txt;13/a l txt;14 link;21 pics;22 video;31 fwd
            # mtype = '0'
            # files = []
            #
            # # txt div
            # txtdiv = feed.select_one('div.WB_detail > div.WB_text.W_f14')
            # txt, mtype, files = PWeiBo.getdetailtxt(txtdiv, mtype, files)
            # # media div
            # mediadiv = feed.select_one('div.WB_detail > div.WB_media_wrap > div.media_box')
            # mtype, files = PWeiBo.getdetailmedia(mediadiv, uid, mid, mtype, files)
            # # fwd div
            # fwddiv = feed.select_one('div.WB_detail > div.WB_feed_expand > div.WB_expand')
            # fwdhsave = None
            # fwdmid = None
            # fwddoc = None
            # if fwddiv is not None:
            #     fwdhsave, fwdmid, fwddoc = PWeiBo.getfwddoc(fwddiv)
            #     mtype = mtype + '31'
            # hmmid = mid
            # try:
            #     savedetail(gid, uid, uname, mid, mtype, curl, ctime, txt, files, fwdhsave, fwdmid, fwddoc)
            #     if len(files) > 0:
            #         PWeiBo.downfexecutor.submit(PWeiBo.downtlmedia, self, mid)
            # except Exception as ex:
            #     PWeiBo.GLOGGER.error('savedetail error:ex:{},gid{},mid:{},uid:{}'.format(str(ex), gid, mid, uid))
            #     # PWeiBo.GLOGGER.exception(ex)

    def fgroupstl(self):
        gtlmaxmid = wbmon.getgtlmaxmid()
        for gid in dbc.TLGIDS:
            print(gid, '==', gtlmaxmid.get(gid, ''))
            # fgweibo.fgrouptl(gid, maxmid=int(gsmmid.get(gid, '0')))

    def fgrouptl(self, gid, stamid='', endmid='', endday=''):
        if not endday:
            endday = cald.getdaystr(cald.calmonths(x=12))
        gtlurl, hemid, hpge, feeds = self.__fgrouptlpage(gid)
        hmmid = ''
        self.__alygtlfeeds(gid, gtlurl, feeds)


if __name__ == '__main__':
    wbun = 'sretof@live.cn'
    wbpw = '1122aaa'
    wbcomp = WbComp(wbun, wbpw)
    wbcomp.login()
    gtlcmp = WbGTlCmp(wbcomp)
    gtlcmp.fgrouptl('3909747545351455')
