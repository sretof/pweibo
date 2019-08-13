# -*- coding:utf-8 -*-
import base64
import datetime
import json
import logging
import os
import random
import re
import threading
import time
import uuid
from binascii import b2a_hex
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from urllib.parse import unquote

import requests
import rsa
import urllib3
from bs4 import BeautifulSoup

import conf.db as dbc
import util.caldate as cald
import util.tulog as logger

urllib3.disable_warnings()  # 取消警告

from pymongo import MongoClient


class PWeiBo():
    weipicdir = 'F:\OneDrive\weibopic'
    ctcaches = []
    sgsql = "insert into gmsg(mid,gid,bname,content,cttype,fid,fpath,hasd,fdate,ftime) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,str_to_date(%s,'%%Y-%%m-%%d %%H:%%i:%%S.%%f'))"

    GLOGGER = logger.TuLog('wbtlmid', '/log', True, logging.WARNING).getlog()

    MGOCTCOLL = 'Contents'

    ADURL = ('tui.weibo',)

    SENLOCK = threading.Lock()

    downfexecutor = ThreadPoolExecutor(max_workers=5)
    fmbtlexecutor = ThreadPoolExecutor(max_workers=2)

    TLGIDS = ('3653960185837784', '3909747545351455', '4198223948149624', '4005405388023195', '3951063348253369')

    NDIMGCLS = ['W_img_statistics', 'W_face_radius']

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
        self.gumaplock = threading.Lock()
        self.gumap = {}

    def clearsession(self):
        self.session = requests.session()  # 登录用session
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
        }
        self.session.verify = False  # 取消证书验证

    def prelogin(self):
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
        response = self.session.post(url, data=data, allow_redirects=False)  # 提交账号密码等参数
        response.encoding = 'utf-8'
        # print(response.text)
        redirect_url = re.findall(r'location.replace\("(.*?)"\);', response.text)[0]  # 微博在提交数据后会跳转，此处获取跳转的url
        self.trylogincnt = 0
        result = self.session.get(redirect_url, timeout=(30, 60), allow_redirects=False).text  # 请求跳转页面
        ticket, ssosavestate = re.findall(r'ticket=(.*?)&ssosavestate=(.*?)"', result)[0]  # 获取ticket和ssosavestate参数
        uid_url = 'https://passport.weibo.com/wbsso/login?ticket={}&ssosavestate={}&callback=sinaSSOController.doCrossDomainCallBack&scriptId=ssoscript0&client=ssologin.js(v1.4.19)&_={}'.format(
            ticket, ssosavestate, cald.gettimestamp())
        data = self.session.get(uid_url, timeout=(30, 60)).text  # 请求获取uid
        uid = re.findall(r'"uniqueid":"(.*?)"', data)[0]
        PWeiBo.GLOGGER.info('=============login success=============>uid:{}'.format(uid))
        self.pwuid = uid
        # home_url = 'https://weibo.com/u/{}/home?wvr=5&lf=reg'.format(uid)  # 请求首页
        # html = self.session.get(home_url, timeout=(30, 60))
        # html.encoding = 'utf-8'
        # print(html.text)

    @staticmethod
    def getpageinfo(paged):
        hemid = ''
        hpge = ''
        sem = paged.select_one('em[node-type="feedsincemaxid"]')
        if sem is not None:
            semad = sem.get('action-data', '')
            psemad = r'since_id=(\d+)'
            rtext = re.findall(psemad, semad, re.S)
            if len(rtext) > 0:
                hemid = rtext[0]
        lazyd = paged.select_one('div.WB_cardwrap.S_bg2[node-type="lazyload"]')
        if lazyd is not None:
            hpge = lazyd.get('action-data', '')
        feeds = paged.select('div.WB_cardwrap[tbinfo]')
        return hemid, hpge, feeds

    @staticmethod
    def getmupageinfo(paged):
        lazyd = paged.select_one('div.WB_cardwrap.S_bg2[node-type="lazyload"]')
        pagesli = paged.select('div.W_pages > span.list > div.layer_menu_list.W_scroll > ul > li > a[bpfilter]')
        feeds = paged.select('div.WB_cardwrap[tbinfo]')
        return lazyd, pagesli, feeds

    @staticmethod
    def getmupagenexturl(ftype, smuid, page, pagebar, pdomian, ppageid, lazyd, pagesli, feeds, rtcnt):
        smurl = ''
        npagebar = ''
        npage = ''
        if pdomian and ppageid and lazyd is not None:
            smurl = 'https://weibo.com/p/aj/v6/mblog/mbloglist?ajwvr=6&domain={}&is_all=1' \
                    '&pagebar={}&id={}&page={}&pre_page={}&__rnd={}'.format(pdomian, pagebar, ppageid, page, page, cald.gettimestamp())
            npagebar = pagebar + 1
        elif pdomian and ppageid and lazyd is None and len(pagesli) < 1 and len(feeds) > 0:
            smurl = 'LAZYDEND'
        elif pdomian and ppageid and len(pagesli) > 0:
            if page >= len(pagesli):
                smurl = 'PAGESLIEND'
            else:
                if ftype == '0' or ftype == '1':
                    npage = page + 1
                elif ftype == '9':
                    npage = len(pagesli)
                smurl = 'https://weibo.com/u/{}?page={}&is_all=1'.format(smuid, npage)
        elif rtcnt > 3:
            smurl = 'ERROR'
        return smurl, npagebar, npage

    @staticmethod
    def getfeedinfo(feed):
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
    def getdetailinfo(feed):
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
    def getfwddoc(fwd):
        fwdhsave = False
        fmtype = '0'
        # fcurl, ftxt, fctime, fuid, funame = ''
        ffiles = []
        infod = fwd.select_one('div.WB_info a:first-child')
        if infod is None:
            return None, None, None
        suda = infod.get('suda-uatrack', '')
        sreg = r'transuser_nick:(\d+)'
        srtxt = re.findall(sreg, suda, re.S)
        fwdmid = '' if len(srtxt) < 1 else srtxt[0]
        if fwdmid:
            fsdt = getgpbymid(fwdmid)
            if fsdt is None:
                funame = infod.get('nick-name', '')
                fuc = infod.get('usercard', '')
                freg = r'id=(\d+)'
                fuidtxt = re.findall(freg, fuc, re.S)
                fuid = '' if len(fuidtxt) < 1 else fuidtxt[0]
                fctimed = fwd.select_one('div.WB_from a:first-child')
                fcurl = 'https://weibo.com' + fctimed.get('href', '')
                fctime = fctimed.get('title', '')
                txtd = fwd.select_one('div.WB_text')
                fwdtxt, fmtype, ffiles = PWeiBo.getdetailtxt(txtd, fmtype, ffiles)
                mediad = fwd.select_one('div.WB_media_wrap > div.media_box')
                fmtype, ffiles = PWeiBo.getdetailmedia(mediad, fuid, fwdmid, fmtype, ffiles)
                retfwdoc = {'mid': fwdmid, 'ctext': fwdtxt, 'cturl': fcurl, 'ctime': fctime, 'uid': fuid, 'uname': funame, 'mtype': fmtype, 'media': ffiles}
            else:
                fwdhsave = True
                retfwdoc = {'mid': fwdmid, 'ctext': fsdt.get('ctext', ''), 'cturl': fsdt.get('cturl', ''), 'ctime': fsdt.get('ctime', ''),
                            'uid': fsdt.get('uid', ''),
                            'uname': fsdt.get('uname', ''), 'mtype': fsdt.get('mtype', ''), 'media': fsdt.get('media', [])}
        return fwdhsave, fwdmid, retfwdoc

    @staticmethod
    def directfpage(dfweibo, dfurl, rcnt=0):
        mid = ''
        html = dfweibo.session.get(dfurl, timeout=(30, 300))
        html.encoding = 'utf-8'
        text = html.text
        rcode = html.status_code
        html.close()
        if rcode != 200:
            return rcode, ''
        fpg = r'<script>parent.window.location="https://weibo.com/sorry\?pagenotfound"</script>'
        ftext = re.findall(fpg, text, re.S)
        if len(ftext) > 0:
            return 404, ''
        if '你访问的页面地址有误' in text:
            return 404, ''
        rpg = r'<script>FM\.view\({"ns":"pl\.content\.weiboDetail\.index",(.*?)\)</script>'
        jtext = re.findall(rpg, text, re.S)
        if len(jtext) < 1:
            return 200, mid
        jtext = '{' + jtext[0]
        ptext = json.loads(jtext)
        thtml = ptext['html']
        soup = BeautifulSoup(thtml, 'lxml')
        infdom = soup.select_one('div[tbinfo][mid]')
        if infdom is not None:
            mid = infdom['mid']
        return 200, mid

    @staticmethod
    def getdetailtxt(txtdiv, mtype, files):
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
                    PWeiBo.GLOGGER.warning('WB_text_opt adom url???????????????{}'.format(furl))
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
                    PWeiBo.GLOGGER.warning('txtdiv adom1???????????????' + str(adom))
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
                PWeiBo.GLOGGER.warning('txtdiv adom2???????????????' + str(adom))
        for idom in idoms:
            itit = idom.get('title', '')
            if itit:
                txtsuf = txtsuf + itit
        txt = txtdiv.text.strip()
        if txtsuf:
            txt = txt + '//face:' + txtsuf
        return txt, mtype, files

    @staticmethod
    def getvideosource(psv):
        psvs = psv.split('=http')
        if len(psvs) > 0:
            psvs.reverse()
            for p in psvs:
                if 'ssig' in p and 'qType' in p:
                    psv = 'http' + p
                    break
        return unquote(psv)

    @staticmethod
    def getdetailmedia(mediadiv, uid, mid, mtype, files):
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
                    PWeiBo.GLOGGER.warning('getdetailmedia fdiv url???????????????{}'.format(furl))
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
                    pvs = PWeiBo.getvideosource(videoli['video-sources'])
                    vfuid = ''.join(str(uuid.uuid1()).split('-'))
                    file = {'url': pvs, 'hasd': 0, 'mtype': '22', 'fid': vfuid}
                    files.append(file)
            if fvdiv is not None:
                mtype = mtype + '23'
                pvs = PWeiBo.getvideosource(fvdiv['video-sources'])
                vfuid = ''.join(str(uuid.uuid1()).split('-'))
                file = {'url': pvs, 'hasd': 0, 'mtype': '23', 'fid': vfuid}
                files.append(file)
            if mediaul is None and fdiv is None and fvdiv is None:
                PWeiBo.GLOGGER.warning('media_box???????????????' + str(mediadiv))
        return mtype, files

    @staticmethod
    def downpimg(dpweibo, imgurl, fpath, mtype='13'):
        try:
            if mtype == '14' and 'weibo' not in imgurl:
                res = requests.get(imgurl, timeout=(30, 300))
            else:
                res = dpweibo.session.get(imgurl, timeout=(30, 300))
            ftype = res.headers.get('Content-Type', '')
            PWeiBo.GLOGGER.info('downpimg:,filetype:{} | imgurl:{}'.format(ftype, imgurl))
            ftr = r'(\w+)/(\w+)'
            rtext = re.findall(ftr, ftype, re.S)
            if rtext[0][0] != 'image':
                raise Exception('downpimg ftype is not image')
            img = res.content
            fuuid = ''.join(str(uuid.uuid1()).split('-'))
            fname = fuuid + '.' + rtext[0][1]
            with open(fpath + '\\' + fname, 'wb') as f:
                f.write(img)
        except Exception as ex:
            fname = ''
            PWeiBo.GLOGGER.exception(ex)
        return fname

    @staticmethod
    def downwpage(dpweibo, mid, cturl, src, fid, fdir, mtype='13'):
        try:
            if 't.cn' in src:
                res = dpweibo.session.get(src, allow_redirects=False, timeout=(30, 300))
                if '100101B2094254D06BA7FB4998' in res.headers.get('location', ''):
                    return '404'
            if mtype == '14' and 'weibo' not in src and 'sina' not in src:
                html = requests.get(src, timeout=(30, 300))
            else:
                html = dpweibo.session.get(src, timeout=(30, 300))
            html.encoding = 'utf-8'
            text = html.text
            html.close()
            if mtype == '13':
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
                for idom in idoms:
                    idombk = False
                    clss = idom.get('class', [])
                    for cls in clss:
                        if cls in PWeiBo.NDIMGCLS:
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
                        PWeiBo.GLOGGER.warning('???????page iurl ???cturl:{},iurl:{}'.format(cturl, iurl))
                        iurl = ''
                    if iurl:
                        fname = PWeiBo.downpimg(dpweibo, iurl, filepath, mtype)
                        if not fname:
                            PWeiBo.GLOGGER.warning('down page img error:purl:{},iurl:{}'.format(src, iurl))
                        else:
                            idom['src'] = fimgdir + '\\' + fname
            locpath = fdir + '\\' + mid + fid + '.html'
            with open(locpath, 'w', encoding='utf-8') as f:
                f.write(str(soup.html))
        except Exception as ex:
            locpath = ''
            PWeiBo.GLOGGER.error("EEEEEEEEEEEEEEE|downwpage:cturl{} ; purl:{}".format(cturl, src))
            PWeiBo.GLOGGER.exception(ex)
            # raise ex
        return locpath

    @staticmethod
    def downtlpic(dpweibo, mid, cturl, src, fid, fdir):
        try:
            html = dpweibo.session.get(src, timeout=(30, 300))
            html.encoding = 'utf-8'
            text = html.text
            soup = BeautifulSoup(text, 'lxml')
            imgd = soup.select_one('div.artwork > img')
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
                raise Exception('pic fname is none;src:{},fid:{}'.format(src, fid))
            res = dpweibo.session.get(imgurl, timeout=(30, 300))
            locpath = fdir + '\\' + mid + fname
            img = res.content
            with open(locpath, 'wb') as f:
                f.write(img)
        except Exception as ex:
            locpath = ''
            PWeiBo.GLOGGER.exception(ex)
            # raise ex
        return locpath

    @staticmethod
    def downtlvideo(dpweibo, mid, cturl, src, fid, fdir):
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
            res = dpweibo.session.get(src, timeout=(30, 300))
            locpath = fdir + '\\' + mid + fname
            img = res.content
            with open(locpath, 'wb') as f:
                f.write(img)
        except Exception as ex:
            locpath = ''
            PWeiBo.GLOGGER.exception(ex)
            # raise ex
        return locpath

    @staticmethod
    def downtlmedia(dweibo, mid, pdoc=None, fdir=None, ecnt=0):
        PWeiBo.GLOGGER.info('=========downtlmedia;mid:{},ecnt:{}'.format(mid, ecnt))
        if ecnt > 10:
            return
        if pdoc is None:
            pdoc = getgpbymid(mid)
        if pdoc is None:
            PWeiBo.GLOGGER.warning('=========downtlmedia pdoc is None;mid:{},ecnt:{}'.format(mid, ecnt))
            time.sleep(3)
            ecnt = ecnt + 1
            return PWeiBo.downtlmedia(dweibo, mid, ecnt=ecnt)
        medias = pdoc.get('media', [])
        fwdmedias = pdoc.get('fwdmedia', [])
        uid = pdoc['uid']
        mid = pdoc['mid']
        gid = pdoc['gid']
        cturl = pdoc['cturl']
        if not gid:
            gid = 'others'
        if fdir is None:
            fdir = PWeiBo.weipicdir + '\\' + 'tlgid' + gid + '\\' + 'tluid' + uid
        if not os.path.exists(fdir):
            os.makedirs(fdir)
        for media in medias:
            if media['hasd']:
                continue
            purl = media['url']
            fid = media['fid']
            if media['mtype'] == '13' or media['mtype'] == '14' or media['mtype'] == '15':
                locpath = PWeiBo.downwpage(dweibo, mid, cturl, purl, fid, fdir, media['mtype'])
            elif media['mtype'].endswith('21') or media['mtype'].endswith('211'):
                locpath = PWeiBo.downtlpic(dweibo, mid, cturl, purl, fid, fdir)
            else:
                locpath = PWeiBo.downtlvideo(dweibo, mid, cturl, purl, fid, fdir)
            if locpath:
                udpgpmedia(mid, fid, locpath)
            else:
                time.sleep(0.4)
                ecnt = ecnt + 1
                PWeiBo.GLOGGER.error('downtlmedia error mid:{},purl:{}'.format(mid, purl))
                return PWeiBo.downtlmedia(dweibo, mid, pdoc, fdir, ecnt)

    @staticmethod
    def splitacd(acd, *args):
        rmap = {}
        spas = acd.split('&')
        for spa in spas:
            spb = spa.split('=', 1)
            if len(spb) > 1 and spb[0] in args:
                rmap[spb[0]] = spb[1]
        return rmap

    @staticmethod
    def fillwbhref(furl):
        if furl.startswith('//'):
            furl = 'https:' + furl
        elif furl.startswith('/'):
            furl = 'https://weibo.com' + furl
        elif furl.startswith('http'):
            pass
        return furl

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
            html.close()
            return text
        finally:
            if ctype == 'chat':
                self.session.headers.pop('Referer')
            PWeiBo.SENLOCK.release()

    def fgrouptl(self, gid, hisp={}, maxmid=0, maxy=1, rtcnt=0):
        gcturl = 'https://weibo.com/aj/mblog/fsearch?gid={}&_rnd={}'.format(gid, cald.gettimestamp())
        if hisp:
            gcturl = 'https://weibo.com/aj/mblog/fsearch?{}&end_id={}&min_id={}&gid={}&__rnd={}'.format(hisp['page'], hisp['emid'], hisp['mmid'], gid,
                                                                                                        cald.gettimestamp())
        PWeiBo.GLOGGER.info('GGGGGGGGGGGGGGGGGGGCURL====================>fgroupct url:{}'.format(gcturl))
        text = self.gethtml(gcturl)
        tjson = json.loads(text)
        gpsoup = BeautifulSoup(tjson['data'], 'lxml')
        hemid, hpge, feeds = PWeiBo.getpageinfo(gpsoup)
        PWeiBo.GLOGGER.info('GGGGGGGGGGGGGGGGGGGCURL-FLENG====================>LEN:{},HEMID:{},page:{}'.format(len(feeds), hemid, hpge))
        hmmid = ''

        for feed in feeds:
            mid, uid, ruid, detail = PWeiBo.getfeedinfo(feed)
            if detail is None or not mid or not uid:
                PWeiBo.GLOGGER.warning('fgroupct maxmid continue...gid:{},mid:{},uid:{},url:{}'.format(gid, mid, uid, gcturl))
                continue
            if mid <= maxmid:
                hmmid = '-1'
                break

            curl, uname, ctime = PWeiBo.getdetailinfo(feed)
            if not curl or not ctime:
                PWeiBo.GLOGGER.warning('fgroupct maxmid continue...gid:{},mid:{},uid:{},curl:{},ctime:{},url:{}'.format(gid, mid, uid, curl, ctime, gcturl))
                continue
            isad = False
            for adurl in PWeiBo.ADURL:
                if adurl in curl:
                    isad = True
                    break
            if isad:
                continue

            if cald.now().year - int(ctime[0:4]) > maxy:
                PWeiBo.GLOGGER.info('fgroupct maxy stop....gid:{},mid:{},ctime:{},url:{}'.format(gid, mid, ctime, gcturl))
                hmmid = '-2'
                break

            if not hemid:
                hemid = mid
                hpge = hpge or hisp.get('page', '') or 'pre_page=1&page=1'

            PWeiBo.GLOGGER.info('SSSSSSSSSS-CURL====================>fgroupct url:{}'.format(curl))
            # 0 txt;13/a l txt;14 link;21 pics;22 video;31 fwd
            mtype = '0'
            files = []

            # txt div
            txtdiv = feed.select_one('div.WB_detail > div.WB_text.W_f14')
            txt, mtype, files = PWeiBo.getdetailtxt(txtdiv, mtype, files)
            # media div
            mediadiv = feed.select_one('div.WB_detail > div.WB_media_wrap > div.media_box')
            mtype, files = PWeiBo.getdetailmedia(mediadiv, uid, mid, mtype, files)
            # fwd div
            fwddiv = feed.select_one('div.WB_detail > div.WB_feed_expand > div.WB_expand')
            fwdhsave = None
            fwdmid = None
            fwddoc = None
            if fwddiv is not None:
                fwdhsave, fwdmid, fwddoc = PWeiBo.getfwddoc(fwddiv)
                mtype = mtype + '31'
            hmmid = mid
            try:
                savedetail(gid, uid, uname, mid, mtype, curl, ctime, txt, files, fwdhsave, fwdmid, fwddoc)
                if len(files) > 0:
                    PWeiBo.downfexecutor.submit(PWeiBo.downtlmedia, self, mid)
            except Exception as ex:
                PWeiBo.GLOGGER.error('savedetail error:ex:{},gid{},mid:{},uid:{}'.format(str(ex), gid, mid, uid))
                # PWeiBo.GLOGGER.exception(ex)
        if hmmid == '-1':
            PWeiBo.GLOGGER.info('fgroupct END maxmid=====================maxmid stop....gid:{},url:{}'.format(gid, gcturl))
        elif hmmid == '-2':
            PWeiBo.GLOGGER.info('fgroupct END maxy=====================maxy stop....gid:{},url:{}'.format(gid, gcturl))
        elif hemid and hpge and hmmid:
            hsleeptime = random.randint(4, 24)
            hsleeptime = round(hsleeptime * 0.1, 1)
            time.sleep(hsleeptime)
            self.fgrouptl(gid, {'emid': hemid, 'mmid': hmmid, 'page': hpge}, maxmid, maxy)
        elif not hemid and rtcnt < 3:
            PWeiBo.GLOGGER.error('fgroupct rtcnt ???=====================html error rtcnt....gid:{},url:{},rtcnt:{}'.format(gid, gcturl, rtcnt))
            hsleeptime = random.randint(10, 30)
            time.sleep(hsleeptime)
            self.fgrouptl(gid, hisp, maxmid, maxy, rtcnt + 1)
        else:
            PWeiBo.GLOGGER.error('fgroupct END ???=====================html error....gid:{},url:{},html:{}'.format(gid, gcturl, tjson['data']))

    def fgumidexist(self, gid, muid):
        for cgid in PWeiBo.TLGIDS:
            if cgid == gid:
                break
            if cgid in self.gumap and muid in self.gumap[cgid]:
                return True
        return False

    def fgroupuids(self, gid, guurl=''):
        if gid not in self.gumap:
            self.gumap[gid] = []
        if not guurl:
            guurl = 'https://weibo.com/1795005665/myfollow?gid={}'.format(gid)
        PWeiBo.GLOGGER.info('fgroupuids info....gid:{},guurl:{}'.format(gid, guurl))
        text = self.gethtml(guurl)
        rpg = r'<script>FM\.view\({"ns":"pl\.relation\.myFollow\.index",(.*?)\)</script>'
        jtext = re.findall(rpg, text, re.S)
        jtext = '{' + jtext[0]
        ptext = json.loads(jtext)
        thtml = ptext['html']
        soup = BeautifulSoup(thtml, 'lxml')
        uidlis = soup.select('div.member_box > ul.member_ul > li.member_li[action-data]')
        for uidli in uidlis:
            acd = uidli['action-data']
            mumap = PWeiBo.splitacd(acd, 'uid', 'screen_name')
            if 'uid' not in mumap or self.fgumidexist(gid, mumap['uid']):
                continue
            self.gumap[gid].append(mumap['uid'])
        npa = soup.select_one('div.WB_cardpage > div.W_pages a.page.next')
        if npa is not None and npa.get('href', ''):
            self.fgroupuids(gid, PWeiBo.fillwbhref(npa.get('href')))

    def fgroupsuids(self):
        self.gumaplock.acquire()
        self.gumap = {}
        for gid in PWeiBo.TLGIDS:
            self.fgroupuids(gid)
        self.gumaplock.release()

    def fmemberstl(self):
        self.gumaplock.acquire()
        for gid in self.gumap:
            gmlist = self.gumap[gid]
            if gmlist is not None and len(gmlist) > 0:
                for muid in gmlist:
                    murl = 'https://weibo.com/u/{}?&__rnd={}'.format(muid, cald.gettimestamp())
                    PWeiBo.fmbtlexecutor.submit(self.fmembertl, gid, muid, murl)
        self.gumaplock.release()

    def fmembertlsoup(self, murl, ptype, pdomian, ppageid):
        text = self.gethtml(murl)
        if ptype == '0':
            p1 = r'\$CONFIG\[\'domain\'\]\s*=\s*\'(.+?)\''
            p2 = r'\$CONFIG\[\'page_id\'\]\s*=\s*\'(.+?)\''
            pdomian = re.findall(p1, text, re.S)
            ppageid = re.findall(p2, text, re.S)
            if len(pdomian) > 0:
                pdomian = pdomian[0]
            if len(ppageid) > 0:
                ppageid = ppageid[0]
            p = r'<script>FM\.view\({"ns":"pl\.content\.homeFeed\.index","domid":"Pl_Official_MyProfileFeed__20",(.*?)\)</script>'
            jtext = re.findall(p, text, re.S)
            jtext = '{' + jtext[0]
            tjson = json.loads(jtext)
            thtml = tjson['html']
            gpsoup = BeautifulSoup(thtml, 'lxml')
        else:
            tjson = json.loads(text)
            gpsoup = BeautifulSoup(tjson['data'], 'lxml')
        return gpsoup, pdomian, ppageid

    def fmemberminmid(self, gid, muid, murl):
        gpsoup, pdomian, ppageid = self.fmembertlsoup(murl, '0', '', '')
        lazyd, pagesli, feeds = PWeiBo.getmupageinfo(gpsoup)
        smurl, npagebar, npage = PWeiBo.getmupagenexturl('9', muid, 1, 0, pdomian, ppageid, lazyd, pagesli, feeds, 0)

    def fmembertl(self, gid, muid, murl, maxmid='', minmid='', maxy=10, ptype='0', pdomian='', ppageid='', page=1, pagebar=0, rtcnt=0):
        # test uid:3929874414
        gpsoup, pdomian, ppageid = self.fmembertlsoup(murl, ptype, pdomian, ppageid)
        if gpsoup is None:
            PWeiBo.GLOGGER.warning('EXEX====>fmembertl gpsoup Ex...gid:{},uid:{},url:{}'.format(gid, muid, murl))
            return

        if not maxmid or not minmid:
            dmaxmid, dminmid = getmbmaxminmid(muid, maxy)
            if not maxmid:
                maxmid = dmaxmid
            if not minmid:
                minmid = dminmid
        if not minmid or minmid != '-1':
            pass

        lazyd, pagesli, feeds = PWeiBo.getmupageinfo(gpsoup)
        smurl, npagebar, npage = PWeiBo.getmupagenexturl(ptype, muid, page, pagebar, pdomian, ppageid, lazyd, pagesli, feeds, rtcnt)

        for feed in feeds:
            mid, uid, ruid, detail = PWeiBo.getfeedinfo(feed)
            if detail is None or not mid or not uid:
                PWeiBo.GLOGGER.warning('EXEX====>fmembertl feedinfo EX...gid:{},mid:{},uid:{},url:{}'.format(gid, mid, muid, murl))
                continue
            if maxmid and int(mid) <= int(maxmid):
                # PWeiBo.GLOGGER.info('ENDDDD====>fmembertl maxmid stop....gid:{},mid:{},uid:{},maxmid:{},url:{}'.format(gid, mid, muid, maxmid, murl))
                # break
                if minmid and minmid == '-1':
                    PWeiBo.GLOGGER.info('ENDDDD====>fmembertl maxmid stop....'
                                        'gid:{},mid:{},uid:{},maxmid:{},minmid:{},url:{}'.format(gid, mid, muid, maxmid, minmid, murl))
                    break
                if minmid and int(mid) >= int(minmid):
                    # PWeiBo.GLOGGER.info('CTUUUU====>fmembertl max min mid ctu....'
                    #                  'gid:{},mid:{},uid:{},maxmid:{},minmid:{},url:{}'.format(gid, mid, muid, maxmid, minmid, murl))
                    continue

            curl, uname, ctime = PWeiBo.getdetailinfo(feed)
            if not curl or not ctime:
                PWeiBo.GLOGGER.warning(
                    'fmembertl notcurlctime continue...gid:{},mid:{},uid:{},curl:{},ctime:{},url:{}'.format(gid, mid, muid, curl, ctime, murl))
                continue
            isad = False
            for adurl in PWeiBo.ADURL:
                if adurl in curl:
                    isad = True
                    break
            if isad:
                continue

            if cald.now().year - int(ctime[0:4]) > maxy:
                PWeiBo.GLOGGER.info('ENDDDD===>fmembertl maxy stop....gid:{},mid:{},uid:{},ctime:{},url:{}'.format(gid, mid, muid, ctime, murl))
                break

            if ckanddelhismbmid(mid) == 1:
                # PWeiBo.GLOGGER.info('CTUUUU====>fmembertl ckanddelhismbmid...'
                #                   'gid:{},mid:{},uid:{},maxmid:{},minmid:{},url:{}'.format(gid, mid, muid, maxmid, minmid, murl))
                continue

            PWeiBo.GLOGGER.info('SSSSSSSSSS-CURL====================>fmembertl url:{}'.format(curl))
            # 0 txt;13/a l txt;14 link;21 pics;22 video;31 fwd
            mtype = '0'
            files = []

            # txt div
            txtdiv = feed.select_one('div.WB_detail > div.WB_text.W_f14')
            txt, mtype, files = PWeiBo.getdetailtxt(txtdiv, mtype, files)
            # media div
            mediadiv = feed.select_one('div.WB_detail > div.WB_media_wrap > div.media_box')
            mtype, files = PWeiBo.getdetailmedia(mediadiv, uid, mid, mtype, files)
            # fwd div
            fwddiv = feed.select_one('div.WB_detail > div.WB_feed_expand > div.WB_expand')
            fwdhsave = None
            fwdmid = None
            fwddoc = None
            if fwddiv is not None:
                fwdhsave, fwdmid, fwddoc = PWeiBo.getfwddoc(fwddiv)
                mtype = mtype + '31'
            try:
                savedetail(gid, uid, uname, mid, mtype, curl, ctime, txt, files, fwdhsave, fwdmid, fwddoc, 'utl')
                if len(files) > 0:
                    PWeiBo.downfexecutor.submit(PWeiBo.downtlmedia, self, mid)
            except Exception as ex:
                PWeiBo.GLOGGER.error('savedetail error:ex:{},gid{},mid:{},muid:{}'.format(str(ex), gid, mid, muid))
                # PWeiBo.GLOGGER.exception(ex)
        tmptxt = ''
        if smurl == 'ERROR':
            tmptxt = gpsoup.html
        gpsoup = None

        if not smurl:
            PWeiBo.GLOGGER.warning('TRYCNT====>fmembertl rtcnt TRYCNT...gid:{},uid:{},rtcnt:{},url:{}'.format(gid, muid, rtcnt, murl))
            self.fmembertl(gid, muid, murl, maxmid, minmid, maxy, ptype, pdomian, ppageid, page, pagebar, rtcnt + 1)
        elif smurl == 'ERROR':
            PWeiBo.GLOGGER.error('EXEX====>fmembertl rtcnt>3 EX...gid:{},uid:{},url:{},lhtml:{}'.format(gid, muid, murl, tmptxt))
        elif smurl == 'LAZYDEND':
            PWeiBo.GLOGGER.info('ENDDDD====>fmembertl lazyd None...gid:{},uid:{},url:{}'.format(gid, muid, murl))
        elif smurl == 'PAGESLIEND':
            PWeiBo.GLOGGER.info('ENDDDD====>fmembertl page end stop... gid:{},uid:{},page:{}'.format(gid, muid, page))
        else:
            if npagebar:
                self.fmembertl(gid, muid, smurl, maxmid, minmid, maxy, '1', pdomian, ppageid, page, npagebar)
            if npage:
                self.fmembertl(gid, muid, smurl, maxmid, minmid, maxy, '0', '', '', npage, 0)


def login(proxies={}):
    username = 'sretof@live.cn'  # 账号
    password = '1122aaa'  # 密码
    pweibo = PWeiBo(username, password, proxies)
    loginok = False
    while not loginok:
        try:
            pweibo.login()
            loginok = True
        except Exception as ex:
            print(ex)
            time.sleep(3)
    return pweibo


def getMongoWDb():
    conn = MongoClient(dbc.MGOHOST, 27017)
    wdb = conn[dbc.MGOWDB]
    return conn, wdb


def getmaxgpmids():
    conn, wdb = getMongoWDb()
    coll = wdb[PWeiBo.MGOCTCOLL]
    try:
        results = coll.aggregate([{'$group': {'_id': "$gid", 'maxmid': {'$max': "$mid"}}}])
        gsmid = {}
        for res in results:
            gsmid[res['_id']] = res['maxmid']
        return gsmid
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def ckanddelhismbmid(mid):
    ct = getgpbymid(mid)
    if ct is None:
        return 0
    fday = ct.get('fday', '19830104')
    if int(fday) < 20190701:
        delgpbymid(mid)
        return 0
    else:
        return 1


def getmbmaxminmid(muid, maxy):
    conn, wdb = getMongoWDb()
    try:
        coll = wdb[PWeiBo.MGOCTCOLL]
        maxr = coll.find({'uid': muid}).sort('mid', -1).limit(1)
        minr = coll.find({'uid': muid, 'fday': {'$gte': '20190501'}}).sort('mid', 1).limit(1)
        maxmid = ''
        minmid = ''
        for maxro in maxr:
            maxmid = maxro['mid']
            break
        for minro in minr:
            minmid = minro['mid']
            cday = minro['cday']
            if cald.now().year - int(cday[0:4]) > maxy:
                minmid = '-1'
            break
        return maxmid, minmid
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def getgpbymid(mid):
    conn, wdb = getMongoWDb()
    try:
        coll = wdb[PWeiBo.MGOCTCOLL]
        result = coll.find_one({'mid': mid})
        return result
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def delgpbymid(mid):
    conn, wdb = getMongoWDb()
    try:
        coll = wdb[PWeiBo.MGOCTCOLL]
        coll.delete_one({'mid': mid})
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def getgpbygidandmid(gid, mid):
    conn, wdb = getMongoWDb()
    try:
        coll = wdb[PWeiBo.MGOCTCOLL]
        result = coll.find_one({'gid': gid, 'mid': mid})
        return result
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def udpgpdetail(mid, field, val):
    conn, wdb = getMongoWDb()
    try:
        coll = wdb[PWeiBo.MGOCTCOLL]
        coll.update_one({'mid': mid}, {'$set': {field: val}})
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def udpgpmedia(mid, fid, locpath):
    conn, wdb = getMongoWDb()
    try:
        coll = wdb[PWeiBo.MGOCTCOLL]
        if locpath == '404':
            # pass
            coll.update_one({'mid': mid, 'media.fid': fid}, {'$set': {'media.$.hasd': 1, 'media.$.mtype': locpath}})
        else:
            coll.update_one({'mid': mid, 'media.fid': fid}, {'$set': {'media.$.hasd': 1, 'media.$.locpath': locpath}})
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def udpgpfwdmedia(mid, field, val):
    conn, wdb = getMongoWDb()
    try:
        coll = wdb[PWeiBo.MGOCTCOLL]
        coll.update_one({'mid': mid}, {'$set': {field: val}})
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def savedetail(gid, uid, uname, mid, mtype, curl, ctime, txt, files, fwdhsave, fwdmid, fwddoc, tlsrc='gtl'):
    cday = ctime[0:4] + ctime[5:7] + ctime[8:10]
    doc = {
        'gid': gid,
        'uid': uid,
        'uname': uname,
        'mid': mid,
        'mtype': mtype,
        'cturl': curl,
        'ctime': ctime,
        'cday': cday,
        'ctext': txt,
        'media': files,
        'fwdhsave': fwdhsave,
        'fwdmid': fwdmid,
        'fwdtext': '',
        'fwdmedia': [],
        'fwddoc': fwddoc,
        'fday': cald.getdaystr(),
        'ftime': cald.now(),
        'tlsrc': tlsrc,
        'smid': cday + mid
    }
    if fwdhsave is None:
        del doc['fwdhsave']
        del doc['fwdmid']
        del doc['fwddoc']
        del doc['fwdtext']
        del doc['fwdmedia']
    else:
        doc['fwdtext'] = fwddoc['ctext']
        fmedia = fwddoc['media']
        if len(fmedia) > 0:
            doc['fwdmedia'] = fmedia
        else:
            del doc['fwdmedia']
        del fwddoc['ctext']
        del fwddoc['media']
    conn, wdb = getMongoWDb()
    try:
        coll = wdb[PWeiBo.MGOCTCOLL]
        coll.insert_one(doc)
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def fgroupstl(fgweibo):
    gsmmid = getmaxgpmids()
    print(gsmmid)
    for gid in PWeiBo.TLGIDS:
        pass
        # fgweibo.fgrouptl(gid, maxmid=int(gsmmid.get(gid, '0')))


def fwbdoneslp():
    nhour = datetime.datetime.now().hour
    sleeptime = random.randint(60, 60 * 10)
    if 2 <= nhour < 8:
        sleeptime = random.randint(60 * 30, 60 * 60)
    PWeiBo.GLOGGER.info('======sleep hour:{} sleep:{}'.format(nhour, sleeptime))
    time.sleep(sleeptime)


global Gfcnt
Gfcnt = 0

global Ufcnt
Ufcnt = 0

global OPWEIBO
OPWEIBO = None
global OPWEIBOLCNT
OPWEIBOLCNT = 0

global OPWLOCK
OPWLOCK = threading.Lock()


def OPWEIBOLOGIN(tcnt=0):
    global OPWEIBO
    global OPWLOCK
    global OPWEIBOLCNT
    OPWLOCK.acquire()
    if OPWEIBOLCNT != 0:
        time.sleep(60 * 4)
    if tcnt != OPWEIBOLCNT:
        pass
    else:
        OPWEIBO = login()
        OPWEIBOLCNT = OPWEIBOLCNT + 1
    OPWLOCK.release()


def updateMidT(doc, rcnt=0):
    global OPWEIBO
    global OPWLOCK
    global OPWEIBOLCNT
    cday = doc['cday']
    mid = doc['mid']
    cturl = doc['cturl']
    nmid = ''
    smid = ''
    if 'smid' in doc:
        pass
    elif not isinstance(mid, int) and len(mid) == 16 and mid.startswith('4'):
        smid = cday + mid
    else:
        OPWLOCK.acquire()
        tmpwbcnt = OPWEIBOLCNT
        rcode, nmid = PWeiBo.directfpage(OPWEIBO, cturl)
        OPWLOCK.release()
        if rcode == 200 and nmid:
            if nmid != mid:
                smid = cday + nmid
            else:
                smid = cday + nmid
                nmid = ''
        elif rcode == 404:
            nmid = mid
            if isinstance(nmid, int):
                if nmid < 0:
                    nmid = nmid * -1
                nmid = str(nmid)
            smid = cday + nmid
        else:
            if rcnt > 1:
                PWeiBo.GLOGGER.error('eeeeeeeee-mid:{},rcode:{},nmid:{},smid:{},cturl:{}'.format(mid, rcode, nmid, smid, cturl))
            else:
                PWeiBo.GLOGGER.warning('login-mid:{},tmpwbcnt:{},OPWEIBOLCNT:{},cturl:{}'.format(mid, tmpwbcnt, OPWEIBOLCNT, cturl))
                OPWEIBOLOGIN(tmpwbcnt)
                updateMidT(doc, rcnt + 1)
    if smid or nmid:
        PWeiBo.GLOGGER.info('dddddddddd-mid:{},rcode:{},nmid:{},smid:{},cturl:{}'.format(mid, rcode, nmid, smid, cturl))
    if smid:
        udpgpdetail(mid, 'smid', smid)
    if nmid:
        udpgpdetail(mid, 'mid', nmid)


def updateMid():
    conn, wdb = getMongoWDb()
    executor = ThreadPoolExecutor(max_workers=2)
    try:
        coll = wdb[PWeiBo.MGOCTCOLL]
        result = coll.find({'smid': {'$exists': False}}).sort('cday', -1)
        # 1701333050
        # result = coll.find({'mid': '1701333050'})
        OPWEIBOLOGIN()
        for doc in result:
            executor.submit(updateMidT, doc)
    except Exception as mex:
        raise mex
    finally:
        conn.close()


if __name__ == '__main__':
    updateMid()
    # OPWEIBOLOGIN()
    # cturl = 'https://weibo.com/2043878715/I0JRZjNof'
    # rcode, nmid = PWeiBo.directfpage(OPWEIBO, cturl)
    # print(rcode)
# mpweibo = None
# while 1:
#     # 登录
#     try:
#         if Gfcnt == 0 or Gfcnt > 500:
#             mpweibo = login()
#     except Exception as e:
#         Gfcnt = 0
#         PWeiBo.GLOGGER.exception(e)
#         fwbdoneslp()
#         continue
#     # 取group menber
#     try:
#         if Ufcnt == 0 or Ufcnt > 10000000:
#             Ufcnt = 0
#             mpweibo.fgroupsuids()
#             Ufcnt = Ufcnt + 1
#     except Exception as e:
#         Ufcnt = 0
#         PWeiBo.GLOGGER.exception(e)
#     # 取group TL
#     try:
#         fgroupstl(mpweibo)
#         Gfcnt = Gfcnt + 1
#     except Exception as e:
#         Gfcnt = 0
#         PWeiBo.GLOGGER.exception(e)
#     # 取member TL
#     try:
#         if Ufcnt == 1:
#             mpweibo.fmemberstl()
#     except Exception as e:
#         Gfcnt = 0
#         PWeiBo.GLOGGER.exception(e)
#     fwbdoneslp()

# getmbmaxminmid('5764537898', 5)

# mpweibo = login()
# muid = '3929874414'
# murl = 'https://weibo.com/u/{}?&__rnd={}'.format(muid, cald.gettimestamp())
# mpweibo.fmembertl('other', muid, murl)

# text = mpweibo.gethtml('https://weibo.com/u/3929874414')
# p1 = r'\$CONFIG\[\'domain\'\]\s*=\s*\'(.+?)\''
# p2 = r'\$CONFIG\[\'page_id\'\]\s*=\s*\'(.+?)\''
# pdomian = re.findall(p1, text, re.S)
# ppageid = re.findall(p2, text, re.S)
# p = r'<script>FM\.view\({"ns":"pl\.content\.homeFeed\.index","domid":"Pl_Official_MyProfileFeed__20",(.*?)\)</script>'
# jtext = re.findall(p, text, re.S)
# jtext = '{' + jtext[0]
# tjson = json.loads(jtext)
# thtml = tjson['html']
# gpsoup = BeautifulSoup(thtml, 'lxml')
# adoms = gpsoup.select('div.WB_cardwrap  div.WB_detail > div.WB_from > a:first-child')
# print('00)',len(adoms),pdomian,ppageid)
# for adom in adoms:
#     print('00)',adom.text)
# padom = gpsoup.select_one('div.WB_empty.WB_empty_narrow')
# pgdom = gpsoup.select('div.W_pages ul > li > a[bpfilter]')
# # print('00)',padom)
# # print('00)', pgdom)
#
#
# jtext = mpweibo.gethtml('https://weibo.com/p/aj/v6/mblog/mbloglist?domain=100505&is_all=1&id=1005053929874414&pre_page=1')
# tjson = json.loads(jtext)
# gpsoup = BeautifulSoup(tjson['data'], 'lxml')
# adoms = gpsoup.select('div.WB_cardwrap  div.WB_detail > div.WB_from > a:first-child')
# print('01)',len(adoms))
# for adom in adoms:
#     print('01)',adom.text)
#
# jtext = mpweibo.gethtml('https://weibo.com/p/aj/v6/mblog/mbloglist?domain=100505&is_all=1&id=1005053929874414&pagebar=1&pre_page=1')
# tjson = json.loads(jtext)
# gpsoup = BeautifulSoup(tjson['data'], 'lxml')
# adoms = gpsoup.select('div.WB_cardwrap  div.WB_detail > div.WB_from > a:first-child')
# print('11)',len(adoms))
# for adom in adoms:
#     print('11)',adom.text)
#
# jtext = mpweibo.gethtml('https://weibo.com/p/aj/v6/mblog/mbloglist?domain=100505&is_all=1&id=1005053929874414&pagebar=2&pre_page=1')
# tjson = json.loads(jtext)
# gpsoup = BeautifulSoup(tjson['data'], 'lxml')
# adoms = gpsoup.select('div.WB_cardwrap  div.WB_detail > div.WB_from > a:first-child')
# print('21)',len(adoms))
# for adom in adoms:
#     print('21)',adom.text)

# # PWeiBo.downtlmedia(mpweibo, '4327710203535929')
# # TEST GID 4169641444240939
# # mpweibo.fgrouptl('4169641444240939')
# mpweibo.fgroupsuids()
# print(mpweibo.gumap)

# print(unquote('http%3A%2F%2Ff.us.sinaimg.cn%2F002qSGxhlx07vCqsnjGU01041200rkgG0E010.mp4%3Flabel%3Dmp4_720p%26template%3D1280x720.23.0%26trans_finger%3Dbead91e89870c048e540ef7cd58c7c03%26Expires%3D1564039001%26ssig%3DFuzpR6KBz7%26KID%3Dunistore%2Cvideo&qType=720'))

# svurl = 'http%253A%252F%252Ffus.cdn.krcom.cn%252F002U5p9Ulx07vH9K7HzO010412051bpl0E020.mp4%253Flabel%253Dmp4_720p%2526template%253D1280x720.23.0%2526trans_finger%253Dee0f61d2722f59c3d0002c6df46d9912%2526Expires%253D1564037492%2526ssig%253DzhvY7u7NBU%2526KID%253Dunistore%252Cvideo&480=http%3A%2F%2Ffus.cdn.krcom.cn%2F001TVd4flx07vH9x7IYE01041202qUS50E010.mp4%3Flabel%3Dmp4_hd%26template%3D852x480.23.0%26trans_finger%3D68f0dbe8b9301bd6b1b19fe77896f407%26Expires%3D1564037492%26ssig%3DIGY3zJfyNW%26KID%3Dunistore%2Cvideo&720'
# svurl2 = 'http%3A%2F%2Ffus.cdn.krcom.cn%2F002U5p9Ulx07vH9K7HzO010412051bpl0E020.mp4%3Flabel%3Dmp4_720p%26template%3D1280x720.23.0%26trans_finger%3Dee0f61d2722f59c3d0002c6df46d9912%26Expires%3D1564037492%26ssig%3DzhvY7u7NBU%26KID%3Dunistore%2Cvideo&qType=720&1080=http%3A%2F%2Fkrcom.cn%2F2174585797%2Fepisodes%2F2358773%3A4397901137560480'
# vurl = unquote(svurl)
# vurl2 = unquote(svurl2)
# print(vurl)
# print(vurl2)
# getgpbymid('4169669105280413')
# rmtxt = ['2']
# fmid = 'x' if len(rmtxt) < 1 else rmtxt[0]
# print(fmid)
# rmtxt = []
# fmid = 'x' if len(rmtxt) < 1 else rmtxt[0]
# print(fmid)
# ctime = '2018-02-10'
# cday = ctime[0:4] + ctime[5:7] + ctime[8:]
# print(cday)
#
# print(cald.getdaystr())
# getmaxgpmids('1')

# url = 'dfe42234ly1g5anuzw6avg20dc0dche1.files\\7a8dfbd8ade411e99e5264006a93aa65.gif'
# print('.files\\' in url)

# vurl = 'http://f.us.sinaimg.cn/002YVPYAlx07vupKL9ks01041200aD3B0E010.mp4?label=mp4_hd&template=480x480.23.0&trans_finger=53d43933e6520536fed61835e8c1d811&Expires=1563945763&ssig=oNJhcpmOAt&KID=unistore,video'
# ipreg = r'.+/(\w+)\.(\w+)\?'
# rtext = re.findall(ipreg, vurl, re.S)
# print(rtext)

# dstr = '<div class="WB_text W_f14" node-type="feed_list_content">视大盘涨跌而定<img class="W_img_face" render="ext" src="//img.t.sinajs.cn/t4/appstyle/expression/ext/normal/8f/2018new_haha_org.png" title="[哈哈]" alt="[哈哈]" type="face" style="visibility: visible;">//<a target="_blank" render="ext" extra-data="type=atname" href="//weibo.com/n/%E9%81%93%E5%A3%AB%E4%B8%8E%E9%AA%91%E5%A3%AB?from=feed&amp;loc=at" usercard="name=道士与骑士">@道士与骑士</a>:乱。。。乱马？//<a target="_blank" render="ext" extra-data="type=atname" href="//weibo.com/n/Peter%E7%BE%8A?from=feed&amp;loc=at" usercard="name=Peter羊">@Peter羊</a>: 双兔傍地走…<img class="W_img_face" render="ext" src="//img.t.sinajs.cn/t4/appstyle/expression/ext/normal/62/2018new_tanshou_org.png" title="[摊手]" alt="[摊手]" type="face" style="visibility: visible;">//<a target="_blank" render="ext" extra-data="type=atname" href="//weibo.com/n/%E9%81%93%E5%A3%AB%E4%B8%8E%E9%AA%91%E5%A3%AB?from=feed&amp;loc=at" usercard="name=道士与骑士">@道士与骑士</a>:<img class="W_img_face" render="ext" src="//img.t.sinajs.cn/t4/appstyle/expression/ext/normal/8f/2018new_haha_org.png" title="[哈哈]" alt="[哈哈]" type="face" style="visibility: visible;">//<a target="_blank" render="ext" extra-data="type=atname" href="//weibo.com/n/%E9%A3%9E%E5%A5%94%E7%9A%84%E8%80%81%E9%9F%AD%E8%8F%9C?from=feed&amp;loc=at" usercard="name=飞奔的老韭菜">@飞奔的老韭菜</a>: 女粉：不用众筹，我给买！羊师：我叫花木兰<img class="W_img_face" render="ext" src="//img.t.sinajs.cn/t4/appstyle/expression/ext/normal/c9/2018new_chongjing_org.png" title="[憧憬]" alt="[憧憬]" type="face" style="visibility: visible;">//<a target="_blank" render="ext" extra-data="type=atname" href="//weibo.com/n/Peter%E7%BE%8A?from=feed&amp;loc=at" usercard="name=Peter羊">@Peter羊</a>:垃圾手机是重点！来，重新众筹一个！<img class="W_img_face" render="ext" src="//img.t.sinajs.cn/t4/appstyle/expression/ext/normal/7c/2018new_heng_org.png" title="[哼]" alt="[哼]" type="face" style="visibility: visible;"></div>'
# soup = BeautifulSoup(dstr, 'lxml')
# print(soup.text)

# url0 = 'https://weibo.com/aj/mblog/fsearch?ajwvr=6&gid=3653960185837784&wvr=6'
#
# urlt = 'https://weibo.com/aj/mblog/fsearch?ajwvr=6&pre_page=1&page=1&end_id=4397164987657933&min_id=4397162576153957&gid=3653960185837784&wvr=6&leftnav=1&isspecialgroup=1&pagebar=0&__rnd=1563851964894'
# urlt2 = 'https://weibo.com/aj/mblog/fsearch?pre_page=1&page=1&end_id=4395881702503031&min_id=4395808361222795&gid=4005405388023195&__rnd=1563877234968'
# pweibo = login()
# html = pweibo.session.get(urlt2, timeout=(30, 60))
# html.encoding = 'utf-8'
# jtext = html.text
# tjson = json.loads(jtext)
# print(tjson['data'])
# print('=========================')
# html = pweibo.session.get(url1, timeout=(30, 60))
# html.encoding = 'utf-8'
# jtext = html.text
# tjson = json.loads(jtext)
# print(tjson['data'])
# print('=========================')
# # soup = BeautifulSoup(tjson['data'], 'lxml')
# # feeds = soup.select('div.WB_feed.WB_feed_v3.WB_feed_v4 > div[tbinfo]')
# # for feed in feeds:
# #     txtdiv = feed.select_one('div.WB_detail > div.WB_text.W_f14')
# #     txt = txtdiv.text.strip()
# #     print(txt)
# html = pweibo.session.get(url2, timeout=(30, 60))
# html.encoding = 'utf-8'
# jtext = html.text
# tjson = json.loads(jtext)
# print(tjson['data'])
# soup = BeautifulSoup(tjson['data'], 'lxml')
# feeds = soup.select('div.WB_feed.WB_feed_v3.WB_feed_v4 > div[tbinfo]')
# for feed in feeds:
#     txtdiv = feed.select_one('div.WB_detail > div.WB_text.W_f14')
#     txt = txtdiv.text.strip()
#     print(txt)

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
