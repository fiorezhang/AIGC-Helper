# -*- coding: UTF-8 -*-

import requests
import re

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


def translateHelsinkiC2E(con):
    from transformers import MarianMTModel, MarianTokenizer
    tokenizer = MarianTokenizer.from_pretrained("./chatModels/opus-mt-zh-en")
    model = MarianMTModel.from_pretrained("./chatModels/opus-mt-zh-en")

    texts = con.split('\n')
    output = ""

    try:
        for text in texts:
            print(text)
            encoded_text = tokenizer.encode(text, return_tensors='pt')
            translation = model.generate(encoded_text)
            decoded_translation = tokenizer.decode(translation[0], skip_special_tokens=True)
            print(decoded_translation)
            if output == "":
                output = decoded_translation
            else:
                output = output + '\n' + decoded_translation
    except:
        pass

    return output

def translateHelsinkiE2C(con):
    from transformers import MarianMTModel, MarianTokenizer
    tokenizer = MarianTokenizer.from_pretrained("./chatModels/opus-mt-en-zh")
    model = MarianMTModel.from_pretrained("./chatModels/opus-mt-en-zh")

    texts = con.split('\n')
    output = ""

    try:
        for text in texts:
            print(text)
            encoded_text = tokenizer.encode(text, return_tensors='pt')
            translation = model.generate(encoded_text)
            decoded_translation = tokenizer.decode(translation[0], skip_special_tokens=True)
            print(decoded_translation)
            if output == "":
                output = decoded_translation
            else:
                output = output + '\n' + decoded_translation
    except:
        pass

    return output

if __name__ == '__main__':
    '''
    con = "起来，不愿做奴隶的人们，把我们的血肉，筑成我们新的长城。中华民族，到了最危险的时候。每个人被迫着发出最后的吼声。"
    res = translateYouDaoC2E(con)
    print('在线翻译结果：\n', res)
    res = translateHelsinkiC2E(con)
    print('离线翻译结果：\n', res)
    '''
       
    con = "Do you know messi? As an AI language model, I don't have personal knowledge about Messi like humans do. However, through the available data and information in my database, Lionel Andrés 'Leo' Messi is a professional Argentinian footballer who plays for FC Barcelona as well as Argentina national team where he has won Ballon d’Or five times which makes him one of the best players ever lived on earth according to many football lovers."
    con = "Stable Diffusion is an exciting and increasingly popular AI generative art tool that takes simple text prompts and creates incredible images seemingly from nothing. While there are controversies over where it gets its inspiration from, it's proven to be a great tool for generating character model art for RPGs, wall art for those unable to afford artist commissions, and cool concept art to inspire writers and other creative endeavors.\nIf you're interested in exploring how to use Stable Diffusion on a PC, here's our guide on getting started.\nIf you're more of an Apple fan, we also have a guide on how to run Stable Diffusion on a Mac, instead."
    con = "Certainly an Englishman, it was more doubtful whether Phileas Fogg was a Londoner. He was never seen on Change, nor at the Bank, nor in the counting-rooms of the ‘City’; no ships ever came into London docks of which he was the owner; he had no public employment; he had never been entered at any of the Inns of Court, either at the Temple, or Lincoln's Inn, or Gray's Inn; nor had his voice ever resounded in the Court of Chancery, or in the Exchequer, or the Queen's Bench, or the Ecclesiastical Courts. He certainly was not a manufacturer; nor was he a merchant or a gentleman farmer. His name was strange to the scientific and learned societies, and he never was known to take part in the sage deliberations of the Royal Institution or the London Institution, the Artisan's Association, or the Institution of Arts and Sciences. He belonged, in fact, to none of the numerous societies which swarm in the English capital, from the Harmonic to that of the Entomologists, founded mainly for the purpose of abolishing pernicious insects."
    print('\n\n原始段落：\n', con)
    res = translateYouDaoE2C(con)
    print('\n\n在线翻译结果：\n', res)
    res = translateHelsinkiE2C(con)
    print('\n\n离线翻译结果：\n', res)