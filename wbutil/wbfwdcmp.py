#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import util.tulog as logger
import wbutil.wbmon as wbmon
from wbutil import WbComp
from wbutil import WbPageCmp
from wbutil import WbUTlCmp


class WbFwdCmp:
    def __init__(self, wbcomp, wbutlcmp=None, pagecmp=None, mlogger=None):
        if mlogger is None:
            mlogger = logger.TuLog('wbfwdcmp', '/log', True, logging.INFO).getlog()
        self.wbcomp = wbcomp
        if wbutlcmp is None:
            wbutlcmp = WbUTlCmp(wbcomp, mlogger)
            wbutlcmp.fgroupsuidsex()
        if pagecmp is None:
            pagecmp = WbPageCmp(wbcomp, mlogger)
        self.wbutlcmp = wbutlcmp
        self.pagecmp = pagecmp
        self.mlogger = mlogger
        self.fwdexecutor = ThreadPoolExecutor(max_workers=1)

    def ffwddocs(self):
        docs = wbmon.rs2list(wbmon.undownfwd())
        self.mlogger.debug('WbFwdCmp:ffwddocs START=====len:{}'.format(len(docs)))
        for doc in docs:
            mid = doc['mid']
            fmid = doc['fwdmid']
            self.mlogger.debug('WbFwdCmp:ffwddocs ffwddoc START=====>mid:{},fmid:{}'.format(mid, fmid))
            try:
                fctime = doc['fwddoc']['ctime']
                fcday = fctime[0:4] + fctime[5:7] + fctime[8:10]
                self.ffwddoc(doc['gid'], mid, fmid, fcday, doc['fwddoc']['uid'], doc.get('fwdmedia', []))
                self.mlogger.debug('WbFwdCmp:ffwddocs ffwddoc END=====>mid:{},fmid:{}'.format(mid, fmid))
            except Exception as fex:
                self.mlogger.error('WbFwdCmp:ffwddocs ffwddoc EX=====>mid:{},ex:{}'.format(mid, str(fex)))
        self.mlogger.debug('WbFwdCmp:ffwddocs END=====')

    def ffwddoc(self, gid, mid, fmid, fcday, fuid, fmedia):
        alld = True
        for amd in fmedia:
            if not amd['hasd']:
                alld = False
                break
        self.mlogger.debug('WbFwdCmp:ffwddoc check mid:{},alld:{},len(fmedia):{}'.format(mid, alld, len(fmedia)))
        if alld or len(fmedia) == 0 or (self.wbutlcmp is not None and self.wbutlcmp and self.wbutlcmp.hasuid(fuid)):
            self.mlogger.debug('WbFwdCmp:ffwddoc hasdownfwddoc mid:{}'.format(mid))
            wbmon.hasdownfwddoc(mid)
        else:
            self.mlogger.debug('WbFwdCmp:ffwddoc downfwdmedia start mid:{}'.format(mid))
            self.pagecmp.downfwdmedia(gid, mid, fuid, fmid, fcday, fmedia)
        self.mlogger.debug('WbFwdCmp:ffwddoc downfwdmedia end mid:{}'.format(mid))

    def ffwddocsl(self):
        while 1:
            self.ffwddocs()
            # ih = random.randint(1)
            time.sleep(60 * 15)

    def ffwddocsex(self):
        self.fwdexecutor.submit(self.ffwddocsl)


if __name__ == '__main__':
    glogger = logger.TuLog('WbFwdCmp', '/../log', True, logging.DEBUG).getlog()
    wbun = 'sretof@live.cn'
    wbpw = '1122aaa'
    owbcomp = WbComp(wbun, wbpw, mlogger=glogger)
    owbcomp.login()
    ofwdcmp = WbFwdCmp(owbcomp, wbutlcmp='', mlogger=glogger)
    ofwdcmp.ffwddocs()
