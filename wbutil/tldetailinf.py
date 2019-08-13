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
from urllib.parse import unquote

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
            return rcode, text
        except Exception as ghex:
            raise ghex

    ############
    # FEED INFO
    ############
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

    ############
    # DETAIL INFO
    ############
    @staticmethod
    def alytldetailinfo(feed):
        unamed = feed.select_one('div.WB_detail > div.WB_info a:first-child')
        curltimed = feed.select_one('div.WB_detail > div.WB_from.S_txt2 a:first-child')
        uname = unamed.text
        curl = curltimed.get('href', '')
        curl = curl.split('?', 1)[0]
        if not curl.startswith('http'):
            curl = 'https://weibo.com' + curl
        ctime = curltimed.get('title', '')
        return curl, uname, ctime

    ############
    # DETAIL CT
    ############
    @staticmethod
    def alytldetailtxt(txtdiv, mtype, files):
        adoms = txtdiv.select('a')
        idoms = txtdiv.select('img')
        txtsuf = ''
        for adom in adoms:
            fauuid = ''.join(str(uuid.uuid1()).split('-'))
            if adom.get('render', '') == 'ext':
                pass
            elif 'WB_text_opt' in adom.get('class', []):
                mtype = '13'
                furl = adom.get('href', '')
                if furl.startswith('//'):
                    furl = 'https:' + furl
                elif furl.startswith('/'):
                    furl = 'https://weibo.com' + furl
                elif furl.startswith('http'):
                    pass
                else:
                    furl = ''
                    WbComp.GLOGGER.warning('alytldetailtxt WB_text_opt adom url???????????????{}'.format(furl))
                if furl:
                    file = {'url': furl, 'hasd': 0, 'mtype': mtype, 'fid': fauuid}
                    files.append(file)
            elif adom.get('action-type', '') == 'feed_list_url':
                lidom = adom.select_one('i.ficon_cd_link')
                vidom = adom.select_one('i.ficon_cd_video')
                wficon = adom.select_one('i.W_ficon')
                hasd = 0
                furl = adom.get('href', '')
                amtype = '14'
                if 'huati.weibo' in furl:
                    furl = ''
                elif vidom is not None:
                    hasd = 1
                    amtype = '22'
                elif lidom is not None:
                    mtype = '14'
                elif wficon is not None:
                    furl = ''
                else:
                    furl = ''
                    WbComp.GLOGGER.warning('alytldetailtxt txtdiv adom1???????????????' + str(adom))
                if furl:
                    file = {'url': furl, 'hasd': hasd, 'mtype': amtype, 'fid': fauuid}
                    files.append(file)
            elif adom.get('action-type', '') == 'widget_photoview':
                furl = adom.get('short_url', '')
                if furl:
                    file = {'url': furl, 'hasd': 0, 'mtype': '211', 'fid': fauuid}
                    files.append(file)
            elif adom.get('action-type', '') == 'fl_url_addparams':
                pass
            else:
                WbComp.GLOGGER.warning('alytldetailtxt txtdiv adom2???????????????' + str(adom))
        for idom in idoms:
            itit = idom.get('title', '')
            if itit:
                txtsuf = txtsuf + itit
        txt = txtdiv.text.strip()
        if txtsuf:
            txt = txt + '//face:' + txtsuf
        return txt, mtype, files

    @staticmethod
    def alytlvideosource(psv):
        psvs = psv.split('=http')
        if len(psvs) > 0:
            psvs.reverse()
            for p in psvs:
                if 'ssig' in p and 'qType' in p:
                    psv = 'http' + p
                    break
        return unquote(psv)

    @staticmethod
    def alytldetailmedia(mediadiv, uid, mid, mtype, files):
        if mediadiv is not None:
            fmuuid = ''.join(str(uuid.uuid1()).split('-'))
            mediaul = mediadiv.select_one('ul.WB_media_a')
            fdiv = mediadiv.select_one('div.WB_feed_spec[action-data]')
            fvdiv = mediadiv.select_one('div.WB_feed_spec > div.spec_box > div[video-sources]')
            if fdiv is not None and fdiv['action-data'].startswith('url'):
                hasd = 0
                furl = unquote(fdiv['action-data'][4:])
                if furl.startswith('//'):
                    furl = 'https:' + furl
                elif furl.startswith('http'):
                    pass
                else:
                    furl = ''
                    WbComp.GLOGGER.warning('alytldetailmedia fdiv url???????????????{}'.format(furl))
                smtype = '15'
                if 'ttarticle' in furl:
                    for oldf in files:
                        if oldf['mtype'] == '14':
                            oldf['hasd'] = 1
                    mtype = '15'
                else:
                    smtype = '99'
                    hasd = 1
                if furl:
                    file = {'url': furl, 'hasd': hasd, 'mtype': smtype, 'fid': fmuuid}
                    files.append(file)
            if mediaul is not None:
                piclis = mediaul.select('li.WB_pic')
                if len(piclis) > 0:
                    mtype = mtype + '21'
                for picli in piclis:
                    acdtxt = picli.get('action-data', '')
                    rpic = r'pid=(\w+)|pic_id=(\w+)'
                    rtext = re.findall(rpic, acdtxt, re.S)
                    if len(rtext) > 0:
                        pid = rtext[0][0] or rtext[0][1]
                        furl = 'https://photo.weibo.com/{}/wbphotos/large/mid/{}/pid/{}'.format(uid, mid, pid)
                        file = {'url': furl, 'hasd': 0, 'mtype': mtype, 'fid': pid}
                        files.append(file)
                    else:
                        vpic = r'gif_url=([^&]+)'
                        vtext = re.findall(vpic, acdtxt, re.S)
                        if len(vtext) > 0:
                            vurl = 'https:' + unquote(vtext[0])
                            vfuid = ''.join(str(uuid.uuid1()).split('-'))
                            file = {'url': vurl, 'hasd': 0, 'mtype': '22', 'fid': vfuid}
                            files.append(file)
                videoli = mediaul.select_one('li.WB_video[video-sources]')
                if videoli is not None:
                    mtype = mtype + '22'
                    pvs = WbComp.alytlvideosource(videoli['video-sources'])
                    vfuid = ''.join(str(uuid.uuid1()).split('-'))
                    file = {'url': pvs, 'hasd': 0, 'mtype': '22', 'fid': vfuid}
                    files.append(file)
            if fvdiv is not None:
                mtype = mtype + '23'
                pvs = WbComp.alytlvideosource(fvdiv['video-sources'])
                vfuid = ''.join(str(uuid.uuid1()).split('-'))
                file = {'url': pvs, 'hasd': 0, 'mtype': '23', 'fid': vfuid}
                files.append(file)
            if mediaul is None and fdiv is None and fvdiv is None:
                WbComp.GLOGGER.warning('alytldetailmedia media_box???????????????' + str(mediadiv))
        return mtype, files


if __name__ == '__main__':
    wbun = 'sretof@live.cn'
    wbpw = '1122aaa'
    wbcomp = WbComp(wbun, wbpw)
    wbcomp.login()
    ouid = wbcomp.wbuuid
    wbcomp.refresh(ouid)
    wbcomp.refresh(ouid)
