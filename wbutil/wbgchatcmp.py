# -*- coding:utf-8 -*-
import json
import logging
import os
import random
import threading

import conf.db as dbc
import util.caldate as cald
import util.tulog as logger
import wbutil.wbmon as wbmon
from wbutil import WbComp
from wbutil import WbPageCmp
from wbutil.wbex import WbChatGetDocError


class WbGChatCmp:
    def __init__(self, wbcomp, pagecmp=None, mlogger=None):
        if mlogger is None:
            mlogger = logger.TuLog('wbgchatcmp', '/log', True, logging.DEBUG).getlog()
        self.wbcomp = wbcomp
        self.mlogger = mlogger
        if pagecmp is None:
            self.pagecmp = WbPageCmp(wbcomp, mlogger)

    def savecmsg(self, mid, mtime, mday, msg, gid, fdir):
        buid = str(msg['from_uid'])
        bn = (msg.get('from_user', '') and msg['from_user'].get('screen_name', '')) or buid
        cttype = str(msg['media_type'])
        ct = msg['content']
        fid = ''
        fpath = ''
        hd = 0
        # TEXT
        if cttype == '1':
            fid = msg['fids'][0]
            fp = 'https://upload.api.weibo.com/2/mss/msget?fid={}&source={}'.format(fid, dbc.SRCCHAT)
            ct = ct + ' | file:' + fp
            try:
                hd, fpath = self.pagecmp.downchatpic(fp, fdir)
            except Exception as dex:
                self.mlogger.error('WbGChatCmp:savecmsg downchatpic EX=====>gid:{},mid:{},fpath:{},ex:{}'.format(gid, mid, fpath, str(dex)))
        elif cttype == '13':
            uos = msg.get('url_objects', [])
            if len(uos) > 0:
                subtype = str(uos[0].get('info', '0') and uos[0]['info'].get('type', '0'))
                if subtype == '39':
                    hburl = ct
                    ct = uos[0].get('object', '') and uos[0]['object'].get('object', '') and uos[0]['object']['object'].get('display_name', '')
                    nhour = cald.gethour()
                    if '生日' in ct or '寿星' in ct or nhour > 21 or nhour < 9:
                        pass
                    else:
                        if buid == '6400215263' or buid == self.wbcomp.wbuid:
                            slt = random.randint(1, 9)
                        elif buid == '1413018413':
                            slt = random.randint(4, 20)
                        else:
                            slt = random.randint(4, 60)
                        hd, amt, slt = self.pagecmp.fchchathb(hburl, slt)
                        if hd and buid != self.wbcomp.wbuid and '炸弹' not in ct and amt > 0:
                            midx = random.randint(1, len(dbc.HBRMSGS))
                            shburl = 'https://api.weibo.com/webim/groupchat/send_message.json'
                            shbdata = {
                                'content': dbc.HBRMSGS[midx - 1],
                                'id': gid,
                                'media_type': 0,
                                'is_encoded': 0,
                                'source': dbc.SRCCHAT,
                            }
                            mt = threading.Thread(target=self.wbcomp.postdata, args=(shburl, shbdata, 'chat', (30, 60), 12))
                            mt.start()
                        ct = ct + ' | hburl:' + hburl + ' | amt:' + str(amt) + ' | slt:' + str(slt)
                else:
                    cttype = cttype + subtype
        elif cttype == '14':
            hd, fpath = self.pagecmp.fchchathtml(ct)
        if ct:
            if fpath.startswith(self.wbcomp.picdir):
                fpath = fpath.replace(self.wbcomp.picdir, '')
            wbmon.savechatdata(mid, mday, gid, buid, bn, cttype, ct, hd, fid, fpath, mtime)

    def fchatstl(self):
        gcmaxmid = wbmon.getgcmaxmid()
        self.mlogger.info('WbGChatCmp:fgroupstl START=====>gcmaxmid:{}'.format(gcmaxmid))
        for gid in dbc.CHATGIDS:
            self.mlogger.info('WbGChatCmp:fgroupstl fgroupstl START=====>gid:{}'.format(gid))
            try:
                self.fchattl(gid, endsmid=gcmaxmid.get(gid, ''))
                self.mlogger.info('WbGChatCmp:fgroupstl fgroupstl END=====>gid:{}'.format(gid))
            except Exception as gex:
                self.wbcomp.refresh(self.wbcomp.wbuuid)
                self.mlogger.error('WbGChatCmp:fgroupstl fgroupstl EX=====>gid:{},ex:{}'.format(gid, str(gex)))
        self.mlogger.info('WbGChatCmp:fgroupstl END=====')

    def fchattl(self, gid, stasmid='', endsmid='', endday=''):
        if not endday:
            endday = cald.getdaystr(cald.calmonths(x=12))
        hismid = '0'
        while hismid:
            chatapiurl = 'https://api.weibo.com/webim/groupchat/query_messages.json?' \
                         'convert_emoji=1&query_sender=1&count=40&id={}&max_mid={}&source={}&t=1562578587256'.format(gid, hismid, dbc.SRCCHAT)
            hismid = ''
            jtext = self.wbcomp.gethtml(chatapiurl, 'chat')[1]
            msgsjson = json.loads(jtext)
            msgs = msgsjson.get('messages', [])
            retcode = str(msgsjson.get('error_code', 0))
            # raise WbChatGetDocError(retcode)
            if retcode == '21301':
                raise WbChatGetDocError(retcode)
            if len(msgs) == 0:
                self.mlogger.debug('WbGChatCmp:fchattl END1 no ct jtext:{},url:{}'.format(jtext, chatapiurl))
                break
            msgs.reverse()
            self.mlogger.debug('WbGChatCmp:fchattl hismid:{},len:{}'.format(hismid, len(msgs)))
            for msg in msgs:
                mid = str(msg['id'])
                mtime = cald.fromutime(int(msg['time']))
                mday = cald.getdaystr(mtime)
                smid = mday + mid
                if stasmid and smid >= stasmid:
                    hismid = mid
                    self.mlogger.debug('WbGChatCmp:fchattl CT1 stasmid url:{},smin:{},stasmid:{}'.format(chatapiurl, smid, stasmid))
                    continue
                if endsmid and smid <= endsmid:
                    hismid = ''
                    self.mlogger.debug('WbGChatCmp:fchattl END2 endsmid url:{},smin:{},endsmid:{}'.format(chatapiurl, smid, endsmid))
                    break
                if mday < endday:
                    hismid = ''
                    self.mlogger.debug('WbGChatCmp:fchattl END3 endday url:{},endday:{}'.format(chatapiurl, endday))
                    break
                sfdir = '/cgid' + gid + '/' + cald.getperiod(mtime)
                fdir = self.wbcomp.picdir + sfdir
                if not os.path.exists(fdir):
                    os.makedirs(fdir)
                try:
                    self.savecmsg(mid, mtime, mday, msg, gid, fdir)
                    hismid = mid
                except Exception as sex:
                    self.mlogger.error('WbGChatCmp:fchattl savecmsg EX=====>gid:{},mid:{},ex:{}'.format(gid, mid, str(sex)))


if __name__ == '__main__':
    glogger = logger.TuLog('wbgchatcmptest', '/../log', True, logging.DEBUG).getlog()
    wglogger = logger.TuLog('wbgchatcmptest[wbcomp]', '/../log', True, logging.DEBUG).getlog()
    wbun = 'sretof@live.cn'
    wbpw = '1122aaa'
    owbcomp = WbComp(wbun, wbpw, wglogger)
    owbcomp.login()
    gchatcmp = WbGChatCmp(owbcomp, mlogger=glogger)
    gchatcmp.fchatstl()
