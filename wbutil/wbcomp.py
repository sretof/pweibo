#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'
import base64
import json
import logging
import os
import random
import re
import threading
import time
import uuid
from binascii import b2a_hex
from urllib.parse import quote

import requests
import rsa
import urllib3
from bs4 import BeautifulSoup

import conf.db as dbc
import util.caldate as cald
import util.tulog as logger
import wbutil.wbmon as wbmon
from wbutil.wbex import WbCompDownError
from wbutil.wbex import WbCompError
from wbutil.wbex import WbMonNoneDocError

urllib3.disable_warnings()  # 取消警告


class WbComp:
    def __init__(self, username, password, proxies=None, picdir='F:\OneDrive\weibopic', mlogger=None):
        if proxies is None:
            proxies = {}
        if mlogger is None:
            mlogger = logger.TuLog('wbcomp', '/log', True, logging.INFO).getlog()
        self.username = username
        self.password = password
        self.proxies = proxies
        self.picdir = picdir

        self.wbuid = ''
        self.mlogger = mlogger

        self.wblock = threading.Lock()
        self.wbuuid = ''

    def __presession(self):
        self.wbuuid = ''
        self.session = requests.session()  # 登录用session
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
        }
        if self.proxies:
            self.session.proxies = self.proxies
            # adapter = SSLAdapter('TLSv1')
            # self.session.mount('https://', adapter)
        self.session.verify = False  # 取消证书验证

    def __prelogin(self):
        '''预登录，获取一些必须的参数'''
        self.su = base64.b64encode(self.username.encode())  # 阅读js得知用户名进行base64转码
        url = 'https://login.sina.com.cn/sso/prelogin.php?entry=weibo&callback=sinaSSOController.preloginCallBack&su={}&rsakt=mod&checkpin=1&client=ssologin.js(v1.4.19)&_={}'.format(
            quote(self.su), cald.gettimestamp())  # 注意su要进行quote转码
        response = self.session.get(url, timeout=(30, 60)).content.decode()
        # print(response)
        self.nonce = re.findall(r'"nonce":"(.*?)"', response)[0]
        self.pubkey = re.findall(r'"pubkey":"(.*?)"', response)[0]
        self.rsakv = re.findall(r'"rsakv":"(.*?)"', response)[0]
        self.servertime = re.findall(r'"servertime":(.*?),', response)[0]
        return self.nonce, self.pubkey, self.rsakv, self.servertime

    def __get_sp(self):
        '''用rsa对明文密码进行加密，加密规则通过阅读js代码得知'''
        publickey = rsa.PublicKey(int(self.pubkey, 16), int('10001', 16))
        message = str(self.servertime) + '\t' + str(self.nonce) + '\n' + str(self.password)
        self.sp = rsa.encrypt(message.encode(), publickey)
        return b2a_hex(self.sp)

    def __login(self):
        self.__prelogin()
        self.__get_sp()
        url = 'https://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.19)'
        data = {
            'entry': 'weibo',
            'gateway': '1',
            'from': '',
            'savestate': '7',
            'qrcode_flag': 'false',
            'useticket': '1',
            'pagerefer': 'https://login.sina.com.cn/crossdomain2.php?action=logout&r=https%3A%2F%2Fweibo.com%2Flogout.php%3Fbackurl%3D%252F',
            'vsnf': '1',
            'su': self.su,
            'service': 'miniblog',
            'servertime': str(int(self.servertime) + random.randint(1, 20)),
            'nonce': self.nonce,
            'pwencode': 'rsa2',
            'rsakv': self.rsakv,
            'sp': self.__get_sp(),
            'sr': '1536 * 864',
            'encoding': 'UTF - 8',
            'prelt': '35',
            'url': 'https://weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack',
            'returntype': 'META',
        }
        response = self.session.post(url, data=data, allow_redirects=False)  # 提交账号密码等参数
        response.encoding = 'utf-8'
        # print(response.text)
        redirect_url = re.findall(r'location.replace\("(.*?)"\);', response.text)[0]  # 微博在提交数据后会跳转，此处获取跳转的url
        result = self.session.get(redirect_url, timeout=(30, 60), allow_redirects=False).text  # 请求跳转页面
        ticket, ssosavestate = re.findall(r'ticket=(.*?)&ssosavestate=(.*?)"', result)[0]  # 获取ticket和ssosavestate参数
        uid_url = 'https://passport.weibo.com/wbsso/login?ticket={}&ssosavestate={}&callback=sinaSSOController.doCrossDomainCallBack&scriptId=ssoscript0&client=ssologin.js(v1.4.19)&_={}'.format(
            ticket, ssosavestate, cald.gettimestamp())
        data = self.session.get(uid_url, timeout=(30, 60)).text  # 请求获取uid
        uid = re.findall(r'"uniqueid":"(.*?)"', data)[0]
        if uid:
            self.wbuid = uid
            self.wbuuid = str(uuid.uuid1()).replace('-', '')
        # home_url = 'https://weibo.com/u/{}/home?wvr=5&lf=reg'.format(uid)  # 请求首页
        # html = self.session.get(home_url, timeout=(30, 60))
        # html.encoding = 'utf-8'
        # print(html.text)

    def __getres(self, url, ctype, timeout, allow_redirects):
        if not self.wbuid:
            raise WbCompError(999, url)
        headers = {}
        if ctype == 'chat':
            headers['Referer'] = 'https://api.weibo.com/chat/'
        res = self.session.get(url, headers=headers, timeout=timeout, allow_redirects=allow_redirects)
        return res

    def __gethtml(self, url, ctype, timeout, allow_redirects):
        if not self.wbuid:
            raise WbCompError(999, url)
        headers = {}
        if ctype == 'chat':
            headers['Referer'] = 'https://api.weibo.com/chat/'
        if 't.cn' in url:
            res = self.__getres(url, ctype, timeout, False)
            rhd = res.headers.get('location', '')
            res.close()
            if '100101B2094254D06BA7FB4998' in rhd:
                raise WbCompError(404, url, '')
        html = self.session.get(url, headers=headers, timeout=timeout, allow_redirects=allow_redirects)
        rcode = html.status_code
        html.encoding = 'utf-8'
        text = html.text
        html.close()
        if rcode == 200:
            fpg = r'<script>parent.window.location="https://weibo.com/sorry\?pagenotfound"</script>'
            ftext = re.findall(fpg, text, re.S)
            if len(ftext) > 0:
                raise WbCompError(404, url, text)
            if '你访问的页面地址有误' in text:
                raise WbCompError(404, url, text)
            if '违反' in text and '安全检测规则' in text:
                raise WbCompError(9991, url, text)
        elif rcode == 414 or rcode == 404:
            raise WbCompError(rcode, url, text)
        return rcode, text

    @staticmethod
    def fillwbhref(furl):
        if furl.startswith('//'):
            furl = 'https:' + furl
        elif furl.startswith('/'):
            furl = 'https://weibo.com' + furl
        elif furl.startswith('http'):
            pass
        return furl

    @staticmethod
    def splitacd(acd, *args):
        rmap = {}
        spas = acd.split('&')
        for spa in spas:
            spb = spa.split('=', 1)
            if len(spb) > 1 and spb[0] in args:
                rmap[spb[0]] = spb[1]
        return rmap

    def login(self, ouuid='', slt=0, lockwb=False):
        if not lockwb and slt:
            time.sleep(slt)
        self.wblock.acquire()
        if ouuid and ouuid != self.wbuuid:
            self.wblock.release()
            return
        if lockwb and slt:
            time.sleep(slt)
        self.__presession()
        tyrcnt = 0
        rex = None
        success = False
        while tyrcnt < 3:
            tyrcnt = tyrcnt + 1
            try:
                self.__login()
                if self.wbuid:
                    success = True
                    self.mlogger.info('WbComp login success=====>wbuid:{},wbuuid:{}'.format(self.wbuid, self.wbuuid))
                    break
                else:
                    raise Exception('no pwuid')
            except Exception as lex:
                rex = lex
                time.sleep(3)
        self.wblock.release()
        if not success:
            raise rex

    def refresh(self, ouuid, slt=60, lockwb=False):
        self.login(ouuid, slt, lockwb)

    def getres(self, url, ctype='', timeout=(30, 60), allow_redirects=True, rtry=1, refresh=False):
        tyrcnt = 0
        ouuid = self.wbuuid
        while tyrcnt < rtry:
            # self.mlogger.debug('WbComp:getres=====>tyrcnt:{},url:{}'.format(tyrcnt, url))
            tyrcnt = tyrcnt + 1
            try:
                self.wblock.acquire()
                self.wblock.release()
                return self.__getres(url, ctype, timeout, allow_redirects)
            except Exception as ghex:
                rex = ghex
            if tyrcnt >= rtry and refresh:
                refresh = False
                rtry = rtry * 2
                self.refresh(ouuid)
        self.mlogger.error('WbComp:getres error=====>ex:{},url:{}'.format(str(rex), url))
        raise rex

    def gethtml(self, url, ctype='', timeout=(30, 60), allow_redirects=True, rtry=3, refresh=False):
        tyrcnt = 0
        ouuid = self.wbuuid
        while tyrcnt < rtry:
            # self.mlogger.debug('WbComp:gethtml=====>tyrcnt:{},url:{}'.format(tyrcnt, url))
            tyrcnt = tyrcnt + 1
            try:
                self.wblock.acquire()
                return self.__gethtml(url, ctype, timeout, allow_redirects)
            except WbCompError as ghwex:
                rex = ghwex
                excode = ghwex.excode
                if str(excode).startswith('999'):
                    tyrcnt = rtry
                    refresh = False
                elif excode == 404 and tyrcnt < rtry - 1:
                    tyrcnt = rtry - 1
                elif excode == 414:
                    time.sleep(60 * 4)
            except Exception as ghex:
                rex = ghex
            finally:
                self.wblock.release()
            if tyrcnt >= rtry and refresh:
                refresh = False
                rtry = rtry * 2
                self.refresh(ouuid)
        self.mlogger.error('WbComp:gethtml error=====>ex:{},url:{}'.format(str(rex), url))
        raise rex

    def postdata(self, url, data, ctype='', timeout=(30, 60)):
        self.mlogger.debug('WbComp:postdata error=====>url:{}'.url)
        try:
            self.wblock.acquire()
            self.wblock.release()
            headers = {}
            if ctype == 'chat':
                headers['Referer'] = 'https://api.weibo.com/chat/'
            self.session.post(url, data, timeout=timeout)
            self.mlogger.debug('WbComp:postdata success=====>url:{}'.url)
        except Exception as pex:
            self.mlogger.error('WbComp:postdata error=====>ex:{},url:{}'.format(str(pex), url))

    def downmedia(self, mid, doc=None, fdir=None):
        gdoccnt = 0
        while gdoccnt < 1:
            doc = wbmon.getgpbymid(mid)
            if doc is None:
                gdoccnt = gdoccnt + 1
                time.sleep(0.4)
            else:
                break
        if doc is None:
            raise WbMonNoneDocError(mid)
        self.mlogger.debug('WbComp:downmedia START=====>mid:{}'.format(mid))
        medias = doc.get('media', [])
        fwdmedias = doc.get('fwdmedia', [])
        uid = doc['uid']
        mid = doc['mid']
        gid = doc['gid']
        if not gid:
            gid = 'others'
        if fdir is None:
            fdir = self.picdir + '\\' + 'tlgid' + gid + '\\' + 'tluid' + uid
        if not os.path.exists(fdir):
            os.makedirs(fdir)
        exmedias = []
        for media in medias:
            if media['hasd']:
                continue
            purl = media['url']
            fid = media['fid']
            self.mlogger.debug('WbComp:downmedia fid START=====>mid:{},fid:{},ftype:{}'.format(mid, fid, media['mtype']))
            opttext = ''
            if media['mtype'].startswith('13') or media['mtype'] == '14' or media['mtype'] == '15':
                locpath, opttext = self.downpage(mid, purl, fid, fdir, media['mtype'])
            elif media['mtype'].endswith('21') or media['mtype'].endswith('211'):
                locpath = self.downpic(mid, purl, fid, fdir)
            else:
                locpath = self.downvideo(mid, purl, fid, fdir)
            if locpath:
                wbmon.hasdownmedia(mid, fid, locpath, opttext)
            else:
                locpath = ''
                exmedias.append(fid)
            self.mlogger.debug('WbComp:downmedia fid END=====>mid:{},fid:{},ftype:{},locpath:{}'.format(mid, fid, media['mtype'], locpath))
        if len(exmedias) > 0:
            self.mlogger.error('WbComp:downmedia EX;exmedias:{}'.format(exmedias))
        self.mlogger.debug('WbComp:downmedia END=====>mid:{},len(ex):{}'.format(mid, len(exmedias)))
        return exmedias

    def downpageimg(self, imgurl, fpath, mtype='13'):
        try:
            if mtype == '14' and 'weibo' not in imgurl:
                res = requests.get(imgurl, timeout=(30, 60))
            else:
                res = self.getres(imgurl, timeout=(30, 60))
            ftype = res.headers.get('Content-Type', '')
            # self.mlogger.debug('WbComp:downpageimg res success;filetype:{},imgurl:{}'.format(ftype, imgurl))
            ftr = r'(\w+)/(\w+)'
            rtext = re.findall(ftr, ftype, re.S)
            if rtext[0][0] != 'image':
                raise Exception('WbComp:downpageimg ftype is not image;filetype:{},imgurl:{}'.format(ftype, imgurl))
            img = res.content
            fuuid = ''.join(str(uuid.uuid1()).split('-'))
            fname = fuuid + '.' + rtext[0][1]
            with open(fpath + '\\' + fname, 'wb') as f:
                f.write(img)
            return fname
        except Exception as dpiex:
            raise dpiex

    def downpage(self, mid, src, fid, fdir, mtype='13'):
        opttext = ''
        try:
            if mtype == '14' and 'weibo' not in src and 'sina' not in src:
                rres = requests.get(src, timeout=(30, 60), allow_redirects=False)
                if rres.status_code == 302:
                    rloc = rres.headers.get('Location', '')
                    if 'weidian' in rloc:
                        rres.close()
                        raise WbCompDownError('14000', src, 'no need down')
                    else:
                        rres = requests.get(src, timeout=(30, 60))
                if rres.status_code != 200:
                    rres.close()
                    raise WbCompDownError('14001', src, 'ex status_code'.format(rres.status_code))
                rres.encoding = 'utf-8'
                text = rres.text
                rres.close()
            else:
                text = self.gethtml(src, timeout=(30, 60), rtry=1)[1]
            if mtype.startswith('13'):
                rpg = r'<script>FM\.view\({"ns":"pl\.content\.weiboDetail\.index",(.*?)\)</script>'
                jtext = re.findall(rpg, text, re.S)
                jtext = '{' + jtext[0]
                ptext = json.loads(jtext)
                thtml = ptext['html']
                soup = BeautifulSoup(thtml, 'lxml')
            elif mtype == '15':
                soup = BeautifulSoup(text, 'lxml')
                eframe = soup.select_one('div.WB_editor_iframe_new')
                if eframe is None:
                    eframe = soup.select_one('div.WB_editor_iframe')
                if eframe is None:
                    eframe = soup.select_one('div.WB_artical > div.WB_artical_del')
                    if eframe is not None:
                        return '404'
                efsty = eframe.get('style', '')
                if efsty:
                    efsty = efsty.replace('hidden', 'visible')
                    eframe['style'] = efsty
                shtml = str(eframe)
                soup = BeautifulSoup(shtml, 'lxml')
            else:
                soup = BeautifulSoup(text, 'lxml')
            # 13/15下载文章内图片
            if mtype == '13' or mtype == '15':
                idoms = soup.select('img')
                fimgdir = mid + fid + '.files'
                filepath = fdir + '\\' + fimgdir
                if not os.path.exists(filepath):
                    os.makedirs(filepath)
                idomex1 = []
                idomex2 = []
                idomdown = []
                for idom in idoms:
                    idombk = False
                    clss = idom.get('class', [])
                    for cls in clss:
                        if cls in dbc.NDIMGCLS:
                            idombk = True
                            break
                    if idombk:
                        continue
                    iurl = idom.get('src', '')
                    if not iurl or iurl.startswith('data'):
                        iurl = idom.get('data-src', '')
                    if iurl.startswith('//'):
                        iurl = 'https:' + iurl
                    elif iurl.startswith('http'):
                        pass
                    elif '.files\\' in iurl:
                        iurl = ''
                    elif not iurl:
                        pass
                    else:
                        idomex1.append(iurl)
                        iurl = ''
                    if iurl:
                        try:
                            fname = self.downpageimg(iurl, filepath, mtype)
                            idom['src'] = fimgdir + '\\' + fname
                            idomdown.append(iurl)
                        except Exception as dpiex:
                            idomex2.append({'iurl': iurl, 'ex': str(dpiex)})
                if len(idomex1) > 0:
                    self.mlogger.warning('WbComp:downpage:downpageimg EX1;mid:{},fid:{},murl:{},iurls:{}'.format(mid, fid, src, idomex1))
                if len(idomex2) > 0:
                    self.mlogger.error('WbComp:downpage:downpageimg EX2;mid:{},fid:{},murl:{},iurls:{}'.format(mid, fid, src, idomex2))
                self.mlogger.debug('WbComp:downpage:downpageimg success;mid:{},fid:{},murl:{},iurls:{}'.format(mid, fid, src, idomdown))
            locpath = fdir + '\\' + mid + fid + '.html'
            if mtype.startswith('13'):
                dtxdiv = soup.select_one('div.WB_detail > div.WB_text')
                if dtxdiv is not None:
                    opttext = dtxdiv.text.strip()
            if mtype != '1321':
                with open(locpath, 'w', encoding='utf-8') as f:
                    f.write(str(soup.html))
            else:
                locpath = '1321'
        except WbCompDownError as wdex:
            self.mlogger.error('WbComp:downpage EX0;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(wdex), src))
            locpath = '404'
        except WbCompError as wex:
            self.mlogger.exception(wex)
            self.mlogger.error('WbComp:downpage EX1;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(wex), src))
            locpath = ''
        except Exception as ex:
            self.mlogger.exception(ex)
            self.mlogger.error('WbComp:downpage EX2;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(ex), src))
            locpath = ''
        return locpath, opttext

    def downpic(self, mid, src, fid, fdir):
        try:
            text = self.gethtml(src, timeout=(30, 60), rtry=1)[1]
            soup = BeautifulSoup(text, 'lxml')
            imgd = soup.select_one('div.artwork > img')
            if imgd is not None:
                imgurl = imgd['src']
                ipreg = r'.+/(\w+)\.(\w+)'
                rtext = re.findall(ipreg, imgurl, re.S)
                fname = ''
                if len(rtext) > 0 and len(rtext[0]) > 1:
                    fpf = rtext[0][0]
                    fsf = rtext[0][1]
                    if fpf != fid:
                        fid = fid + fpf
                    fname = fid + '.' + fsf
                if not fname:
                    raise Exception('pic fname is none;mid:{},fid:{},src:{}'.format(mid, fid, src))
                res = self.getres(imgurl, timeout=(30, 300))
                locpath = fdir + '\\' + mid + fname
                img = res.content
                with open(locpath, 'wb') as f:
                    f.write(img)
            else:
                imge = soup.select_one('div.m_error > img')
                if imge is not None:
                    locpath = '404'
                else:
                    raise Exception('WbComp:downpic EX:none img dom')
        except Exception as ex:
            locpath = ''
            self.mlogger.exception(ex)
            self.mlogger.error('WbComp:downpic EX;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(ex), src))
        return locpath

    def downvideo(self, mid, src, fid, fdir):
        try:
            # html = dpweibo.session.get(src, timeout=(30, 300))
            # html.encoding = 'utf-8'
            # text = html.text
            # soup = BeautifulSoup(text, 'lxml')
            # dvd = soup.select_one('div.weibo_player_fa > div[node-type="common_video_player"][video-sources]')
            # vurl = unquote(dvd['video-sources'])
            # vurl = vurl.replace('fluency=', '', 1)
            ipreg = r'.+/(\S+)\.(\S+)\?'
            rtext = re.findall(ipreg, src, re.S)
            fname = ''
            if len(rtext) > 0 and len(rtext[0]) > 1:
                fpf = rtext[0][0]
                fsf = rtext[0][1]
                fname = fpf + '.' + fsf
            if not fname:
                raise Exception('video fname is none;src:{},fid:{}'.format(src, fid))
            res = self.getres(src, timeout=(30, 300))
            locpath = fdir + '\\' + mid + fname
            img = res.content
            with open(locpath, 'wb') as f:
                f.write(img)
        except Exception as ex:
            locpath = ''
            self.mlogger.exception(ex)
            self.mlogger.error('WbComp:downvideo EX;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(ex), src))
        return locpath


if __name__ == '__main__':
    glogger = logger.TuLog('wbcomptest', '/../log', True, logging.DEBUG).getlog()
    wbun = 'sretof@live.cn'
    wbpw = '1122aaa'
    wbcomp = WbComp(wbun, wbpw, mlogger=glogger)
    # wbcomp.login()
    # wbcomp.gethtml('https://weibo.com/5705221157/HwfbzDytxcc', refresh=True)

    # ulocpath, utxt = wbcomp.downpage('1', 'https://weibo.com/1886824091/I3raPz6hL', '11', 'F:\\bg', mtype='1321')
    # print(ulocpath, utxt)
    #
    # ulocpath, utxt = wbcomp.downpage('2', 'https://weibo.com/1886824091/I3raPz6hL', '21', 'F:\\bg', mtype='13')
    # print(ulocpath, utxt)

    # wbcomp.downmedia('4408119490344814', fdir='F:\\bg\\4408119490344814')
    tacd = 'uid=3275508441&profile_image_url=http://tva2.sinaimg.cn/crop.0.0.720.720.50/c33c4ad9jw8ek1hvopr8ej20k00k0ju0.jpg?Expires=1566553334&ssig=JEwmIKyLB8&KID=imgbed,tva&gid=3909747545351455&gname=股票&screen_name=跟我走吧14&sex=m'
    tmumap = WbComp.splitacd(tacd, 'uid', 'screen_name')
    print(tmumap)