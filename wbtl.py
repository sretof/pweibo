# -*- coding:utf-8 -*-
import datetime
import logging
import random
import time

import conf.db as dbc
import util.tulog as logger
from wbutil import WbComp
from wbutil import WbFwdCmp
from wbutil import WbGTlCmp
from wbutil import WbPageCmp
from wbutil import WbUTlCmp


def fgtlslp(slogger):
    nhour = datetime.datetime.now().hour
    sleeptime = random.randint(60 * 5, 60 * 15)
    if 0 <= nhour < 5:
        sleeptime = random.randint(60 * 15, 60 * 60)
    slogger.info('wbgrouptl sleep;hour:{},sleep:{}min'.format(nhour, int(sleeptime / 60)))
    time.sleep(sleeptime)


if __name__ == '__main__':
    tllogger = logger.TuLog('wbtl', '/log', True, logging.WARNING).getlog()
    utllogger = logger.TuLog('[wbtl]wbutl', '/log', True, logging.DEBUG).getlog()
    tlwbcomp = WbComp(dbc.WBUN, dbc.WBPW, mlogger=tllogger)
    tlwbcomp.login()
    utlwbcomp = WbComp(dbc.WBUN, dbc.WBPW, mlogger=utllogger)
    utlwbcomp.login()
    pagecmp = WbPageCmp(tlwbcomp, mlogger=tllogger)
    gtlcmp = WbGTlCmp(tlwbcomp, pagecmp=pagecmp, mlogger=tllogger)
    utlcmp = WbUTlCmp(utlwbcomp, pagecmp=pagecmp, mlogger=utllogger)
    utlcmp.fgroupsuidsex()
    # flogger = logger.TuLog('[wbtl]wbfwdcmp', '/log', True, logging.WARNING).getlog()
    # fwdcmp = WbFwdCmp(tlwbcomp, utlcmp, mlogger=flogger)
    # fwdcmp.ffwddocsex()
    while 1:
        gtlcmp.fgroupstl()
        fgtlslp(tllogger)
