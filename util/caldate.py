#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'

import calendar
import datetime
import time


def ymd2date(ymd, se='N'):
    date = datetime.date(int(ymd[0:4]), int(ymd[4:6]), int(ymd[6:8]))
    if se == 'S':
        date = calmonths(date)
    elif se == 'E':
        date = calmonthe(date)
    return date


def calmonths(date=datetime.date.today(), x=0):
    if x <= 0:
        return datetime.date(date.year, date.month, 1)
    while x >= 1:
        date = datetime.date(date.year, date.month, 1)
        date = date - datetime.timedelta(days=1)
        date = datetime.date(date.year, date.month, 1)
        x -= 1
    return date


def calmonthe(date=datetime.date.today(), x=0):
    date = calmonths(date, x)
    days_num = calendar.monthrange(date.year, date.month)[1]
    date = date + datetime.timedelta(days_num - 1)
    return date


def today():
    return datetime.date.today()


def now():
    return datetime.datetime.now()


def preday(date=datetime.date.today(), n=1):
    return date + datetime.timedelta(n * -1)


def presec(ptime=datetime.datetime.now(), n=1):
    tn = n * -1
    return ptime - datetime.timedelta(seconds=tn)


def premin(ptime=datetime.datetime.now(), n=1):
    tn = 60 * n * -1
    return presec(ptime, tn)


def gettimestamp():
    return int(time.time() * 1000)  # 获取13位时间戳


def getdaystr(day=None, fmt='%Y%m%d'):
    if day is None:
        day = now()
    return day.strftime(fmt)


def test():
    print(getdaystr(preday()))
    # print('01===>', int('01') == 1)
    # print('02===>', int(today().strftime('%Y%m%d')[6:8]) == 1, int(today().strftime('%Y%m%d')[6:8]))
    # print('1===>', calmonths(), calmonthe())
    # tdate = datetime.date.today()
    # for i in range(0, 25):
    #     print(i, ' ', calmonths(tdate, i), ' ', calmonthe(tdate, i))


if __name__ == '__main__':
    test()
