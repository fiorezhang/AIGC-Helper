# -*- coding: UTF-8 -*-

import requests

def ifWithChinese(string):
    for char in string:
        if '\u4e00' <= char <= '\u9fa5':
            return True
    return False

def translateYouDaoC2E(con):
    if ifWithChinese(con):
        try:
            data = {'doctype': 'json',
                    type: 'ZH_CN2EN',
                    'i': con}
            r = requests.get("https://fanyi.youdao.com/translate", params=data)
            res_json = r.json()
            res_d = res_json['translateResult'][0]
            tgt = []
            for i in range(len(res_d)):
                tgt.append(res_d[i]['tgt'])
            return ''.join(tgt)
        except Exception as e:
            print('Translate failed: ', e)
            return ""
    else:
        return con

def translateYouDaoE2C(con):
    if not ifWithChinese(con):
        try:
            data = {'doctype': 'json',
                    type: 'ZH_EN2CN',
                    'i': con}
            r = requests.get("https://fanyi.youdao.com/translate", params=data)
            res_json = r.json()
            res_d = res_json['translateResult'][0]
            tgt = []
            for i in range(len(res_d)):
                tgt.append(res_d[i]['tgt'])
            return ''.join(tgt)
        except Exception as e:
            print('Translate failed: ', e)
            return ""
    else:
        return con

if __name__ == '__main__':
    con = "Do you know messi? As an AI language model, I don't have personal knowledge about Messi like humans do. However, through the available data and information in my database, Lionel Andrés 'Leo' Messi is a professional Argentinian footballer who plays for FC Barcelona as well as Argentina national team where he has won Ballon d’Or five times which makes him one of the best players ever lived on earth according to many football lovers."
    res = translateYouDaoE2C(con)
    print('翻译结果：\n', res)