# -*- coding:utf-8 -*-
import logging
import re

import urllib3

import util.tulog as logger

urllib3.disable_warnings()  # 取消警告


class TLFeedInf:
    GLOGGER = logger.TuLog('tlfeedinf', '/../log', True, logging.WARNING).getlog()

    @staticmethod
    def alytlfeedinfo(feed):
        mid = feed.get('mid', '')
        tbinfo = feed.get('tbinfo', '')
        pti = r'ouid=(\d+)&rouid=(\d+)|ouid=(\d+)'
        jtext = re.findall(pti, tbinfo, re.S)
        uid = ''
        ruid = ''
        if len(jtext) > 0:
            uid = jtext[0][2] or jtext[0][0]
            ruid = jtext[0][1]
        detail = feed.select_one('div.WB_detail')
        return mid, uid, ruid, detail
