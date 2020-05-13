#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'

from pymongo import MongoClient

import conf.db as dbc
import util.caldate as cald


def getMongoWDb():
    conn = MongoClient(dbc.MGOHOST, username=dbc.MGOWAUU, password=dbc.MGOWAUP, authSource=dbc.MGOWDB, authMechanism='SCRAM-SHA-256')
    wdb = conn[dbc.MGOWDB]
    coll = wdb[dbc.MGOCTCOLL]
    return conn, wdb, coll


def getMongoWChatDb():
    conn = MongoClient(dbc.MGOHOST, username=dbc.MGOWAUU, password=dbc.MGOWAUP, authSource=dbc.MGOWDB, authMechanism='SCRAM-SHA-256')
    wdb = conn[dbc.MGOWDB]
    coll = wdb[dbc.MGOCHATCOLL]
    return conn, wdb, coll


def rs2list(rsdocs):
    rsl = []
    for rsdoc in rsdocs:
        rsl.append(rsdoc)
    return rsl


def getgtlmaxmid():
    conn, wdb, coll = getMongoWDb()
    try:
        pdstr = cald.getdaystr(cald.preday(n=7))
        results = coll.aggregate(
            [{'$match': {'cday': {'$gte': pdstr}}}, {'$group': {'_id': "$gid", 'maxmid': {'$max': "$smid"}}}])
        gtlmaxmid = {}
        for res in results:
            gtlmaxmid[res['_id']] = res['maxmid']
        return gtlmaxmid
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def getgpbymid(mid):
    conn, wdb, coll = getMongoWDb()
    try:
        result = coll.find_one({'mid': mid})
        return result
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def getgpbyfmidandfsave(fmid, fsave):
    conn, wdb, coll = getMongoWDb()
    try:
        result = coll.find({'fwdmid': fmid, 'fwdhsave': fsave}).sort('smid', -1)
        return result
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def delgpbymid(mid):
    conn, wdb, coll = getMongoWDb()
    try:
        coll.delete_one({'mid': mid})
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


def hasdownmedia(mid, fid, locpath, opttext):
    conn, wdb, coll = getMongoWDb()
    try:
        if locpath == '404' or locpath == '1321' or locpath == 'timeout' or locpath.startswith('excode'):
            # pass
            coll.update_one({'mid': mid, 'media.fid': fid}, {'$set': {'media.$.hasd': 1, 'media.$.mtype': locpath}})
        else:
            coll.update_one({'mid': mid, 'media.fid': fid}, {'$set': {'media.$.hasd': 1, 'media.$.locpath': locpath}})
        if opttext:
            coll.update_one({'mid': mid}, {'$set': {'ctext': opttext}})
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def hasdownfwdmedia(mid, fid, locpath, opttext):
    conn, wdb, coll = getMongoWDb()
    try:
        if locpath == '404' or locpath == '1321' or locpath == 'timeout':
            # pass
            coll.update_one({'mid': mid, 'fwdmedia.fid': fid}, {'$set': {'fwdmedia.$.hasd': 1, 'fwdmedia.$.mtype': 'excode' + locpath}})
        elif locpath.startswith('excode'):
            coll.update_one({'mid': mid, 'fwdmedia.fid': fid}, {'$set': {'fwdmedia.$.hasd': 1, 'fwdmedia.$.mtype': locpath}})
        else:
            coll.update_one({'mid': mid, 'fwdmedia.fid': fid}, {'$set': {'fwdmedia.$.hasd': 1, 'fwdmedia.$.locpath': locpath}})
        if opttext:
            coll.update_one({'mid': mid}, {'$set': {'fwdtext': opttext}})
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def savedoc(gid, doc, tlsrc='gtl'):
    if doc['fwdhsave'] is None:
        del doc['fwdhsave']
        del doc['fwdmid']
        del doc['fwddoc']
    else:
        fwddoc = doc['fwddoc']
        doc['fwdtext'] = fwddoc['ctext']
        fmedia = fwddoc['media']
        if len(fmedia) > 0:
            doc['fwdmedia'] = fmedia
        del fwddoc['ctext']
        del fwddoc['media']
    doc = dict({'gid': gid}, **doc)
    doc['fday'] = cald.getdaystr()
    doc['ftime'] = cald.now()
    doc['smid'] = doc['cday'] + doc['mid']
    doc['tlsrc'] = tlsrc
    conn, wdb, coll = getMongoWDb()
    try:
        coll.insert_one(doc)
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def undownfwd(fday=None):
    if fday is None:
        fday = cald.getdaystr(cald.today())
    conn, wdb, coll = getMongoWDb()
    try:
        isodt = cald.premin(n=30)
        result = coll.find({'fday': {'$lte': fday}, 'ftime': {'$lte': isodt}, 'fwdhsave': False}).sort('smid', -1).limit(100)
        return result
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def hasdownfwddoc(mid):
    conn, wdb, coll = getMongoWDb()
    try:
        coll.update_one({'mid': mid}, {'$set': {'fwdhsave': True}})
        fsdt = getgpbymid(mid)
        setdoc = {'fwdhsave': True, 'fwddoc': fsdt['fwddoc'], 'fwdtext': fsdt['fwdtext']}
        fmedias = fsdt.get('fwdmedia', [])
        if len(fmedias) > 0:
            setdoc['fwdmedia'] = fmedias
        coll.update_many({'fwdmid': fsdt['fwdmid'], 'fwdhsave': False}, {'$set': setdoc})
    except Exception as mex:
        raise mex
    finally:
        conn.close()


################
# UTL
################
def getutlhect():
    conn = MongoClient(dbc.MGOHOST, 27017)
    wdb = conn[dbc.MGOWDB]
    coll = wdb[dbc.MGOUTLHCOLL]
    try:
        result = coll.find()
        return result
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def getmtlmindoc(uid, conn=None, coll=None):
    nclose = False
    if conn is None:
        nclose = True
        conn, wdb, coll = getMongoWDb()
    try:
        doc = coll.find({'uid': uid}).sort('smid', 1).limit(1)
        return doc
    except Exception as mex:
        raise mex
    finally:
        if nclose:
            conn.close()


################
# CHAT
################
def getgcmaxmid():
    conn, wdb, coll = getMongoWChatDb()
    try:
        pdstr = cald.getdaystr(cald.preday(n=7))
        results = coll.aggregate(
            [{'$match': {'mday': {'$gte': pdstr}}}, {'$group': {'_id': "$gid", 'maxmid': {'$max': "$smid"}}}])
        gcmaxmid = {}
        for res in results:
            gcmaxmid[res['_id']] = res['maxmid']
        return gcmaxmid
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def savechatdata(mid, mday, gid, buid, bn, cttype, ct, hd, fid, fpath, mtime):
    doc = dict()
    doc['gid'] = gid
    doc['mid'] = mid
    doc['buid'] = buid
    doc['bn'] = bn
    doc['cttype'] = cttype
    doc['ct'] = ct
    doc['hd'] = hd
    doc['fid'] = fid
    doc['fpath'] = fpath
    doc['mday'] = mday
    doc['mtime'] = mtime
    doc['ftime'] = cald.now()
    smid = mday + mid
    doc['smid'] = smid
    savechatdoc(doc)


def savechatdoc(doc):
    if 'id' in doc:
        del doc['id']
    if 'mdate' in doc:
        doc['mday'] = doc['mdate']
        del doc['mdate']
    if 'smid' not in doc:
        doc['smid'] = doc['mday'] + doc['mid']
    conn, wdb, coll = getMongoWChatDb()
    try:
        coll.insert_one(doc)
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def savechatdocs(docs):
    for doc in docs:
        if 'id' in doc:
            del doc['id']
        if 'mdate' in doc:
            doc['mday'] = doc['mdate']
            del doc['mdate']
        if 'smid' not in doc:
            doc['smid'] = doc['mday'] + doc['mid']
    conn, wdb, coll = getMongoWChatDb()
    try:
        coll.insert_many(docs)
    except Exception as mex:
        raise mex
    finally:
        conn.close()


################

def getmbmaxminmid(muid, maxy):
    conn, wdb, coll = getMongoWDb()
    try:
        maxr = coll.find({'uid': muid}).sort('mid', -1).limit(1)
        minr = coll.find({'uid': muid, 'cday': {'$gte': '20190801'}}).sort('mid', 1).limit(1)
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


def getgpbygidandmid(gid, mid):
    conn, wdb, coll = getMongoWDb()
    try:
        result = coll.find_one({'gid': gid, 'mid': mid})
        return result
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def udpgpdetail(mid, field, val):
    conn, wdb, coll = getMongoWDb()
    try:
        coll.update_one({'mid': mid}, {'$set': {field: val}})
    except Exception as mex:
        raise mex
    finally:
        conn.close()


def udpgpfwdmedia(mid, field, val):
    conn, wdb, coll = getMongoWDb()
    try:
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
    conn, wdb, coll = getMongoWDb()
    try:
        coll.insert_one(doc)
    except Exception as mex:
        raise mex
    finally:
        conn.close()


if __name__ == '__main__':
    # rsdocs = undownfwd()
    # for rsdoc in rsdocs:
    #     print(rsdoc['mid'])
    # hasdownfwddoc('4409900610253824')
    # rss = undownfwd()
    # for rs in rss:
    #     print(rs['mid'])
    # rss = rs2list(getgpbyfmidandfsave('44112781115655721', True))
    # print(rss)
    # hasdownfwddoc('4411315231832192')
    #username=dbc.MGOWU, password=dbc.MGOWU, authSource=dbc.MGOWDB,
    #oconn = MongoClient("139.199.13.252", username='weibo', password='Weibo@173', authSource='weibo', authMechanism='SCRAM-SHA-1')
    oconn = MongoClient("139.199.13.252", username=dbc.MGOWAUU, password=dbc.MGOWAUP, authSource=dbc.MGOWDB, authMechanism='SCRAM-SHA-256')
    owdb = oconn[dbc.MGOWDB]
    ocoll = owdb[dbc.MGOCHATCOLL]
    results = ocoll.aggregate(
        [{'$match': {'mday': {'$gte': '20191114'}}}, {'$group': {'_id': "$gid", 'maxmid': {'$max': "$smid"}}}])
    for res in results:
        print(res['maxmid'])
