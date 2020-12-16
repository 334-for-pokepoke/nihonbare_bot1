import re
import random

def calcform(form):
    print(form)
    if (len(form) == 0):
        return 0.0
    
    m = re.fullmatch('\d+\.?\d*|\.\d+', form)
    if (m != None):
        return float(form)
    
    m = re.search(r'\(.*\)', form)
    if (m != None):
        return calcform(form[:m.start()] + str(calcform(m.group()[1:-1])) + form[m.end():])
    
    m = re.search(r'\+', form)
    if (m != None):
        span = m.start()
        return calcform(form[:span]) + calcform(form[span+1:])
    
    m = re.search(r'\-', form)
    if (m != None):
        span = m.start()
        return calcform(form[:span]) - calcform(form[span+1:])
    
    m = re.search(r'\*', form)
    if (m != None):
        span = m.start()
        return calcform(form[:span]) * calcform(form[span+1:])
    
    m = re.search(r'\/', form)
    if (m != None):
        span = m.start()
        return calcform(form[:span]) / calcform(form[span+1:])
    
    m = re.search(r'\^', form)
    if (m != None):
        span = m.start()
        return calcform(form[:span]) ** calcform(form[span+1:])
    
    return None
        

def calc(formula):
    form = formula[1:].replace(' ', '')
    if (len(formula) <= 0):
        return 1, '不適切な数式です'

    m = re.findall(r'[^0-9\+\-\*\/\^\(\)\.]', form)
    if (len(m) > 0):
        return 0, m
    
    if (form.count('(') != form.count(')')):
        return 1, '括弧の数が間違っています'

    try:
        form_tree = calcform(form)
    except ZeroDivisionError:
        form_tree = '0で除算しました'
    return 1, form_tree

def shuffle(argv):
    l = len(argv)
    if (l <= 0):
        return []

    for i in range(l):
        r = random.randrange(l - i)
        argv[r], argv[l-i-1] = argv[l-i-1], argv[r]
    return argv