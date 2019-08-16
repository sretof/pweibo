# -*- coding:utf-8 -*-
import datetime
import logging
import random
import time

import conf.db as dbc
import util.tulog as logger
from wbutil import WbComp
from wbutil import WbGTlCmp

GLOGGER = logger.TuLog('wbgrouptl', '/log', True, logging.DEBUG).getlog()


def fgtlslp():
    nhour = datetime.datetime.now().hour
    sleeptime = random.randint(60 * 5, 60 * 30)
    if 0 <= nhour < 9:
        sleeptime = random.randint(60 * 60, 60 * 180)
    GLOGGER.info('wbgrouptl sleep;hour:{},sleep:{}min'.format(nhour, int(sleeptime / 60)))
    time.sleep(sleeptime)


if __name__ == '__main__':
    wbcomp = WbComp(dbc.WBUN, dbc.WBPW)
    wbcomp.login()
    gtlcmp = WbGTlCmp(wbcomp)
    while 1:
        gtlcmp.fgroupstl()
        fgtlslp()
