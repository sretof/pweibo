#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'

import re

import conf.db as dbc
import uuid


class TLDetailAly:
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
