# -*- coding: UTF-8 -*-

import requests
import os
from PIL import Image, ImageOps
from pptx import Presentation
from pptx.util import Inches, Pt, Cm

from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE
import time

#EMU to CM
img_unit_base = 360000

'''
ppt slides template
0 Title (presentation title slide)
1 Title and Content
2 Section Header (sometimes called Segue)
3 Two Content (side by side bullet textboxes)
4 Comparison (same but additional title for each side by side content box)
5 Title Only
6 Blank
7 Content with Caption
8 Picture with Caption
'''

def create_new_ppt_by_name(file_name_t):
    prs = Presentation(file_name_t)   # creat a new ppt
    return prs

def create_new_ppt():
    prs = Presentation()   # creat a new ppt
    return prs

def save_ppt(prs):
    curr_time = (str)((int)(time.time()))
    file_path = r'C:\ed\GPT\AIGC-Helper\\'
    file_name = 'test_' + curr_time + '.pptx'
    #print(curr_time)
    prs.save(file_path + file_name)

def check_one_slide_layout(slide):
    for shape in slide.placeholders:
        phf = shape.placeholder_format
        print(shape.placeholder_format)
        print(phf.idx)
        print(shape.name)
        print(phf.type)
        print(f"{phf.idx}--{shape.name}--{phf.type}")
        #shape.text = f"{phf.idx}--{shape.name}--{phf.type}"

def get_one_slide_layout(slide, idx_a, name_a):
    cc = 0
    for shape in slide.placeholders:
        phf = shape.placeholder_format
        idx_a.append(phf.idx)
        name_a.append(shape.name)
        cc+=1
    return cc

def get_slides(presentation):
    slides = presentation.slides
    slide_num = slides.len
    return slides, slide_num

# default is Title only page (5)
def add_one_slide(prs, SLD_LAYOUT_TITLE_AND_CONTENT = 5):
   slide_layout = prs.slide_layouts[SLD_LAYOUT_TITLE_AND_CONTENT]
   slide = prs.slides.add_slide(slide_layout)
   return slide

def get_one_slide(slides_t, slide_index_t):
    return slides_t[slide_index_t]

def add_pic(slide, img, img_left, img_top, img_height):
    img_path = img
    left = Cm(img_left)
    top  = Cm(img_top)
    pic  = slide.shapes.add_picture(img_path, left, top, height=Cm(img_height))

def insert_pic(slide, index, img):
    placeholder = slide.placeholders[index]
    pic = placeholder.insert_picture(img)

def add_title(slide, title_text):
    #check_one_slide_layout(slide)
    title = slide.shapes.title
    title.text = title_text
    #print('add_title\t' + title_text)

def add_textbox(slide, index_t, text_t):
    tb_top = Cm(5.6)
    tb_left = Cm(1)
    tb_w = Cm(24)
    tb_h = Cm(10)
    
    text_box = slide.shapes.add_textbox(tb_left, tb_top, tb_w, tb_h)
    text_body = text_box.text_frame
   
    print('before filled\t', text_body.margin_bottom, text_body.margin_left, text_body.margin_right, text_body.margin_top, text_body.vertical_anchor)    

    text_body.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    text_body.word_wrap = True
    text_body.text = text_t
    text_body.vertical_anchor = MSO_ANCHOR.MIDDLE

    cc = 0
    while(cc < 20):
        p = text_body.add_paragraph()
        run = p.add_run()
        run.text = "带圆点的符号2"
        cc += 1
    print('after filled\t', text_body.margin_bottom, text_body.margin_left, text_body.margin_right, text_body.margin_top, text_body.vertical_anchor)    


def add_text(slide, index_t, text_t):
    text_body = slide.placeholders[index_t].text_frame
    text_body.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    text_body.word_wrap = True
    text_body.text = text_t
    #text_body.fit_text(max_size=20)
    #text_body.fit_text()

if __name__ == '__main__':
    print(OK)