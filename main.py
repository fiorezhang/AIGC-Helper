# -*- coding: UTF-8 -*-

# ==== IMPORT ====
# ---- UI related libraries 
import tkinter as tk
from tkinter.filedialog import *
#from tkinter.ttk import Progressbar
import ttkbootstrap
from ttkbootstrap.constants import *
from PIL import ImageTk,Image

# ---- utils
import os
import time
import random
import queue
import threading
import numpy as np
import win32clipboard
from io import BytesIO
import subprocess
import cv2

# ---- translate between English and Chinese, leverage YouDao online service
from translate import translateYouDaoC2E, translateYouDaoE2C

# ---- redirect std stream to avoid "pyinstaller -w" issue(stdout/stderr miss handle while no command line), MUST before SD functions' initialization
import stdredirect
mystd = stdredirect.myStdout()

# ---- import SD functions
from stablediffusionov import downloadModel, compileModel, generateImage

# ==== GLOBAL MACROS ====
# version info
VERSION = 'v4.2'

# whether use youdao transfer
TRANSLATE = False

# resolutions
RES_ORIGINAL = 512
RES_PREVIEW  = 256
RES_GALLERY  = 48
RES_WORKING  = 192
RES_MASK     = 64

# ==== UI Framework ====
class UiHelper():
    # ====================================================================
    # ---- initialize the UI elements and variables, crerate subprocess
    def __init__(self):
        # ====== create main window with ttkbootstrap style
        style = ttkbootstrap.Style(theme='superhero') # DARK- solar, superhero, darkly, cyborg, vapor; LIGHT- cosmo, flatly, journal, litera, lumen, minty, pulse, sandstone, united, yeti, morph, simplex, cerculean
        self.root = style.master
        # set window size and position
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        app_width = 400
        app_height = 720#screen_height-80
        self.root.geometry(str(app_width)+'x'+str(app_height)+'+'+str(screen_width-app_width)+'+0') # size, start position
        print(str(app_width)+'x'+str(app_height)+'+'+str(screen_width-app_width)+'+0')
        # set window attibutes
        self.root.resizable(False, False) # resize
        self.root.overrideredirect(False) # title lane
        self.root.title('AIGC Helper ' + VERSION)
        self.root.attributes("-topmost",0) # top window
        self.root.iconphoto(True, ImageTk.PhotoImage(file="ui/ui-blank.png")) # icon

        # ====== create notebook panels for different sub-functions
        self.notebook = ttkbootstrap.Notebook(self.root)
        self.chatFrame = ttkbootstrap.Frame()
        self.drawFrame = ttkbootstrap.Frame()
        self.editFrame = ttkbootstrap.Frame()
        self.configFrame = ttkbootstrap.Frame()
        self.notebook.add(self.chatFrame, text="Chat")
        self.notebook.add(self.drawFrame, text="Draw")
        self.notebook.add(self.editFrame, text="Edit")
        self.notebook.add(self.configFrame, text="Config")
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # ====== draw image ====== create multiple Frames
        self.drawPreviewFrame = ttkbootstrap.Frame(self.drawFrame, width=390, height=270)
        self.drawSettingFrame = ttkbootstrap.Frame(self.drawFrame, width=190, height=230)
        self.drawWorkingFrame = ttkbootstrap.Frame(self.drawFrame, width=200, height=230)
        self.drawPromptFrame = ttkbootstrap.Frame(self.drawFrame, width=390, height=200)
        
        self.drawPreviewFrame.grid(row=0, column=0, columnspan=2)
        self.drawPreviewFrame.grid_propagate(False)
        self.drawSettingFrame.grid(row=2, column=0)
        self.drawSettingFrame.grid_propagate(False)             
        self.drawWorkingFrame.grid(row=2, column=1)
        self.drawWorkingFrame.grid_propagate(False)
        self.drawPromptFrame.grid(row=3, column=0, columnspan=2)
        self.drawPromptFrame.grid_propagate(False)

        # ------ locate main canvas in preview Frame
        self.drawPreviewImage = ImageTk.PhotoImage(Image.open('ui/ui-welcome.png').resize((RES_PREVIEW, RES_PREVIEW)))
        self.drawPreviewLabel = ttkbootstrap.Label(self.drawPreviewFrame, image=self.drawPreviewImage)
        self.drawPreviewLabel.grid(row=0, column=0, rowspan=8, padx=2, pady=2)
        
        self.drawPreviewLabel.bind("<Double-Button-1>", self.drawCopyToClipboard)

        # ------ locate gallery image in gallery Frame
        self.listGeneratedImages = []   #generated images, can be many
        self.listDrawGalleryImages = []   #generated canvas for gallery, fixed
        self.vDrawSelectedImageIndex = tk.IntVar()  # current which image is selected in <imageRadiobutton>
        self.vDrawSelectedImageIndex.set(0)
        
        # max images in gallery
        self.maxGalleryImageCount = 8
        self.countImagePerRow = 2
        for indexImage in range(self.maxGalleryImageCount):
            galleryImage = ImageTk.PhotoImage(Image.open('ui/ui-blank.png').resize((RES_GALLERY, RES_GALLERY)))
            self.drawGalleryRadiobutton = tk.Radiobutton(self.drawPreviewFrame, image=galleryImage, variable=self.vDrawSelectedImageIndex, value=indexImage, width=RES_GALLERY, height=RES_GALLERY, indicatoron=False)
            self.drawGalleryRadiobutton.grid(row=0+int(indexImage/self.countImagePerRow), column=1+int(indexImage%self.countImagePerRow), padx=2, pady=2)
            self.listDrawGalleryImages.append({'button':self.drawGalleryRadiobutton, 'image':galleryImage})

        # ------ locate canvas(working in progress) image in canvas Frame
        self.drawWorkingCanvas = ttkbootstrap.Canvas(self.drawWorkingFrame, width=RES_WORKING, height=RES_WORKING)
        self.drawWorkingImage = ImageTk.PhotoImage(Image.open('ui/ui-blank.png').resize((RES_WORKING, RES_WORKING)))
        self.drawWorkingCanvas.create_image(0, 0, anchor=NW, image=self.drawWorkingImage)
        self.drawWorkingCanvas.grid(row=2+round(self.maxGalleryImageCount/self.countImagePerRow), column=0, columnspan=self.countImagePerRow, padx=2, pady=2)

        self.drawWorkingCanvas.bind('<Button-1>', self.drawGetMaskStartInfo)
        self.drawWorkingCanvas.bind('<B1-Motion>', self.drawGetMaskMidInfo)
        self.drawWorkingCanvas.bind('<ButtonRelease-1>', self.drawGetMaskEndInfo)

      # ------ locate settings in setting Frame     
        self.drawImportLabel = ttkbootstrap.Label(self.drawSettingFrame, text='Import / load image') 
        self.drawImportButton = ttkbootstrap.Button(self.drawSettingFrame, text='Import', width="5", command=self.drawImportCallback, bootstyle=(INFO, OUTLINE))
        self.drawLoadButton = ttkbootstrap.Button(self.drawSettingFrame, text='Load', width="5", command=self.drawLoadCallback, bootstyle=(INFO, OUTLINE))
        self.drawResetButton = ttkbootstrap.Button(self.drawSettingFrame, text='Reset', width="5", command=self.drawResetCallback, bootstyle=(INFO, OUTLINE))
        self.drawMaskLabel = ttkbootstrap.Label(self.drawSettingFrame, text='Clear mask') 
        self.drawClearMaskButton = ttkbootstrap.Button(self.drawSettingFrame, text='Clear', width="5", command=self.drawClearMaskCallback, bootstyle=(INFO, OUTLINE))
        self.drawBackMaskButton = ttkbootstrap.Button(self.drawSettingFrame, text='Back', width="5", command=self.drawBackMaskCallback, bootstyle=(INFO, OUTLINE))

        self.drawNoiseLabel = ttkbootstrap.Label(self.drawSettingFrame, text='Variation Ratio: 0.1-0.9') 
        self.drawNoiseStatusLabel = ttkbootstrap.Label(self.drawSettingFrame, text='', width=4) 
        self.drawNoiseScale = ttkbootstrap.Scale(self.drawSettingFrame, from_=1, to=5, orient=HORIZONTAL, command=self.drawNoiseScaleCallback)
        self.drawNoiseScale.set(3)
        self.drawBatchLabel = ttkbootstrap.Label(self.drawSettingFrame, text='Batch Count: 1 - 4') 
        self.drawBatchStatusLabel = ttkbootstrap.Label(self.drawSettingFrame, text='', width=4)
        self.drawBatchScale = ttkbootstrap.Scale(self.drawSettingFrame, from_=1, to=4, orient=HORIZONTAL, command=self.drawBatchScaleCallback)
        self.drawBatchScale.set(1)        
        
        self.drawImportLabel.grid(row=0, column=0, columnspan=3, padx=2, pady=2)
        self.drawImportButton.grid(row=1, column=0, padx=2, pady=2)
        self.drawLoadButton.grid(row=1, column=1, padx=2, pady=2)
        self.drawResetButton.grid(row=1, column=2, padx=2, pady=2)
        self.drawMaskLabel.grid(row=2, column=0, columnspan=3, padx=2, pady=2)
        self.drawClearMaskButton.grid(row=3, column=0, padx=2, pady=2)
        self.drawBackMaskButton.grid(row=3, column=1, padx=2, pady=2)
        self.drawNoiseLabel.grid(row=4, column=0, columnspan=3, padx=2, pady=2)
        self.drawNoiseScale.grid(row=5, column=0, columnspan=2, padx=2, pady=2)
        self.drawNoiseStatusLabel.grid(row=5, column=2, padx=2, pady=2)
        self.drawBatchLabel.grid(row=6, column=0, columnspan=3, padx=2, pady=2)
        self.drawBatchScale.grid(row=7, column=0, columnspan=2, padx=2, pady=2)
        self.drawBatchStatusLabel.grid(row=7, column=2, padx=2, pady=2)
        
        # ------ locate user input in prompt Frame
        self.drawPromptText = ttkbootstrap.Text(self.drawPromptFrame, width=50, height=3)    
        self.drawInitializeButton = ttkbootstrap.Button(self.drawPromptFrame, text='Initialize', width="10", command=self.drawInitializeCallback, bootstyle=(PRIMARY, OUTLINE))
        self.drawGenerateButton = ttkbootstrap.Button(self.drawPromptFrame, text='Generate', width="10", command=self.drawGenerateCallback, bootstyle=(PRIMARY, OUTLINE))
        self.drawGenerateProgressbar = ttkbootstrap.Progressbar(self.drawPromptFrame, length=200, style='success.Striped.Horizontal.TProgressbar')
        self.drawGenerateAllProgressbar = ttkbootstrap.Progressbar(self.drawPromptFrame, length=200, style='success.Striped.Horizontal.TProgressbar')

        self.drawPromptText.grid(row=0, column=0, columnspan=2, padx=2, pady=2)
        self.drawInitializeButton.grid(row=1, column=0, padx=2, pady=2)
        self.drawGenerateButton.grid(row=2, column=0, padx=2, pady=2)
        self.drawGenerateProgressbar.grid(row=1, column=1, padx=2, pady=2)
        self.drawGenerateAllProgressbar.grid(row=2, column=1, padx=2, pady=2)
                        
        self.isGenerating = False

        # ====== edit image ====== create multiple Frames
        self.editPreviewFrame = ttkbootstrap.Frame(self.editFrame, width=390, height=270)
        self.editSettingFrame = ttkbootstrap.Frame(self.editFrame, width=190, height=230)
        self.editWorkingFrame = ttkbootstrap.Frame(self.editFrame, width=200, height=230)
        self.editZoomFrame = ttkbootstrap.Frame(self.editFrame, width=390, height=200)
        
        self.editPreviewFrame.grid(row=0, column=0, columnspan=2)
        self.editPreviewFrame.grid_propagate(False)
        self.editSettingFrame.grid(row=2, column=0)
        self.editSettingFrame.grid_propagate(False)             
        self.editWorkingFrame.grid(row=2, column=1)
        self.editWorkingFrame.grid_propagate(False)
        self.editZoomFrame.grid(row=3, column=0, columnspan=2)
        self.editZoomFrame.grid_propagate(False)
        
        # ------ locate main canvas in preview Frame
        self.editPreviewImage = ImageTk.PhotoImage(Image.open('ui/ui-welcome.png').resize((RES_PREVIEW, RES_PREVIEW)))
        self.editPreviewLabel = ttkbootstrap.Label(self.editPreviewFrame, image=self.editPreviewImage)
        self.editPreviewLabel.grid(row=0, column=0, rowspan=8, padx=2, pady=2)
        
        self.editPreviewLabel.bind("<Double-Button-1>", self.editCopyToClipboard)
        
        # ------ locate gallery image in gallery Frame 
        #self.listGeneratedImages = []   #generated images, can be many   ---- reuse the same gallery to bridge the workflow between "draw" and "edit"
        self.listEditGalleryImages = []   #generated canvas for gallery, fixed
        self.vEditSelectedImageIndex = tk.IntVar()  # current which image is selected in <imageRadiobutton>
        self.vEditSelectedImageIndex.set(0)
        
        # max images in gallery ---- keep sync with draw frame
        #self.maxGalleryImageCount = 10
        #self.countImagePerRow = 5
        for indexImage in range(self.maxGalleryImageCount):
            galleryImage = ImageTk.PhotoImage(Image.open('ui/ui-blank.png').resize((RES_GALLERY, RES_GALLERY)))
            self.editGalleryRadiobutton = tk.Radiobutton(self.editPreviewFrame, image=galleryImage, variable=self.vEditSelectedImageIndex, value=indexImage, width=RES_GALLERY, height=RES_GALLERY, indicatoron=False)
            self.editGalleryRadiobutton.grid(row=0+int(indexImage/self.countImagePerRow), column=1+int(indexImage%self.countImagePerRow), padx=2, pady=2)
            self.listEditGalleryImages.append({'button':self.editGalleryRadiobutton, 'image':galleryImage})
        
        # ------ locate canvas(working in progress) image in canvas Frame
        self.editWorkingCanvas = ttkbootstrap.Canvas(self.editWorkingFrame, width=RES_WORKING, height=RES_WORKING)
        self.editWorkingImage = ImageTk.PhotoImage(Image.open('ui/ui-blank.png').resize((RES_WORKING, RES_WORKING)))
        self.editWorkingCanvas.create_image(0, 0, anchor=NW, image=self.editWorkingImage)
        self.editWorkingCanvas.grid(row=2+round(self.maxGalleryImageCount/self.countImagePerRow), column=0, columnspan=self.countImagePerRow, padx=2, pady=2)

        self.editWorkingCanvas.bind('<Button-1>', self.editGetRegionStartInfo)
        self.editWorkingCanvas.bind('<B1-Motion>', self.editGetRegionMidInfo)
        self.editWorkingCanvas.bind('<ButtonRelease-1>', self.editGetRegionEndInfo)

        # ------ locate settings in setting Frame     
        self.editImportLabel = ttkbootstrap.Label(self.editSettingFrame, text='Import / load image') 
        self.editImportButton = ttkbootstrap.Button(self.editSettingFrame, text='Import', width="5", command=self.editImportCallback, bootstyle=(INFO, OUTLINE))
        self.editLoadButton = ttkbootstrap.Button(self.editSettingFrame, text='Load', width="5", command=self.editLoadCallback, bootstyle=(INFO, OUTLINE))
        self.editResetButton = ttkbootstrap.Button(self.editSettingFrame, text='Reset', width="5", command=self.editResetCallback, bootstyle=(INFO, OUTLINE))
        self.editSettingNullFrame = ttkbootstrap.Frame(self.editSettingFrame, width=30, height=60)
        self.editMatLabel = ttkbootstrap.Label(self.editSettingFrame, text='Cut/Mat from region') 
        self.editCutButton = ttkbootstrap.Button(self.editSettingFrame, text='Cut', width="5", command=self.editCutCallback, bootstyle=(PRIMARY, OUTLINE))
        self.editMatButton = ttkbootstrap.Button(self.editSettingFrame, text='Mat', width="5", command=self.editMatCallback, bootstyle=(PRIMARY, OUTLINE))
        
        self.editImportLabel.grid(row=0, column=0, columnspan=3, padx=2, pady=2)
        self.editImportButton.grid(row=1, column=0, padx=2, pady=2)
        self.editLoadButton.grid(row=1, column=1, padx=2, pady=2)
        self.editResetButton.grid(row=1, column=2, padx=2, pady=2)
        self.editSettingNullFrame.grid(row=2, column=0, padx=2, pady=2)
        self.editSettingNullFrame.grid_propagate(False)
        self.editMatLabel.grid(row=3, column=0, columnspan=3, padx=2, pady=2)
        self.editCutButton.grid(row=4, column=0, padx=2, pady=2)
        self.editMatButton.grid(row=4, column=1, padx=2, pady=2)
        
        # ------ locate scale functions in zoom Frame
        self.inputWidth = 0
        self.inputHeight = 0
        self.outputWidth = 0
        self.outputHeight = 0
        
        self.editZoomNullFrame = ttkbootstrap.Frame(self.editZoomFrame, width=30, height=10)
        self.editResizeLabel = ttkbootstrap.Label(self.editZoomFrame, text='Resize image') 
        self.editResizeButton = ttkbootstrap.Button(self.editZoomFrame, text='Resize', width="10", command=self.editResizeCallback, bootstyle=(PRIMARY, OUTLINE))
        self.editWidthLabel = ttkbootstrap.Label(self.editZoomFrame, text='Width', width=10, bootstyle="inverse-secondary")
        self.editHeightLabel = ttkbootstrap.Label(self.editZoomFrame, text='Height', width=10, bootstyle="inverse-secondary")
        self.editInputLabel = ttkbootstrap.Label(self.editZoomFrame, text='Input', width=10, bootstyle="inverse-secondary")
        self.editInputWidthLabel = ttkbootstrap.Label(self.editZoomFrame, text='', width=10, bootstyle="inverse-info")
        self.editInputHeightLabel = ttkbootstrap.Label(self.editZoomFrame, text='', width=10, bootstyle="inverse-info")
        self.editOutputLabel = ttkbootstrap.Label(self.editZoomFrame, text='Output', width=10, bootstyle="inverse-secondary")
        self.editOutputWidthLabel = ttkbootstrap.Label(self.editZoomFrame, text='', width=10, bootstyle="inverse-success")
        self.editOutputHeightLabel = ttkbootstrap.Label(self.editZoomFrame, text='', width=10, bootstyle="inverse-success")    
        self.editZoomLabel = ttkbootstrap.Label(self.editZoomFrame, text='Scale level: 0.5-2.0') 
        self.editZoomScale = ttkbootstrap.Scale(self.editZoomFrame, from_=1, to=4, orient=HORIZONTAL, command=self.editZoomScaleCallback)
        self.editZoomScale.set(2)
        
        self.editResizeLabel.grid(row=0, column=0, padx=2, pady=2)
        self.editZoomNullFrame.grid(row=0, column=1, rowspan=3, padx=2, pady=2)
        self.editZoomNullFrame.grid_propagate(False)
        self.editWidthLabel.grid(row=0, column=3, padx=2, pady=2)
        self.editHeightLabel.grid(row=0, column=4, padx=2, pady=2)
        self.editResizeButton.grid(row=1, column=0, padx=2, pady=2)
        self.editInputLabel.grid(row=1, column=2, padx=2, pady=2)
        self.editInputWidthLabel.grid(row=1, column=3, padx=2, pady=2)
        self.editInputHeightLabel.grid(row=1, column=4, padx=2, pady=2)
        self.editZoomLabel.grid(row=2, column=0, padx=2, pady=2)
        self.editOutputLabel.grid(row=2, column=2, padx=2, pady=2)
        self.editOutputWidthLabel.grid(row=2, column=3, padx=2, pady=2)
        self.editOutputHeightLabel.grid(row=2, column=4, padx=2, pady=2)        
        self.editZoomScale.grid(row=3, column=0, padx=2, pady=2)
        
        # ====== chat page ====== create multiple Frames
        self.chatOutputFrame = ttkbootstrap.Frame(self.chatFrame, width=270, height=600)
        self.chatHistoryFrame = ttkbootstrap.Frame(self.chatFrame, width=120, height=600)
        self.chatInputFrame = ttkbootstrap.Frame(self.chatFrame, width=390, height=100)
        
        self.chatOutputFrame.grid(row=0, column=0)
        self.chatOutputFrame.grid_propagate(False)
        self.chatOutputFrame.columnconfigure(0, weight=1)
        self.chatOutputFrame.rowconfigure(0, weight=1)
        self.chatHistoryFrame.grid(row=0, column=1)
        self.chatHistoryFrame.grid_propagate(False)             
        self.chatInputFrame.grid(row=1, column=0, columnspan=2)
        self.chatInputFrame.grid_propagate(False)
        self.chatInputFrame.columnconfigure(0, weight=1)
        self.chatInputFrame.rowconfigure(0, weight=1)
        
        # ---- chat output
        self.chatOutputText = ttkbootstrap.Text(self.chatOutputFrame, state=tk.DISABLED) 
        self.chatOutputText.grid(row=0, column=0, sticky='nsew', padx=2, pady=2)
        self.chatOutputText.tag_config('tagNormal', foreground='white')
        self.chatOutputText.tag_config('tagReact', foreground='lightgreen')
        self.chatOutputText.tag_config('tagWarning', foreground='red')
        
        # ---- chat history
        self.chatHistoryLabel = ttkbootstrap.Label(self.chatHistoryFrame, text='Chat History', bootstyle=INFO)
        self.chatHistoryLabel.grid(row=0, column=0, padx=2, pady=2)

        self.listChatRecordStrings = []   # generated output strings, could be many
        self.listChatRecordButtons = []   # buttons of history, fixed
        self.vChatSelectedRecordIndex = tk.IntVar()  # current which image is selected in <imageRadiobutton>
        self.vChatSelectedRecordIndex.set(0)
        
        # max images in gallery ---- keep sync with draw frame
        self.maxChatRecordCount = 8
        for indexRecord in range(self.maxChatRecordCount):
            self.chatRecordRadiobutton = tk.Radiobutton(self.chatHistoryFrame, text="", width=14, height=3, variable=self.vChatSelectedRecordIndex, value=indexRecord, indicatoron=False)
            self.chatRecordRadiobutton.grid(row=1+indexRecord, column=0, padx=2, pady=2)
            self.listChatRecordButtons.append(self.chatRecordRadiobutton)
        
        # ---- chat input
        self.chatInputEntry = ttkbootstrap.Entry(self.chatInputFrame) 
        self.chatInputEntry.grid(row=0, column=0, sticky='ew', padx=2, pady=2)
        self.chatInputEntry.bind("<Return>", self.chatInputEnterCallback)
        self.chatInputEntry.bind("<Up>", self.chatInputUpCallback)        
        
        # ====    locate configurations in config Frame
        # ------ for overall setting
        self.configOverallFrame = ttkbootstrap.Labelframe(self.configFrame, text='OVERALL', width=390, height=200, bootstyle=PRIMARY)
        self.configOverallFrame.grid(row=0, column=0)
        self.configOverallFrame.grid_propagate(False)
        
        self.alwaysTopLabel = ttkbootstrap.Label(self.configOverallFrame, text='Always on top', bootstyle=INFO)
        self.alwaysTopLabel.grid(row=0, column=0, padx=2, pady=2)  
        self.vAlwaysTop = tk.IntVar()
        self.vAlwaysTop.set(0)
        self.alwaysTopCheckbutton = ttkbootstrap.Checkbutton(self.configOverallFrame, text="AlwaysTop", variable=self.vAlwaysTop, width=10, bootstyle="success-round-toggle")
        self.alwaysTopCheckbutton.grid(row=1, column=1, padx=2, pady=2)        
        
        self.autoHideLabel = ttkbootstrap.Label(self.configOverallFrame, text='Auto hide', bootstyle=INFO)
        self.hideIntroLabel = ttkbootstrap.Label(self.configOverallFrame, text='Move mouse to Right edge of screen to wake') 
        self.autoHideLabel.grid(row=2, column=0, padx=2, pady=2)  
        self.hideIntroLabel.grid(row=4, column=1, columnspan=3, padx=2, pady=2)  
        self.vAutoHide = tk.IntVar()
        self.vAutoHide.set(0)
        self.autoHideCheckbutton = ttkbootstrap.Checkbutton(self.configOverallFrame, text="AutoHide", variable=self.vAutoHide, width=10, bootstyle="success-round-toggle")
        self.autoHideCheckbutton.grid(row=3, column=1, padx=2, pady=2)
        
        # ------ for draw image
        self.configDrawFrame = ttkbootstrap.Labelframe(self.configFrame, text='DRAW', width=390, height=200, bootstyle=PRIMARY)
        self.configDrawFrame.grid(row=1, column=0)
        self.configDrawFrame.grid_propagate(False)

        self.generateLabel = ttkbootstrap.Label(self.configDrawFrame, text='Generation Speed', bootstyle=INFO)
        self.generateLabel.grid(row=0, column=0, padx=2, pady=2)  
        self.qualityLabel = ttkbootstrap.Label(self.configDrawFrame, text='Fast<<    >>Quality') 
        self.qualityScale = ttkbootstrap.Scale(self.configDrawFrame, from_=1, to=4, orient=HORIZONTAL, command=self.configQualityScaleCallback)
        self.configQualityStatusLabel = ttkbootstrap.Label(self.configDrawFrame, text='20')
        self.qualityScale.set(2) 
        self.qualityLabel.grid(row=1, column=1, columnspan=2, padx=2, pady=2)
        self.qualityScale.grid(row=2, column=1, columnspan=2, padx=2, pady=2)
        self.configQualityStatusLabel.grid(row=2, column=3, padx=2, pady=2)
        self.timeLabel = ttkbootstrap.Label(self.configDrawFrame, text='Time: ', width=30) #must have, can hide
        #self.timeLabel.grid(row=2, column=0, columnspan=3, padx=2, pady=2)
        
        self.xpuLabel = ttkbootstrap.Label(self.configDrawFrame, text='Select "XPU"', bootstyle=INFO)
        self.xpuLabel.grid(row=3, column=0, padx=2, pady=2)
        
        self.listXpu = [('CPU  ', 0), ('GPU 0', 1), ('GPU 1', 2), ('AUTO', 3)]
        self.vXpu = tk.IntVar()
        self.vXpu.set(3)
        for xpu, num in self.listXpu:
            self.xpuRadiobutton = tk.Radiobutton(self.configDrawFrame, text=xpu, variable=self.vXpu, value=num, width=10, indicatoron=False)
            self.xpuRadiobutton.grid(row=4+int(num/2), column=1+int(num%2), padx=2, pady=2)  

        # ------ for edit image
        self.configEditFrame = ttkbootstrap.Labelframe(self.configFrame, text='EDIT', width=390, height=200, bootstyle=PRIMARY)
        self.configEditFrame.grid(row=2, column=0)
        self.configEditFrame.grid_propagate(False)   

        self.scaleLabel = ttkbootstrap.Label(self.configEditFrame, text='Scale algorithm', bootstyle=INFO)
        self.scaleLabel.grid(row=0, column=0, padx=2, pady=2)
        
        self.listScale = [('BICUBIC', 0), ('LANCZOS', 1)]
        self.vScale = tk.IntVar()
        self.vScale.set(1)
        for scale, num in self.listScale:
            self.scaleRadiobutton = tk.Radiobutton(self.configEditFrame, text=scale, variable=self.vScale, value=num, width=10, indicatoron=False)
            self.scaleRadiobutton.grid(row=1, column=1+num, padx=2, pady=2)          
          
        
        # ======== initialize varialbs and subprocess
        # ------ bind keys to show or hide window
        self.root.bind("<Enter>", self.showWindow)
        self.root.bind("<Leave>", self.hideWindow)
        self.isWorking = False
        self.hideTimer = None
        
        # ------ ensure output folder exists
        if not os.path.exists('output'):
            os.mkdir('output')        
                
        # ------ draw initialize
        # queue for generation tasks    
        self.queueTaskGenerate = queue.Queue()
        # record last XPU selected
        self.lastXpuIndex = -1
        # record last selected image index in gallery
        self.lastDrawGeneratedImageIndex = -1   
        self.lastEditGeneratedImageIndex = -1  
        # local ov pipe instance
        self.localPipe = None
        # main image file path
        self.drawPreviewFile = ""
        # working image file path, "" means no image locked in working
        self.drawWorkingFile = ""        
        # mask coordination
        self.drawMaskStartX = 0
        self.drawMaskStartY = 0
        self.drawMaskMidX   = 0
        self.drawMaskMidY   = 0
        self.drawMaskEndX   = 0
        self.drawMaskEndY   = 0
        self.listDrawMaskRect = []
        # call generation subprocess (with after method)
        self.asyncLoopGenerate()
        
        # ------ edit initialize
        self.editRegionRect = {"startX": 1, "startY": 1, "endX": RES_WORKING-2, "endY": RES_WORKING-2, "id": None}
        self.asyncLoopEdit()

        # ------ chat initialize
        # queue for generation tasks   
        self.chatModel = None 
        self.isChatting = False
        self.chatLastLine = ""
        self.queueTaskChat = queue.Queue()
        self.lastChatRecordIndex = -1
        
        self.inputThread = threading.Thread(target=self.threadLoopChatResponse)
        self.inputThread.daemon = True
        self.inputThread.start()
            
        # ======== kick off main loop
        self.root.mainloop()              

    # ====================================================================
    # ==== show/hide window
    def showWindow(self, event):
        if self.vAutoHide.get() == 1:
            #print("showWindow")
            #self.root.update()
            self.root.deiconify()
            if self.hideTimer is not None:
                self.root.after_cancel(self.hideTimer)
            self.hideTimer = None
            self.isWorking = True
        if self.vAlwaysTop.get() == 1:
            self.root.attributes("-topmost",1)
        else:
            self.root.attributes("-topmost",0)
        
    def hideWindow(self, event):
        if self.vAutoHide.get() == 1:
            #print("hideWindow")
            if not self.isWorking:
                self.root.withdraw()
            if self.hideTimer is not None:
                self.root.after_cancel(self.hideTimer)
            self.hideTimer = self.root.after(1000, self.checkMousePosition)
            
    def checkMousePosition(self):
        #print("checkMousePosition")
        x, y = self.root.winfo_pointerxy()
        screenWidth, screenHeight = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        app_x, app_y = self.root.winfo_x(), self.root.winfo_y()
        appWidth, appHeight = self.root.winfo_width(), self.root.winfo_height()
        if screenWidth - x < 10 and y > app_y and y < app_y+appHeight:    # only enter this area the app is waken up
            self.showWindow(None)
        else:
            if x < app_x or x > app_x+appWidth or y < app_y or y > app_y+appHeight:
                self.isWorking = False
            else:
                self.isWorking = True
            #print(self.isWorking)
            self.hideWindow(None)


    # ====================================================================
    # ==== actions to buttons
    # ---- draw image, initialize the stable diffusion models once switched XPU
    def drawInitializeCallback(self):        
        downloadModel()

        xpuIndex = self.vXpu.get()
        if xpuIndex != self.lastXpuIndex:
            if xpuIndex == 0: #CPU
                self.localPipe = compileModel('CPU')
                self.drawPreviewImage = ImageTk.PhotoImage(Image.open('ui/ui-ready.png').resize((RES_PREVIEW, RES_PREVIEW)))
                self.drawPreviewLabel.configure(image=self.drawPreviewImage)  
            elif xpuIndex == 1: #GPU 0
                self.localPipe = compileModel('GPU.0')
                self.drawPreviewImage = ImageTk.PhotoImage(Image.open('ui/ui-ready.png').resize((RES_PREVIEW, RES_PREVIEW)))
                self.drawPreviewLabel.configure(image=self.drawPreviewImage)  
            elif xpuIndex == 2: #GPU 1
                self.localPipe = compileModel('GPU.1')
                self.drawPreviewImage = ImageTk.PhotoImage(Image.open('ui/ui-ready.png').resize((RES_PREVIEW, RES_PREVIEW)))
                self.drawPreviewLabel.configure(image=self.drawPreviewImage)  
            elif xpuIndex == 3: #AUTO
                self.localPipe = compileModel('AUTO')
                self.drawPreviewImage = ImageTk.PhotoImage(Image.open('ui/ui-ready.png').resize((RES_PREVIEW, RES_PREVIEW)))
                self.drawPreviewLabel.configure(image=self.drawPreviewImage)                   

            # clear progressbar
            self.drawGenerateProgressbar['value'] = 0
            self.drawGenerateAllProgressbar['value'] = 0
            # clear generated images
            #self.listGeneratedImages.clear()
            #self.clearGalleryGeneratedImages()
            self.drawPreviewFile = ""
            self.drawWorkingFile = ""
            self.drawResetCallback()
            
            self.lastXpuIndex = xpuIndex

    # ---- copy image to clipboard
    def _pasteToClipboard(self, file):
        with open(file, 'rb') as f:
            imageData = f.read()
            formatData = win32clipboard.RegisterClipboardFormat("PNG")
        
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(formatData, imageData)
            win32clipboard.CloseClipboard()

    def drawCopyToClipboard(self, event):
        self._pasteToClipboard(self.drawPreviewFile)
        print("Copy to clipboard")
        
    def editCopyToClipboard(self, event):
        self._pasteToClipboard(self.editPreviewFile)
        print("Copy to clipboard")        
        
    # ---- import /load and reset working image, this working image is for image->image or other purpose    
    def _fitImage(self, image, targetSize): # fit image to proper size (ex: (96, 128) -> (384, 512) when fit (512, 512))
        iw, ih = image.size
        w, h = targetSize
        scale = min(w/iw, h/ih)
        
        nw = int(iw * scale)
        nh = int(ih * scale)
        
        scale = self.vScale.get()
        if scale == 0:  #BICUBIC
            resizeImage = image.resize((nw, nh), Image.BICUBIC)
        elif scale == 1:    #LANCZOS
            resizeImage = image.resize((nw, nh), Image.LANCZOS)
        else:
            resizeImage = image.resize((nw, nh))
        return resizeImage

    def _padImage(self, image, targetSize): # pad image to proper size (ex: (96, 128) -> (512, 512) when fit (512, 512), pad at right or bottom, important for inpaint mask position)
        iw, ih = image.size
        w, h = targetSize
        scale = min(w/iw, h/ih)
        
        nw = int(iw * scale)
        nh = int(ih * scale)
        
        scale = self.vScale.get()
        if scale == 0:  #BICUBIC
            resizeImage = image.resize((nw, nh), Image.BICUBIC)
        elif scale == 1:    #LANCZOS
            resizeImage = image.resize((nw, nh), Image.LANCZOS)
        else:
            resizeImage = image.resize((nw, nh))
            
        paddedImage = Image.new('RGB', targetSize, (128, 128, 128))
        
        #paddedImage.paste(resizeImage, ((w-nw)//2, (h-nh)//2))
        paddedImage.paste(resizeImage, (0, 0))
        return paddedImage

    def drawImportCallback(self):
        if self.isGenerating == False:
            try:
                imageFile = tk.filedialog.askopenfilename()
                image = Image.open(imageFile)
                str_image = '_temp'+'_time_'+str(int(time.time()))
                savedImageFile = 'output/' + str(str_image)+'.png'
                image.save(savedImageFile)
                #print(savedImageFile)
                self.drawWorkingFile = savedImageFile
                self.insertGeneratedImage(savedImageFile)
                self.drawWorkingImage = ImageTk.PhotoImage(self._padImage(Image.open(self.drawWorkingFile), (RES_WORKING, RES_WORKING)))
                self.drawWorkingCanvas.delete("all")
                self.drawClearMaskCallback()
                self.drawWorkingCanvas.create_image(0, 0, anchor=NW, image=self.drawWorkingImage)
            except:
                pass
                print("drawImportCallback ERROR")

    def editImportCallback(self):
        if True: #self.isGenerating == False:
            try:
                imageFile = tk.filedialog.askopenfilename()
                image = Image.open(imageFile)
                str_image = '_temp'+'_time_'+str(int(time.time()))
                savedImageFile = 'output/' + str(str_image)+'.png'
                image.save(savedImageFile)
                #print(savedImageFile)
                self.editWorkingFile = savedImageFile
                self.insertGeneratedImage(savedImageFile)
                self.editWorkingImage = ImageTk.PhotoImage(self._padImage(Image.open(self.editWorkingFile), (RES_WORKING, RES_WORKING)))
                self.editWorkingCanvas.delete("all")
                #self.drawClearMaskCallback()
                self.editWorkingCanvas.create_image(0, 0, anchor=NW, image=self.editWorkingImage)
                self.inputWidth, self.inputHeight = Image.open(self.editWorkingFile).size
                self.editInputWidthLabel.configure(text=str(self.inputWidth))
                self.editInputHeightLabel.configure(text=str(self.inputHeight))
                self.editZoomScale.set(2)   #set back to 1x                
                self.editZoomScaleCallback(self.editZoomScale.get())   
                self.editWorkingCanvas.delete("regionRect")                
            except:
                pass
                print("editImportCallback ERROR")
        
    def drawLoadCallback(self):
        if self.isGenerating == False:    
            currentGeneratedImageIndex = self.vDrawSelectedImageIndex.get()
            try:
                self.drawWorkingFile = self.listGeneratedImages[currentGeneratedImageIndex]
                self.drawWorkingImage = ImageTk.PhotoImage(self._padImage(Image.open(self.drawWorkingFile), (RES_WORKING, RES_WORKING)))
                self.drawWorkingCanvas.delete("all")
                self.drawClearMaskCallback()
                self.drawWorkingCanvas.create_image(0, 0, anchor=NW, image=self.drawWorkingImage)
            except:
                pass
                print("drawLoadCallback ERROR")

    def editLoadCallback(self):
        if True: #self.isGenerating == False:    
            currentGeneratedImageIndex = self.vEditSelectedImageIndex.get()
            try:
                self.editWorkingFile = self.listGeneratedImages[currentGeneratedImageIndex]
                self.editWorkingImage = ImageTk.PhotoImage(self._padImage(Image.open(self.editWorkingFile), (RES_WORKING, RES_WORKING)))
                self.editWorkingCanvas.delete("all")
                #self.drawClearMaskCallback()
                self.editWorkingCanvas.create_image(0, 0, anchor=NW, image=self.editWorkingImage)
                self.inputWidth, self.inputHeight = Image.open(self.editWorkingFile).size
                self.editInputWidthLabel.configure(text=str(self.inputWidth))
                self.editInputHeightLabel.configure(text=str(self.inputHeight))
                self.editZoomScale.set(2)   #set back to 1x
                self.editZoomScaleCallback(self.editZoomScale.get())
                self.editWorkingCanvas.delete("regionRect")
            except:
                pass
                print("editLoadCallback ERROR")

    def drawResetCallback(self):
        if self.isGenerating == False:    
            self.drawWorkingFile = ""
            self.drawWorkingImage = ImageTk.PhotoImage(Image.open('ui/ui-blank.png').resize((RES_WORKING, RES_WORKING)))
            self.drawWorkingCanvas.delete("all")
            self.drawClearMaskCallback()
            self.drawWorkingCanvas.create_image(0, 0, anchor=NW, image=self.drawWorkingImage)

    def editResetCallback(self):
        if True: #self.isGenerating == False:    
            self.editWorkingFile = ""
            self.editWorkingImage = ImageTk.PhotoImage(Image.open('ui/ui-blank.png').resize((RES_WORKING, RES_WORKING)))
            self.editWorkingCanvas.delete("all")
            #self.drawClearMaskCallback()
            self.editWorkingCanvas.create_image(0, 0, anchor=NW, image=self.editWorkingImage)
            
            self.inputWidth, self.inputHeight = 0, 0
            self.outputWidth, self.outputHeight = 0, 0
            self.editInputWidthLabel.configure(text="")
            self.editInputHeightLabel.configure(text="")
            self.editOutputWidthLabel.configure(text="")
            self.editOutputHeightLabel.configure(text="")
            self.editZoomScale.set(2)   #set back to 1x

    # ---- image to image, mask operations
    def _clipNum(self, v, vmin, vmax):
        if v < vmin:
            v = vmin
        elif v > vmax:
            v = vmax
        return v

    def drawGetMaskStartInfo(self, event):
        self.drawMaskStartX = self._clipNum(event.x, 0, RES_WORKING-1)
        self.drawMaskStartY = self._clipNum(event.y, 0, RES_WORKING-1)
        
    def drawGetMaskMidInfo(self, event):
        self.drawMaskMidX = self._clipNum(event.x, 0, RES_WORKING-1)
        self.drawMaskMidY = self._clipNum(event.y, 0, RES_WORKING-1)
        self.drawWorkingCanvas.delete("tempRect")
        idMaskTempRect = self.drawWorkingCanvas.create_rectangle(self.drawMaskStartX, self.drawMaskStartY, self.drawMaskMidX, self.drawMaskMidY, fill='', outline='black', tags='tempRect')
        
    def drawGetMaskEndInfo(self, event):
        self.drawMaskEndX = self._clipNum(event.x, 0, RES_WORKING-1)
        self.drawMaskEndY = self._clipNum(event.y, 0, RES_WORKING-1)
        self.drawWorkingCanvas.delete("tempRect")
        idMaskRect = self.drawWorkingCanvas.create_rectangle(self.drawMaskStartX, self.drawMaskStartY, self.drawMaskEndX, self.drawMaskEndY, fill='black', outline='black', tags='maskRect')
        self.listDrawMaskRect.append({"startX": self.drawMaskStartX, "startY": self.drawMaskStartY, "endX": self.drawMaskEndX, "endY": self.drawMaskEndY, "id": idMaskRect})

    def drawClearMaskCallback(self):
        self.listDrawMaskRect.clear()
        self.drawWorkingCanvas.delete("maskRect")
    
    def drawBackMaskCallback(self):
        if len(self.listDrawMaskRect) > 0:
            lastMaskRect = self.listDrawMaskRect.pop()
            if lastMaskRect is not None:
                self.drawWorkingCanvas.delete(lastMaskRect["id"])

    # ---- matting, select out region, all beyond the region will be treat as background by default
    def editGetRegionStartInfo(self, event):
        self.editRegionStartX = self._clipNum(event.x, 0, RES_WORKING-1)
        self.editRegionStartY = self._clipNum(event.y, 0, RES_WORKING-1)
        
    def editGetRegionMidInfo(self, event):
        self.editRegionMidX = self._clipNum(event.x, 0, RES_WORKING-1)
        self.editRegionMidY = self._clipNum(event.y, 0, RES_WORKING-1)
        self.editWorkingCanvas.delete("tempRect")
        idRegionTempRect = self.editWorkingCanvas.create_rectangle(self.editRegionStartX, self.editRegionStartY, self.editRegionMidX, self.editRegionMidY, fill='', outline='black', tags='tempRect')
        
    def editGetRegionEndInfo(self, event):
        self.editRegionEndX = self._clipNum(event.x, 0, RES_WORKING-1)
        self.editRegionEndY = self._clipNum(event.y, 0, RES_WORKING-1)
        self.editWorkingCanvas.delete("tempRect")
        self.editWorkingCanvas.delete("regionRect")
        idRegionRect = self.editWorkingCanvas.create_rectangle(self.editRegionStartX, self.editRegionStartY, self.editRegionEndX, self.editRegionEndY, fill='', outline='red', tags='regionRect')
        self.editRegionRect = {"startX": self.editRegionStartX, "startY": self.editRegionStartY, "endX": self.editRegionEndX, "endY": self.editRegionEndY, "id": idRegionRect}

    # ---- show scale results in draw
    def drawNoiseScaleCallback(self, event):
        self.drawNoiseStatusLabel.configure(text=str(float(event)/5-0.1)[:4])
        
    def drawBatchScaleCallback(self, event):
        self.drawBatchStatusLabel.configure(text=str(round(float(event))))
        
    # ---- show scale results in config
    def configQualityScaleCallback(self, event):
        self.configQualityStatusLabel.configure(text=str(round(float(event)*10)))

    # ---- matting function
    def editCutCallback(self):
        if self.editWorkingFile != "":
            if True:
                # read image, define mask and models
                image = cv2.imread(self.editWorkingFile, cv2.IMREAD_UNCHANGED)
                h, w = image.shape[:2]
                resPadded = max(w, h)
                # get cutting outbound region
                regionRect = self.editRegionRect
                startX, startY, endX, endY = regionRect["startX"], regionRect["startY"], regionRect["endX"], regionRect["endY"]
                if startX > endX:
                    startX, endX = endX, startX
                if startY > endY:
                    startY, endY = endY, startY
                # modify the region coordination by image actual size
                rect = (round(startX*resPadded/RES_WORKING), round(startY*resPadded/RES_WORKING), round(endX*resPadded/RES_WORKING), round(endY*resPadded/RES_WORKING))
                #print(rect)            
                image = image[rect[1]:rect[3], rect[0]:rect[2], :]
                str_image = '_cutting_time_'+str(int(time.time()))
                savedImageFile = 'output/' + str(str_image)+'.png'
                cv2.imwrite(savedImageFile, image)
                self.insertGeneratedImage(savedImageFile)
            #except:
            #    pass
            #    print("editCutCallback ERROR")
                
    def editMatCallback(self):
        if self.editWorkingFile != "":
            if True:
                # read image, define mask and models
                image = cv2.imread(self.editWorkingFile, cv2.IMREAD_UNCHANGED)
                mask = np.zeros(image.shape[:2],np.uint8)
                bgdModel = np.zeros((1,65),np.float64)
                fgdModel = np.zeros((1,65),np.float64)
                
                # calculate padded image resolution
                h, w = image.shape[:2]
                resPadded = max(w, h)
                
                # get matting outbound region
                regionRect = self.editRegionRect
                startX, startY, endX, endY = regionRect["startX"], regionRect["startY"], regionRect["endX"], regionRect["endY"]
                if startX > endX:
                    startX, endX = endX, startX
                if startY > endY:
                    startY, endY = endY, startY
                # modify the region coordination by image actual size
                rect = (round(startX*resPadded/RES_WORKING), round(startY*resPadded/RES_WORKING), round(endX*resPadded/RES_WORKING), round(endY*resPadded/RES_WORKING))
                #print(rect)
                
                image = image[:, :, :3]
                cv2.grabCut(image, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)
                mask2 = np.where((mask==2)|(mask==0),0,1).astype('uint8')
                image = image * mask2[:,:,np.newaxis]
                alpha = mask2 * 255
                str_image = '_matting_time_'+str(int(time.time()))
                savedImageFile = 'output/' + str(str_image)+'.png'
                cv2.imwrite(savedImageFile, cv2.merge((image, alpha)))
                self.insertGeneratedImage(savedImageFile)
            #except:
            #    pass
            #    print("editMatCallback ERROR")

    # ---- change resolution targets and scale in edit    
    def editResizeCallback(self):
        self.editZoomScaleCallback(self.editZoomScale.get())
        if self.editWorkingFile != "":       
            try:
                str_image = '_scale_'+str(self.outputWidth)+'x'+str(self.outputHeight)+'_time_'+str(int(time.time()))
                savedImageFile = 'output/' + str(str_image)+'.png'
                image = Image.open(self.editWorkingFile)
                image = self._fitImage(image, (self.outputWidth, self.outputHeight))
                image.save(savedImageFile)
                self.insertGeneratedImage(savedImageFile)
            except:
                pass
                print("editResizeCallback ERROR")
                
    def editZoomScaleCallback(self, event):
        zoom = float(event) / 2 #scale 1-4 map to 0.5-2
        if self.inputWidth != None and self.inputWidth != 0 and self.inputHeight != None and self.inputHeight != 0 and self.outputWidth != None and self.outputHeight != None:
            self.outputWidth = round(self.inputWidth * zoom)
            self.outputHeight = round(self.inputHeight * zoom)
            self.editOutputWidthLabel.configure(text=str(self.outputWidth))
            self.editOutputHeightLabel.configure(text=str(self.outputHeight))

    # ---- manage gallery images
    def insertGeneratedImage(self, file):   # shared
        if len(self.listGeneratedImages) == self.maxGalleryImageCount:
            self.listGeneratedImages.pop(-1)
        self.listGeneratedImages.insert(0, file)
        #when insert image, reset the index for both gallery to force redraw gallery
        self.lastDrawGeneratedImageIndex = -1
        self.lastEditGeneratedImageIndex = -1
        self.vDrawSelectedImageIndex.set(0)
        self.vEditSelectedImageIndex.set(0)
        self.drawShowGalleryGeneratedImages()
        self.editShowGalleryGeneratedImages()
        
    def drawShowGalleryGeneratedImages(self):
        for indexImage, generatedImage in enumerate(self.listGeneratedImages):
            self.listDrawGalleryImages[indexImage]["image"] = ImageTk.PhotoImage(self._padImage(Image.open(generatedImage), (RES_GALLERY, RES_GALLERY)))
            self.listDrawGalleryImages[indexImage]["button"].configure(image=self.listDrawGalleryImages[indexImage]["image"])    
            
    def editShowGalleryGeneratedImages(self):
        for indexImage, generatedImage in enumerate(self.listGeneratedImages):
            self.listEditGalleryImages[indexImage]["image"] = ImageTk.PhotoImage(self._padImage(Image.open(generatedImage), (RES_GALLERY, RES_GALLERY)))
            self.listEditGalleryImages[indexImage]["button"].configure(image=self.listEditGalleryImages[indexImage]["image"])              

    def drawClearGalleryGeneratedImages(self):
        for indexImage in range(self.maxGalleryImageCount):
            self.listDrawGalleryImages[indexImage]["image"] = ImageTk.PhotoImage(Image.open('ui/ui-blank.png').resize((RES_GALLERY, RES_GALLERY)))
            self.listDrawGalleryImages[indexImage]["button"].configure(image=self.listDrawGalleryImages[indexImage]["image"])
            
    def editClearGalleryGeneratedImages(self):
        for indexImage in range(self.maxGalleryImageCount):
            self.listEditGalleryImages[indexImage]["image"] = ImageTk.PhotoImage(Image.open('ui/ui-blank.png').resize((RES_GALLERY, RES_GALLERY)))
            self.listEditGalleryImages[indexImage]["button"].configure(image=self.listEditGalleryImages[indexImage]["image"])                

    # ---- generate images, actually put requests in a queue, and set the button to 'interupt'; when click again, clear the queue
    def drawGenerateCallback(self):
        # async routine, when generate clicked, change the 'text' to 'interrupt', when next click, interrupt current unfinished task queue
        if self.isGenerating == False:   
            # read parameters for text -> image
            prompt = self.drawPromptText.get('1.0', END).replace('\n', '').replace('\t', '')
            if TRANSLATE:
                prompt = translateYouDaoC2E(prompt)
            negative = 'paintings,sketches,low quality,grayscale,urgly face,extra fingers,fewer fingers,watermark'#self.negativeText.get('1.0', END).replace('\n', '').replace('\t', '')
            seedList = [random.randint(0, 9999) for x in range(round(self.drawBatchScale.get()))]
            steps = round(self.qualityScale.get())*10
            # get input image and strenth for image -> image
            image = self.drawWorkingFile
            strength = self.drawNoiseScale.get() / 5 - 0.1
            strength = self._clipNum(strength, 0, 1)
            # get mask for inpaint(enhanced image -> image)
            if len(self.listDrawMaskRect) > 0:
                mask = np.ones((1, 4, RES_MASK, RES_MASK))
                for maskRect in self.listDrawMaskRect:
                    startX, startY, endX, endY = maskRect["startX"], maskRect["startY"], maskRect["endX"], maskRect["endY"]
                    startX, startY, endX, endY = round(startX/RES_WORKING*RES_MASK), round(startY/RES_WORKING*RES_MASK), round(endX/RES_WORKING*RES_MASK), round(endY/RES_WORKING*RES_MASK)
                    if startX > endX:
                        startX, endX = endX, startX
                    if startY > endY:
                        startY, endY = endY, startY
                    mask[:,:,startY:endY,startX:endX]=0
            else:
                mask = None
        
            try:
                self.drawGenerateAllProgressbar['maximum'] = steps * len(seedList)
                self.drawGenerateAllProgressbar['value'] = 0
                
                for seed in seedList:
                    xpuIndex = self.vXpu.get()
                    if xpuIndex == 0: #CPU
                        taskGenerate = ['CPU', prompt, negative, seed, steps, image, strength, mask]
                    elif xpuIndex == 1: #GPU 0
                        taskGenerate = ['GPU.0', prompt, negative, seed, steps, image, strength, mask]
                    elif xpuIndex == 2: #GPU 1
                        taskGenerate = ['GPU.1', prompt, negative, seed, steps, image, strength, mask]
                    elif xpuIndex == 3: #AUTO
                        taskGenerate = ['AUTO', prompt, negative, seed, steps, image, strength, mask]
                    self.queueTaskGenerate.put(taskGenerate)
                        
                self.drawGenerateButton['text'] = 'Interrupt'
                self.isGenerating = True
            except NameError:
                self.drawPreviewImage = ImageTk.PhotoImage(Image.open('ui/ui-initialize.png').resize((RES_PREVIEW, RES_PREVIEW)))
                self.drawPreviewLabel.configure(image=self.drawPreviewImage)
                print("drawGenerateCallback ERROR")
            except ValueError:
                self.drawPreviewImage = ImageTk.PhotoImage(Image.open('ui/ui-input.png').resize((RES_PREVIEW, RES_PREVIEW)))
                self.drawPreviewLabel.configure(image=self.drawPreviewImage) 
                print("drawGenerateCallback ERROR")
        # async routine, when in last generation batch, the button shows 'interrupt', can't start next batch. click the button to clear the queue
        elif self.isGenerating == True:
            self.queueTaskGenerate.queue.clear()
            #generateProgressbar['value'] = 0
            #generateAllProgressbar['value'] = 0
        
    def drawProgressbarCallback(self):
        self.drawGenerateProgressbar['value'] = self.drawGenerateProgressbar['value'] + 1
        self.drawGenerateAllProgressbar['value'] = self.drawGenerateAllProgressbar['value'] + 1
        self.root.update()

    # ====================================================================
    # ==== async subprocess             
    def asyncLoopGenerate(self):
    # Create a loop here to async generate images - unblock mainloop windows message management
    # when clicked button, quickly exit the response function there, then the loop routine get chance to get in
    # in this loop routine, if we do a while to draw images, the windows messsage will be blocked then we still can't see all
    # we have to draw one image then return current loop routine, draw next in next loop, then everything perfect        
        intervalLoop = 100 #ms
        if not self.queueTaskGenerate.empty():   # in generation work
            taskGenerate = self.queueTaskGenerate.get()
            try:
                startTime = time.time()
                xpu, prompt, negative, seed, steps, image, strength, mask = taskGenerate
                self.drawGenerateProgressbar['maximum'] = steps
                self.drawGenerateProgressbar['value'] = 0
                
                if self.localPipe == None:
                    print("Error: null local pipe!")
                else:
                    result = generateImage(xpu, self.localPipe, prompt, negative, seed, steps, image, strength, mask, self.drawProgressbarCallback)
                self.drawPreviewFile = result
                self.drawPreviewImage = ImageTk.PhotoImage(self._padImage(Image.open(self.drawPreviewFile), (RES_PREVIEW, RES_PREVIEW)))
                self.drawPreviewLabel.configure(image=self.drawPreviewImage)
                endTime = time.time()
                useTime = endTime-startTime
                roughSteps = int(steps) if image == "" else int(steps)*float(strength)
                self.timeLabel.configure(text='Time: ' + "%.2f"%useTime + 's (' + "%.2f"%(roughSteps/useTime) + 'it/s)')   
                self.insertGeneratedImage(self.drawPreviewFile)
            except NameError:
                self.drawPreviewImage = ImageTk.PhotoImage(Image.open('ui/ui-initialize.png').resize((RES_PREVIEW, RES_PREVIEW)))
                self.drawPreviewLabel.configure(image=self.drawPreviewImage)
                print("asyncLoopGenerate ERROR")
            except ValueError:
                self.drawPreviewImage = ImageTk.PhotoImage(Image.open('ui/ui-input.png').resize((RES_PREVIEW, RES_PREVIEW)))
                self.drawPreviewLabel.configure(image=self.drawPreviewImage)   
                print("asyncLoopGenerate ERROR")
        else:   # not in generation work, free for next work
            self.drawGenerateButton['text'] = 'Generate'
            self.isGenerating = False

            # show selected image to main canvas
            currentGeneratedImageIndex = self.vDrawSelectedImageIndex.get()
            if currentGeneratedImageIndex!= self.lastDrawGeneratedImageIndex:
                if (currentGeneratedImageIndex < len(self.listGeneratedImages)):
                    self.drawPreviewFile = self.listGeneratedImages[currentGeneratedImageIndex]
                    self.drawPreviewImage = ImageTk.PhotoImage(self._padImage(Image.open(self.drawPreviewFile), (RES_PREVIEW, RES_PREVIEW)))
                    self.drawPreviewLabel.configure(image=self.drawPreviewImage)
                    self.lastDrawGeneratedImageIndex = currentGeneratedImageIndex
        # iterately call next routine
        self.root.after(intervalLoop, self.asyncLoopGenerate)

    def asyncLoopEdit(self):
        intervalLoop = 100 #ms
        # show selected image to main canvas
        currentGeneratedImageIndex = self.vEditSelectedImageIndex.get()
        if currentGeneratedImageIndex!= self.lastEditGeneratedImageIndex:
            if (currentGeneratedImageIndex < len(self.listGeneratedImages)):
                self.editPreviewFile = self.listGeneratedImages[currentGeneratedImageIndex]
                self.editPreviewImage = ImageTk.PhotoImage(self._padImage(Image.open(self.editPreviewFile), (RES_PREVIEW, RES_PREVIEW)))
                self.editPreviewLabel.configure(image=self.editPreviewImage)
                self.lastEditGeneratedImageIndex = currentGeneratedImageIndex
        # iterately call next routine
        self.root.after(intervalLoop, self.asyncLoopEdit)        

    # ---- handle input/output in chat panel 
    def chatInputEnterCallback(self, event):
        if self.isChatting == False:
            chatInputString = self.chatInputEntry.get()
            if chatInputString != '':
                self.chatInputEntry.delete(0, END)
                self.queueTaskChat.put(chatInputString)
                self.isChatting = True
                self.chatLastLine = chatInputString

    def chatInputUpCallback(self, event):
        if self.isChatting == False: 
            chatInputString = self.chatInputEntry.get()
            if chatInputString == '':
                self.chatInputEntry.insert(0, self.chatLastLine)

    def chatOutputCallback(self, text):
        #print(text)
        self.chatOutputText.insert(END, text, 'tagNormal')
        self.chatOutputText.see(END)

    def threadLoopChatResponse(self):
        # import Chat GPT model
        from pyllamacpp.model import Model    
        self.chatModel = Model(ggml_model='./chatModels/gpt4all-model.bin', n_ctx=512)
        while True:
            if self.isChatting == True:
                # call GPT to generate feedback
                chatInputString = self.queueTaskChat.get()
                if TRANSLATE:
                    chatInputString = translateYouDaoC2E(chatInputString)
                if chatInputString.isascii():
                    while chatInputString:
                        self.chatInputEntry.config(state=tk.DISABLED)
                        self.chatOutputText.config(state=tk.NORMAL)
                        self.chatOutputText.delete('1.0', END)
                        self.chatOutputText.insert(END, '>', 'tagReact')
                        chatOutputString = self.chatModel.generate(chatInputString+'\n\n', n_predict=512, repeat_penalty=1.3, new_text_callback=self.chatOutputCallback, n_threads=8)
                        self.chatOutputText.config(state=tk.DISABLED)
                        self.chatInputEntry.config(state=tk.NORMAL)
                        #print(chatInputString.strip() == chatOutputString.strip())
                        if chatInputString.strip() != chatOutputString.strip():
                            chatInputString = None
                            self.insertChatRecord(chatOutputString)
                else:
                    self.chatOutputText.config(state=tk.NORMAL)
                    self.chatOutputText.delete('1.0', END)
                    self.chatOutputText.insert(END, '>>> ', 'tagWarning')
                    self.chatOutputText.insert(END, "Sorry. I don't understand. Would you please speak English? ", 'tagNormal')
                    self.chatOutputText.config(state=tk.DISABLED)
                self.isChatting = False    
            else:   # not in chatting response stage, can show history
                currentChatRecordIndex = self.vChatSelectedRecordIndex.get()
                if currentChatRecordIndex != self.lastChatRecordIndex:
                    if (currentChatRecordIndex < len(self.listChatRecordStrings)):
                        self.chatOutputText.config(state=tk.NORMAL)
                        self.chatOutputText.delete('1.0', END)
                        self.chatOutputText.insert(END, '> ', 'tagReact')
                        chatRecordString = self.listChatRecordStrings[currentChatRecordIndex]
                        self.chatOutputText.insert(END, chatRecordString, 'tagNormal')
                        print(chatRecordString)
                        if TRANSLATE:
                            chatRecordStringInput, chatRecordStringOutput = chatRecordString.split('\n\n')[0], chatRecordString.split('\n\n')[1]
                            chatRecordStringInput = chatRecordStringInput.replace('\n', ' ')
                            chatRecordStringInput = translateYouDaoE2C(chatRecordStringInput)
                            chatRecordStringOutput = chatRecordStringOutput.replace('\n', ' ')
                            chatRecordStringOutput = translateYouDaoE2C(chatRecordStringOutput)
                            print(chatRecordStringInput)
                            print(chatRecordStringOutput)
                            self.chatOutputText.insert(END, '\n\n> ', 'tagReact')
                            self.chatOutputText.insert(END, chatRecordStringInput, 'tagNormal')
                            self.chatOutputText.insert(END, '\n\n'+chatRecordStringOutput, 'tagNormal')
                        self.chatOutputText.see(END)    
                        self.chatOutputText.config(state=tk.DISABLED)
                    else:
                        self.chatOutputText.config(state=tk.NORMAL)
                        self.chatOutputText.delete('1.0', END)
                        self.chatOutputText.config(state=tk.DISABLED)
                    self.lastChatRecordIndex = currentChatRecordIndex
            time.sleep(0.5)

    # ---- manage chat history
    def insertChatRecord(self, string):   
        if len(self.listChatRecordStrings) == self.maxChatRecordCount:
            self.listChatRecordStrings.pop(-1)
        self.listChatRecordStrings.insert(0, string)
        #when insert image, reset the index for both gallery to force redraw gallery
        self.vChatSelectedRecordIndex.set(0)
        self.showChatRecords()
        self.lastChatRecordIndex = -1
        
    def showChatRecords(self):
        for indexRecord, recordString in enumerate(self.listChatRecordStrings):
            string = recordString.split('\n')[0]
            string = string[:15] + '\n' + string[15:30] +  '\n' + string[30:45]
            self.listChatRecordButtons[indexRecord].configure(text=string)                 

# ### MAIN
#   
if __name__ == "__main__":       
    UiHelper()
    pass