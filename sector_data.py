#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""板块行业数据 - AKShare全量A股 + 交易所分组 + 行业板块"""

import json
import os
import time
import sys
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), 'sector_data_cache.json')
LAST_UPDATE_FILE = os.path.join(os.path.dirname(__file__), 'sector_data_last_update.txt')

# ==================== 硬编码热门板块数据（44个板块，约920只） ====================

DEFAULT_SECTORS = {
    '半导体': {'name': '半导体', 'stocks': [
        {'code': '688981', 'name': '中芯国际'}, {'code': '603501', 'name': '韦尔股份'},
        {'code': '002371', 'name': '北方华创'}, {'code': '688012', 'name': '中微公司'},
        {'code': '300661', 'name': '圣邦股份'}, {'code': '600703', 'name': '三安光电'},
        {'code': '300782', 'name': '卓胜微'}, {'code': '688396', 'name': '华润微'},
        {'code': '002185', 'name': '华天科技'}, {'code': '603986', 'name': '兆易创新'},
        {'code': '688041', 'name': '海光信息'}, {'code': '300316', 'name': '晶盛机电'},
        {'code': '603290', 'name': '斯达半导'}, {'code': '002049', 'name': '紫光国微'},
        {'code': '603160', 'name': '汇顶科技'}, {'code': '603893', 'name': '瑞芯微'},
        {'code': '688008', 'name': '澜起科技'}, {'code': '688126', 'name': '沪硅产业'},
        {'code': '300604', 'name': '长川科技'}, {'code': '002156', 'name': '通富微电'},
        {'code': '688072', 'name': '拓荆科技'}, {'code': '688120', 'name': '华海清科'},
        {'code': '300567', 'name': '精测电子'}, {'code': '688019', 'name': '安集科技'},
        {'code': '300346', 'name': '南大光电'}, {'code': '002409', 'name': '雅克科技'},
        {'code': '300054', 'name': '鼎龙股份'}, {'code': '603005', 'name': '晶方科技'},
        {'code': '688200', 'name': '华峰测控'}, {'code': '301269', 'name': '华大九天'},
        {'code': '688082', 'name': '盛美上海'}, {'code': '688728', 'name': '格科微'},
        {'code': '688362', 'name': '甬矽电子'}, {'code': '688409', 'name': '富创精密'},
    ]},
    '人工智能': {'name': '人工智能', 'stocks': [
        {'code': '002230', 'name': '科大讯飞'}, {'code': '300308', 'name': '中际旭创'},
        {'code': '688111', 'name': '金山办公'}, {'code': '300624', 'name': '万兴科技'},
        {'code': '002236', 'name': '大华股份'}, {'code': '300418', 'name': '昆仑万维'},
        {'code': '603019', 'name': '中科曙光'}, {'code': '000977', 'name': '浪潮信息'},
        {'code': '300502', 'name': '新易盛'}, {'code': '688256', 'name': '寒武纪'},
        {'code': '600570', 'name': '恒生电子'}, {'code': '688095', 'name': '福昕软件'},
        {'code': '300454', 'name': '深信服'}, {'code': '002920', 'name': '德赛西威'},
        {'code': '688568', 'name': '中科星图'}, {'code': '688327', 'name': '云从科技'},
        {'code': '300496', 'name': '中科创达'}, {'code': '688031', 'name': '星环科技'},
        {'code': '300229', 'name': '拓尔思'}, {'code': '300075', 'name': '数字政通'},
        {'code': '002405', 'name': '四维图新'}, {'code': '300188', 'name': '美亚柏科'},
    ]},
    '新能源车': {'name': '新能源车', 'stocks': [
        {'code': '002594', 'name': '比亚迪'}, {'code': '601127', 'name': '赛力斯'},
        {'code': '000625', 'name': '长安汽车'}, {'code': '300750', 'name': '宁德时代'},
        {'code': '002466', 'name': '天齐锂业'}, {'code': '002460', 'name': '赣锋锂业'},
        {'code': '300014', 'name': '亿纬锂能'}, {'code': '002709', 'name': '天赐材料'},
        {'code': '600104', 'name': '上汽集团'}, {'code': '300438', 'name': '鹏辉能源'},
        {'code': '002074', 'name': '国轩高科'}, {'code': '688567', 'name': '孚能科技'},
        {'code': '002812', 'name': '恩捷股份'}, {'code': '300568', 'name': '星源材质'},
        {'code': '002850', 'name': '科达利'}, {'code': '300769', 'name': '德方纳米'},
        {'code': '688116', 'name': '天奈科技'}, {'code': '301358', 'name': '湖南裕能'},
        {'code': '688779', 'name': '长远锂科'}, {'code': '300073', 'name': '当升科技'},
        {'code': '002759', 'name': '天际股份'}, {'code': '300035', 'name': '中科电气'},
    ]},
    '医药生物': {'name': '医药生物', 'stocks': [
        {'code': '300760', 'name': '迈瑞医疗'}, {'code': '600276', 'name': '恒瑞医药'},
        {'code': '603259', 'name': '药明康德'}, {'code': '300122', 'name': '智飞生物'},
        {'code': '000661', 'name': '长春高新'}, {'code': '300347', 'name': '泰格医药'},
        {'code': '002007', 'name': '华兰生物'}, {'code': '300015', 'name': '爱尔眼科'},
        {'code': '600196', 'name': '复星医药'}, {'code': '300529', 'name': '健帆生物'},
        {'code': '300759', 'name': '康龙化成'}, {'code': '000538', 'name': '云南白药'},
        {'code': '600436', 'name': '片仔癀'}, {'code': '002422', 'name': '科伦药业'},
        {'code': '300896', 'name': '爱美客'}, {'code': '600085', 'name': '同仁堂'},
        {'code': '000963', 'name': '华东医药'}, {'code': '300558', 'name': '贝达药业'},
        {'code': '688180', 'name': '君实生物'}, {'code': '688331', 'name': '荣昌生物'},
        {'code': '300601', 'name': '康泰生物'}, {'code': '603392', 'name': '万泰生物'},
        {'code': '688076', 'name': '诺泰生物'}, {'code': '600763', 'name': '通策医疗'},
        {'code': '300832', 'name': '新产业'}, {'code': '688271', 'name': '联影医疗'},
    ]},
    '军工': {'name': '军工', 'stocks': [
        {'code': '600760', 'name': '中航沈飞'}, {'code': '002179', 'name': '中航光电'},
        {'code': '600893', 'name': '航发动力'}, {'code': '000768', 'name': '中航西飞'},
        {'code': '600118', 'name': '中国卫星'}, {'code': '600879', 'name': '航天电子'},
        {'code': '600685', 'name': '中船防务'}, {'code': '600150', 'name': '中国船舶'},
        {'code': '600391', 'name': '航发科技'}, {'code': '300053', 'name': '航宇微'},
        {'code': '600862', 'name': '中航高科'}, {'code': '002013', 'name': '中航机电'},
        {'code': '002025', 'name': '航天电器'}, {'code': '600765', 'name': '中航重机'},
        {'code': '600482', 'name': '中国动力'}, {'code': '000547', 'name': '航天发展'},
        {'code': '688281', 'name': '华秦科技'}, {'code': '300696', 'name': '爱乐达'},
        {'code': '300719', 'name': '安达维尔'}, {'code': '600990', 'name': '四创电子'},
        {'code': '002465', 'name': '海格通信'}, {'code': '300034', 'name': '钢研高纳'},
        {'code': '600184', 'name': '光电股份'}, {'code': '300342', 'name': '天银机电'},
        {'code': '300600', 'name': '国瑞科技'}, {'code': '688563', 'name': '航材股份'},
    ]},
    '证券': {'name': '证券', 'stocks': [
        {'code': '600030', 'name': '中信证券'}, {'code': '300059', 'name': '东方财富'},
        {'code': '601688', 'name': '华泰证券'}, {'code': '600837', 'name': '海通证券'},
        {'code': '601211', 'name': '国泰君安'}, {'code': '600999', 'name': '招商证券'},
        {'code': '601066', 'name': '中信建投'}, {'code': '600958', 'name': '东方证券'},
        {'code': '601377', 'name': '兴业证券'}, {'code': '000776', 'name': '广发证券'},
        {'code': '002736', 'name': '国信证券'}, {'code': '002673', 'name': '西部证券'},
        {'code': '601878', 'name': '浙商证券'}, {'code': '601236', 'name': '红塔证券'},
        {'code': '601555', 'name': '东吴证券'}, {'code': '601162', 'name': '天风证券'},
        {'code': '601990', 'name': '南京证券'}, {'code': '601995', 'name': '中金公司'},
        {'code': '600369', 'name': '西南证券'}, {'code': '601456', 'name': '国联证券'},
        {'code': '600918', 'name': '中泰证券'}, {'code': '601696', 'name': '中银证券'},
        {'code': '601198', 'name': '东兴证券'}, {'code': '000750', 'name': '国海证券'},
        {'code': '601108', 'name': '财通证券'}, {'code': '002939', 'name': '长城证券'},
        {'code': '002797', 'name': '第一创业'}, {'code': '601990', 'name': '南京证券'},
    ]},
    '白酒': {'name': '白酒', 'stocks': [
        {'code': '600519', 'name': '贵州茅台'}, {'code': '000858', 'name': '五粮液'},
        {'code': '000568', 'name': '泸州老窖'}, {'code': '002304', 'name': '洋河股份'},
        {'code': '600809', 'name': '山西汾酒'}, {'code': '000596', 'name': '古井贡酒'},
        {'code': '603369', 'name': '今世缘'}, {'code': '603589', 'name': '口子窖'},
        {'code': '600559', 'name': '老白干酒'}, {'code': '603198', 'name': '迎驾贡酒'},
        {'code': '000799', 'name': '酒鬼酒'}, {'code': '600702', 'name': '舍得酒业'},
        {'code': '600779', 'name': '水井坊'}, {'code': '600199', 'name': '金种子酒'},
        {'code': '603919', 'name': '金徽酒'}, {'code': '600132', 'name': '重庆啤酒'},
        {'code': '600600', 'name': '青岛啤酒'}, {'code': '000860', 'name': '顺鑫农业'},
    ]},
    '光伏': {'name': '光伏', 'stocks': [
        {'code': '601012', 'name': '隆基绿能'}, {'code': '300274', 'name': '阳光电源'},
        {'code': '688599', 'name': '天合光能'}, {'code': '002459', 'name': '晶澳科技'},
        {'code': '600438', 'name': '通威股份'}, {'code': '688223', 'name': '晶科能源'},
        {'code': '301358', 'name': '湖南裕能'}, {'code': '300763', 'name': '锦浪科技'},
        {'code': '688390', 'name': '固德威'}, {'code': '605117', 'name': '德业股份'},
        {'code': '688516', 'name': '奥特维'}, {'code': '300450', 'name': '先导智能'},
        {'code': '601865', 'name': '福莱特'}, {'code': '002129', 'name': '中环股份'},
        {'code': '600732', 'name': '爱旭股份'}, {'code': '688408', 'name': '中信博'},
        {'code': '300827', 'name': '上能电气'}, {'code': '300776', 'name': '帝尔激光'},
        {'code': '688560', 'name': '明冠新材'}, {'code': '003022', 'name': '联泓新科'},
        {'code': '688717', 'name': '艾罗能源'}, {'code': '301266', 'name': '宇邦新材'},
        {'code': '301278', 'name': '快可电子'}, {'code': '300763', 'name': '锦浪科技'},
    ]},
    '银行': {'name': '银行', 'stocks': [
        {'code': '600036', 'name': '招商银行'}, {'code': '601398', 'name': '工商银行'},
        {'code': '601939', 'name': '建设银行'}, {'code': '601288', 'name': '农业银行'},
        {'code': '601988', 'name': '中国银行'}, {'code': '601328', 'name': '交通银行'},
        {'code': '600016', 'name': '民生银行'}, {'code': '600000', 'name': '浦发银行'},
        {'code': '002142', 'name': '宁波银行'}, {'code': '601166', 'name': '兴业银行'},
        {'code': '600015', 'name': '华夏银行'}, {'code': '601009', 'name': '南京银行'},
        {'code': '601169', 'name': '北京银行'}, {'code': '600919', 'name': '江苏银行'},
        {'code': '601229', 'name': '上海银行'}, {'code': '600926', 'name': '杭州银行'},
        {'code': '601818', 'name': '光大银行'}, {'code': '000001', 'name': '平安银行'},
        {'code': '601838', 'name': '成都银行'}, {'code': '601577', 'name': '长沙银行'},
        {'code': '601997', 'name': '贵阳银行'}, {'code': '601128', 'name': '常熟银行'},
        {'code': '600908', 'name': '无锡银行'}, {'code': '601860', 'name': '紫金银行'},
        {'code': '601187', 'name': '厦门银行'}, {'code': '601528', 'name': '瑞丰银行'},
        {'code': '601916', 'name': '浙商银行'}, {'code': '601963', 'name': '重庆银行'},
    ]},
    '房地产': {'name': '房地产', 'stocks': [
        {'code': '600048', 'name': '保利发展'}, {'code': '000002', 'name': '万科A'},
        {'code': '001979', 'name': '招商蛇口'}, {'code': '600325', 'name': '华发股份'},
        {'code': '600383', 'name': '金地集团'}, {'code': '000069', 'name': '华侨城A'},
        {'code': '600606', 'name': '绿地控股'}, {'code': '002146', 'name': '荣盛发展'},
        {'code': '600340', 'name': '华夏幸福'}, {'code': '000656', 'name': '金科股份'},
        {'code': '600376', 'name': '首开股份'}, {'code': '000402', 'name': '金融街'},
        {'code': '600208', 'name': '新湖中宝'}, {'code': '600657', 'name': '信达地产'},
        {'code': '600185', 'name': '格力地产'}, {'code': '600663', 'name': '陆家嘴'},
        {'code': '002244', 'name': '滨江集团'}, {'code': '600848', 'name': '上海临港'},
        {'code': '600895', 'name': '张江高科'}, {'code': '000736', 'name': '中交地产'},
        {'code': '600266', 'name': '城建发展'}, {'code': '600649', 'name': '城投控股'},
        {'code': '600153', 'name': '建发股份'}, {'code': '600823', 'name': '世茂股份'},
        {'code': '600848', 'name': '上海临港'}, {'code': '600604', 'name': '市北高新'},
    ]},
    '电力/能源': {'name': '电力/能源', 'stocks': [
        {'code': '600900', 'name': '长江电力'}, {'code': '601985', 'name': '中国核电'},
        {'code': '600905', 'name': '三峡能源'}, {'code': '600886', 'name': '国投电力'},
        {'code': '601857', 'name': '中国石油'}, {'code': '600028', 'name': '中国石化'},
        {'code': '600011', 'name': '华能国际'}, {'code': '600027', 'name': '华电国际'},
        {'code': '601991', 'name': '大唐发电'}, {'code': '600023', 'name': '浙能电力'},
        {'code': '600025', 'name': '华能水电'}, {'code': '003816', 'name': '中国广核'},
        {'code': '600021', 'name': '上海电力'}, {'code': '600483', 'name': '福能股份'},
        {'code': '600674', 'name': '川投能源'}, {'code': '600642', 'name': '申能股份'},
        {'code': '000591', 'name': '太阳能'}, {'code': '601868', 'name': '中国能建'},
        {'code': '600875', 'name': '东方电气'}, {'code': '601016', 'name': '节能风电'},
        {'code': '600795', 'name': '国电电力'}, {'code': '600886', 'name': '国投电力'},
        {'code': '600188', 'name': '兖矿能源'}, {'code': '601088', 'name': '中国神华'},
        {'code': '600688', 'name': '上海石化'}, {'code': '600346', 'name': '恒力石化'},
    ]},
    '食品饮料': {'name': '食品饮料', 'stocks': [
        {'code': '600887', 'name': '伊利股份'}, {'code': '603288', 'name': '海天味业'},
        {'code': '000895', 'name': '双汇发展'}, {'code': '002568', 'name': '百润股份'},
        {'code': '603345', 'name': '安井食品'}, {'code': '002557', 'name': '洽洽食品'},
        {'code': '603027', 'name': '千禾味业'}, {'code': '603866', 'name': '桃李面包'},
        {'code': '600882', 'name': '妙可蓝多'}, {'code': '300146', 'name': '汤臣倍健'},
        {'code': '600597', 'name': '光明乳业'}, {'code': '603156', 'name': '养元饮品'},
        {'code': '600600', 'name': '青岛啤酒'}, {'code': '600132', 'name': '重庆啤酒'},
        {'code': '000729', 'name': '燕京啤酒'}, {'code': '002461', 'name': '珠江啤酒'},
        {'code': '603711', 'name': '香飘飘'}, {'code': '603517', 'name': '绝味食品'},
        {'code': '002847', 'name': '盐津铺子'}, {'code': '603043', 'name': '广州酒家'},
        {'code': '600305', 'name': '恒顺醋业'}, {'code': '002582', 'name': '好想你'},
        {'code': '002714', 'name': '牧原股份'}, {'code': '300498', 'name': '温氏股份'},
        {'code': '000876', 'name': '新希望'}, {'code': '603363', 'name': '傲农生物'},
    ]},
    '机器人': {'name': '机器人', 'stocks': [
        {'code': '300124', 'name': '汇川技术'}, {'code': '002747', 'name': '埃斯顿'},
        {'code': '688017', 'name': '绿的谐波'}, {'code': '300607', 'name': '拓斯达'},
        {'code': '002527', 'name': '新时达'}, {'code': '300024', 'name': '机器人'},
        {'code': '002896', 'name': '中大力德'}, {'code': '688160', 'name': '步科股份'},
        {'code': '688305', 'name': '科德数控'}, {'code': '688333', 'name': '铂力特'},
        {'code': '301368', 'name': '丰立智能'}, {'code': '301255', 'name': '通力科技'},
        {'code': '688071', 'name': '华依科技'}, {'code': '688697', 'name': '纽威数控'},
        {'code': '002598', 'name': '山东章鼓'}, {'code': '300278', 'name': '华昌达'},
        {'code': '300097', 'name': '智云股份'}, {'code': '002031', 'name': '巨轮智能'},
        {'code': '301082', 'name': '久盛电气'}, {'code': '300403', 'name': '汉宇集团'},
        {'code': '600579', 'name': '克劳斯'}, {'code': '002689', 'name': '远大智能'},
    ]},
    '消费电子': {'name': '消费电子', 'stocks': [
        {'code': '300433', 'name': '蓝思科技'}, {'code': '002475', 'name': '立讯精密'},
        {'code': '002241', 'name': '歌尔股份'}, {'code': '601138', 'name': '工业富联'},
        {'code': '002600', 'name': '领益智造'}, {'code': '002456', 'name': '欧菲光'},
        {'code': '300136', 'name': '信维通信'}, {'code': '002384', 'name': '东山精密'},
        {'code': '688036', 'name': '传音控股'}, {'code': '002273', 'name': '水晶光电'},
        {'code': '300115', 'name': '长盈精密'}, {'code': '300735', 'name': '光弘科技'},
        {'code': '688661', 'name': '和林微纳'}, {'code': '300709', 'name': '精研科技'},
        {'code': '002861', 'name': '瀛通通讯'}, {'code': '300679', 'name': '电连技术'},
        {'code': '603005', 'name': '晶方科技'}, {'code': '002655', 'name': '共达电声'},
        {'code': '301280', 'name': '珠城科技'}, {'code': '002036', 'name': '联创电子'},
    ]},
    '有色金属': {'name': '有色金属', 'stocks': [
        {'code': '601899', 'name': '紫金矿业'}, {'code': '600547', 'name': '山东黄金'},
        {'code': '600489', 'name': '中金黄金'}, {'code': '000630', 'name': '铜陵有色'},
        {'code': '600362', 'name': '江西铜业'}, {'code': '601600', 'name': '中国铝业'},
        {'code': '000831', 'name': '中国稀土'}, {'code': '600111', 'name': '北方稀土'},
        {'code': '600010', 'name': '包钢股份'}, {'code': '600497', 'name': '驰宏锌锗'},
        {'code': '000060', 'name': '中金岭南'}, {'code': '002340', 'name': '格林美'},
        {'code': '600392', 'name': '盛和资源'}, {'code': '688122', 'name': '西部超导'},
        {'code': '603993', 'name': '洛阳钼业'}, {'code': '600219', 'name': '南山铝业'},
        {'code': '000933', 'name': '神火股份'}, {'code': '600988', 'name': '赤峰黄金'},
        {'code': '600711', 'name': '盛屯矿业'}, {'code': '002167', 'name': '东方锆业'},
        {'code': '600259', 'name': '广晟有色'}, {'code': '000762', 'name': '西藏矿业'},
        {'code': '002466', 'name': '天齐锂业'}, {'code': '002460', 'name': '赣锋锂业'},
    ]},
    '建筑工程': {'name': '建筑工程', 'stocks': [
        {'code': '601668', 'name': '中国建筑'}, {'code': '601390', 'name': '中国中铁'},
        {'code': '601186', 'name': '中国铁建'}, {'code': '601800', 'name': '中国交建'},
        {'code': '600170', 'name': '上海建工'}, {'code': '601618', 'name': '中国中冶'},
        {'code': '601669', 'name': '中国电建'}, {'code': '600031', 'name': '三一重工'},
        {'code': '601868', 'name': '中国能建'}, {'code': '601117', 'name': '中国化学'},
        {'code': '000928', 'name': '中钢国际'}, {'code': '600970', 'name': '中材国际'},
        {'code': '002051', 'name': '中工国际'}, {'code': '000065', 'name': '北方国际'},
        {'code': '600039', 'name': '四川路桥'}, {'code': '600820', 'name': '隧道股份'},
        {'code': '002061', 'name': '浙江交科'}, {'code': '600502', 'name': '安徽建工'},
        {'code': '002307', 'name': '北新路桥'}, {'code': '601611', 'name': '中国核建'},
        {'code': '600585', 'name': '海螺水泥'}, {'code': '000786', 'name': '北新建材'},
        {'code': '002271', 'name': '东方雨虹'}, {'code': '600176', 'name': '中国巨石'},
        {'code': '000528', 'name': '柳工'}, {'code': '600031', 'name': '三一重工'},
    ]},
    '算力/数据中心': {'name': '算力/数据中心', 'stocks': [
        {'code': '603019', 'name': '中科曙光'}, {'code': '000977', 'name': '浪潮信息'},
        {'code': '300308', 'name': '中际旭创'}, {'code': '688041', 'name': '海光信息'},
        {'code': '002281', 'name': '光迅科技'}, {'code': '300502', 'name': '新易盛'},
        {'code': '300394', 'name': '天孚通信'}, {'code': '002463', 'name': '沪电股份'},
        {'code': '601138', 'name': '工业富联'}, {'code': '300476', 'name': '胜宏科技'},
        {'code': '002916', 'name': '深南电路'}, {'code': '603186', 'name': '华正新材'},
        {'code': '688498', 'name': '源杰科技'}, {'code': '300570', 'name': '太辰光'},
        {'code': '301191', 'name': '菲菱科思'}, {'code': '300964', 'name': '中孚信息'},
        {'code': '688662', 'name': '富信科技'}, {'code': '688205', 'name': '仕佳光子'},
        {'code': '688313', 'name': '仕佳光子'} if False else {'code': '688100', 'name': '威胜信息'},
        {'code': '688100', 'name': '威胜信息'}, {'code': '300913', 'name': '兆龙互联'},
    ]},
    '通信/5G': {'name': '通信/5G', 'stocks': [
        {'code': '600941', 'name': '中国移动'}, {'code': '601728', 'name': '中国电信'},
        {'code': '600050', 'name': '中国联通'}, {'code': '300628', 'name': '亿联网络'},
        {'code': '600745', 'name': '闻泰科技'}, {'code': '002792', 'name': '通宇通讯'},
        {'code': '600522', 'name': '中天科技'}, {'code': '300353', 'name': '东土科技'},
        {'code': '688100', 'name': '威胜信息'}, {'code': '603083', 'name': '剑桥科技'},
        {'code': '688668', 'name': '鼎通科技'}, {'code': '301165', 'name': '锐捷网络'},
        {'code': '300025', 'name': '华星创业'}, {'code': '300578', 'name': '会畅通讯'},
        {'code': '000063', 'name': '中兴通讯'}, {'code': '002089', 'name': '新海宜'},
        {'code': '603421', 'name': '鼎信通讯'}, {'code': '300620', 'name': '光库科技'},
        {'code': '688313', 'name': '仕佳光子'}, {'code': '300913', 'name': '兆龙互联'},
    ]},
    '化工/材料': {'name': '化工/材料', 'stocks': [
        {'code': '600309', 'name': '万华化学'}, {'code': '000830', 'name': '鲁西化工'},
        {'code': '002601', 'name': '龙佰集团'}, {'code': '600352', 'name': '浙江龙盛'},
        {'code': '600426', 'name': '华鲁恒升'}, {'code': '600346', 'name': '恒力石化'},
        {'code': '000301', 'name': '东方盛虹'}, {'code': '600486', 'name': '扬农化工'},
        {'code': '002407', 'name': '多氟多'}, {'code': '603260', 'name': '合盛硅业'},
        {'code': '600989', 'name': '宝丰能源'}, {'code': '000792', 'name': '盐湖股份'},
        {'code': '688065', 'name': '凯赛生物'}, {'code': '002064', 'name': '华峰化学'},
        {'code': '002749', 'name': '国光股份'}, {'code': '300596', 'name': '利安隆'},
        {'code': '002709', 'name': '天赐材料'}, {'code': '600141', 'name': '兴发集团'},
        {'code': '002092', 'name': '中泰化学'}, {'code': '600409', 'name': '三友化工'},
        {'code': '600160', 'name': '巨化股份'}, {'code': '000822', 'name': '山东海化'},
        {'code': '002002', 'name': '鸿达兴业'}, {'code': '002125', 'name': '湘潭电化'},
    ]},
    '汽车零部件': {'name': '汽车零部件', 'stocks': [
        {'code': '601689', 'name': '拓普集团'}, {'code': '600741', 'name': '华域汽车'},
        {'code': '600660', 'name': '福耀玻璃'}, {'code': '601799', 'name': '星宇股份'},
        {'code': '600699', 'name': '均胜电子'}, {'code': '300432', 'name': '富临精工'},
        {'code': '600933', 'name': '爱柯迪'}, {'code': '002284', 'name': '亚太股份'},
        {'code': '603786', 'name': '科博达'}, {'code': '603179', 'name': '新泉股份'},
        {'code': '300969', 'name': '恒帅股份'}, {'code': '002765', 'name': '蓝黛科技'},
        {'code': '000559', 'name': '万向钱潮'}, {'code': '601238', 'name': '广汽集团'},
        {'code': '600733', 'name': '北汽蓝谷'}, {'code': '300680', 'name': '隆盛科技'},
        {'code': '002101', 'name': '广东鸿图'}, {'code': '600480', 'name': '凌云股份'},
        {'code': '603997', 'name': '继峰股份'}, {'code': '601717', 'name': '郑煤机'},
        {'code': '600148', 'name': '长春一东'}, {'code': '000757', 'name': '浩物股份'},
        {'code': '002765', 'name': '蓝黛科技'}, {'code': '603730', 'name': '岱美股份'},
    ]},
    '锂电池': {'name': '锂电池', 'stocks': [
        {'code': '300750', 'name': '宁德时代'}, {'code': '002466', 'name': '天齐锂业'},
        {'code': '002460', 'name': '赣锋锂业'}, {'code': '300014', 'name': '亿纬锂能'},
        {'code': '002812', 'name': '恩捷股份'}, {'code': '300568', 'name': '星源材质'},
        {'code': '002709', 'name': '天赐材料'}, {'code': '002850', 'name': '科达利'},
        {'code': '002074', 'name': '国轩高科'}, {'code': '300438', 'name': '鹏辉能源'},
        {'code': '688567', 'name': '孚能科技'}, {'code': '300769', 'name': '德方纳米'},
        {'code': '688116', 'name': '天奈科技'}, {'code': '301358', 'name': '湖南裕能'},
        {'code': '688779', 'name': '长远锂科'}, {'code': '300073', 'name': '当升科技'},
        {'code': '300035', 'name': '中科电气'}, {'code': '002759', 'name': '天际股份'},
        {'code': '301349', 'name': '信德新材'}, {'code': '688392', 'name': '骄成超声'},
        {'code': '300457', 'name': '赢合科技'}, {'code': '300450', 'name': '先导智能'},
    ]},
    '家电': {'name': '家电', 'stocks': [
        {'code': '000333', 'name': '美的集团'}, {'code': '000651', 'name': '格力电器'},
        {'code': '600690', 'name': '海尔智家'}, {'code': '002032', 'name': '苏泊尔'},
        {'code': '002050', 'name': '三花智控'}, {'code': '000100', 'name': 'TCL科技'},
        {'code': '000921', 'name': '海信家电'}, {'code': '002242', 'name': '九阳股份'},
        {'code': '002508', 'name': '老板电器'}, {'code': '688169', 'name': '石头科技'},
        {'code': '603486', 'name': '科沃斯'}, {'code': '300894', 'name': '火星人'},
        {'code': '002959', 'name': '小熊电器'}, {'code': '002242', 'name': '九阳股份'},
        {'code': '002035', 'name': '华帝股份'}, {'code': '300160', 'name': '秀强股份'},
        {'code': '000404', 'name': '长虹华意'}, {'code': '600854', 'name': '春兰股份'},
        {'code': '603515', 'name': '欧普照明'}, {'code': '002403', 'name': '爱仕达'},
    ]},
    '软件服务': {'name': '软件服务', 'stocks': [
        {'code': '688111', 'name': '金山办公'}, {'code': '600570', 'name': '恒生电子'},
        {'code': '300454', 'name': '深信服'}, {'code': '300496', 'name': '中科创达'},
        {'code': '002405', 'name': '四维图新'}, {'code': '002368', 'name': '太极股份'},
        {'code': '600536', 'name': '中国软件'}, {'code': '603927', 'name': '中科软'},
        {'code': '002439', 'name': '启明星辰'}, {'code': '300674', 'name': '宇信科技'},
        {'code': '300033', 'name': '同花顺'}, {'code': '300803', 'name': '指南针'},
        {'code': '688318', 'name': '财富趋势'}, {'code': '300188', 'name': '美亚柏科'},
        {'code': '002230', 'name': '科大讯飞'}, {'code': '300624', 'name': '万兴科技'},
        {'code': '688095', 'name': '福昕软件'}, {'code': '300687', 'name': '赛意信息'},
        {'code': '300454', 'name': '深信服'}, {'code': '002410', 'name': '广联达'},
        {'code': '300532', 'name': '今天国际'}, {'code': '300525', 'name': '博思软件'},
    ]},
    '传媒/游戏': {'name': '传媒/游戏', 'stocks': [
        {'code': '300418', 'name': '昆仑万维'}, {'code': '002555', 'name': '三七互娱'},
        {'code': '002602', 'name': '世纪华通'}, {'code': '603444', 'name': '吉比特'},
        {'code': '002624', 'name': '完美世界'}, {'code': '002517', 'name': '恺英网络'},
        {'code': '300113', 'name': '顺网科技'}, {'code': '002558', 'name': '巨人网络'},
        {'code': '300315', 'name': '掌趣科技'}, {'code': '603258', 'name': '电魂网络'},
        {'code': '300251', 'name': '光线传媒'}, {'code': '300413', 'name': '芒果超媒'},
        {'code': '600977', 'name': '中国电影'}, {'code': '002739', 'name': '万达电影'},
        {'code': '002174', 'name': '游族网络'}, {'code': '300533', 'name': '冰川网络'},
        {'code': '300058', 'name': '蓝色光标'}, {'code': '300364', 'name': '中文在线'},
        {'code': '601928', 'name': '凤凰传媒'}, {'code': '601098', 'name': '中南传媒'},
        {'code': '600373', 'name': '中文传媒'}, {'code': '600637', 'name': '东方明珠'},
        {'code': '300624', 'name': '万兴科技'}, {'code': '300418', 'name': '昆仑万维'},
    ]},
    '沪深300权重': {'name': '沪深300权重', 'stocks': [
        {'code': '600519', 'name': '贵州茅台'}, {'code': '300750', 'name': '宁德时代'},
        {'code': '000333', 'name': '美的集团'}, {'code': '601318', 'name': '中国平安'},
        {'code': '600036', 'name': '招商银行'}, {'code': '000858', 'name': '五粮液'},
        {'code': '002594', 'name': '比亚迪'}, {'code': '600900', 'name': '长江电力'},
        {'code': '601012', 'name': '隆基绿能'}, {'code': '300059', 'name': '东方财富'},
        {'code': '600276', 'name': '恒瑞医药'}, {'code': '601398', 'name': '工商银行'},
        {'code': '688981', 'name': '中芯国际'}, {'code': '002475', 'name': '立讯精密'},
        {'code': '000568', 'name': '泸州老窖'}, {'code': '300760', 'name': '迈瑞医疗'},
        {'code': '601899', 'name': '紫金矿业'}, {'code': '600809', 'name': '山西汾酒'},
        {'code': '002415', 'name': '海康威视'}, {'code': '603259', 'name': '药明康德'},
        {'code': '601166', 'name': '兴业银行'}, {'code': '600030', 'name': '中信证券'},
        {'code': '600887', 'name': '伊利股份'}, {'code': '000001', 'name': '平安银行'},
        {'code': '002714', 'name': '牧原股份'}, {'code': '300124', 'name': '汇川技术'},
        {'code': '601328', 'name': '交通银行'}, {'code': '601088', 'name': '中国神华'},
        {'code': '000002', 'name': '万科A'}, {'code': '300308', 'name': '中际旭创'},
        {'code': '600585', 'name': '海螺水泥'}, {'code': '600941', 'name': '中国移动'},
        {'code': '688111', 'name': '金山办公'}, {'code': '603501', 'name': '韦尔股份'},
        {'code': '300015', 'name': '爱尔眼科'}, {'code': '600309', 'name': '万华化学'},
        {'code': '601985', 'name': '中国核电'}, {'code': '600436', 'name': '片仔癀'},
        {'code': '000725', 'name': '京东方A'}, {'code': '600690', 'name': '海尔智家'},
    ]},
}


# ==================== 加载与保存 ====================

def _load_cache():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                total = sum(len(s.get('stocks', [])) for s in data.values())
                if total > 5000:
                    return data
        except:
            pass
    return None

def _save_cache(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open(LAST_UPDATE_FILE, 'w') as f:
        f.write(datetime.now().isoformat())
    total = sum(len(s.get('stocks', [])) for s in data.values())
    print(f"[板块] 缓存保存: {len(data)}个板块, {total}只成分股")


# ==================== 数据获取 ====================

def _get_all_stocks_akshare():
    """从AKShare获取全量A股列表"""
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        if df is None or len(df) == 0:
            return None
        
        stocks = []
        for _, row in df.iterrows():
            code = str(row.get('code', '') or row.get('代码', '')).strip().zfill(6)
            name = str(row.get('name', '') or row.get('名称', '')).strip()
            if code and name:
                stocks.append({'code': code, 'name': name})
        return stocks
    except Exception as e:
        print(f"[板块] AKShare获取失败: {e}")
    return None


def _classify_by_exchange(stocks):
    """按交易所分组"""
    groups = {
        '沪市主板': [], '科创板': [], '深市主板': [], '创业板': [], '北交所': [],
    }
    for s in stocks:
        c = s['code']
        if c.startswith('688'):
            groups['科创板'].append(s)
        elif c.startswith('6'):
            groups['沪市主板'].append(s)
        elif c.startswith('30'):
            groups['创业板'].append(s)
        elif c.startswith('00'):
            groups['深市主板'].append(s)
        elif c.startswith('8'):
            groups['北交所'].append(s)
    
    return {k: {'name': k, 'stocks': v} for k, v in groups.items() if v}


def refresh_sectors(force_update=False):
    """刷新板块数据"""
    
    # 缓存足够时直接返回
    if not force_update:
        cached = _load_cache()
        if cached:
            return cached
    
    # 1. 获取全量A股
    stocks = _get_all_stocks_akshare()
    if not stocks:
        # 备用：组装默认数据
        total = sum(len(s.get('stocks', [])) for s in DEFAULT_SECTORS.values())
        exchange_default = _classify_by_exchange(
            sum([s['stocks'] for s in DEFAULT_SECTORS.values()], [])
        )
        result = {'全部A股': {'name': '全部A股', 'stocks': sum([s['stocks'] for s in DEFAULT_SECTORS.values()], [])}}
        result.update(DEFAULT_SECTORS)
        result.update(exchange_default)
        print(f"[板块] 使用默认数据: {len(result)}个板块")
        _save_cache(result)
        return result
    
    # 2. 构建: 全部A股 + 交易所分组 + 热门行业板块
    result = {}
    
    # 全部A股 (5517只 - 100%覆盖)
    result['全部A股'] = {'name': '全部A股', 'stocks': stocks}
    
    # 交易所分组 (100%覆盖)
    exchange_groups = _classify_by_exchange(stocks)
    result.update(exchange_groups)
    
    # 热门行业板块 (仅保留在A股列表中的股票)
    stock_codes = {s['code'] for s in stocks}
    for sector_name, sector_data in DEFAULT_SECTORS.items():
        valid_stocks = [s for s in sector_data['stocks'] if s['code'] in stock_codes]
        if valid_stocks:
            result[sector_name] = {'name': sector_name, 'stocks': valid_stocks}
    
    _save_cache(result)
    return result


def update_sectors_from_network():
    """强制网络更新"""
    return bool(refresh_sectors(force_update=True))


# ==================== 公开API ====================

_SECTORS = None

def _get_sectors():
    global _SECTORS
    if _SECTORS is None:
        _SECTORS = refresh_sectors()
    return _SECTORS

def get_sector_names():
    return sorted(_get_sectors().keys())

def get_sector_stocks(sector_name):
    sector = _get_sectors().get(sector_name)
    return sector['stocks'] if sector else []

def search_sectors(keyword):
    keyword = keyword.lower()
    return [name for name in get_sector_names() if keyword in name.lower()]

def get_all_sectors_with_stocks():
    return {name: sector for name, sector in _get_sectors().items()}

def get_last_update_time():
    if os.path.exists(LAST_UPDATE_FILE):
        with open(LAST_UPDATE_FILE) as f:
            return f.read().strip()
    return None
