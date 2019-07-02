import base64
import json
import random
import re
import time
from binascii import b2a_hex
from urllib.parse import quote

import requests
import rsa
import urllib3

urllib3.disable_warnings()  # 取消警告


def get_timestamp():
    return int(time.time() * 1000)  # 获取13位时间戳


class PWeiBo():
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.session()  # 登录用session
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
        }
        self.session.verify = False  # 取消证书验证
        self.trylogincnt = 0

    @staticmethod
    def creatgid(gid, gname):
        return '{}&name={}&type=2'.format(gid, quote(gname))

    @staticmethod
    def getgmsgfct(text):
        p = r'<script>FM\.view\({"ns":"pl\.msgbox\.detail\.index",(.*?)\)</script>'
        jtext = re.findall(p, text, re.S)
        jtext = '{' + jtext[0]
        ptext = json.loads(jtext)
        thtml = ptext['html']
        print(thtml)

    def clearsession(self):
        self.session = requests.session()  # 登录用session
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
        }
        self.session.verify = False  # 取消证书验证

    def prelogin(self):
        '''预登录，获取一些必须的参数'''
        self.su = base64.b64encode(self.username.encode())  # 阅读js得知用户名进行base64转码
        url = 'https://login.sina.com.cn/sso/prelogin.php?entry=weibo&callback=sinaSSOController.preloginCallBack&su={}&rsakt=mod&checkpin=1&client=ssologin.js(v1.4.19)&_={}'.format(
            quote(self.su), get_timestamp())  # 注意su要进行quote转码
        response = self.session.get(url).content.decode()
        # print(response)
        self.nonce = re.findall(r'"nonce":"(.*?)"', response)[0]
        self.pubkey = re.findall(r'"pubkey":"(.*?)"', response)[0]
        self.rsakv = re.findall(r'"rsakv":"(.*?)"', response)[0]
        self.servertime = re.findall(r'"servertime":(.*?),', response)[0]
        return self.nonce, self.pubkey, self.rsakv, self.servertime

    def get_sp(self):
        '''用rsa对明文密码进行加密，加密规则通过阅读js代码得知'''
        publickey = rsa.PublicKey(int(self.pubkey, 16), int('10001', 16))
        message = str(self.servertime) + '\t' + str(self.nonce) + '\n' + str(self.password)
        self.sp = rsa.encrypt(message.encode(), publickey)
        return b2a_hex(self.sp)

    def login(self):
        self.prelogin()
        self.get_sp()
        url = 'https://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.19)'
        data = {
            'entry': 'weibo',
            'gateway': '1',
            'from': '',
            'savestate': '7',
            'qrcode_flag': 'false',
            'useticket': '1',
            'pagerefer': 'https://login.sina.com.cn/crossdomain2.php?action=logout&r=https%3A%2F%2Fweibo.com%2Flogout.php%3Fbackurl%3D%252F',
            'vsnf': '1',
            'su': self.su,
            'service': 'miniblog',
            'servertime': str(int(self.servertime) + random.randint(1, 20)),
            'nonce': self.nonce,
            'pwencode': 'rsa2',
            'rsakv': self.rsakv,
            'sp': self.get_sp(),
            'sr': '1536 * 864',
            'encoding': 'UTF - 8',
            'prelt': '35',
            'url': 'https://weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack',
            'returntype': 'META',
        }
        response = self.session.post(url, data=data, allow_redirects=False).text  # 提交账号密码等参数
        try:
            redirect_url = re.findall(r'location.replace\("(.*?)"\);', response)[0]  # 微博在提交数据后会跳转，此处获取跳转的url
            self.trylogincnt = 0
        except IndexError:
            print("login field......:" + str(self.trylogincnt))
            self.trylogincnt = self.trylogincnt + 1
            if self.trylogincnt < 60:
                st = self.trylogincnt // 10 + 1
                self.clearsession()
                time.sleep(st)
                self.login()
            return

        result = self.session.get(redirect_url, allow_redirects=False).text  # 请求跳转页面
        ticket, ssosavestate = re.findall(r'ticket=(.*?)&ssosavestate=(.*?)"', result)[0]  # 获取ticket和ssosavestate参数
        uid_url = 'https://passport.weibo.com/wbsso/login?ticket={}&ssosavestate={}&callback=sinaSSOController.doCrossDomainCallBack&scriptId=ssoscript0&client=ssologin.js(v1.4.19)&_={}'.format(
            ticket, ssosavestate, get_timestamp())
        data = self.session.get(uid_url).text  # 请求获取uid
        uid = re.findall(r'"uniqueid":"(.*?)"', data)[0]
        print(uid)
        # home_url = 'https://weibo.com/u/{}/home?wvr=5&lf=reg'.format(uid)  # 请求首页
        # html = self.session.get(home_url)
        # html.encoding = 'utf-8'
        # print(html.text)

    def fgroupmsg(self, gid):
        gmsg_url = 'https://weibo.com/message/history?gid={}&_t={}'.format(gid, get_timestamp())
        print(gmsg_url)
        html = self.session.get(gmsg_url)
        html.encoding = 'utf-8'
        text = html.text
        PWeiBo.getgmsgfct(text)


def main(pweibo):
    pass
    pweibo.login()


if __name__ == '__main__':
    username = 'sretof@live.cn'  # 微博账号
    password = '1122aaa'  # 微博密码
    gids = (PWeiBo.creatgid('4305987512698522', 'Peter羊的V+'),)
    pweibo = PWeiBo(username, password)
    main(pweibo)
    for gid in gids:
        pweibo.fgroupmsg(gid)
