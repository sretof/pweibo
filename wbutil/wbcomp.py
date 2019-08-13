# -*- coding:utf-8 -*-
import base64
import logging
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

import util.caldate as cald
import util.tulog as logger

urllib3.disable_warnings()  # 取消警告


class WbComp:
    GLOGGER = logger.TuLog('wbcomp', '/../log', True, logging.WARNING).getlog()

    def __init__(self, username, password, proxies={}):
        self.username = username
        self.password = password
        self.proxies = proxies

        self.wbuid = ''
        self.mlogger = WbComp.GLOGGER

        self.wblock = threading.Lock()
        self.wbuuid = ''

    def __presession(self):
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
            self.mlogger.info('=============login success=============>wbuid:{},wbuuid:{}'.format(self.wbuid, self.wbuuid))
        # home_url = 'https://weibo.com/u/{}/home?wvr=5&lf=reg'.format(uid)  # 请求首页
        # html = self.session.get(home_url, timeout=(30, 60))
        # html.encoding = 'utf-8'
        # print(html.text)

    def login(self, ouuid=''):
        self.wblock.acquire()
        if ouuid and ouuid != self.wbuuid:
            self.wblock.release()
            return
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
                    break
                else:
                    raise Exception('no pwuid')
            except Exception as lex:
                rex = lex
                time.sleep(3)
        self.wblock.release()
        if not success:
            raise rex

    def refresh(self, ouuid):
        self.login(ouuid)

    def gethtml(self, url, ctype='', timeout=(30, 60)):
        try:
            self.wblock.acquire()
            self.wblock.release()
            headers = {}
            if ctype == 'chat':
                headers['Referer'] = 'https://api.weibo.com/chat/'
            if ctype == 'file':
                timeout = (30, 300)
            html = self.session.get(url, headers=headers, timeout=timeout)
            rcode = html.status_code
            text = ''
            if rcode == 200:
                html.encoding = 'utf-8'
                text = html.text
            html.close()
            return rcode, text, None
        except Exception as ghex:
            return 599, '', ghex


if __name__ == '__main__':
    wbun = 'sretof@live.cn'
    wbpw = '1122aaa'
    wbcomp = WbComp(wbun, wbpw)
    wbcomp.login()
    ouid = wbcomp.wbuuid
    wbcomp.refresh(ouid)
    wbcomp.refresh(ouid)
