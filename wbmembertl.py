# -*- coding:utf-8 -*-
import datetime
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor

import conf.db as dbc
import util.tulog as logger
from wbutil import WbComp
from wbutil import WbUTlCmp

GLOGGER = logger.TuLog('wbmembertl', '/log', True, logging.DEBUG).getlog()


def fgtlslp():
    nhour = datetime.datetime.now().hour
    sleeptime = random.randint(60 * 5, 60 * 30)
    if 0 <= nhour < 9:
        sleeptime = random.randint(60 * 60, 60 * 180)
    GLOGGER.info('wbgrouptl sleep;hour:{},sleep:{}min'.format(nhour, int(sleeptime / 60)))
    time.sleep(sleeptime)


def fgroupsuidst(putlcmp):
    while 1:
        putlcmp.fgroupsuids()
        ih = random.randint(4, 48)
        time.sleep(3600 * ih)


if __name__ == '__main__':
    wbcomp = WbComp(dbc.WBUN, dbc.WBPW, mlogger=GLOGGER)
    wbcomp.login()
    utlcmp = WbUTlCmp(wbcomp, mlogger=GLOGGER)
    fguexecutor = ThreadPoolExecutor(max_workers=1)
    fguexecutor.submit(fgroupsuidst, utlcmp)
    # while 1:
    #     gtlcmp.fgroupstl()
    #     fgtlslp()
