#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'

import logging
import os
import time


class TuLog:
    def __init__(self, lname, lpath='/log', sch=False, flevel=logging.ERROR, clevel=logging.DEBUG):
        '''
            指定保存日志的文件路径，日志级别，以及调用文件
            将日志存入到指定的文件中
            logger 强制,否则logging.getLogger()取RootLogger共用
        '''

        # 创建一个logger
        self.logger = logging.getLogger(lname)
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            # 创建一个handler，用于写入日志文件
            self.log_time = time.strftime("%Y_%m_%d")
            file_dir = lpath
            if not os.path.exists(file_dir):
                os.mkdir(file_dir)
            self.log_path = file_dir
            self.log_name = self.log_path + "/" + lname + "." + self.log_time + '.log'

            fh = logging.FileHandler(self.log_name, encoding='utf-8')  # 默认追加模式
            fh.setLevel(flevel)

            # 定义handler的输出格式
            formatter = logging.Formatter(
                '[%(asctime)s]\tFile \"%(filename)s\" %(thread)d:,line %(lineno)s\t%(levelname)s: %(message)s')
            fh.setFormatter(formatter)

            # 再创建一个handler，用于输出到控制台
            ch = logging.StreamHandler()
            ch.setLevel(clevel)
            ch.setFormatter(formatter)

            # 给logger添加handler
            self.logger.addHandler(fh)
            if sch:
                self.logger.addHandler(ch)

            #  添加下面一句，在记录日志之后移除句柄
            # self.logger.removeHandler(ch)
            # self.logger.removeHandler(fh)
            # 关闭打开的文件
            fh.close()

    def getlog(self):
        return self.logger


def main():
    print(os.getcwd())
    log1 = TuLog('log1', sch=True).getlog()
    TuLog('log1').getlog()
    TuLog('log1').getlog()
    log1.debug('debug==log1======>')
    log1.info('info==log1======>')

    # log2 = TuLog('log2').getlog()
    # log2.debug('debug==log2======>')
    # log2.info('info==log2======>')


if __name__ == '__main__':
    main()
