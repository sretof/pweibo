# -*- coding:utf-8 -*-
import logging
import random
import time

import conf.db as dbc
import util.caldate as cald
import util.tulog as logger
from wbutil import WbComp
from wbutil import WbGChatCmp


def fchatslp(onhour, slogger):
    oslt = random.randint(10, 60 * 10)
    if 9 < onhour < 18:
        oslt = random.randint(4, 14)
    oslt = round(oslt * 0.1, 1)
    if onhour > 21 or onhour < 8:
        oslt = random.randint(60 * 30, 60 * 120)
    slogger.info('wbchat sleep;hour:{},sleep:{}sec'.format(onhour, oslt))
    time.sleep(oslt)


if __name__ == '__main__':
    wclogger = logger.TuLog('wbchat', '/log', True, logging.WARNING).getlog()
    wbcomp = WbComp(dbc.WBUN, dbc.WBPW, picdir='/www/oneds/weibopicfz', mlogger=wclogger)
    wbcomp.login()
    chatcmp = WbGChatCmp(wbcomp, mlogger=wclogger)
    while 1:
        lonhour = cald.gethour()
        chatcmp.fchatstl()
        fchatslp(lonhour, wclogger)
