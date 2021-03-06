# -*- coding: utf-8 -*-
"""
通过法院名称搜索
"""
import json
import re
import scrapy
import redis
from rmfygg import settings
import jsonpath
import logging

from rmfygg.config import court_custom_settings
from rmfygg.work_utils.clean_data import get_real_cf_xzjg

logger = logging.getLogger(__name__)


class RmfyCourtSpider(scrapy.Spider):
    name = 'court'

    custom_settings = court_custom_settings
    list_url = 'https://rmfygg.court.gov.cn/web/rmfyportal/noticeinfo?p_p_id=noticelist_WAR_rmfynoticeListportlet&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_resource_id=initNoticeList&p_p_cacheability=cacheLevelPage&p_p_col_id=column-1&p_p_col_count=1'
    index_url = 'https://rmfygg.court.gov.cn/web/rmfyportal/noticedetail?p_p_id=noticedetail_WAR_rmfynoticeDetailportlet&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_resource_id=noticeDetail&p_p_cacheability=cacheLevelPage&p_p_col_id=column-1&p_p_col_count=1'
    keywords = ['开庭传票', '裁判文书', '执行文书', '仲裁文书', '拍卖公告', '行政处罚通知书', '起诉状、上诉状副本', '公示催告', '宣告失踪、死亡', '无主财产认领公告', '起诉状副本及开庭传票', '其他', '更正', '遗失声明', '司法鉴定书', '海事文书', '清算公告', '版权公告', '公益诉讼', '送达公告', '公益诉讼案件公告']
    pool = redis.ConnectionPool(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, password=settings.REDIS_PASSWORD)
    redis_client = redis.Redis(connection_pool=pool, decode_responses=True)

    def start_requests(self):
        handle_list = [
            {"name": "sEcho", "value": 1},
            {"name": "iColumns", "value": 6},
            {"name": "sColumns", "value": ",,,,,"},
            {"name": "iDisplayStart", "value": 0},
            {"name": "iDisplayLength", "value": 15},
            {"name": "mDataProp_0", "value": "null"},
            {"name": "mDataProp_1", "value": "null"},
            {"name": "mDataProp_2", "value": "null"},
            {"name": "mDataProp_3", "value": "null"},
            {"name": "mDataProp_4", "value": "null"},
            {"name": "mDataProp_5", "value": "null"},
        ]
        list_court = self.redis_client.smembers('court:name')
        for court in list_court:
            court = court.decode('utf-8')
            for keyword in self.keywords:
                if keyword == '开庭传票':
                    sj_type = '75'
                    site_id = 29035
                    xxly = '人民法院公告网-开庭传票'
                elif keyword == '裁判文书':
                    sj_type = '74'
                    site_id = 29206
                    xxly = '人民法院公告网-裁判文书'
                elif keyword == '执行文书':
                    sj_type = '76'
                    site_id = 29236
                    xxly = '人民法院公告网-执行公告'
                elif keyword == '仲裁文书':
                    sj_type = '仲裁文书'
                    site_id = 29583
                    xxly = '人民法院公告网-仲裁文书'
                elif keyword == '拍卖公告':
                    sj_type = '17'
                    site_id = 29568
                    xxly = '人民法院公告网-拍卖公告'
                elif keyword == '行政处罚决定书':
                    sj_type = ''
                    site_id = 29651
                    xxly = '人民法院公告网-行政处罚通知书'
                else:
                    sj_type = '77'
                    site_id = 29614
                    xxly = '人民法院公告网-其他公告'
                meta_data = {'sj_type': sj_type, 'site_id': site_id, 'xxly': xxly}
                form_data = {
                    '_noticelist_WAR_rmfynoticeListportlet_content': '',
                    '_noticelist_WAR_rmfynoticeListportlet_searchContent': '',
                    '_noticelist_WAR_rmfynoticeListportlet_courtParam': str(court),
                    '_noticelist_WAR_rmfynoticeListportlet_IEVersion': 'ie',
                    '_noticelist_WAR_rmfynoticeListportlet_flag': 'click',
                    '_noticelist_WAR_rmfynoticeListportlet_noticeTypeVal': str(keyword),
                    '_noticelist_WAR_rmfynoticeListportlet_aoData': str(handle_list),
                }
                yield scrapy.FormRequest(
                    url=self.list_url,
                    formdata=form_data,
                    callback=self.parse_index,
                    meta={'form_data': form_data, 'item': meta_data},
                    dont_filter=True,
                )

    def parse_index(self, response):
        """ 理论上该函数翻页解析可以结合到一起，目的是避免重复请求第一页，等有时间修改下 """
        form_data = response.meta.get('form_data')
        item = response.meta.get('item')
        results_first = json.loads(response.text)
        # 解析
        results = json.loads(response.text).get('data')
        if not results:
            return None
        for result in results:
            # cf_xzjg = result.get('court')  # 法院名称 公告人
            # ws_nr_txt = result.get('noticeContent')  # 内容
            # noticeCodeEnc = result.get('noticeCodeEnc')  # pdf下载参数
            # noticeCode = result.get('noticeCode')  # pdf得位置
            oname = result.get('tosendPeople')  # 当事人
            fb_rq = result.get('publishDate')  # 发布时间
            cf_type = result.get('noticeType')  # 类型
            uuid = result.get('uuid')  # 详情页参数
            xq_url = 'https://rmfygg.court.gov.cn/web/rmfyportal/noticedetail?paramStr={}'.format(uuid)
            list_data = dict(oname=oname, xq_url=xq_url, fb_rq=fb_rq, cf_type=cf_type, cf_cflb=cf_type, cf_zt=cf_type)
            data = {**item, **list_data}
            form_data = {"_noticedetail_WAR_rmfynoticeDetailportlet_uuid": str(uuid)}
            yield scrapy.FormRequest(
                url=self.index_url,
                formdata=form_data,
                method='POST',
                callback=self.parse_detail,
                meta={'item': data},
                priority=3,
            )
        # 翻页
        is_first = response.meta.get('is_first', True)
        page_count = jsonpath.jsonpath(results_first, expr='$..iTotalRecords')
        if is_first:
            if page_count:
                counts = int(int(page_count[0]) / 15 + 1) if int(page_count[0]) % 15 == 0 else int(int(page_count[0]) / 15) + 2
                for page in range(2, counts):
                    handle_list = [
                        {"name": "sEcho", "value": page},
                        {"name": "iColumns", "value": 6},
                        {"name": "sColumns", "value": ",,,,,"},
                        {"name": "iDisplayStart", "value": 15 * (page - 1)},
                        {"name": "iDisplayLength", "value": 15},
                        {"name": "mDataProp_0", "value": "null"},
                        {"name": "mDataProp_1", "value": "null"},
                        {"name": "mDataProp_2", "value": "null"},
                        {"name": "mDataProp_3", "value": "null"},
                        {"name": "mDataProp_4", "value": "null"},
                        {"name": "mDataProp_5", "value": "null"}
                    ]
                    form_data['_noticelist_WAR_rmfynoticeListportlet_aoData'] = str(handle_list)
                    yield scrapy.FormRequest(
                        url=self.list_url,
                        formdata=form_data,
                        callback=self.parse_index,
                        # dont_filter=True,  # 不过滤，已经请求了第一页算页码数，不设置将获取不到第一页得数据
                        priority=3,
                        meta={'item': item, 'is_first': False}
                    )

    def parse_detail(self, response):
        """ 详情页解析 """
        base_item = response.meta.get("item")
        sj_type = base_item.get('sj_type')
        results = json.loads(response.text)
        bz = results.get('publishPage')  # 刊登版面
        cf_jdrq = results.get('publishDate')  # 决定日期
        sf = results.get('province')  # 省份
        cf_cfmc = results.get('tosendPeople')  # 当事人
        ws_nr_txt = results.get('noticeContent')
        ws_nr_txt = self.handles_text(ws_nr_txt)
        if sj_type == '':
            cf_xzjg = get_real_cf_xzjg(ws_nr_txt)
        elif sj_type == '仲裁文书':
            cf_xzjg = get_real_cf_xzjg(ws_nr_txt)
            if '劳动' in cf_xzjg or '劳动争议' in cf_xzjg:
                sj_type = '19'
            else:
                sj_type = '20'
        else:
            cf_xzjg = results.get('court')  # 处罚机关，法院名
        index_item = dict(cf_xzjg=cf_xzjg, bz=bz, cf_jdrq=cf_jdrq, sf=sf, cf_cfmc=cf_cfmc, cf_jg=ws_nr_txt, ws_nr_txt=ws_nr_txt, sj_type=sj_type)
        item = {**base_item, **index_item}
        yield item

    @classmethod
    def handles_text(cls, txt):
        if txt:
            txt = re.sub(r'\r|\n|\t|\s', '', txt)
        else:
            txt = ''
        return txt