#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'

import re
import uuid
from urllib.parse import unquote

import wbutil.wbmon as wbmon
from wbutil.wbcomp import WbComp


class TLDetailAly:
    @staticmethod
    def chkandudpmediamtype(gid, medias):
        hasvideo = False
        if len(medias) > 0:
            hasm13 = False
            haspic = False
            m13doc = {}
            for amd in medias:
                amtype = amd['mtype']
                if amtype == '13':
                    hasm13 = True
                    m13doc = amd
                if amtype.endswith('21') or amtype.endswith('211'):
                    haspic = True
                if amtype == '22' or amtype == '23':
                    hasvideo = True
            if hasm13 and haspic and gid not in ['3653960185837784', '3909747545351455']:
                m13doc['mtype'] = '1321'
        return hasvideo

    @staticmethod
    def getvideosource(psv):
        psvs = psv.split('=http')
        psv = ''
        if len(psvs) > 0:
            psvs.reverse()
            for p in psvs:
                if 'ssig' in p and 'qType' in p:
                    psv = 'http' + p
                    break
                if 'youku' in p and 'qType' in p:
                    sps = p.split('"')
                    psv = 'http' + sps[0]
                    break
            if not psv:
                for p in psvs:
                    if 'qType' in p:
                        psv = 'http' + p
                        break
            if not psv:
                psv = 'http' + psvs[0]
        return unquote(psv)

    @staticmethod
    def getdetailtxt(txtdiv, mtype='0', files=None, skipdoms=None):
        if files is None:
            files = []
        if skipdoms is None:
            skipdoms = []
        adoms = txtdiv.select('a')
        idoms = txtdiv.select('img')
        txtsuf = ''
        txtstock = ''
        for adom in adoms:
            fauuid = ''.join(str(uuid.uuid1()).split('-'))
            if adom.get('render', '') == 'ext':
                pass
            elif adom.get('action-type', '') == 'fl_url_addparams':
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
            elif 'stock' in adom.get('suda-uatrack', ''):
                furl = adom.get('href', '')
                txtstock = '[' + WbComp.fillwbhref(furl) + ']'
            elif adom.get('action-type', '') == 'widget_photoview':
                furl = adom.get('short_url', '')
                if furl:
                    file = {'url': furl, 'hasd': 0, 'mtype': '211', 'fid': fauuid}
                    files.append(file)
            elif adom.get('action-type', '') == 'feed_list_url':
                lidom = adom.select_one('i.ficon_cd_link')
                vidom = adom.select_one('i.ficon_cd_video')
                title = adom.get('title', '')
                hasd = 0
                furl = adom.get('href', '')
                amtype = '14'
                if 'huati.weibo' in furl:
                    furl = ''
                elif vidom is not None:
                    hasd = 1
                    amtype = '22'
                elif '抽奖' in title:
                    hasd = 1
                    amtype = '91'
                elif lidom is not None:
                    mtype = '14'
                else:
                    furl = ''
                    skipdoms.append('getdetailtxt adom2 feed_list_url err dom?{}'.format(str(adom)))
                if furl:
                    file = {'url': furl, 'hasd': hasd, 'mtype': amtype, 'fid': fauuid}
                    files.append(file)
            else:
                skipdoms.append('getdetailtxt adom3 err dom?{}'.format(str(adom)))
        for idom in idoms:
            itit = idom.get('title', '')
            if itit:
                txtsuf = txtsuf + itit
        txt = txtdiv.text.strip()
        if txtsuf:
            txt = txt + '//face:' + txtsuf
        if txtstock:
            txt = txtstock + txt
        return txt, mtype, files, skipdoms

    @staticmethod
    def getdetailmedia(mediadiv, uid, mid, mtype, files, skipdoms):
        if files is None:
            files = []
        if skipdoms is None:
            skipdoms = []
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
            # for file in files:
            #     if file.mtype == '13' and
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
                if not pvs:
                    skipdoms.append('getdetailmedia media_box vssource null?{}'.format(videoli['video-sources']))
                    pvs = videoli['video-sources']
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
            ffsdt = wbmon.rs2list(wbmon.getgpbyfmidandfsave(fwdmid, True))
            if len(ffsdt) > 0:
                fsdt = ffsdt[0]
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
            fmtype, ffiles, fskipdoms = TLDetailAly.getdetailmedia(mediad, fuid, fwdmid, fmtype, ffiles, fskipdoms)
            if ffiles is None or not ffiles or len(ffiles) == 0:
                fwdhsave = True
            retfwdoc = {'mid': fwdmid, 'ctext': fwdtxt, 'cturl': fcurl, 'ctime': fctime, 'uid': fuid,
                        'uname': funame, 'mtype': fmtype, 'media': ffiles}
        else:
            fwdhsave = True
            retfwdoc = {'mid': fwdmid, 'ctext': fsdt.get('ctext', ''), 'cturl': fsdt.get('cturl', ''),
                        'ctime': fsdt.get('ctime', ''),
                        'uid': fsdt.get('uid', ''),
                        'uname': fsdt.get('uname', ''), 'mtype': fsdt.get('mtype', ''),
                        'media': fsdt.get('media', [])}
            fskipdoms = []
        return mtype, fwdhsave, fwdmid, retfwdoc, fskipdoms


if __name__ == '__main__':
    # vsurl = 'fluency=https%253A%252F%252Fapi.youku.com%252Fvideos%252Fplayer%252Ffile%253Fdata%253DWcEl1o6uUdTJOVFUzT1RnMU5nPT18MHwxfDEwMDUwfDAO0O0O&amp;480=' \
    #         'https%3A%2F%2Fapi.youku.com%2Fvideos%2Fplayer%2Ffile%3Fdata%3DWcEl1o6uUdTJOVFUzT1RnMU5nPT18MHwwfDEwMDUwfDAO0O0O&amp;720=&amp;qType=480' \
    #         '" action-data="type=feedvideo&amp;objectid=1007002:4407121391878427&amp;keys=4407121394270612&amp;' \
    #         'video_src=https%3A%2F%2Fapi.youku.com%2Fvideos%2Fplayer%2Ffile%3Fdata%3DWcEl1o6uUdTJOVFUzT1RnMU5nPT18MHwxfDEwMDUwfDAO0O0O&amp;cover_img' \
    #         '=https%3A%2F%2Fvthumb.ykimg.com%2F054101015AAA14EF8B3C46AAC91B7D9E&amp;card_height=540&amp;card_width=960&amp;play_count=5506&amp;duration=390&amp;short_url' \
    #         '=http%3A%2F%2Ft.cn%2FAiQ4tfcc%3Fm%3D4407121392845445%26u%3D1807436544&amp;encode_mode=&amp;bitrate=&amp;biz_id=231193&amp;current_mid=4407121392845445&amp;video_orientation=horizontal'
    vsurl = '=https%253A%252F%252Fmultimedia.api.weibo.com%252F2%252Fmultimedia%252Fredirect_tencent_video.json%253Fvid%253Db0031sjobsz&480=https%3A%2F%2Fmultimedia.api.weibo.com%2F2%2Fmultimedia%2Fredirect_tencent_video.json%3Fvid%3Db0031sjobsz&720=&qType=480'
    print(TLDetailAly.getvideosource(vsurl))
    # print('===', unquote(''))

    # cmedia = []
    # mto = {'mtype': '13'}
    # mtp = {'mtype': '21'}
    # cmedia.append(mto)
    # cmedia.append(mtp)
    # tdoc = {'media': cmedia}
    # hasv = TLDetailAly.chkandudpmediamtype('1', tdoc)
    # print(hasv)
    # print(tdoc)
