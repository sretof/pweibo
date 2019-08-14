#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'

import re

import conf.db as dbc
import uuid
from urllib.parse import unquote

import wbutil.wbmon as wbmon

from wbutil.wbcomp import WbComp


class TLDetailAly:
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
    def getdetailtxt(txtdiv, mtype='0', files=[], skipdoms=[]):
        adoms = txtdiv.select('a')
        idoms = txtdiv.select('img')
        txtsuf = ''
        for adom in adoms:
            fauuid = ''.join(str(uuid.uuid1()).split('-'))
            if adom.get('render', '') == 'ext':
                pass
            elif 'WB_text_opt' in adom.get('class', []):
                mtype = '13'
                furl = WbComp.fillwbhref(adom.get('href', ''))
                if not furl.startswith('http'):
                    furl = ''
                    skipdoms.append('getdetailtxt adom1 WB_text_opt err dom?{}'.format(str(adom)))
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
                    skipdoms.append('getdetailtxt adom2 feed_list_url err dom?{}'.format(str(adom)))
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
                skipdoms.append('getdetailtxt adom3 err dom?{}'.format(str(adom)))
        for idom in idoms:
            itit = idom.get('title', '')
            if itit:
                txtsuf = txtsuf + itit
        txt = txtdiv.text.strip()
        if txtsuf:
            txt = txt + '//face:' + txtsuf
        return txt, mtype, files, skipdoms

    @staticmethod
    def getdetailmedia(mediadiv, uid, mid, mtype, files, skipdoms):
        if mediadiv is None:
            return mtype, files, skipdoms
        fmuuid = ''.join(str(uuid.uuid1()).split('-'))
        mediaul = mediadiv.select_one('ul.WB_media_a')
        fdiv = mediadiv.select_one('div.WB_feed_spec[action-data]')
        fvdiv = mediadiv.select_one('div.WB_feed_spec > div.spec_box > div[video-sources]')
        if fdiv is not None and fdiv['action-data'].startswith('url'):
            hasd = 0
            furl = WbComp.fillwbhref(unquote(fdiv['action-data'][4:]))
            if not furl.startswith('http'):
                furl = ''
                skipdoms.append('getdetailmedia fdiv1 action-data err url?{}'.format(fdiv['action-data']))
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
                    file = {'url': furl, 'hasd': 0, 'mtype': '21', 'fid': pid}
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
                pvs = TLDetailAly.getvideosource(videoli['video-sources'])
                vfuid = ''.join(str(uuid.uuid1()).split('-'))
                file = {'url': pvs, 'hasd': 0, 'mtype': '22', 'fid': vfuid}
                files.append(file)
        if fvdiv is not None:
            mtype = mtype + '23'
            pvs = TLDetailAly.getvideosource(fvdiv['video-sources'])
            vfuid = ''.join(str(uuid.uuid1()).split('-'))
            file = {'url': pvs, 'hasd': 0, 'mtype': '23', 'fid': vfuid}
            files.append(file)
        if mediaul is None and fdiv is None and fvdiv is None:
            skipdoms.append('getdetailmedia media_box none dom?{}'.format(str(mediadiv)))
        return mtype, files, skipdoms

    @staticmethod
    def getfwddoc(fwd, mtype):
        if fwd is None:
            return mtype, None, None, None, []
        fwdhsave = False
        infod = fwd.select_one('div.WB_info a:first-child')
        if infod is None:
            return mtype, None, None, None, []
        suda = infod.get('suda-uatrack', '')
        sreg = r'transuser_nick:(\d+)'
        srtxt = re.findall(sreg, suda, re.S)
        fwdmid = '' if len(srtxt) < 1 else srtxt[0]
        if not fwdmid:
            return mtype, None, None, None, []
        mtype = mtype + '31'
        fsdt = wbmon.getgpbymid(fwdmid)
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
            fwdtxt, fmtype, ffiles, fskipdoms = TLDetailAly.getdetailtxt(txtd)
            mediad = fwd.select_one('div.WB_media_wrap > div.media_box')
            mtype, files, fskipdoms = TLDetailAly.getdetailmedia(mediad, fuid, fwdmid, fmtype, ffiles, fskipdoms)
            retfwdoc = {'mid': fwdmid, 'ctext': fwdtxt, 'cturl': fcurl, 'ctime': fctime, 'uid': fuid,
                        'uname': funame, 'mtype': fmtype, 'media': ffiles}
        else:
            fwdhsave = True
            retfwdoc = {'mid': fwdmid, 'ctext': fsdt.get('ctext', ''), 'cturl': fsdt.get('cturl', ''),
                        'ctime': fsdt.get('ctime', ''),
                        'uid': fsdt.get('uid', ''),
                        'uname': fsdt.get('uname', ''), 'mtype': fsdt.get('mtype', ''),
                        'media': fsdt.get('media', [])}
        return mtype, fwdhsave, fwdmid, retfwdoc, fskipdoms
