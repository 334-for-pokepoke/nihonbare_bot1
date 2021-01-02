import pickle
import os
import re
import getSQL


def getargc(text):
    i = 0
    for c in text:
        if (c == '?'):
            i += 1
    return i

def sqlreq(cmd, argtpl):
    print('SQL request:' + cmd)
    result = getSQL.sqlrequest(cmd, argtpl)
    if (result[1] == -1):
        return False, '該当するデータが見つかりませんでした'
    elif (result[1] == -2):
        return False, '\n要求エラー：'+result[0]
    else:
        return True, result[0]

def addsql(arg, SQLCMD_PATH):
    MAX_TABLE  = 8
    if (len(arg) <= 1):
        return -1, None     #不適切なコマンド
    cmd = arg[0]
    text = ''
    info=''
    flg = 0
    for i in range(len(arg)-1):
        text += arg[i+1] + ' '
        
    text_head = text[:6].lower()
    if (text_head == 'select' or text[:1] == '?'):
        pass
    else:
        return -1, None
        
    sql_dict = {}
    if os.path.getsize(SQLCMD_PATH) > 0:
        with open(SQLCMD_PATH, 'rb') as f:
            sql_dict = pickle.load(f)
                
        if (cmd in sql_dict):
            return -2, None     #定義済みのコマンド
    
    if (text_head == 'select'):
        sql_dict[cmd] = {'SQL':text,'info':'', 'argc':getargc(text)}
    else:
        errflg = 0
        cmds = []
        prefix_len = len('?')
        for txt in arg[1:]:
            if (txt.startswith('?')):
                cmds.append(txt[prefix_len:])
            else:
                errflg = 1
                break
        if (errflg):
            return -1, None
        if (len(cmds) > MAX_TABLE):
            return -1, None
        
        with open(SQLCMD_PATH, 'rb') as f:
            sql_dict = pickle.load(f)
        
        cnt = 0
        errflg = 0
        for c in cmds:
            if  (c not in sql_dict.keys()):
                errflg = -3
                break
            if (sql_dict[c]['SQL'].startswith('?')):
                errflg = -5
                break
            cnt += sql_dict[c]['argc']
        if (errflg != 0):
            return errflg, None
        sql_dict[cmd] = {'SQL':text,'info':'', 'argc':cnt}


    with open(SQLCMD_PATH, 'wb') as f:
        pickle.dump(sql_dict, f)
    return 1, cmd

def showsql(arg, SQLCMD_PATH):
    if os.path.getsize(SQLCMD_PATH) <= 0:
        return -3, None #コマンドが未登録
    with open(SQLCMD_PATH, 'rb') as f:
        sql_dict = pickle.load(f)

    text = []
    if (len(arg) == 0):
        for cmds in sql_dict:
            text.append(cmds)
        return 1, text
    else:
        for cmds in arg:
            if (cmds in sql_dict):
                text.append([cmds,sql_dict[cmds]['info']])
        return 2, text

def delsql(cmd, SQLCMD_PATH):
    if os.path.getsize(SQLCMD_PATH) <= 0:
        return -3
    with open(SQLCMD_PATH, 'rb') as f:
        sql_dict = pickle.load(f)
    if (cmd in sql_dict):
        del sql_dict[cmd]
        with open(SQLCMD_PATH, 'wb') as f:
            pickle.dump(sql_dict, f)
        return 1
    return -4

def playsql(mes):
        arg1 = ''
        arg2 = ''
        flg = 0
        for i in mes:
            if (flg == 0):
                if(i=='\n'):
                    flg = 1
                else:
                    arg1 += i
            else:
                if(i=='\n'):
                    break
                arg2 += i
        arg1 = arg1[5:]
        arglist = arg2.split()
        argtpl  = tuple(arglist)
        return sqlreq(arg1, argtpl)
            
def editsql(mes, SQLCMD_PATH):
    if os.path.getsize(SQLCMD_PATH) <= 0:
        return 'エラー1：コマンドが見つかりません'
    cmd = ''
    text = ''
    flg = 0
    for i in mes:
        if (flg == 0):
            if(i=='\n'):
                flg = 1
            else:
                cmd += i
        else:
            text += i
                
    cmd = cmd[len('!editsql '):]
    sql_dict = {}
    with open(SQLCMD_PATH, 'rb') as f:
        sql_dict = pickle.load(f)
            
    if (cmd in sql_dict):
        pass
    else:
        return 'エラー2：コマンド「'+cmd+'」が見つかりません'
        
    sql_dict[cmd]['info'] = text
    with open(SQLCMD_PATH, 'wb') as f:
        pickle.dump(sql_dict, f)
    return '説明文を追加しました'

def registered_sql(mes, SQLCMD_PATH):
    MAX_TABLE = 8
    if os.path.getsize(SQLCMD_PATH) <= 0:
        return False, 'エラー：コマンドが見つかりません'
    lmes = mes.split()
    cmds = []
    args = []
    prefix_len = len('?')
    #コマンドと引数の呼び出し
    for text in lmes:
        if (text.startswith('?')):
            cmds.append(text[prefix_len:])
        else:
            args.append(text)

    if (len(cmds) > MAX_TABLE):
        return False, 'エラー：コマンドが多すぎます'

    with open(SQLCMD_PATH, 'rb') as f:
        sql_dict = pickle.load(f)
    
    argc = []
    cnt = 0
    errflg = 0
    for cmd in cmds:
        if (cmd not in sql_dict.keys()):
            errflg  = 1
            break
        argc.append(sql_dict[cmd]['argc'])
        cnt += sql_dict[cmd]['argc']

    if (errflg):
        return False, 'エラー：コマンド「'+cmd+'」が見つかりません'

    if (cnt != len(args)):
        return False, 'エラー：引数の数が間違っています'

    #コマンドがコマンドの連結である場合
    flg = 0
    for cmd in cmds:
        if (cmd not in sql_dict.keys()):
            flg = -1
            break
        if (sql_dict[cmd]['SQL'].startswith('?')):
            flg = 1
            req = sql_dict[cmd]['SQL']
            for s in args:
                req += ' ' + s
            res, result = registered_sql(req, SQLCMD_PATH)
            break
        
    if (flg == 1):
        return res, result
    if (flg == -1):
        return False, 'エラー：コマンド「'+cmd+'」が見つかりません'

    if (len(cmds) == 1):
        if (cmd in sql_dict):
            return sqlreq(sql_dict[cmd]['SQL'] , tuple(args))
            

    flg = 0
    for cmd in cmds:
        if (cmd.startswith('?')):
            flg = 1
            req = sql_dict[cmd]['SQL']
            for s in args:
                req += ' ' + s
            res, result = registered_sql(req, SQLCMD_PATH)
    if (flg):
        return res, result

    errflg = 0
    cnt = 0
    i = 0
    for cmd in cmds:
        if (cmd in sql_dict.keys()):
            #コマンドに対応する数の引数のリストを作成
            arglist = args[cnt:cnt+argc[i]]
            cnt += argc[i]
            i += 1
            #SQLの実行
            res, result = sqlreq(sql_dict[cmd]['SQL'] , tuple(arglist))
            #実行結果をテーブルに保存
            if (res and len(result[0]) == 1):
                if (i == 1):
                    outANDout = set([x[0] for x in result])
                else:
                    outANDout &= set([x[0] for x in result])
            else:
                errflg = 1
                break
        else:
            errflg = 2
            break
    if (errflg == 1):
        return False, 'エラー：'+str(i)+'つ目のコマンドでエラーが発生しました'
    if (errflg == 2):
        return False, 'エラー：コマンド「'+cmd+'」が見つかりません'
    
    return 1, list(outANDout)