#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'

from pymongo import MongoClient

import conf.db as dbc
import util.caldate as cald


def getMongoWDb():
    conn = MongoClient(dbc.MGOHOST, 27017)
    wdb = conn[dbc.MGOWDB]
    coll = wdb[dbc.MGOCTCOLL]
    return conn, wdb, coll


def getgtlmaxmid():
    conn, wdb, coll = getMongoWDb()
    try:
        results = coll.aggregate(
            [{'$match': {'cday': {'$gt': '20190809'}}}, {'$group': {'_id': "$gid", 'maxmid': {'$max': "$smid"}}}])
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


def hasdownmedia(mid, fid, locpath):
    conn, wdb, coll = getMongoWDb()
    try:
        if locpath == '404':
            # pass
            coll.update_one({'mid': mid, 'media.fid': fid}, {'$set': {'media.$.hasd': 1, 'media.$.mtype': locpath}})
        else:
            coll.update_one({'mid': mid, 'media.fid': fid}, {'$set': {'media.$.hasd': 1, 'media.$.locpath': locpath}})
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


def delgpbymid(mid):
    conn, wdb, coll = getMongoWDb()
    try:
        coll.delete_one({'mid': mid})
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
    gtlmaxmid = getgtlmaxmid()
    print(gtlmaxmid)
