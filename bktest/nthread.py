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
from threading import current_thread
from urllib.parse import quote

import pymysql
import requests
import rsa
import urllib3

import conf.db as dbc
import util.caldate as cald
import util.tulog as logger

urllib3.disable_warnings()  # 取消警告


def get_timestamp():
    return int(time.time() * 1000)  # 获取13位时间戳


def getMysqlConn():
    conn = pymysql.connect(dbc.DBHOST, dbc.DBUNAME, dbc.DBPWD, dbc.NDBSCHEMA)
    return conn


def closeMysqlConn(conn):
    try:
        conn.close()
    except:
        pass


def getmmmid(gid):
    conn = getMysqlConn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute('select max(mid) as maxid,min(mid) as minid from gmsg where gid={};'.format(gid))
    mmid = cursor.fetchone()
    cursor.close()
    closeMysqlConn(conn)
    return mmid


def getmaxmids(gid):
    conn = getMysqlConn()
    # cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor = conn.cursor()
    cursor.execute('select mid from gmsg where gid={} order by mid desc limit 20;'.format(gid))
    maxmids = cursor.fetchall()
    maxmidls = []
    for maxmid in maxmids:
        maxmidls.append(maxmid[0])
    cursor.close()
    closeMysqlConn(conn)
    return maxmidls


def savegcts(sql):
    conn = getMysqlConn()
    cursor = conn.cursor()
    try:
        cursor.executemany(sql, PWeiBo.ctcaches)
        conn.commit()
    except Exception as ex:
        print('save error....')
        raise ex
    finally:
        PWeiBo.ctcaches = []
        closeMysqlConn(conn)


class PWeiBo():
    weipicdir = 'F:\weibopicn'
    ctcaches = []
    sgsql = "insert into gmsg(mid,gid,buid,bname,content,cttype,fid,fpath,hasd,mdate,ftime,mtime) " \
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,str_to_date(%s,'%%Y-%%m-%%d %%H:%%i:%%S.%%f'),str_to_date(%s,'%%Y-%%m-%%d %%H:%%i:%%S.%%f'))"
    gurllock = threading.Lock()
    savelock = threading.Lock()
    chatsource = '209678993'
    pagesource = '4037146678'

    GLOGGER = logger.TuLog('pweibon', '/log', True, logging.INFO).getlog()
    CHATGIDS = ('4305987512698522',)

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
        self.trylogincnt = 0
        self.uid = uuid.uuid1()

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
                    hd = PWeiBo.fgrouphb(pweibo, ct)
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
    def fgrouphb(pweibo, hburl):
        success = 1
        html = pweibo.session.get(hburl, timeout=(30, 60))
        html.encoding = 'utf-8'
        text = html.text
        # PWeiBo.GLOGGER.error('hb page text:{}'.format(text))
        # soup = BeautifulSoup(text, 'lxml')
        return success

    @staticmethod
    def fhtmlct(pweibo, cturl):
        success = 0
        fpath = ''
        # html = pweibo.session.get(cturl, timeout=(30, 60))
        # html.encoding = 'utf-8'
        # text = html.text
        # PWeiBo.GLOGGER.error('hb page text:{}'.format(text))
        # soup = BeautifulSoup(text, 'lxml')
        return success, fpath

    @staticmethod
    def catchmcts(mid, gid, buid, bn, cttype, ct, hd, fid, fpath, mtime):
        vals = [mid, gid, buid, bn, ct, cttype, fid, fpath, hd,
                mtime.strftime('%Y%m%d'), cald.now().strftime('%Y-%m-%d %H:%M:%S.%f'), mtime.strftime('%Y-%m-%d %H:%M:%S.%f')]
        PWeiBo.ctcaches.append(vals)

    def clearsession(self):
        self.session = requests.session()  # 登录用session
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
        }
        self.session.verify = False  # 取消证书验证

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

    def prelogin(self):
        '''预登录，获取一些必须的参数'''
        self.su = base64.b64encode(self.username.encode())  # 阅读js得知用户名进行base64转码
        url = 'https://login.sina.com.cn/sso/prelogin.php?entry=weibo&callback=sinaSSOController.preloginCallBack&su={}&rsakt=mod&checkpin=1&client=ssologin.js(v1.4.19)&_={}'.format(
            quote(self.su), get_timestamp())  # 注意su要进行quote转码
        response = self.session.get(url, timeout=(30, 60)).content.decode()
        # print(response)
        self.nonce = re.findall(r'"nonce":"(.*?)"', response)[0]
        self.pubkey = re.findall(r'"pubkey":"(.*?)"', response)[0]
        self.rsakv = re.findall(r'"rsakv":"(.*?)"', response)[0]
        self.servertime = re.findall(r'"servertime":(.*?),', response)[0]
        return self.nonce, self.pubkey, self.rsakv, self.servertime

    def get_sp(self):
        '''用rsa对明文密码进行加密，加密规则通过阅读js代码得知'''
        publickey = rsa.PublicKey(int(self.pubkey, 16), int('10001', 16))
        message = str(self.servertime) + '\t' + str(self.nonce) + '\n' + str(self.password)
        self.sp = rsa.encrypt(message.encode(), publickey)
        return b2a_hex(self.sp)

    def login(self):
        self.prelogin()
        self.get_sp()
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
            'sp': self.get_sp(),
            'sr': '1536 * 864',
            'encoding': 'UTF - 8',
            'prelt': '35',
            'url': 'https://weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack',
            'returntype': 'META',
        }
        response = self.session.post(url, data=data, allow_redirects=False).text  # 提交账号密码等参数
        redirect_url = re.findall(r'location.replace\("(.*?)"\);', response)[0]  # 微博在提交数据后会跳转，此处获取跳转的url
        self.trylogincnt = 0
        result = self.session.get(redirect_url, timeout=(30, 60), allow_redirects=False).text  # 请求跳转页面
        ticket, ssosavestate = re.findall(r'ticket=(.*?)&ssosavestate=(.*?)"', result)[0]  # 获取ticket和ssosavestate参数
        uid_url = 'https://passport.weibo.com/wbsso/login?ticket={}&ssosavestate={}&callback=sinaSSOController.doCrossDomainCallBack&scriptId=ssoscript0&client=ssologin.js(v1.4.19)&_={}'.format(
            ticket, ssosavestate, get_timestamp())
        data = self.session.get(uid_url, timeout=(30, 60)).text  # 请求获取uid
        uid = re.findall(r'"uniqueid":"(.*?)"', data)[0]
        PWeiBo.GLOGGER.info('=============login success=============>uid:{}'.format(uid))
        # home_url = 'https://weibo.com/u/{}/home?wvr=5&lf=reg'.format(uid)  # 请求首页
        # html = self.session.get(home_url, timeout=(30, 60))
        # html.encoding = 'utf-8'
        # print(html.text)

    def getHtml(self, url, ctype='', timeout=(30, 60)):
        try:
            PWeiBo.gurllock.acquire()
            if ctype == 'chat':
                self.session.headers['Referer'] = 'https://api.weibo.com/chat/'
            if ctype == 'file':
                timeout = (30, 300)
            html = self.session.get(url, timeout=timeout)
            html.encoding = 'utf-8'
            text = html.text
            return text
        finally:
            if ctype == 'chat':
                self.session.headers.pop('Referer')
            PWeiBo.gurllock.release()

    def fgroupmsg(self, gid, mid='0', maxmids=[]):
        chatapiurl = 'https://api.weibo.com/webim/groupchat/query_messages.json?' \
                     'convert_emoji=1&query_sender=1&count=20&id={}&max_mid={}&source=209678993&t=1562578587256'.format(gid, mid)
        jtext = self.getHtml(chatapiurl, 'chat')
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
            PWeiBo.GLOGGER.warning(
                '>==========fgroupmsg ctcnt == 0 or not hismid url:{},hismid:{} end'.format(chatapiurl, hismid))
            return
        else:
            PWeiBo.GLOGGER.debug('fgroupmsg success gid:{},mid:{},len(ct):{}'.format(gid, mid, lenct))
            self.fgroupmsg(gid, hismid, maxmids)


def login(proxies={}):
    username = 'sretof@live.cn'  # 账号
    password = '1122aaa'  # 密码
    npweibo = PWeiBo(username, password, proxies)
    npweibo.login()
    return npweibo


def fgroupsmsg(pweibo):
    cn=5
    while cn>0:
        print('t:{},muid:{}'.format(current_thread().getName(), pweibo.uid))
        time.sleep(1)
        cn=cn-1
    # try:
    #     for gid in PWeiBo.CHATGIDS:
    #         maxmids = getmaxmids(gid)
    #         pweibo.fgroupmsg(gid, maxmids=maxmids)
    # except Exception as ex:
    #     PWeiBo.GLOGGER.exception(ex)
    #     raise ex


def fgroupshismsg(pweibo):
    print('t:{},muid:{}'.format(current_thread().getName(), pweibo.uid))
    time.sleep(2)
    raise Exception('sleep ex......')
    # try:
    #     for gid in PWeiBo.CHATGIDS:
    #         mmid = getmmmid(gid)
    #         # mmid['minid'] = '4392899204268935'
    #         pweibo.fgroupmsg(gid, mmid['minid'])
    # except Exception as ex:
    #     PWeiBo.GLOGGER.exception(ex)
    #     raise ex


global Gfcnt
Gfcnt = 0


def tcallback(f):
    global Gfcnt
    try:
        f.result()
    except Exception as ex:
        print('======nnnnnn')
        Gfcnt = 0
        # raise ex


if __name__ == '__main__':
    # mpweibo = None
    # mproxies = {}
    # hisgmsgexecutor = ThreadPoolExecutor(max_workers=1)
    # hcg = None
    # while 1:
    #     print('=================ms:', Gfcnt)
    #     try:
    #         if Gfcnt == 0:
    #             mpweibo = login(mproxies)
    #             Gfcnt = 1
    #         if hcg is not None:
    #             print('=================hcg.done:', hcg.done())
    #         if hcg is None or hcg.done():
    #             hcg = hisgmsgexecutor.submit(fgroupshismsg, mpweibo)
    #             hcg.add_done_callback(tcallback)
    #         fgroupsmsg(mpweibo)
    #     except requests.exceptions.SSLError as e:
    #         PWeiBo.GLOGGER.exception(e)
    #         mproxies = {'http': 'http://127.0.0.1:10080', 'https': 'http://127.0.0.1:10080'}
    #         Gfcnt = 0
    #     except requests.exceptions.ProxyError as e:
    #         PWeiBo.GLOGGER.exception(e)
    #         mproxies = {}
    #         Gfcnt = 0
    #     except Exception as e:
    #         print('=========================ex1')
    #         PWeiBo.GLOGGER.exception(e)
    #         Gfcnt = 0
    #     finally:
    #         print('=========================fy2')
    #         nhour = datetime.datetime.now().hour
    #         sleeptime = random.randint(1, 2)
    #         if 2 <= nhour < 8:
    #             sleeptime = random.randint(10, 1800)
    #         PWeiBo.GLOGGER.info('======sleep hour:{} sleep:{}'.format(nhour, sleeptime))
    #         time.sleep(sleeptime)
    src = 'http://gslb.miaopai.com/stream/PqCT8HhDo3ly77rSY5JKg64dV6PQoavv9ClQ.mp4?yx=&refer=weibo_app&vend=weibo&label=mp4_hd&mpflag=16&Expires=1564080983&ssig=c2BBzeGJtz&KID=unistore,video&720=&qType=480,fid:880cbc9faf0511e9b71e64006a93aa65'
    ipreg = r'.+/(\S+)\.(\S+)\?'
    rtext = re.findall(ipreg, src, re.S)
    fname = ''
    if len(rtext) > 0 and len(rtext[0]) > 1:
        fpf = rtext[0][0]
        fsf = rtext[0][1]
        fname = fpf + '.' + fsf
    print(fname)
