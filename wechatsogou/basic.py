# -*- coding: utf-8 -*-

import urllib.request
import requests
import random
import time
import re
import tempfile

from lxml import etree
from PIL import Image

from . import config
from .base import WechatSogouBase
from .exceptions import *
from .ruokuaicode import RClient
from .filecache import WechatCache


class WechatSogouBasic(WechatSogouBase):
    """基于搜狗搜索的的微信公众号爬虫接口 基本功能类
    """

    def __init__(self):
        self.cache = WechatCache(config.cache_dir, 60 * 60)
        self.session = self.cache.get(config.cache_session_name) if self.cache.get(
            config.cache_session_name) else requests.session()

        if config.dama_type == 'ruokuai':
            self.ocr = RClient(config.dama_name, config.dama_pswd, config.dama_soft_id, config.dama_soft_key)

        self.agent = [
            "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; AcooBrowser; .NET CLR 1.1.4322; .NET CLR 2.0.50727)",
            "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0; Acoo Browser; SLCC1; .NET CLR 2.0.50727; Media Center PC 5.0; .NET CLR 3.0.04506)",
            "Mozilla/4.0 (compatible; MSIE 7.0; AOL 9.5; AOLBuild 4337.35; Windows NT 5.1; .NET CLR 1.1.4322; .NET CLR 2.0.50727)",
            "Mozilla/5.0 (Windows; U; MSIE 9.0; Windows NT 9.0; en-US)",
            "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Win64; x64; Trident/5.0; .NET CLR 3.5.30729; .NET CLR 3.0.30729; .NET CLR 2.0.50727; Media Center PC 6.0)",
            "Mozilla/5.0 (compatible; MSIE 8.0; Windows NT 6.0; Trident/4.0; WOW64; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; .NET CLR 1.0.3705; .NET CLR 1.1.4322)",
            "Mozilla/4.0 (compatible; MSIE 7.0b; Windows NT 5.2; .NET CLR 1.1.4322; .NET CLR 2.0.50727; InfoPath.2; .NET CLR 3.0.04506.30)",
            "Mozilla/5.0 (Windows; U; Windows NT 5.1; zh-CN) AppleWebKit/523.15 (KHTML, like Gecko, Safari/419.3) Arora/0.3 (Change: 287 c9dfb30)",
            "Mozilla/5.0 (X11; U; Linux; en-US) AppleWebKit/527+ (KHTML, like Gecko, Safari/419.3) Arora/0.6",
            "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.8.1.2pre) Gecko/20070215 K-Ninja/2.1.1",
            "Mozilla/5.0 (Windows; U; Windows NT 5.1; zh-CN; rv:1.9) Gecko/20080705 Firefox/3.0 Kapiko/3.0",
            "Mozilla/5.0 (X11; Linux i686; U;) Gecko/20070322 Kazehakase/0.4.5",
            "Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.8) Gecko Fedora/1.9.0.8-1.fc10 Kazehakase/0.5.6",
            "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_3) AppleWebKit/535.20 (KHTML, like Gecko) Chrome/19.0.1036.7 Safari/535.20",
            "Opera/9.80 (Macintosh; Intel Mac OS X 10.6.8; U; fr) Presto/2.9.168 Version/11.52",
        ]

    def get_elem_text(self, elem):
        """抽取lxml.etree库中elem对象中文字

        Args:
            elem: lxml.etree库中elem对象

        Returns:
            elem中文字
        """
        rc = []
        for node in elem.itertext():
            rc.append(node.strip())
        return ''.join(rc)

    def get_encoding_from_reponse(self, r):
        """获取requests库get或post返回的对象编码

        Args:
            r: requests库get或post返回的对象

        Returns:
            对象编码
        """
        encoding = requests.utils.get_encodings_from_content(r.text)
        return encoding[0] if encoding else requests.utils.get_encoding_from_headers(r.headers)

    def get(self, url, host='', referer='', proxy=False):
        """封装request库get方法

        Args:
            url: 请求url
            host: 请求host
            referer: 请求referer
            proxy: 是否启用代理请求

        Returns:
            text: 请求url的网页内容

        Raises:
            WechatSogouException: 操作频繁以致出现验证码或requests请求返回码错误
        """
        headers = {
            "User-Agent": self.agent[random.randint(0, len(self.agent) - 1)],
            "Referer": referer if referer else 'http://weixin.sogou.com/',
            'Host': host if host else 'weixin.sogou.com',
        }
        if proxy:
            # todo 代理
            r = self.session.get(url, headers=headers)
        else:
            r = self.session.get(url, headers=headers)
        if r.status_code == requests.codes.ok:
            r.encoding = self.get_encoding_from_reponse(r)
            if '用户您好，您的访问过于频繁，为确认本次访问为正常用户行为，需要您协助验证' in r.text:
                self.vcode_url = url
                raise WechatSogouVcodeException('weixin.sogou.com verification code')
        else:
            raise WechatSogouRequestsException('requests status_code error', r.status_code)
        return r.text

    def jiefeng(self, ruokuai=False):
        """对于出现验证码，识别验证码，解封

        Args:
            ruokuai: 是否采用若快打码平台

        Raises:
            WechatSogouVcodeException: 解封失败，可能验证码识别失败
        """
        codeurl = 'http://weixin.sogou.com/antispider/util/seccode.php?tc=' + str(time.time())[0:10]
        coder = self.session.get(codeurl)
        if hasattr(self, 'ocr'):
            result = self.ocr.create(coder.content, 3060)
            img_code = result['Result']
        else:
            f = tempfile.TemporaryFile()
            f.write(coder.content)
            im = Image.open(f)
            im.show()
            img_code = input("please input code: ")
        post_url = 'http://weixin.sogou.com/antispider/thank.php'
        post_data = {
            'c': img_code,
            'r': urllib.request.quote(self.vcode_url),
            'v': 5
        }
        headers = {
            "User-Agent": self.agent[random.randint(0, len(self.agent) - 1)],
            'Host': 'weixin.sogou.com',
            'Referer': 'http://weixin.sogou.com/antispider/?from=%2f' + urllib.request.quote(
                self.vcode_url.replace('http://', ''))
        }
        rr = self.session.post(post_url, post_data, headers=headers)
        remsg = eval(rr.content)
        if remsg['code'] != 0:
            raise WechatSogouVcodeException('cannot jiefeng because ' + remsg['msg'])
        self.cache.set(config.cache_session_name, self.session)
        print(remsg['msg'])

    def replace_html(self, s):
        """替换html‘&quot;’等转义内容为正常内容

        Args:
            s: 文字内容

        Returns:
            s: 处理反转义后的文字
        """
        s = s.replace('&quot;', '"')
        s = s.replace('&amp;', '&')
        s = s.replace('amp;', '')
        s = s.replace('&lt;', '<')
        s = s.replace('&gt;', '>')
        s = s.replace('&nbsp;', ' ')
        s = s.replace(r"\\", r'')
        return s

    def replace_space(self, s):
        s = s.replace(' ', '')
        s = s.replace('\r\n', '')
        return s

    def search_gzh_text(self, name, page=1):
        """通过搜狗搜索获取关键字返回的文本

        Args:
            name: 搜索关键字
            page: 搜索的页数

        Returns:
            text: 返回的文本
        """
        request_url = 'http://weixin.sogou.com/weixin?query=' + urllib.request.quote(
            name) + '&_sug_type_=&_sug_=n&type=1&page=' + str(page) + '&ie=utf8'
        try:
            text = self.get(request_url)
        except WechatSogouVcodeException:
            self.jiefeng()
            text = self.get(request_url, '', 'http://weixin.sogou.com/antispider/?from=%2f' + urllib.request.quote(
                self.vcode_url.replace('http://', '')))
        return text

    def search_article_text(self, name, page=1):
        """通过搜狗搜索微信文章关键字返回的文本
        Args:
            name: 搜索文章关键字
            page: 搜索的页数

        Returns:
            text: 返回的文本
        """
        request_url = 'http://weixin.sogou.com/weixin?query=' + urllib.request.quote(
            name) + '&_sug_type_=&_sug_=n&type=2&page=' + str(page) + '&ie=utf8'
        try:
            text = self.get(request_url)
        except WechatSogouVcodeException:
            self.jiefeng()
            text = self.get(request_url, '', 'http://weixin.sogou.com/antispider/?from=%2f' + urllib.request.quote(
                self.vcode_url.replace('http://', '')))
        return text

    def get_gzh_article_by_url_text(self, url):
        """最近文章页的文本

        Args:
            url: 最近文章页地址

        Returns:
            text: 返回的文本
        """
        return self.get(url, 'mp.weixin.qq.com')

    def get_gzh_article_gzh_by_url_dict(self, text, url):
        """最近文章页  公众号信息

        Args:
            text: 最近文章文本

        Returns:
            字典{'name':name,'wechatid':wechatid,'jieshao':jieshao,'renzhen':renzhen,'qrcode':qrcodes,'img':img,'url':url}
            name: 公众号名称
            wechatid: 公众号id
            jieshao: 介绍
            renzhen: 认证，为空表示未认证
            qrcode: 二维码
            img: 头像图片
            url: 最近文章地址
        """
        page = etree.HTML(text)
        profile_info_area = page.xpath("//div[@class='profile_info_area']")[0]
        img = profile_info_area.xpath('div[1]/span/img/@src')[0]
        name = profile_info_area.xpath('div[1]/div/strong/text()')[0]
        name = self.replace_space(name)
        wechatid = profile_info_area.xpath('div[1]/div/p/text()')
        if wechatid:
            wechatid = wechatid[0].replace('微信号: ', '')
        else:
            wechatid = ''
        jieshao = profile_info_area.xpath('ul/li[1]/div/text()')[0]
        renzhen = profile_info_area.xpath('ul/li[2]/div/text()')
        renzhen = renzhen[0] if renzhen else ''
        qrcode = page.xpath('//*[@id="js_pc_qr_code_img"]/@src')[0]
        qrcode = 'http://mp.weixin.qq.com/'+qrcode if qrcode else ''
        return {
            'name': name,
            'wechatid': wechatid,
            'jieshao': jieshao,
            'renzhen': renzhen,
            'qrcode': qrcode,
            'img': img,
            'url': url
        }

    def get_gzh_article_by_url_dict(self, text):
        """最近文章页 文章信息

        Args:
            text: 最近文章文本

        Returns:
            msgdict: 最近文章信息字典
        """
        msglist = re.findall("var msgList = '(.+?)';", text, re.S)[0]
        msgdict = eval(self.replace_html(msglist))
        return msgdict

    def deal_gzh_article_dict(self, msgdict):
        """处理最近文章页信息

        Args:
            msgdict: 最近文章信息字典

        Returns:
            列表，均是{'main':'', 'title':','digest':'','content':'','fileid':'','content_url':'','source_url':'','cover':'','author':'','copyright_stat':''}
            main: 是否是一次推送中第一篇文章，1则是
            title: 文章标题
            digest: 摘要
            content:
            fileid:
            content_url: 文章地址
            source_url: 原文地址
            cover: 封面图片
            author: 作者
            copyright_stat: 文章内容版权性
        """
        items = list()
        for listdic in msgdict['list']:
            item = listdic['app_msg_ext_info']
            items.append(
                {
                    'main': '1',
                    'title': item.get('title', ''),
                    'digest': item.get('digest', ''),
                    'content': item.get('content', ''),
                    'fileid': item.get('fileid', ''),
                    'content_url': 'http://mp.weixin.qq.com' + item.get('content_url') if item.get(
                        'content_url') else '',
                    'source_url': item.get('source_url', ''),
                    'cover': item.get('cover', ''),
                    'author': item.get('author', ''),
                    'copyright_stat': item.get('copyright_stat', '')
                }
            )
            if item['is_multi'] == 1:
                for multidic in item['multi_app_msg_item_list']:
                    items.append(
                        {
                            'main': '0',
                            'title': multidic.get('title', ''),
                            'digest': multidic.get('digest', ''),
                            'content': multidic.get('content', ''),
                            'fileid': multidic.get('fileid', ''),
                            'content_url': 'http://mp.weixin.qq.com' + multidic.get('content_url') if multidic.get(
                                'content_url') else '',
                            'source_url': multidic.get('source_url', ''),
                            'cover': multidic.get('cover', ''),
                            'author': multidic.get('author', ''),
                            'copyright_stat': multidic.get('copyright_stat', '')
                        }
                    )
        return items

    def get_gzh_article_text(self, url):
        """获取文章文本

        Args:
            url: 文章链接

        Returns:
            text: 文章文本
        """
        return self.get(url, 'mp.weixin.qq.com')

    def deal_related(self, article):
        """获取文章相似文章

        Args:
            article: 文章信息字典
            包含字典：article['content_url'],article['title'] 即可

        Returns:
            related_dict: 相似文章字典

        Raises:
            WechatSogouException: 错误信息errmsg
        """
        content_url = article['content_url']
        title = article['title']
        related_req_url = 'http://mp.weixin.qq.com/mp/getrelatedmsg?' \
                          'url=' + urllib.request.quote(content_url) \
                          + '&title=' + title \
                          + '&uin=&key=&pass_ticket=&wxtoken=&devicetype=&clientversion=0&x5=0'
        related_text = self.get(related_req_url, 'mp.weixin.qq.com', content_url)
        related_dict = eval(related_text)
        ret = related_dict['base_resp']['ret']
        errmsg = related_dict['base_resp']['errmsg'] if related_dict['base_resp']['errmsg'] else 'ret:' + str(ret)
        if ret != 0:
            raise WechatSogouException(errmsg)
        return related_dict
