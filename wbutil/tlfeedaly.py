#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'

import re

import conf.db as dbc
from wbutil.tldetailaly import TLDetailAly


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
        ctlist = []
        doclist = []
        bkdict = {}
        exdoms = []
        hmmid = ''
        for feed in feeds:
            mid, uid, ruid, detail = TLFeedAly.alyfeedinfo(feed)
            if detail is None or not mid or not uid:
                exdoms.append({'type': 11, 'mid': mid, 'feed': str(feed)})
                continue
            curl, uname, ctime = TLFeedAly.alydetailinfo(feed)
            if not curl or not ctime:
                exdoms.append({'type': 12, 'mid': mid, 'feed': str(feed)})
                continue
            if TLFeedAly.isad(curl):
                ctlist.append({'type': 13, 'mid': mid, 'feed': str(feed)})
                continue
            cday = ctime[0:4] + ctime[5:7] + ctime[8:10]
            smid = cday + mid
            if stasmid and smid >= stasmid:
                ctlist.append({'type': 21, 'mid': mid, 'smid': smid, 'stasmid': stasmid})
                continue
            if endsmid and smid <= endsmid:
                bkdict = {'type': 61, 'mid': mid, 'smid': smid, 'endsmid': endsmid}
                hmmid = ''
                break
            if endday and cday < endday:
                bkdict = {'type': 62, 'mid': mid, 'smid': smid, 'cday': cday}
                hmmid = ''
                break
            hmmid = mid
            # txt div
            txt, mtype, files, skipdoms = TLDetailAly.getdetailtxt(TLFeedAly.seltxtdiv(feed))
            # media div
            mtype, files, skipdoms = TLDetailAly.getdetailmedia(TLFeedAly.selmediadiv(feed), uid, mid,
                                                                mtype, files, skipdoms)
            # fwd div
            mtype, fwdhsave, fwdmid, fwddoc, fskipdoms = TLDetailAly.getfwddoc(TLFeedAly.selfwddiv(feed), mtype)
            if len(skipdoms) > 0 or len(fskipdoms) > 0:
                exdom = {'mid': mid}
                if len(skipdoms) > 0:
                    exdom['exdom'] = skipdoms
                if len(fskipdoms) > 0:
                    exdom['fexdom'] = fskipdoms
                exdoms.append(exdom)
            doc = {'uid': uid, 'uname': uname, 'mid': mid, 'mtype': mtype, 'cturl': curl, 'ctime': ctime,
                   'cday': cday, 'ctext': txt, 'media': files, 'fwdhsave': fwdhsave, 'fwdmid': fwdmid,
                   'fwddoc': fwddoc}
            doclist.append(doc)
        return hmmid, bkdict, doclist, ctlist, exdoms

    @staticmethod
    def seltxtdiv(feed):
        return feed.select_one('div.WB_detail > div.WB_text.W_f14')

    @staticmethod
    def selmediadiv(feed):
        return feed.select_one('div.WB_detail > div.WB_media_wrap > div.media_box')

    @staticmethod
    def selfwddiv(feed):
        return feed.select_one('div.WB_detail > div.WB_feed_expand > div.WB_expand')
