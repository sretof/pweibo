#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'
import json
import logging
import os
import re
import time
import uuid

import requests
from bs4 import BeautifulSoup

import conf.db as dbc
import util.caldate as cald
import util.tulog as logger
import wbutil.wbmon as wbmon
from wbutil import WbComp
from wbutil.wbex import WbCompDownError
from wbutil.wbex import WbCompError
from wbutil.wbex import WbMonNoneDocError


class WbPageCmp:
    def __init__(self, wbcomp, mlogger=None):
        if mlogger is None:
            mlogger = logger.TuLog('wbpagecmp', '/log', True, logging.INFO).getlog()
        self.wbcomp = wbcomp
        self.mlogger = mlogger

    def __downmedia(self, mid, medias, fdir):
        if not os.path.exists(fdir):
            os.makedirs(fdir)
        exmedias = []
        okmedias = []
        for media in medias:
            if media['hasd']:
                continue
            purl = media['url']
            fid = media['fid']
            self.mlogger.debug('WbPageCmp:__downmedia fid START=====>mid:{},fid:{},ftype:{}'.format(mid, fid, media['mtype']))
            opttext = ''
            if media['mtype'].startswith('13') or media['mtype'] == '14' or media['mtype'] == '15':
                locpath, opttext = self.downpage(mid, purl, fid, fdir, media['mtype'])
            elif media['mtype'].endswith('21') or media['mtype'].endswith('211'):
                locpath = self.downpic(mid, purl, fid, fdir)
            else:
                locpath = self.downvideo(mid, purl, fid, fdir)
            if locpath and locpath == 'excode414':
                locpath = ''
            if locpath:
                okmedias.append({'mid': mid, 'fid': fid, 'locpath': locpath, 'opttext': opttext})
            else:
                locpath = ''
                exmedias.append(fid)
            self.mlogger.debug('WbPageCmp:__downmedia fid END=====>mid:{},fid:{},ftype:{},locpath:{}'.format(mid, fid, media['mtype'], locpath))
        self.mlogger.debug('WbPageCmp:__downmedia END=====>mid:{},len(ex):{}'.format(mid, len(exmedias)))
        return okmedias, exmedias

    def downfwdmedia(self, gid, mid, uid, fmid, fcday, fmedia):
        fdir = self.wbcomp.picdir + '\\tlgid' + gid + '\\fwd\\tluid' + uid + '\\' + fcday[0:6]
        okmedias, exmedias = self.__downmedia(fmid, fmedia, fdir)
        for okmedia in okmedias:
            wbmon.hasdownfwdmedia(mid, okmedia['fid'], okmedia['locpath'], okmedia['opttext'])
        if len(exmedias) > 0:
            self.mlogger.error('WbPageCmp:downfwdmedia EX;exmedias:{}'.format(exmedias))
        else:
            wbmon.hasdownfwddoc(mid)

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
        self.mlogger.debug('WbPageCmp:downmedia START=====>mid:{}'.format(mid))
        medias = doc.get('media', [])
        uid = doc['uid']
        mid = doc['mid']
        gid = doc.get('gid', '')
        dcday = doc.get('cday', '')
        if not gid:
            gid = 'others'
        if not dcday:
            dcday = cald.getdaystr()
        if fdir is None:
            fdir = self.wbcomp.picdir + '\\tlgid' + gid + '\\tluid' + uid + '\\' + dcday[0:6]
        if not os.path.exists(fdir):
            os.makedirs(fdir)
        okmedias, exmedias = self.__downmedia(mid, medias, fdir)
        for okmedia in okmedias:
            wbmon.hasdownmedia(mid, okmedia['fid'], okmedia['locpath'], okmedia['opttext'])
        if len(exmedias) > 0:
            self.mlogger.error('WbPageCmp:downmedia EX;exmedias:{}'.format(exmedias))
        self.mlogger.debug('WbPageCmp:downmedia END=====>mid:{},len(ex):{}'.format(mid, len(exmedias)))
        return exmedias

    def downpageimg(self, imgurl, fpath, mtype='13'):
        try:
            if mtype == '14' and 'weibo' not in imgurl:
                res = requests.get(imgurl, timeout=(30, 60))
            else:
                res = self.wbcomp.getres(imgurl, timeout=(30, 60))
            ftype = res.headers.get('Content-Type', '')
            # self.mlogger.debug('WbComp:downpageimg res success;filetype:{},imgurl:{}'.format(ftype, imgurl))
            ftr = r'(\w+)/(\w+)'
            rtext = re.findall(ftr, ftype, re.S)
            if rtext[0][0] != 'image':
                raise Exception('WbPageCmp:downpageimg ftype is not image;filetype:{},imgurl:{}'.format(ftype, imgurl))
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
                text = self.wbcomp.gethtml(src, timeout=(30, 60), rtry=1)[1]
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
                    self.mlogger.warning('WbPageCmp:downpage:downpageimg EX1;mid:{},fid:{},murl:{},iurls:{}'.format(mid, fid, src, idomex1))
                if len(idomex2) > 0:
                    self.mlogger.error('WbPageCmp:downpage:downpageimg EX2;mid:{},fid:{},murl:{},iurls:{}'.format(mid, fid, src, idomex2))
                self.mlogger.debug('WbPageCmp:downpage:downpageimg success;mid:{},fid:{},murl:{},iurls:{}'.format(mid, fid, src, idomdown))
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
            self.mlogger.warning('WbPageCmp:downpage EX0;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(wdex), src))
            locpath = '404'
        except WbCompError as wex:
            self.mlogger.warning('WbPageCmp:downpage EX1;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(wex), src))
            locpath = 'excode' + str(wex.excode)
        except TimeoutError as tex:
            self.mlogger.warning('WbPageCmp:downpage EX2;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(tex), src))
            locpath = 'timeout'
        except Exception as ex:
            if 'WinError 10060' in str(ex):
                self.mlogger.warning('WbPageCmp:downpage EX3;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(ex), src))
                locpath = 'timeout'
            else:
                self.mlogger.exception(ex)
                self.mlogger.error('WbPageCmp:downpage EX4;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(ex), src))
                locpath = ''
        return locpath, opttext

    def downpic(self, mid, src, fid, fdir):
        try:
            text = self.wbcomp.gethtml(src, timeout=(30, 60), rtry=1)[1]
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
                res = self.wbcomp.getres(imgurl, timeout=(30, 300))
                locpath = fdir + '\\' + mid + fname
                img = res.content
                with open(locpath, 'wb') as f:
                    f.write(img)
            else:
                imge = soup.select_one('div.m_error')
                if imge is not None:
                    locpath = '404'
                else:
                    raise Exception('WbPageCmp:downpic EX:none img dom')
        except TimeoutError as tex:
            self.mlogger.exception(tex)
            self.mlogger.error('WbPageCmp:downpic EX2;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(tex), src))
            locpath = 'timeout'
        except Exception as ex:
            locpath = ''
            self.mlogger.exception(ex)
            self.mlogger.error('WbPageCmp:downpic EX;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(ex), src))
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
            res = self.wbcomp.getres(src, timeout=(30, 300))
            locpath = fdir + '\\' + mid + fname
            img = res.content
            with open(locpath, 'wb') as f:
                f.write(img)
        except TimeoutError as tex:
            self.mlogger.exception(tex)
            self.mlogger.error('WbPageCmp:downvideo EX2;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(tex), src))
            locpath = 'timeout'
        except Exception as ex:
            locpath = ''
            self.mlogger.exception(ex)
            self.mlogger.error('WbPageCmp:downvideo EX;mid:{},fid:{},ex:{},murl:{}'.format(mid, fid, str(ex), src))
        return locpath

    def downchatpic(self, src, fdir):
        fid = ''
        locpath = ''
        success = 1
        fids = re.findall(r'\S+fid=(\d+)', src, re.S)
        if len(fids) == 1:
            fid = fids[0]
        res = self.wbcomp.getres(src, timeout=(30, 300))
        cdi = res.headers.get('Content-Disposition', '')
        if cdi:
            cdis = re.findall(r'\S+filename="(\S+)"', cdi, re.S)
            if len(cdis) == 1:
                sfix = cdis[0]
                filename = fid + 'f' + sfix
                locpath = fdir + '\\' + filename
                img = res.content
                with open(locpath, 'wb') as f:
                    f.write(img)
        return success, locpath

    def fchchathb(self, hburl, slt=0):
        success = 0
        if slt:
            slt = round(slt * 0.1, 1)
            time.sleep(slt)
        text = self.wbcomp.gethtml(hburl, 'chat')[1]
        hbamt = 0
        p = r'\$CONFIG\[\'bonus\'\]\s*=\s*\"(.+?)\"'
        hbamttxt = re.findall(p, text, re.S)
        if len(hbamttxt) > 0:
            hbamt = float(hbamttxt[0])
        if '已存入您的钱包' in text and hbamt > 0:
            success = 1
        if not success:
            self.mlogger.warning('hb success:{} hbamt:{} text:{}'.format(success, hbamt, text))
        return success, hbamt, slt

    def fchchathtml(self, hurl):
        self.mlogger.debug('fchchathtml:{}'.format(hurl))
        success = 0
        fpath = ''
        return success, fpath


if __name__ == '__main__':
    glogger = logger.TuLog('testwbpage', '/../log', True, logging.DEBUG).getlog()
    owbun = 'sretof@live.cn'
    owbpw = '1122aaa'
    owbcomp = WbComp(owbun, owbpw, mlogger=glogger)
    owbcomp.login()
    owbpagecmp = WbPageCmp(owbcomp)
    owbpagecmp.downmedia('4410177627355609', fdir='F:\\bg')
