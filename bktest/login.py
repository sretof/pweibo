import base64
import json
import logging
import random
import re
import threading
import time
from binascii import b2a_hex
from urllib.parse import quote

import pymysql
import requests
import rsa
import urllib3
from bs4 import BeautifulSoup

import conf.db as dbc
import util.caldate as cald
import util.tulog as logger

urllib3.disable_warnings()  # 取消警告

from pymongo import MongoClient


def get_timestamp():
    return int(time.time() * 1000)  # 获取13位时间戳


def getMysqlConn():
    conn = pymysql.connect(dbc.DBHOST, dbc.DBUNAME, dbc.DBPWD, dbc.DBSCHEMA)
    return conn


def closeMysqlConn(conn):
    try:
        conn.close()
    except:
        pass


def getmmmid(gid):
    conn = getMysqlConn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("select max(mid) as maxid,min(mid) as minid from gmsg where gid=%s;" % (gid))
    mmid = cursor.fetchone()
    cursor.close()
    closeMysqlConn(conn)
    return mmid


def getmaxmids(gid):
    conn = getMysqlConn()
    # cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor = conn.cursor()
    cursor.execute("select mid from gmsg where gid=%s order by mid desc limit 20;" % (gid))
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
        PWeiBo.ctcaches = []
    except Exception as e:
        print('save error....')
        raise (e)
    finally:
        closeMysqlConn(conn)


class PWeiBo():
    weipicdir = 'F:\weibopic'
    ctcaches = []
    sgsql = "insert into gmsg(mid,gid,bname,content,cttype,fid,fpath,hasd,fdate,ftime) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,str_to_date(%s,'%%Y-%%m-%%d %%H:%%i:%%S.%%f'))"

    GLOGGER = logger.TuLog('pweibologin', '/../log', True, logging.INFO).getlog()

    MGOCTCOLL = 'Contents'

    ADUID = ('1678870364',)
    ADURL = ('tui.weibo.com',)

    SENLOCK = threading.Lock()

    # sgsql = "insert into gmsg(mid,gid,bname,content,cttype,fid,fpath,hasd,fdate) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)"

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

    @staticmethod
    def creatgid(gid, gname):
        return '{}&name={}&type=2'.format(gid, quote(gname))

    @staticmethod
    def getgmsgfct(text):
        p = r'<script>FM\.view\({"ns":"pl\.msgbox\.detail\.index",(.*?)\)</script>'
        jtext = re.findall(p, text, re.S)
        jtext = '{' + jtext[0]
        ptext = json.loads(jtext)
        thtml = ptext['html']
        return thtml

    @staticmethod
    def getgmsghct(text):
        ptext = json.loads(text)
        thtml = ptext['data']['html']
        hismid = ptext['data']['oldid']
        return thtml, hismid

    @staticmethod
    def splitgmsgacd(acd):
        acds = re.findall(r'id=(\d+)&gid=(\d+)', acd, re.S)
        if len(acds) == 1 and len(acds[0]) == 2:
            return acds[0][0], acds[0][1]
        else:
            return '', ''

    # 如果有maxmid,到maxmid就返回-1
    @staticmethod
    def fgroupmsgct(pweibo, thtml, gid, maxmids=[]):
        soup = BeautifulSoup(thtml, 'lxml')
        bubdoms = soup.select('div.msg_bubble_list.bubble_l[node-type="item"]')
        retl = 0
        if bubdoms is None or len(bubdoms) == 0:
            PWeiBo.GLOGGER.warning('fgroupmsgct not content gid:{} maxmids:{}...'.format(gid, maxmids[0:2]))
        else:
            fmids = []
            retl = len(bubdoms)
            bubdoms.reverse()
            for bubdom in bubdoms:
                mid = bubdom['mid']
                if maxmids and mid in maxmids:
                    PWeiBo.GLOGGER.info('fgroupmsgct gid:{} mid:{} maxmids:{}... stop'.format(gid, mid, maxmids[0:2]))
                    retl = -1
                    break
                bn = ''
                ct = ''
                cttype = '1'
                fid = ''
                fpath = ''
                hd = 0
                bndom = bubdom.select_one('p.bubble_name')
                if bndom is not None:
                    bn = bndom.text
                bcodom = bubdom.select_one('div.bubble_cont')
                if bcodom is not None:
                    bmdom = bcodom.select_one('div.bubble_main')
                    if bmdom is not None:
                        # 文本
                        ctdom = bmdom.select_one('div.cont > p.page')
                        if ctdom is not None:
                            ct = ctdom.text
                            if not ct:
                                ctwimgdoms = ctdom.select('img.W_img_face')
                                if ctwimgdoms is not None:
                                    for ctwimgdom in ctwimgdoms:
                                        title = ctwimgdom['title']
                                        if title:
                                            ct = ct + title
                        # CARD
                        cddomhb = bmdom.select_one('div.WB_feed_spec.S_bg2.S_line1 div.WB_feed_spec_clearfix a')
                        if cddomhb is not None:
                            text = cddomhb.text
                            hburl = cddomhb['href']
                            if text == '抢红包':
                                cttype = '4'
                                success = PWeiBo.fgrouphb(pweibo, hburl)
                                ct = ct + ' | success:' + str(success) + ' | hburl:' + hburl
                        cddomct = bmdom.select_one('div.WB_feed_spec.S_bg2.S_line1 div.WB_feed_spec_cont a')
                        if cddomct is not None:
                            cttype = '2'
                            cturl = cddomhb['href']
                            ct = ct + ' | cturl:' + cturl
                        # 附件
                        fpbdom = bmdom.select_one('div.cont > div.pic_s_mod > div.pic_box > img')
                        if fpbdom is not None:
                            ofp = fpbdom['src']
                            fid = re.findall(r'\S+fid=(\d+)', ofp, re.S)
                            source = re.findall(r'\S+source=(\d+)', ofp, re.S)
                            if len(fid) == 1 and len(source) == 1:
                                cttype = '3'
                                fp = 'https://upload.api.weibo.com/2/mss/msget?fid={}&source={}'.format(fid[0], source[0])
                                ct = ct + ' | file:' + fp
                                try:
                                    fpath = pweibo.downpic(fp)
                                    hd = 1
                                except Exception as e:
                                    print("down pic field......:", fp)
                                    print(e)
                if ct:
                    PWeiBo.catchmcts(mid, gid, bn, cttype, ct, hd, fid, fpath)
                    savegcts(PWeiBo.sgsql)
                    fmids.append(mid)
            PWeiBo.GLOGGER.info('fgroupmsgct gid:{} mid:{},maxmids:{}...,fmids:{}'.format(gid, mid, maxmids[0:2], fmids))
        return retl

    @staticmethod
    def fgrouphb(pweibo, hburl):
        success = 0
        html = pweibo.session.get(hburl, timeout=(30, 60))
        html.encoding = 'utf-8'
        text = html.text
        # PWeiBo.GLOGGER.error('hb page text:{}'.format(text))
        # soup = BeautifulSoup(text, 'lxml')
        return success

    @staticmethod
    def catchmcts(mid, gid, bn, cttype, ct, hd, fid, fpath):
        vals = [mid, gid, bn, ct, cttype, fid, fpath, hd, cald.today().strftime('%Y%m%d'), cald.now().strftime('%Y-%m-%d %H:%M:%S.%f')]
        # vals = [mid, gid, bn, ct, cttype, fid, fpath, hd, cald.today().strftime('%Y%m%d')]
        PWeiBo.ctcaches.append(vals)
        # {
        #     'mid': mid,
        #     'gid': gid,
        #     'bname': bn,
        #     'content': ct,
        #     'cttype': cttype,
        #     'fid': 'fid',
        #     'fpath': 'fpath',
        #     'hasd': hd,
        #     'fdate': cald.today().strftime('%Y%m%d'),
        #     'ftime': cald.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        # }

    def clearsession(self):
        self.session = requests.session()  # 登录用session
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
        }
        self.session.verify = False  # 取消证书验证

    def downpic(self, src, gid='4305987512698522'):
        fid = ''
        path = ''
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
        return path

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

    def gethtml(self, url, ctype='', timeout=(30, 60)):
        try:
            PWeiBo.SENLOCK.acquire()
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
            PWeiBo.SENLOCK.release()

    def fgroupmsg(self, gid, fgid, maxmids):
        PWeiBo.GLOGGER.info('==========fgroupmsg ssssss gid:{} maxmids:{}========='.format(gid, maxmids))
        gmsg_url = 'https://weibo.com/message/history?gid={}&_t={}'.format(fgid, get_timestamp())
        html = self.session.get(gmsg_url, timeout=(30, 60))
        html.encoding = 'utf-8'
        text = html.text
        PWeiBo.GLOGGER.info('fgroupmsg success get html;gurl:{}'.format(gmsg_url))
        # PWeiBo.GLOGGER.info('fgroupmsg text:{}'.format(text))
        # 取群组当前对话记录
        thtml = PWeiBo.getgmsgfct(text)
        ctcnt = PWeiBo.fgroupmsgct(self, thtml, gid, maxmids)
        if ctcnt == 0:
            PWeiBo.GLOGGER.error('fgroupmsg content length is 0')
        elif ctcnt == -1:  # 已到maxmid
            PWeiBo.GLOGGER.info('fgroupmsg ctcnt == -1 stop')
        else:
            # 取群组历史记录
            soup = BeautifulSoup(thtml, 'lxml')
            acddom = soup.select_one('p.private_dialogue_more')
            if acddom is None or acddom['action-data'] is None:
                PWeiBo.GLOGGER.error('fgroupmsg acddom is None or acddom[\'action-data\'] is None')
            else:
                acdata = acddom['action-data']
                acdata = PWeiBo.splitgmsgacd(acdata)
                mid = acdata[0]
                if mid:
                    PWeiBo.GLOGGER.info('fgroupmsg hismid:[{}]'.format(mid))
                    self.fgroupmsghis(gid, mid, maxmids)
        PWeiBo.GLOGGER.info('==========fgroupmsg eeeeeeeee=========')

    def fgroupmsghis(self, gid, mid, maxmids=[]):
        gmsgh_url = 'https://weibo.com/aj/groupchat/getdialog?_wv=5&ajwvr=6&mid={}&gid={}&_t=0&__rnd={}'.format(mid, gid, get_timestamp())
        # gmsgh_url = 'https://weibo.com/aj/groupchat/getdialog?_wv=5&ajwvr=6&mid=4382738813173855&gid=4305987512698522&_t=0&__rnd=453'
        html = self.session.get(gmsgh_url, timeout=(30, 60))
        html.encoding = 'utf-8'
        text = html.text
        PWeiBo.GLOGGER.info('fgroupmsghis success get html;gid:[{}] mid:[{}] maxmid:[{}] gurl:{}'.format(gid, mid, maxmids, gmsgh_url))
        # PWeiBo.GLOGGER.info('fgroupmsghis success get html;gid:[{}] mid:[{}] maxmid:[{}] gurl:{} text:{}'.format(gid, mid, maxmids, gmsgh_url, text))
        thtml, hismid = PWeiBo.getgmsghct(text)
        # PWeiBo.GLOGGER.info(thtml)
        ctcnt = PWeiBo.fgroupmsgct(self, thtml, gid, maxmids)
        if ctcnt == -1:
            PWeiBo.GLOGGER.info('>==========groupmsghis to maxmids end')
            return
        if ctcnt == 0 or not hismid:
            PWeiBo.GLOGGER.warning(
                '>==========fgroupmsghis ctcnt == 0 or not hismid url:{},hismid:{} end'.format(gmsgh_url, hismid))
            return
        else:
            PWeiBo.GLOGGER.debug('fgroupmsghis success gid:{},mid:{},len(ct):{}'.format(gid, mid, ctcnt))
            self.fgroupmsghis(gid, hismid, maxmids)

    def fgroupct(self, gid, maxmid=0, maxy=3):
        gcturl = 'https://weibo.com/mygroups?gid={}'.format(gid)
        text = self.gethtml(gcturl)
        p = r'<script>FM\.view\({"ns":"pl\.content\.homefeed\.index",(.*?)\)</script>'
        jtext = re.findall(p, text, re.S)
        jtext = '{' + jtext[0]
        ptext = json.loads(jtext)
        thtml = ptext['html']
        # print(thtml)
        soup = BeautifulSoup(thtml, 'lxml')
        feeds = soup.select('div.WB_feed.WB_feed_v3.WB_feed_v4 > div[tbinfo]')
        for feed in feeds:
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
            if detail is None or not mid or not uid or uid in PWeiBo.ADUID:
                continue
            unamed = detail.select_one('div.WB_info a:first-child')
            curltimed = detail.select_one('div.WB_from.S_txt2 a:first-child')

            uname = unamed.text
            curl = curltimed.get('href', '')
            for adurl in PWeiBo.ADURL:
                if adurl in curl:
                    continue
            curl = curl.split('?', 1)[0]
            if not curl.startswith('http'):
                curl = 'https://weibo.com' + curl
            ctime = curltimed.get('title', '')

            # 0 txt;131 l txt;132 a;14 link;211 pics;21 video;41() fwd
            mtype = 0
            files = []

            # txt div
            txtdiv = feed.select_one('div.WB_detail > div.WB_text.W_f14')
            adoms = txtdiv.select('a')
            idoms = txtdiv.select('img')
            txtpre = ''
            txtsuf = ''
            for adom in adoms:
                if adom.get('render', '') == 'ext':
                    txtpre = txtpre + adom.text
                elif 'WB_text_opt' in adom.get('class', []):
                    mtype = 13
                    furl = adom.get('href', '')
                    if not furl.startswith('http'):
                        furl = 'https:' + furl
                    file = {'url': furl, 'hasd': 0, 'fpath': '', 'mtype': mtype}
                    files.append(file)
                elif adom.get('action-type', '') == 'feed_list_url':
                    mtype = 14
                    furl = adom.get('href', '')
                    file = {'url': furl, 'hasd': 0, 'fpath': '', 'mtype': mtype}
                    files.append(file)
                else:
                    PWeiBo.GLOGGER.warning('???????????????' + str(adom))
            for idom in idoms:
                itit = idom.get('title', '')
                if itit:
                    txtsuf = txtsuf + itit
            txt = txtdiv.text.strip()
            txt = txtpre + txt + txtsuf

            # media div
            mediadiv = feed.select_one('div.WB_detail > div.WB_media_wrap > div.media_box')
            if mediadiv is not None:
                picsul = mediadiv.select_one('ul.WB_media_a')
                piclis = []
                mtype = 21
                if picsul is not None:
                    piclis = picsul.select('li.WB_pic')
                for picli in piclis:
                    acdtxt = picli.get('action-data', '')
                    rpic = r'pid=(\w+)|pic_id=(\w+)'
                    rtext = re.findall(rpic, acdtxt, re.S)
                    pid = rtext[0][0] or rtext[0][1]
                    if pid:
                        furl = 'https://photo.weibo.com/{}/wbphotos/large/mid/{}/pid/{}'.format(uid, mid, pid)
                        file = {'url': furl, 'hasd': 0, 'fpath': '', 'mtype': mtype}
                        files.append(file)
            maxt = 10
            if len(txt) < maxt:
                maxt = len(txt)
            print(mid, '|', uid, '|', uname, '|', curl, '|', ctime, '|', mtype, '|', files, '|', txt[0:maxt])


def login(proxies={}):
    username = 'sretof@live.cn'  # 账号
    password = '1122aaa'  # 密码
    pweibo = PWeiBo(username, password, proxies)
    pweibo.login()
    return pweibo


def fgroupmsg(pweibo):
    gids = ({'gid': '4305987512698522', 'fgid': PWeiBo.creatgid('4305987512698522', 'Peter羊的V+')},)
    for gid in gids:
        # 手动取跳过的历史对话
        # if gid['gid'] == '4305987512698522':
        #     smid = '4391502253478611'
        #     emids = ['4390830732740103', '4390830510592780']
        #     pweibo.fgroupmsghis(gid['gid'], smid, emids)
        # 正常循环取当前对话
        maxmids = getmaxmids(gid['gid'])
        pweibo.fgroupmsg(gid['gid'], gid['fgid'], maxmids)
        # 第一次取所有历史对话
        # mmid = getmmmid(gid['gid'])
        # PWeiBo.GLOGGER.info('==========fgroupmsghis ssssss gid:{} minmid:{}========='.format(gid, mmid['minid']))
        # pweibo.fgroupmsghis(gid['gid'], mmid['minid'])
        # PWeiBo.GLOGGER.info('==========fgroupmsghis eeeeeeeee=========')

        # 新接口
        # smid0 = '4362373467209194'
        # smid1 = '4362373462292292'
        # smid2 = '4385575618104619'
        # gmsgh_url = 'https://api.weibo.com/webim/groupchat/query_messages.json?' \
        #             'convert_emoji=1&query_sender=1&count=20&id=4305987512698522&max_mid={}&source=209678993&t=1562578587256'.format(smid2)
        # pweibo.session.headers['Referer'] = 'https://api.weibo.com/chat/'
        # html = pweibo.session.get(gmsgh_url, timeout=(30, 60))
        # html.encoding = 'utf-8'
        # text = html.text
        # print(text)

        # 302
        # html = pweibo.session.get('http://t.cn/Aip7M85C')
        # html.encoding = 'utf-8'
        # text = html.text
        # print(text)


def fpagemid(pweibo, url):
    html = pweibo.session.get('https://weibo.com/aj/v6/comment/big?ajwvr=6&id=4393233741827553&page=3', timeout=(30, 60))
    html.encoding = 'utf-8'


def getMongoWDb():
    conn = MongoClient(dbc.MGOHOST, 27017)
    wdb = conn[dbc.MGOWDB]
    return wdb


def getmaxgpmids(gid):
    wdb = getMongoWDb()
    coll = wdb[PWeiBo.MGOCTCOLL]
    results = coll.aggregate([{'$group': {'_id': "$gid", 'maxmid': {'$max': "$mid"}}}])
    print(gid)
    print(type(results))
    for r in results:
        print(r)


if __name__ == '__main__':
    getmaxgpmids('1')
    pweibo = login()
    pweibo.fgroupct('3653960185837784')

# text1 = 'ouid=5705221157&rouid=2752396553'
# text2 = 'ouid=5705221157'
# pti = r'ouid=(\d+)&rouid=(\d+)|ouid=(\d+)'
# jtext1 = re.findall(pti, text1, re.S)
# print(jtext1,(jtext1[0][2] or jtext1[0][0]))
# jtext2 = re.findall(pti, text2, re.S)
# print(jtext2,(jtext2[0][2] or jtext2[0][0]))

# fcnt = 0
# pweibo = None
# proxies = {}
# while 1:
#     try:
#         if fcnt == 0:
#             pweibo = login(proxies)
#         fgroupmsg(pweibo)
#         fcnt = fcnt + 1
#         if fcnt > 500:
#             fcnt = 0
#     except requests.exceptions.SSLError as e:
#         PWeiBo.GLOGGER.exception(e)
#         proxies = {'http': 'http://127.0.0.1:10080', 'https': 'http://127.0.0.1:10080'}
#         fcnt = 0
#     except requests.exceptions.ProxyError as e:
#         PWeiBo.GLOGGER.exception(e)
#         proxies = {}
#         fcnt = 0
#     except Exception as e:
#         PWeiBo.GLOGGER.error(e)
#         fcnt = 0
#     finally:
#         nhour = datetime.datetime.now().hour
#         sleeptime = random.randint(1, 3)
#         if 1 <= nhour < 8:
#             sleeptime = random.randint(60, 1800)
#         PWeiBo.GLOGGER.info('======sleep hour:{} sleep:{}'.format(nhour, sleeptime))
#         time.sleep(sleeptime)

# text = "<div class=\"WB_red_bgimg\" id=\"pl_redEnvelope_showRedTPL\"><script type=\"text/javascript\">" \
#         "$CONFIG['bonus'] = \"4.81\"; $CONFIG['set_id'] = \"6000052111534\"; $CONFIG['bomb_id'] = \"\"</script>"
# # p = r'\$CONFIG[\'bonus\'](\.+)'
# p = r'\$CONFIG\[\'bonus\'\]\s*=\s*\"(.+?)\"'
# jtext = re.findall(p, text, re.S)
# print(type(jtext[0]))
# print(float(jtext[0])>0)

# pweibo = login()
# html = pweibo.session.get('https://weibo.com/aj/v6/comment/big?ajwvr=6&id=4393233741827553&page=3', timeout=(30, 60))
# html.encoding = 'utf-8'
# jtext = html.text
# tjson = json.loads(jtext)
# thtml = tjson['data']['html']
# print(thtml)

# html = pweibo.session.get('http://t.cn/AiWYz5nN', timeout=(30, 60))
# html.encoding = 'utf-8'
# text = html.text
# p = r'<script>FM\.view\({"ns":"pl\.content\.weiboDetail\.index",(.*?)\)</script>'
# jtext = re.findall(p, text, re.S)
# jtext = '{' + jtext[0]
# tjson = json.loads(jtext)
# thtml = tjson['html']
# soup = BeautifulSoup(thtml, 'lxml')
# # infodom = soup.select('div.msg_bubble_list.bubble_l[node-type="item"]')
# cwdom = soup.select('div.WB_cardwrap.WB_feed_type.S_bg2[tbinfo][mid]')
# print(cwdom)

# thtml = '<div class="WB_text W_f14" node-type="feed_list_content">sfa<img class="W_img_face" render="ext" src="//img.t.sinajs.cn/t4/appstyle/expression/ext/normal/a1/2018new_doge02_org.png" title="[doge]" alt="[doge]" type="face">fsa</div>'
# soup = BeautifulSoup(thtml, 'lxml')
# ddom = soup.select_one('div.WB_text.W_f14')
# print(ddom.html)

# thtml = '<div class="WB_text W_f14">' \
#         '<a suda-uatrack="key=minicard&amp;value=pagelink_minicard_click" title="网页链接" href="http://t.cn/AiljHACp" alt="http://t.cn/AiljHACp" action-type="feed_list_url" target="_blank" rel="noopener noreferrer"><i class="W_ficon ficon_cd_link">O</i>网页链接</a>' \
#         '<a target="_blank" render="ext" suda-uatrack="key=topic_click&amp;value=click_topic" class="a_topic" extra-data="type=topic" href="//s.weibo.com/weibo?q=%23%E5%A4%A7%E5%9C%B0%E8%AF%B4%E5%8E%9F%E6%B2%B9%23&amp;from=default">#大地说原油#</a>' \
#         '<a target="_blank" href="//weibo.com/1648195723/HEBqIyHbl" class="WB_text_opt" suda-uatrack="key=original_blog_unfold&amp;value=click_unfold:4396770048269147:1648195723" action-type="fl_unfold" action-data="mid=4396770048269147&amp;is_settop&amp;is_sethot&amp;is_setfanstop&amp;is_setyoudao">展开全文<i class="W_ficon ficon_arrow_down">c</i></a>' \
#         '<img class="W_img_face" render="ext" src="//img.t.sinajs.cn/t4/appstyle/expression/ext/normal/9f/2018new_jiayou_org.png" title="[加油]" alt="[加油]" type="face" style="visibility: visible;"></div>'
# soup = BeautifulSoup(thtml, 'lxml')
# adoms = soup.select('div.WB_text.W_f14 a')
# for adom in adoms:
#     print(adom.get('render', ''), '||', adom.get('class', ''), '||', adom.get('href', ''), '||', adom.text)
#
# idoms = soup.select('div.WB_text.W_f14 img')
# for idom in idoms:
#     print(idom.get('title', ''))

# text1 = 'isPrivate=0&relation=0&pic_id=006mrbaagy1g57k3lwck2j34h42zjnpo'
# text2 = 'isPrivate=0&relation=0&pid=6fb2f7c2gy1g58qcn9av3j206o06oglo&object_ids=1042018%3A0373e17b054929f01d9b1d70fbbe3003&photo_tag_pids=&uid=1873999810&mid=4396902356908951&pic_ids=6fb2f7c2gy1g58qcn9av3j206o06oglo&pic_objects='
#
# pti = r'pid=(\w+)|pic_id=(\w+)'
# jtext1 = re.findall(pti, text1, re.S)
# jtext2 = re.findall(pti, text2, re.S)
#
# print(jtext1[0][0] or jtext1[0][1])
# print(jtext2[0][0] or jtext1[0][1])
