#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'


class WbCompError(Exception):
    def __init__(self, excode, gurl='', htext=''):
        self.excode = excode
        self.gurl = gurl
        self.htext = htext
        super().__init__(self)

    def __str__(self):
        return 'WbCompError Code:{},Gurl:{}'.format(self.excode, self.gurl)


class WbCompDownError(Exception):
    def __init__(self, excode, gurl='', htext=''):
        self.excode = excode
        self.gurl = gurl
        self.htext = htext
        super().__init__(self)

    def __str__(self):
        return 'WbCompError Code:{},Gurl:{}'.format(self.excode, self.gurl)


class WbMonNoneDocError(Exception):
    def __init__(self, mid):
        self.mid = mid
        super().__init__(self)

    def __str__(self):
        return 'WbMonNoneDocError mid:{}'.format(self.mid)


class WbChatGetDocError(Exception):
    def __init__(self, excode):
        self.excode = excode
        super().__init__(self)

    def __str__(self):
        return 'WbChatGetDocError mid:{}'.format(self.excode)


if __name__ == '__main__':
    wbe = WbMonNoneDocError('1')
    print(wbe)
