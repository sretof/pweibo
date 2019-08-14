#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'

import re

import conf.db as dbc


class TLFeedAly:
    @staticmethod
    def isad(curl):
        ad = False
        for adurl in dbc.ADURL:
            if adurl in curl:
                ad = True
                break
        return ad

    @staticmethod
    def alyfeedinfo(feed):
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

    @staticmethod
    def alydetailinfo(feed):
        unamed = feed.select_one('div.WB_detail > div.WB_info a:first-child')
        curltimed = feed.select_one('div.WB_detail > div.WB_from.S_txt2 a:first-child')
        uname = unamed.text
        curl = curltimed.get('href', '')
        curl = curl.split('?', 1)[0]
        if not curl.startswith('http'):
            curl = 'https://weibo.com' + curl
        ctime = curltimed.get('title', '')
        return curl, uname, ctime

    @staticmethod
    def alygtlfeeds(feeds, stasmid, endsmid, endday):
        contlist = []
        doclist = []
        bkdict = {}
        for feed in feeds:
            try:
                mid, uid, ruid, detail = TLFeedAly.alyfeedinfo(feed)
                if detail is None or not mid or not uid:
                    contlist.append({'type': 11, 'mid': mid, 'feed': str(feed)})
                    continue
                curl, uname, ctime = TLFeedAly.alydetailinfo(feed)
                if not curl or not ctime:
                    contlist.append({'type': 12, 'mid': mid, 'feed': str(feed)})
                    continue
                if TLFeedAly.isad(curl):
                    contlist.append({'type': 13, 'mid': mid, 'feed': str(feed)})
                    continue
                cday = ctime[0:4] + ctime[5:7] + ctime[8:10]
                smid = cday + smid
                if smid >= stasmid:
                    contlist.append({'type': 21, 'mid': mid, 'smid': smid, 'stasmid': stasmid})
                    continue
                if smid <= endsmid:
                    bkdict = {'type': 61, 'mid': mid, 'smid': smid, 'endsmid': endsmid}
                    break
                if cday < endday:
                    bkdict = {'type': 62, 'mid': mid, 'smid': smid, 'cday': cday}
                    break
            except Exception as fex:
                pass
        return bkdict, doclist, contlist
