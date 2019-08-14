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


if __name__ == '__main__':
    wbe = WbCompError('404','aaaaa')
    print(wbe)
