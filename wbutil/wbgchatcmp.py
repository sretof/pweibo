# -*- coding:utf-8 -*-
import base64
import datetime
import json
import logging
import random
import re
import threading
import time
import uuid
from binascii import b2a_hex
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import pymysql
import requests
import rsa
import urllib3

import conf.db as dbc
import util.caldate as cald
import util.tulog as logger

urllib3.disable_warnings()  # 取消警告

from pymongo import MongoClient

import util.caldate as cald
import util.tulog as logger
import wbutil.wbmon as wbmon



class WbGChatCmp():
    chatsource = '209678993'
    pagesource = '4037146678'

    def __init__(self, wbcomp, mlogger=None):
        if mlogger is None:
            mlogger = logger.TuLog('wbgtlcmp', '/log', True, logging.INFO).getlog()
        self.wbcomp = wbcomp
        self.mlogger = mlogger
        self.downfexecutor = ThreadPoolExecutor(max_workers=1)
        self.vdownfexecutor = ThreadPoolExecutor(max_workers=2)
        self.hbresexecutor = ThreadPoolExecutor(max_workers=5)
        self.downfexecutor = ThreadPoolExecutor(max_workers=5)



    # 历史群组信息
    hisgmsgexecutor = ThreadPoolExecutor(max_workers=1)
    # 红包结果
    hbresexecutor = ThreadPoolExecutor(max_workers=5)
    # 下载文件
    downfexecutor = ThreadPoolExecutor(max_workers=5)

    SENLOCK = threading.Lock()
    GLOGGER = logger.TuLog('wbgchat', '/log', True, logging.WARNING).getlog()
    CHATGIDS = ('4305987512698522',)
    TLGIDS = ('3653960185837784', '3909747545351455', '4198223948149624', '4005405388023195', '3951063348253369')

    ADUID = ('1678870364',)
    ADURL = ('tui.weibo.com',)

    MYWBUID = '1795005665'

    MGOCTCOLL = 'Contents'

    def __init__(self, username, password, proxies):
        self.username = username
        self.password = password
        self.proxies = proxies
        self.session = requests.session()  # 登录用session
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
        }
        if proxies:
            self.session.proxies = proxies
            # adapter = SSLAdapter('TLSv1')
            # self.session.mount('https://', adapter)
        self.session.verify = False  # 取消证书验证
        self.uid = uuid.uuid1()
        self.wbuid = PWeiBo.MYWBUID

    # 如果有maxmid,到maxmid就返回-1
    @staticmethod
    def fgroupmsgct(pweibo, jtext, gid, maxmids=[]):
        msgsjson = json.loads(jtext)
        msgs = msgsjson.get('messages', [])
        retl = 0
        hmid = 0
        if len(msgs) == 0:
            PWeiBo.GLOGGER.warning('fgroupmsgct content=0 gid:{} maxmids:{}...'.format(gid, maxmids[0:2]))
        else:
            fmids = []
            retl = len(msgs)
            msgs.reverse()
            for msg in msgs:
                mid = str(msg['id'])
                if maxmids and mid in maxmids:
                    PWeiBo.GLOGGER.info('fgroupmsgct gid:{} mid:{} maxmids:{}... stop'.format(gid, mid, maxmids[0:2]))
                    retl = -1
                    break
                buid = str(msg['from_uid'])
                bn = (msg.get('from_user', '') and msg['from_user'].get('screen_name', '')) or buid
                cttype = str(msg['media_type'])
                ct = msg['content']
                mtime = datetime.datetime.fromtimestamp(int(msg['time']))
                fid = ''
                fpath = ''
                hd = 0
                # TEXT
                if cttype == '1':
                    fid = msg['fids'][0]
                    fp = 'https://upload.api.weibo.com/2/mss/msget?fid={}&source={}'.format(fid, PWeiBo.chatsource)
                    ct = ct + ' | file:' + fp
                    try:
                        hd, fpath = pweibo.downpic(fp)
                    except Exception as ex:
                        print("down pic field......:", fp)
                        print(ex)
                elif cttype == '13':
                    PWeiBo.GLOGGER.info('hb text {}'.format(msg))
                    uos = msg.get('url_objects', [])
                    if len(uos) > 0:
                        subtype = str(uos[0].get('info', '0') and uos[0]['info'].get('type', '0'))
                        if subtype == '39':
                            hburl = ct
                            ct = uos[0].get('object', '') and uos[0]['object'].get('object', '') and uos[0]['object']['object'].get('display_name', '')
                            hd, amt, slt = PWeiBo.fgrouphb(pweibo, hburl, gid, buid, ct)
                            ct = ct + ' | hburl:' + hburl + ' | amt:' + str(amt) + ' | slt:' + str(slt)
                        else:
                            cttype = cttype + subtype
                elif cttype == '14':
                    hd, fpath = PWeiBo.fhtmlct(pweibo, ct)
                if ct:
                    PWeiBo.savelock.acquire()
                    PWeiBo.catchmcts(mid, gid, buid, bn, cttype, ct, hd, fid, fpath, mtime)
                    savegcts(PWeiBo.sgsql)
                    PWeiBo.savelock.release()
                    fmids.append(mid)
            if len(fmids) > 0:
                hmid = fmids[len(fmids) - 1]
            PWeiBo.GLOGGER.info('fgroupmsgct gid:{} mid:{},maxmids:{}...,fmids:{}'.format(gid, mid, maxmids[0:2], fmids))
        return retl, hmid

    @staticmethod
    def fgrouphb(pweibo, hburl, gid, buid, ct):
        # 302 :设置属性:allow_redirects = True ,则head方式会自动解析重定向链接，requests.get()方法的allow_redirects默认为True，head方法默认为False
        msgs = ['感谢大佬', '谢谢大佬', '谢谢大佬红包']
        success = 0
        slt = 0
        nhour = datetime.datetime.now().hour
        if '生日' in ct or '寿星' in ct or nhour > 21 or nhour < 10:
            pass
        else:
            if buid == '6400215263' or buid == PWeiBo.MYWBUID:
                slt = random.randint(1, 9)
            elif buid == '1413018413':
                slt = random.randint(4, 32)
            else:
                slt = random.randint(4, 128)
            slt = round(slt * 0.1, 1)
            time.sleep(slt)
            html = pweibo.session.get(hburl, timeout=(30, 60))
            html.encoding = 'utf-8'
            text = html.text
            hbamt = 0
            p = r'\$CONFIG\[\'bonus\'\]\s*=\s*\"(.+?)\"'
            hbamttxt = re.findall(p, text, re.S)
            if len(hbamttxt) > 0:
                hbamt = float(hbamttxt[0])
            if '已存入您的钱包' in text and hbamt > 0:
                success = 1
            if not success:
                PWeiBo.GLOGGER.warning('hb success:{} hbamt:{} text:{}'.format(success, hbamt, text))
        if success and buid != PWeiBo.MYWBUID and '炸弹' not in ct:
            midx = random.randint(1, len(msgs))
            mt = threading.Thread(target=PWeiBo.sendgroupmsg, args=(pweibo, gid, msgs[midx - 1], 12))
            mt.start()
        return success, hbamt, slt

    @staticmethod
    def sendgroupmsg(pweibo, gid, msg, slt):
        if slt:
            time.sleep(slt)
        sgmsgurl = 'https://api.weibo.com/webim/groupchat/send_message.json'
        data = {
            'content': msg,
            'id': gid,
            'media_type': 0,
            'is_encoded': 0,
            'source': PWeiBo.chatsource,
        }
        pweibo.postdata(sgmsgurl, data, 'chat')



    @staticmethod
    def catchmcts(mid, gid, buid, bn, cttype, ct, hd, fid, fpath, mtime):
        vals = [mid, gid, buid, bn, ct, cttype, fid, fpath, hd,
                mtime.strftime('%Y%m%d'), cald.now().strftime('%Y-%m-%d %H:%M:%S.%f'), mtime.strftime('%Y-%m-%d %H:%M:%S.%f')]
        PWeiBo.ctcaches.append(vals)


    def downpic(self, src, gid='4305987512698522'):
        fid = ''
        path = ''
        success = 1
        fids = re.findall(r'\S+fid=(\d+)', src, re.S)
        if len(fids) == 1:
            fid = fids[0]
        res = self.session.get(src, timeout=(30, 300))
        cdi = res.headers.get('Content-Disposition', '')
        if cdi:
            cdis = re.findall(r'\S+filename="(\S+)"', cdi, re.S)
            if len(cdis) == 1:
                sfix = cdis[0]
                filename = fid + 'f' + sfix
                dir = PWeiBo.weipicdir
                if gid:
                    dir = dir + '\gid' + gid
                path = dir + '\\' + filename
                img = res.content
                with open(path, 'wb') as f:
                    f.write(img)
        return success, path


    def fgroupmsg(self, gid, mid='0', maxmids=[]):
        chatapiurl = 'https://api.weibo.com/webim/groupchat/query_messages.json?' \
                     'convert_emoji=1&query_sender=1&count=40&id={}&max_mid={}&source=209678993&t=1562578587256'.format(gid, mid)
        jtext = self.gethtml(chatapiurl, 'chat')
        PWeiBo.GLOGGER.info(
            'fgroupmsg success get html;pweibo:{};gid:{} mid:{} maxmids:{} gurl:{}'.format(str(self.uid), gid, mid, maxmids[0:2], chatapiurl))
        try:
            lenct, hismid = PWeiBo.fgroupmsgct(self, jtext, gid, maxmids)
            # print(jtext)
        except Exception as ex:
            PWeiBo.GLOGGER.error(
                'fgroupmsg parse html error;pweibo:{};gid:{} mid:{} maxmids:{} gurl:{} text:{}'.format(
                    str(self.uid), gid, mid, maxmids[0:2], chatapiurl, jtext))
            raise ex
        if lenct == -1:
            PWeiBo.GLOGGER.info('>==========fgroupmsg to maxmids end')
            return
        if lenct == 0:
            raise Exception('fgroupmsg ctcnt == 0 or not hismid url:{},hismid:{} end'.format(chatapiurl, hismid))
        else:
            PWeiBo.GLOGGER.debug('fgroupmsg success gid:{},mid:{},len(ct):{}'.format(gid, mid, lenct))
            self.fgroupmsg(gid, hismid, maxmids)


def login(proxies={}):
    username = 'sretof@live.cn'  # 账号
    password = '1122aaa'  # 密码
    npweibo = PWeiBo(username, password, proxies)
    npweibo.login()
    return npweibo


def fgroupct(pweibo):
    try:
        for gid in PWeiBo.CHATGIDS:
            maxmids = getmaxgpmids(gid)
            pweibo.fgroupct(gid, maxmids=maxmids)
    except Exception as ex:
        PWeiBo.GLOGGER.exception(ex)
        raise ex


def fgroupsmsg(pweibo):
    try:
        for gid in PWeiBo.CHATGIDS:
            maxmids = getmaxmids(gid)
            pweibo.fgroupmsg(gid, maxmids=maxmids)
    except Exception as ex:
        PWeiBo.GLOGGER.exception(ex)
        raise ex


def fgroupshismsg(pweibo):
    try:
        for gid in PWeiBo.CHATGIDS:
            mmid = getmmmid(gid)
            # mmid['minid'] = '4392899204268935'
            maxmids = []
            pweibo.fgroupmsg(gid, mmid['minid'], maxmids=maxmids)
    except Exception as ex:
        PWeiBo.GLOGGER.exception(ex)
        raise ex


global Gfcnt
Gfcnt = 0


def tcallback(f):
    global Gfcnt
    try:
        f.result()
    except Exception:
        Gfcnt = 0


if __name__ == '__main__':
    mpweibo = None
    mproxies = {}
    hcg = None
    while 1:
        try:
            if Gfcnt == 0:
                mpweibo = login(mproxies)
                Gfcnt = 1
            # if hcg is None or hcg.done():
            #     hcg = PWeiBo.hisgmsgexecutor.submit(fgroupshismsg, mpweibo)
            #     hcg.add_done_callback(tcallback)
            fgroupsmsg(mpweibo)
        except requests.exceptions.SSLError as e:
            PWeiBo.GLOGGER.exception(e)
            mproxies = {'http': 'http://127.0.0.1:10080', 'https': 'http://127.0.0.1:10080'}
            Gfcnt = 0
        except requests.exceptions.ProxyError as e:
            PWeiBo.GLOGGER.exception(e)
            mproxies = {}
            Gfcnt = 0
        except Exception as e:
            PWeiBo.GLOGGER.exception(e)
            Gfcnt = 0
        finally:
            nhour = datetime.datetime.now().hour
            sleeptime = random.randint(10, 60 * 10)
            if 12 < nhour < 16:
                sleeptime = random.randint(4, 14)
            sleeptime = round(sleeptime * 0.1, 1)
            if nhour > 21 or nhour < 8:
                sleeptime = random.randint(60 * 30, 60 * 120)
            PWeiBo.GLOGGER.info('======sleep hour:{} sleep:{}'.format(nhour, sleeptime))
            time.sleep(sleeptime)
