# -*- coding: UTF-8 -*-

from transformers import pipeline

def summarize(input_):
    summarizer = pipeline("summarization", model="./chatModels/bart-large-cnn-samsum")
    texts = input_.split('\n')
    output = ""

    try:
        for text in texts:
            print(text)
            summary = summarizer(text, min_length=16, max_length=128)[0]['summary_text']
            print(summary)
            if output == "":
                output = summary
            else:
                output = output + '\n' + summary
    except:
        pass

    return output