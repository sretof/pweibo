#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'
import base64
import logging
import random
import re
import threading
import time
import uuid
from binascii import b2a_hex
from urllib.parse import quote
from urllib.parse import unquote
import json

import requests
import rsa
import urllib3

import util.caldate as cald
import util.tulog as logger
import wbutil.wbmon as wbmon
from wbutil.wbex import WbCompError

urllib3.disable_warnings()  # 取消警告


class WbComp:
    def __init__(self, username, password, proxies=None, picdir='F:\OneDrive\weibopicfz', mlogger=None):
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
            # 'Referer': "https://weibo.com/",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
        }
        if self.proxies:
            self.session.proxies = self.proxies
            # adapter = SSLAdapter('TLSv1')
            # self.session.mount('https://', adapter)
        self.session.verify = False  # 取消证书验证

    def __prelogin(self):
        self.session.get('https://weibo.com/login.php')
        '''预登录，获取一些必须的参数'''
        # self.su = base64.b64encode(self.username.encode())  # 阅读js得知用户名进行base64转码
        self.su = self.username
        # print(quote(self.su)) c3JldG9mQGxpdmUuY24%3D  c3JldG9mJTQwbGl2ZS5jbg=
        url = 'https://login.sina.com.cn/sso/prelogin.php?entry=weibo&callback=sinaSSOController.preloginCallBack&su={}&rsakt=mod&checkpin=1&client=ssologin.js(v1.4.19)&_={}'.format(
            quote(self.su), cald.gettimestamp())  # 注意su要进行quote转码

        headers = {
            'Accept': '* / *',
            'Accept-Encoding': 'gzip,deflate,br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
            'Connection': 'keep-alive',
            'Host': 'login.sina.com.cn',
            'Referer': 'https://weibo.com/',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="98", "Google Chrome";v="98"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Dest': 'script',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
        }
        response = self.session.get(url, headers=headers, timeout=(30, 60)).content.decode()
        self.nonce = re.findall(r'"nonce":"(.*?)"', response)[0]
        self.pubkey = re.findall(r'"pubkey":"(.*?)"', response)[0]
        self.rsakv = re.findall(r'"rsakv":"(.*?)"', response)[0]
        self.servertime = re.findall(r'"servertime":(.*?),', response)[0]
        self.pcid = re.findall(r'"pcid":"(.*?)"', response)[0]
        # print(self.pcid)
        return self.nonce, self.pubkey, self.rsakv, self.servertime

    def __get_sp(self):
        '''用rsa对明文密码进行加密，加密规则通过阅读js代码得知'''
        publickey = rsa.PublicKey(int(self.pubkey, 16), int('10001', 16))
        message = str(self.servertime) + '\t' + str(self.nonce) + '\n' + str(self.password)
        self.sp = rsa.encrypt(message.encode(), publickey)
        return b2a_hex(self.sp)

    def __qrlogin(self):
        qrstimestamp = int(time.time() * 1000)
        qrloginurl = 'https://login.sina.com.cn/sso/qrcode/image?entry=sinawap&size=180&callback=STK_{}'.format(qrstimestamp) + '1'
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip,deflate,br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
            'Connection': 'keep-alive',
            'Host': 'login.sina.com.cn',
            'Referer': 'https://weibo.com/',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="98", "Google Chrome";v="98"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Dest': 'script',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
        }
        html = self.session.get(qrloginurl, headers=headers, timeout=(30, 60))
        html.encoding = 'utf-8'
        text = html.text
        html.close()
        qrparamsg = re.search("window.STK_\d+.\d+ && STK_\d+.\d+\(?", text)
        qrparams = json.loads(text.strip().lstrip(qrparamsg.group()).rstrip(");"))
        qrid = qrparams['data']['qrid']
        qrimage = qrparams['data']['image']
        print(qrimage)
        wbmon.saveMongoQyImg(qrid, qrimage, '00000000')
        getqrstatusurl = 'https://login.sina.com.cn/sso/qrcode/check?entry=weibo&qrid={}&callback=STK_{}'
        time.sleep(1)
        qrctimestamp = int(time.time() * 1000)
        gapts = int((qrctimestamp-qrstimestamp)/1000)*2+1
        while gapts < 120:
            getqrstatusurlf = getqrstatusurl.format(qrid, qrstimestamp) + str(gapts)
            html = self.session.get(getqrstatusurlf, headers=headers, timeout=(30, 60))
            html.encoding = 'utf-8'
            text = html.text
            html.close()
            rcodeg = re.search("window.STK_\d+.\d+ && STK_\d+.\d+\(?", text)
            rcodej = json.loads(text.strip().lstrip(rcodeg.group()).rstrip(");"))
            rcode = str(rcodej['retcode'])
            wbmon.saveMongoQyImg(qrid, qrimage, rcode, gapts)
            if '20000000' in rcode:
                alt = rcodej['data']['alt']
                alturl = 'https://login.sina.com.cn/sso/login.php?entry=weibo&returntype=TEXT&crossdomain=1&cdult=3&domain=weibo.com&alt={}&savestate=30&callback=STK_{}'
                alturlf = alturl.format(alt, qrstimestamp) + str(gapts + 2)
                html = self.session.get(alturlf, headers=headers, timeout=(30, 60))
                html.encoding = 'utf-8'
                text = html.text
                html.close()
                # print('===============5===========')
                # print(text)
                crurlg = re.search("STK_\d+\(?", text)
                crurlj = json.loads(text.strip().lstrip(crurlg.group()).rstrip(");"))
                crurll = crurlj['crossDomainUrlList']
                # print(crurll)
                uid = crurlj['uid']
                # print(uid)
                self.session.get(crurll[0], timeout=(30, 60))
                self.session.get(crurll[1] + '&action=login', timeout=(30, 60))
                self.session.get(crurll[2], timeout=(30, 60))
                self.wbuid = uid
                self.wbuuid = str(uuid.uuid1()).replace('-', '')
                break
            else:
                #其他情况
                #二维码未失效，请扫码！'50114001'
                #已扫码，请确认！'50114002'
                #二维码已失效，请重新运行！'50114004'
                print(rcode)
            time.sleep(4)
            gapts = gapts + 2

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
        redirect_url = re.findall(r'location.replace\("(.*?)"\);', response.text)[0]  # 微博在提交数据后会跳转，此处获取跳转的url
        rg_redirect_url = unquote(redirect_url, 'gb2312') + "&"
        retcode = re.findall(r'retcode=(.*?)&', rg_redirect_url)[0]
        if retcode == '2071':
            token = re.findall(r'token=(.*?)&', rg_redirect_url)[0]
            sendcodeurl = 'https://passport.weibo.com/protection/privatemsg/send'
            getstatusurl = 'https://passport.weibo.com/protection/privatemsg/getstatus'
            codedate = {'token': token}
            self.session.post(sendcodeurl, codedate, timeout=(30, 60), allow_redirects=False).text
            status_code = 1
            count = 0
            rlurl = ''
            while count < 120 and status_code != '2' and rlurl == '':
                getstatusresult = self.session.post(getstatusurl, codedate, timeout=(30, 60), allow_redirects=False).text
                tjson = json.loads(getstatusresult)
                status_code = tjson['data']['status_code']
                if status_code == '2':
                    rlurl = tjson['data']['redirect_url']
                    rtext = self.session.get(rlurl, timeout=(30, 60)).text
                    tlurl = re.findall(r'location.replace\("(.*?)"\);', rtext)[0]
                    tlurl = unquote(tlurl, 'gb2312')
                    ticket = re.findall(r'ticket=(.*?)&', tlurl)[0]
                    ssosavestate = re.findall(r'ssosavestate=(.*?)&', tlurl)[0]
                    break
                time.sleep(10)
        elif retcode == '0':
            result = self.session.get(redirect_url, timeout=(30, 60), allow_redirects=False).text  # 请求跳转页面
            ticket, ssosavestate = re.findall(r'ticket=(.*?)&ssosavestate=(.*?)"', result)[0]  # 获取ticket和ssosavestate参数
        else:
            raise Exception('login error:'+rg_redirect_url)
        if ticket and ssosavestate:
            # uid_url = 'https://passport.weibo.com/wbsso/login?ticket={}&ssosavestate={}&callback=sinaSSOController.doCrossDomainCallBack&scriptId=ssoscript0&client=ssologin.js(v1.4.19)&_={}'.format(
            #     ticket, ssosavestate, cald.gettimestamp())
            uid_url = 'https://passport.weibo.com/wbsso/login?ticket={}&ssosavestate={}&action=login'.format(ticket, ssosavestate)
            print(uid_url)
            html = self.session.get(uid_url, timeout=(30, 60))  # 请求获取uid
            html.encoding = 'utf-8'
            data = html.text
            print(data)
            uid = re.findall(r'"uniqueid":"(.*?)"', data)[0]
        else:
            raise Exception('login error:ticket & ssosavestate is none')
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
            if '414 Request-URI Too Large' in text:
                raise WbCompError(414, url, text)
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
                self.__qrlogin()
                if self.wbuid:
                    success = True
                    self.mlogger.info('WbComp login success=====>wbuid:{},wbuuid:{}'.format(self.wbuid, self.wbuuid))
                    break
                else:
                    raise Exception('no pwuid')
            except Exception as lex:
                rex = lex
                time.sleep(60)
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
            self.mlogger.debug('WbComp:gethtml=====>tyrcnt:{},url:{}'.format(tyrcnt, url))
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
                self.mlogger.error('WbComp:gethtml error=====>ex:{},tyrcnt:{},url:{}'.format(str(rex), tyrcnt, url))
            finally:
                self.wblock.release()
            if tyrcnt >= rtry and refresh:
                refresh = False
                rtry = rtry * 2
                self.refresh(ouuid)
        raise rex

    def postdata(self, url, data, ctype='', timeout=(30, 60), slt=0):
        self.mlogger.error('WbComp:postdata=====>url:{},data:{}'.format(url, data))
        if slt:
            time.sleep(slt)
        try:
            self.wblock.acquire()
            self.wblock.release()
            headers = {}
            if ctype == 'chat':
                headers['Referer'] = 'https://api.weibo.com/chat/'
            self.session.post(url, data, headers=headers, timeout=timeout)
            self.mlogger.debug('WbComp:postdata success=====>url:{}'.format(url))
        except Exception as pex:
            self.mlogger.error('WbComp:postdata error=====>ex:{},url:{}'.format(str(pex), url))


if __name__ == '__main__':
    glogger = logger.TuLog('wbcomptest', '/../log', True, logging.DEBUG).getlog()
    wbun = 'c3JldG9mJTQwbGl2ZS5jbg=='
    wbpw = '879211Qas'
    wbcomp = WbComp(wbun, wbpw, mlogger=glogger)
    wbcomp.login()
    rcode, text = wbcomp.gethtml('https://weibo.com/5705221157/HwfbzDytxcc', refresh=True)
    print(rcode)
    print(text)

    # ulocpath, utxt = wbcomp.downpage('1', 'https://weibo.com/1886824091/I3raPz6hL', '11', 'F:\\bg', mtype='1321')
    # print(ulocpath, utxt)
    #
    # ulocpath, utxt = wbcomp.downpage('2', 'https://weibo.com/1886824091/I3raPz6hL', '21', 'F:\\bg', mtype='13')
    # print(ulocpath, utxt)

    # wbcomp.downmedia('4408119490344814', fdir='F:\\bg\\4408119490344814')
    # tacd = 'uid=3275508441&profile_image_url=http://tva2.sinaimg.cn/crop.0.0.720.720.50/c33c4ad9jw8ek1hvopr8ej20k00k0ju0.jpg?Expires=1566553334&ssig=JEwmIKyLB8&KID=imgbed,tva&gid=3909747545351455&gname=股票&screen_name=跟我走吧14&sex=m'
    # tmumap = WbComp.splitacd(tacd, 'uid', 'screen_name')
    # print(tmumap)
