#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def alygtlfeeds(feeds):
    exdom = []
    for i in feeds:
        # mid = 'mid' + str(i)
        # skipdoms = []
        # txt, skipdoms = getdetailtxt(mid)
        # media, skipdoms = getmediatxt(mid, skipdoms)
        # if len(skipdoms) > 0:
        #     print(i, txt, media, skipdoms)
        txt, tp = listp('mid' + str(i))
        print(i, tp)

        txt, dp = dictp('mid' + str(i))
        print(i, dp)

        txt, sp = strp('mid' + str(i))
        print(i, sp)


def listp(mid, p=[]):
    print('lbp:', p)
    txt = 'txt:' + mid
    p.append(txt)
    return txt, p


def dictp(mid, p={}):
    print('dbp:', p)
    txt = 'media:' + mid
    p[mid] = txt
    return txt, p


def strp(mid, p='int'):
    print('sbp:', p)
    txt = 'media:' + mid
    p = txt
    return txt, p


if __name__ == '__main__':
    alygtlfeeds([0, 1])
