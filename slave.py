import discord
from discord.ext import commands
import os
import sys
import re
import asyncio
import configparser
import pathlib
import random
from glob import glob
sys.path.append(os.path.join(os.path.dirname(__file__), 'Commands'))
import cmd_status
import cmd_sql
import cmd_home
import cmd_system
import cmd_other
import cmd_bgm
import vc
import rw_csv
import userinfo
import image_

MAINPATH     = os.path.dirname(os.path.abspath(__file__)) #このファイルの位置
CONFIG_PATH  = '' + MAINPATH + '/Data/config.ini'

config = configparser.ConfigParser()
if not os.path.exists(CONFIG_PATH):
    raise FileNotFoundError
config.read(CONFIG_PATH, encoding='utf-8')
channel_id = dict(config.items('CHANNEL'))
role_id    = dict(config.items('ROLE'))

def get_path(name):
    return MAINPATH + config.get('DIR', name)

now_vc       = None                     #
voice        = None                     #現在参加しているボイスチャンネルをグローバル変数として管理する
vc_state     = 0                        #ボイスチャンネルにいる人の数を0で初期化
TOKEN_PATH   = get_path('token')
STOCK_PATH   = get_path('stock')
IMG_PATH     = get_path('img')
SQLCMD_PATH  = get_path('sql_cmd')
EVENT_PATH   = get_path('event')
MUSIC_PATH   = config.get('DIR', 'bgm')

#TOKENの読み込み
with open(TOKEN_PATH, "r",encoding="utf-8_sig") as f:
    l = f.readlines()
    l_strip = [s.strip() for s in l]
    TOKEN = l_strip[0]

# "!"から始まるものをコマンドと認識する
prefix = '!'
#helpコマンドの日本語化
class JapaneseHelpCommand(commands.DefaultHelpCommand):
    def __init__(self):
        super().__init__()
        self.commands_heading = "コマンド:"
        self.no_category = "その他"
        self.command_attrs["help"] = "コマンド一覧と簡単な説明を表示"

    def get_ending_note(self):
        return (f"各コマンドの説明: {prefix}help <コマンド名>\n"
                f"各カテゴリの説明: {prefix}help <カテゴリ名>\n")

#bgmコマンドで使う再生キュー
class AudioQueue(asyncio.Queue):
    def __init__(self):
        super().__init__(0)         #再生キューの上限を設定しない

    def __getitem__(self, idx):
        return self._queue[idx]     #idx番目を取り出し

    def to_list(self):
        return list(self._queue)    #キューをリスト化

    def reset(self):
        self._queue.clear()         #キューのリセット

#bgmコマンドで使う，現在の再生状況を管理するクラス
class AudioStatus:
    def __init__(self, vc):
        self.vc = vc                                #自分が今入っているvc
        self.queue = AudioQueue()                   #再生キュー
        self.playing = asyncio.Event()
        asyncio.create_task(self.playing_task())
        self.bgminfo = None

    #曲の追加
    async def add_audio(self, title, path, isloop = False):
        await self.queue.put([title, path, isloop])

    #曲の再生（再生にはffmpegが必要）    
    async def playing_task(self):
        while True:
            self.playing.clear()
            try:
                title, path, isloop = await asyncio.wait_for(self.queue.get(), timeout = 100)
            except asyncio.TimeoutError:
                asyncio.ensure_future(self.leave())
            self.vc.play(discord.FFmpegPCMAudio(source=path), after = self.play_next)
            if (isloop):
                await self.add_audio(title, path, isloop = True)
            activity = discord.Activity(name=title, type=discord.ActivityType.listening)    #アクティビティの更新
            self.bgminfo = path
            await bot.change_presence(activity=activity)
            await self.playing.wait()
    
    #playing_taskの中で呼び出される
    #再生が終わると次の曲を再生する
    def play_next(self, err=None):
        self.bgminfo = None
        self.playing.set()
        return
            
    def playing_info(self):
        if (self.bgminfo is None):
            return 'This bot is not playing an Audio File'
        return self.bgminfo[len(MUSIC_PATH)+1:]

    #vcから切断
    async def leave(self):
        self.queue.reset()  #キューのリセット
        self.bgminfo = None
        if self.vc:
            await self.vc.disconnect()
            self.vc = None
        return
    
    #曲が再生中ならtrue
    def is_playing(self):
        return self.vc.is_playing()
    
    #vcに接続していればtrue
    def is_connected(self):
        return self.vc.is_connected()

    #再生する曲が無くなる等でweb socketが切断されていればtrue
    def is_closed(self):
        self.bgminfo = None
        return (self.vc is None or (self.vc.is_connected() == False))

#botの作成
bot = commands.Bot(command_prefix=prefix, help_command=JapaneseHelpCommand())

# bot起動時に"login"と表示
@bot.event
async def on_ready():
    activity = discord.Activity(name='Python', type=discord.ActivityType.playing)
    await bot.change_presence(activity=activity)
    print('login\n')

#コマンドに関するエラー
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.send(f'{ctx.author.mention}エラー：引数の数が不正です')
        return

    if isinstance(error, commands.errors.CommandNotFound):
        await ctx.send(f'{ctx.author.mention}エラー：コマンドが見つかりません')
        return
    print(error)
    raise error

#botが自分自身を区別するための関数
is_me = lambda m: m.author == bot.user

#現状tuple等の送信に対応していないので応急処置
def listcontent(list_):
    if (type(list_) is not list):
        return list_
    return listcontent(list_[0])

#多重リストを区切り文字で展開する
def list2str(list_, delimiter):
    result = ''
    if (len(delimiter) == 0):
        d = ' '
        for s in list_:
            result += str(s) + d
        return result[:-1]
    
    d = delimiter[0]
    for s in list_:
        if (type(s) is list):
            result += list2str(s, delimiter[1:]) + d
        else:
            result += str(s) + d
    return result[:-1*len(d)]

#文字列やリストの送信を行う関数
#send_method：送信を行う関数
#mention：メンション（空白文字列にすればメンションしない）
#mes：発言する内容
#title：embedを送信する場合のタイトル
#delimiter：リストを文字列にする場合の区切り文字
#isembed：リストを送信する場合にembedを使うならTrue
#senderr：embedが文字数制限で送信できなかった場合にその旨を送信するならTrue
#戻り値：メッセージの送信に成功したのであればそのメッセージが，embed等の送信に失敗すればNoneが返る
async def send_message(send_method, mention, mes, title = 'Result', delimiter = ['\n'], isembed = True, senderr = True, half = False, ishalf = False):
    message = None
    mtype = type(mes)
    if (mtype is list):
        if (len(mes) == 0):
            message = await send_method(f'{mention} 該当するデータがありません')
        elif (len(mes) == 1 and mtype is not list):
            message = await send_method(f'{mention} ' + listcontent(mes))
            
        else:
            reply = list2str(mes, delimiter)
            if (ishalf):
                reply += "\n………"
            if (isembed):
                try:
                    embed = discord.Embed(title=title, description=reply)
                    message = await send_method(f'{mention} ', embed=embed)
                except:
                    if (half and len(mes) > 1):
                        message = await send_message(send_method, mention, mes[:int(len(mes)/2)], title, delimiter, isembed, senderr, half, ishalf = True)
                        return message
                    if (senderr):
                        await send_method(f'{mention} エラー：該当するデータが多すぎます')
                    message = None
            else:
                message = await send_message(send_method, mention, '\n'+reply, title = title)
    elif (mtype is str):
        if (len(mes) == 0):
            message = await send_method(f'{mention} 該当するデータがありません')
        else:
            message = await send_method(f'{mention} ' + mes)
    elif (mtype is int or mtype is float):
        message = await send_method(f'{mention} {mes}')
    else:
        pass
    return message

#確認を取るメッセージ(y)の受理
#30s以内に対象とするメンバーがyと発言すればTrue, そうでなければFalseが返る
#member：確認を取る対象
async def confirm(member):
    def check_y(m):
        return (m.content == 'y') and (m.author == member)
    try:
        await bot.wait_for('message', check=check_y, timeout=30.0)
    except asyncio.TimeoutError:
        return False
    else:
        return True

#発言の削除を行う
#_channel：削除する発言があるch
#mes_id：削除する発言のメッセージID
async def del_message(_channel, mes_id):
    channel = bot.get_channel(_channel)
    try:
        message = await channel.fetch_message(mes_id)
        if is_me(message):
            await message.delete()
    except:
        pass
    return

class __BGM(commands.Cog, name= 'BGM管理'):
    def search_audiofiles(self):
        cur_path = os.getcwd()
        os.chdir(MUSIC_PATH)    #オーディオファイルがある場所の頂点に移動

        self.music_pathes = [p for p in glob('Music/**', recursive=True) if os.path.isfile(p)]              #オーディオファイルの検索（相対パス）
        self.music_titles = [os.path.splitext(os.path.basename(path))[0] for path in self.music_pathes]     #オーディオファイルの名前から拡張子とパスを除去したリストを作成
        self.music_pathes = [MUSIC_PATH + os.sep + p for p in self.music_pathes]                            #フルパスに変更
        length = len(self.music_titles)
        for i in range(length):                                                                 #トラック番号も除去
            if (re.fullmatch(r'[0-9][0-9] .*', self.music_titles[i])):
                self.music_titles[i] = (self.music_titles[i])[3:]

        self.music_dirs = glob(os.path.join('Music', '**' + os.sep), recursive=True)                 #ディレクトリの一覧を作成（相対パス）
        self.mdir_name  = [pathlib.Path(f).parts[-1] for f in self.music_dirs]                       #ディレクトリの一覧からパスを除去
        os.chdir(cur_path)          #カレントディレクトリを戻す
        return

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.mn = ''
        self.audio_status = None
        self.search_audiofiles()
    
    #再生キューが空の状態で放置しているとvcから切断されるため，bgm及びremoveコマンドで現在の接続状況を再読み込みする
    async def reload_state(self):
        if (self.audio_status == None or self.audio_status.is_closed()):    #vcから切断済みである場合
            global voice, now_vc
            activity = discord.Activity(name='Python', type=discord.ActivityType.playing)   #アクティビティも修正する
            await bot.change_presence(activity=activity)
            now_vc = None
            voice = None
        return

    #embedに収まる範囲でファイル構造を送信する
    #path：送るファイル構造の頂点のファイルパス
    #nest：何階層分を送信するか
    async def send_tree(self, ctx, path, nest = -1):
        if (nest == 0):
            await send_message(ctx.send, '', 'エラー：該当するデータが多すぎます')
        if (nest == -1):
            tree = cmd_bgm.make_filetree(path)
            nest = cmd_bgm.depth(tree)
        else:
            tree = cmd_bgm.make_filetree(path, nest = nest)
        result = await send_message(ctx.send, '', tree, delimiter = ['\n'+'....'*i+'├' for i in range(nest)], senderr = False)
        if (result is None):
            await self.send_tree(ctx, path, nest = nest-1)  #ネストを1つ浅くしてやり直し
        return
    
    @commands.command()
    async def remove(self, ctx):
        """botをvcから切断"""
        global voice, now_vc
        await self.reload_state()
        if (voice is None):
            return
        await self.stop(ctx)
        await self.clear(ctx)
        await voice.disconnect()
        activity = discord.Activity(name='Python', type=discord.ActivityType.playing)
        await bot.change_presence(activity=activity)
        now_vc = None
        voice = None
        await ctx.message.delete()
        return

    @commands.command()
    async def bgminfo(self, ctx):
        """現在再生している曲のパスを表示する"""
        if (self.audio_status is None):
            await send_message(ctx.send, ctx.author.mention, 'This bot is not playing an Audio File')
        else:
            await send_message(ctx.send, ctx.author.mention, self.audio_status.playing_info())
        return

    @commands.command()
    async def bgm(self, ctx, *bgm_or_dir_name):
        """キューを使って再生"""
        name = ''
        for s in bgm_or_dir_name:
            name += s + ' '
        name = name[:-1]
        global voice, now_vc
        await self.reload_state()
        if (ctx.author.voice is None):
            await send_message(ctx.send, ctx.author.mention, 'ボイスチャンネルが見つかりません')
            return
        
        if ((now_vc is None) or (now_vc != ctx.author.voice.channel)):  #vcに入っていなければ接続する
            now_vc = ctx.author.voice.channel
            voice = await bot.get_channel(now_vc.id).connect()
            self.audio_status = AudioStatus(voice)

        if (len(name) == 0):            #コマンド引数無しなら全ての曲を再生キューに追加
            numbers = [i for i in range(len(self.music_pathes))]
            random.shuffle(numbers)
            await ctx.message.delete()
            for i in numbers:
                await self.audio_status.add_audio(self.music_titles[i], self.music_pathes[i])
        elif (name in self.music_titles):    #曲名に一致した場合，該当する曲を再生キューに追加
            idx = self.music_titles.index(name)
            await ctx.message.delete()
            await self.audio_status.add_audio(name, self.music_pathes[idx])
        elif (name in self.mdir_name):       #ディレクトリ名に一致した場合，該当するディレクトリ下にある全ての曲を再生キューに追加
            idx = self.mdir_name.index(name)
            cur_path = os.getcwd()
            os.chdir(MUSIC_PATH + os.sep + self.music_dirs[idx])
            music_pathes = [p for p in glob('**', recursive=True) if os.path.isfile(p)]
            music_titles = [os.path.splitext(os.path.basename(path))[0] for path in music_pathes]
            os.chdir(cur_path)          #カレントディレクトリを戻す
            length = len(music_titles)
            for i in range(length):
                if (re.fullmatch(r'[0-9][0-9] .*', music_titles[i])):
                    music_titles[i] = (music_titles[i])[3:]
            numbers = [i for i in range(len(music_pathes))]
            random.shuffle(numbers)
            await ctx.message.delete()
            for i in numbers:
                await self.audio_status.add_audio(music_titles[i], MUSIC_PATH + os.sep + self.music_dirs[idx] + os.sep + music_pathes[i])
        else:                           #該当無し
            await send_message(ctx.send, '', 'Audio File Not Found')
        return

    @commands.command()
    async def loopbgm(self, ctx, *bgm_or_dir_name):
        """キューを使ってループ再生"""
        global voice, now_vc
        await self.reload_state()
        if (ctx.author.voice is None):
            await send_message(ctx.send, ctx.author.mention, 'ボイスチャンネルが見つかりません')
            return
        
        if ((now_vc is None) or (now_vc != ctx.author.voice.channel)):  #vcに入っていなければ接続する
            now_vc = ctx.author.voice.channel
            voice = await bot.get_channel(now_vc.id).connect()
            self.audio_status = AudioStatus(voice)

        for name in bgm_or_dir_name:
            if (len(name) == 0):            #コマンド引数無しなら全ての曲を再生キューに追加
                numbers = [i for i in range(len(self.music_pathes))]
                random.shuffle(numbers)
                await ctx.message.delete()
                for i in numbers:
                    await self.audio_status.add_audio(self.music_titles[i], self.music_pathes[i], isloop = True)
            elif (name in self.music_titles):    #曲名に一致した場合，該当する曲を再生キューに追加
                idx = self.music_titles.index(name)
                await ctx.message.delete()
                await self.audio_status.add_audio(name, self.music_pathes[idx], isloop = True)
            elif (name in self.mdir_name):       #ディレクトリ名に一致した場合，該当するディレクトリ下にある全ての曲を再生キューに追加
                idx = self.mdir_name.index(name)
                cur_path = os.getcwd()
                os.chdir(MUSIC_PATH + os.sep + self.music_dirs[idx])
                music_pathes = [p for p in glob('**', recursive=True) if os.path.isfile(p)]
                music_titles = [os.path.splitext(os.path.basename(path))[0] for path in music_pathes]
                os.chdir(cur_path)          #カレントディレクトリを戻す
                length = len(music_titles)
                for i in range(length):
                    if (re.fullmatch(r'[0-9][0-9] .*', music_titles[i])):
                        music_titles[i] = (music_titles[i])[3:]
                numbers = [i for i in range(len(music_pathes))]
                random.shuffle(numbers)
                await ctx.message.delete()
                for i in numbers:
                    await self.audio_status.add_audio(music_titles[i], MUSIC_PATH + os.sep + self.music_dirs[idx] + os.sep + music_pathes[i], isloop = True)
            else:                           #該当無し
                await send_message(ctx.send, '', f'{name} Not Found')
        return

    @commands.command()
    async def pause(self, ctx):
        """再生中のbgmの一時停止"""
        if (self.audio_status.is_playing()):
            self.audio_status.vc.pause()
        await ctx.message.delete()
        return
        
    @commands.command()
    async def resume(self, ctx):
        """再生中のbgmの再開"""
        self.audio_status.vc.resume()
        await ctx.message.delete()
        return

    @commands.command()
    async def stop(self, ctx):
        """再生中のbgmの中断"""
        if (self.audio_status.is_playing()):
            self.audio_status.vc.stop()
        return

    @commands.command()
    async def clear(self, ctx):
        """再生キューのリセット"""
        self.audio_status.queue.reset()
        return
    
    @commands.command()
    async def queue(self, ctx):
        """再生キューの表示"""
        await send_message(ctx.send, '', [x[0] for x in self.audio_status.queue], title = '再生キュー', isembed = True, half = True)
        return

    @commands.command()
    async def findbgm(self, ctx, filename):
        """指定した文字列を含む音楽ファイルを返す"""
        if (len(filename) == 0):
            await send_message(ctx.send, ctx.author.mention, '検索ワードを指定してください')
        else:
            await send_message(ctx.send, ctx.author.mention, ["/".join(pathlib.Path(d).parts[-2:]) for f, d in zip(self.music_titles, self.music_pathes) if (filename in f)], half = True, title = '「' + filename + '」の検索結果', isembed = True)
            #なぜか\\.joinにすると偶にembedがバグる
        return

    @commands.command()
    async def bgmlist(self, ctx, *dir_name):
        """一覧"""
        cur_path = os.getcwd()
        os.chdir(MUSIC_PATH)        #カレントディレクトリの移動
        dirname = ''
        for s in dir_name:          #引数を1つの文字列に纏める
            dirname += s + ' '
        dirname = dirname[:-1]
        if (len(dirname) == 0):     #引数無しなら全てのディレクトリを表示
            await self.send_tree(ctx=ctx, path=MUSIC_PATH+os.sep+'Music')
        else:
            for f in self.music_dirs:                                            
                if (dirname == pathlib.Path(f).parts[-1]):                  #ディレクトリ名と引数が一致した場合，表示
                    current = f.split(os.sep)[1:][0]
                    print(dirname)
                    tree = cmd_bgm.make_filetree(MUSIC_PATH+os.sep+f[:-1*len(os.sep)])
                    if (len(tree) != 1):                                    #該当ディレクトリの下にディレクトリがあった場合は木構造を表示
                        result = await send_message(ctx.send, '', tree, delimiter = ['\n'+'....'*i+'├' for i in range(10)])
                        if (result is None):
                            nest = cmd_bgm.depth(tree)
                            await self.send_tree(ctx=ctx, path=MUSIC_PATH+os.sep+f, nest = nest-1)
                    else:                                                   #ディレクトリを持たなければオーディオファイルの一覧を表示
                        os.chdir(MUSIC_PATH + os.sep + f)
                        music_titles = [os.path.splitext(os.path.basename(p))[0] for p in glob('*', recursive=True) if os.path.isfile(p)]
                        length = len(music_titles)
                        for i in range(length):
                            if (re.fullmatch(r'[0-9][0-9] .*', music_titles[i])):
                                music_titles[i] = (music_titles[i])[3:]
                        await send_message(ctx.send, '', music_titles)
                    break
        os.chdir(cur_path)      #カレントディレクトリを戻す
        return
    
    @commands.command()
    async def addbgm(self, ctx, *info):
        """bgmの追加：infoはファイルパス"""
        cur_path = os.getcwd()
        os.chdir(MUSIC_PATH)
        attach = ctx.message.attachments    #=添付ファイル
        if (attach and len(info) > 1):      #添付ファイルが存在するとき
            fpath = ''
            for p in info[:-1]:             #保存するファイルパスの作成
                fpath += p + os.sep
            filepath = MUSIC_PATH + os.sep + 'Music' + os.sep + fpath + info[-1] + os.path.splitext(attach[0].url)[-1]  #拡張子は元ファイル参照
            os.makedirs(os.path.dirname(filepath), exist_ok=True)   #ディレクトリが無ければ作成
            result = await image_.audio_dl(attach[0].url, filepath) #添付ファイルのDL
            if (result):
                await send_message(ctx.send, ctx.author.mention, '追加しました')
                print(f'addbgm:{info}')
            else:
                await send_message(ctx.send, ctx.author.mention, '失敗しました')
        os.chdir(cur_path)
        self.search_audiofiles()
        return

@bot.command()
async def shuffle(ctx, *arguments):
    """与えられた要素をシャッフル"""
    await send_message(ctx.send, ctx.author.mention, cmd_other.shuffle(list(arguments)), title = '結果')
    return
        
@bot.command()
async def bkp(ctx):
    """botのデータのバックアップを取る"""
    if (ctx.message.author.top_role.id != int(role_id['host'])):
        await send_message(ctx.send, ctx.author.mention, '権限が足りません')
        return
    channel  = bot.get_channel(int(channel_id['bkp']))
    filelist = ['Stock.txt', 'cmdsql.pickle']
    result = await cmd_system.bkp(channel.send, filelist, MAINPATH+'/Data')
    if (result):
        mes = 'バックアップを取りました'
    else:
        mes = 'バックアップに失敗しました'
    await send_message(ctx.send, ctx.author.mention, mes)
    return

#################################
#SQLite
#################################
class __Status(commands.Cog, name = '数値確認'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    async def send_err(self, ctx, errtype, msg):
        if (errtype == -1):
            await send_message(ctx.send, ctx.author.mention, 'エラー：'+msg+'が見つかりませんでした')
        if (errtype == -2):
            await send_message(ctx.send, ctx.author.mention, msg, title = 'もしかして')
        if (errtype == -3):
            await send_message(ctx.send, ctx.author.mention, 'エラー：引数の数が不正です')
        return

    @commands.command()
    async def st(self, ctx, *pokedata):
        """種族値の表示，数値を書くと該当Lvでの実数値を表示"""
        res, result = cmd_status.st(pokedata)
        if (res == 1):
            print('status')
            await send_message(ctx.send, ctx.author.mention, list(result), delimiter = ['\n', '-'], isembed = False)
        else:
            await self.send_err(ctx, res, result)
        return

    @commands.command()
    async def korippo(self, ctx, poke):
        """コオリッポ算"""
        res, result = cmd_status.korippo(poke)
        if (res == 1):
            print('korippo->'+poke)
            await send_message(ctx.send, ctx.author.mention, result + '(/コオリッポ)です')
        else:
            await self.send_err(ctx, res, result)
        return

    @commands.command()
    async def calciv(self, ctx, poke, lv, *args):
        """個体値チェック"""
        res, result = cmd_status.calciv(poke, lv, args)
        if (res == 1):
            print('checkiv->'+poke)
            await send_message(ctx.send, ctx.author.mention, result, delimiter = [' - ', '～'], isembed = False)
        else:
            await self.send_err(ctx, res, result)
        return
    
    @commands.command()
    async def lang(self, ctx, *keyword_lang):
        """日本語→外国語"""
        res, result = cmd_status.lang(keyword_lang)
        if (res == 1):
            print('lang->'+str(keyword_lang))
            await send_message(ctx.send, ctx.author.mention, result)
        else:
            await self.send_err(ctx, res, result)
        return

    @commands.command()
    async def puzzle(self, ctx, *ivs):
        """個体値パズルの可否を判定"""
        res, result = cmd_status.ivpuzzle(ivs)
        if (res == 1):
            print('puzzle->'+ ivs)
            await send_message(ctx.send, ctx.author.mention, result, isembed=False)
        else:
            await self.send_err(ctx, res, result)
        return

class __SQL(commands.Cog, name = 'SQL'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def make_err(self, ctx, errtype):
        if (errtype == -1):
            await send_message(ctx.send, ctx.author.mention, 'エラー：コマンドが不適切です')
        if (errtype == -2):
            await send_message(ctx.send, ctx.author.mention, 'エラー：既に定義されています')
        if (errtype == -3):
            await send_message(ctx.send, ctx.author.mention, 'エラー：コマンドが登録されていません')
        if (errtype == -4):
            await send_message(ctx.send, ctx.author.mention, 'エラー：コマンドが見つかりません')
        if (errtype == -5):
            await send_message(ctx.send, ctx.author.mention, '<:9mahogyaku:766976884562198549>')
        return

    @commands.command()
    async def editsql(self, ctx, *sqlcmdname_information):
        """登録したSQLコマンドに説明を加える"""
        return

    @commands.command()
    async def addsql(self, ctx, *cmd_SQL):
        """新規SQL文の登録"""
        return
      
    @commands.command()
    async def psql(self, ctx, *cmd_SQL):
        """登録済みSQL文の表示"""
        res, text = cmd_sql.showsql(cmd_SQL, SQLCMD_PATH)
        if (res == 1):
            await send_message(ctx.send, ctx.author.mention, text, title = '', delimiter = ['\n'])
        elif (res == 2):
            if (len(text) == 0):
                text = ''
            elif (len(text) == 1):
                text = '\n・'+text[0][0]+'\n'+text[0][1]
            else:
                text[0][0] = '・' + text[0][0]
            await send_message(ctx.send, ctx.author.mention, text, title = '', delimiter = ['\n・', '：\n    '])
        else:
            await self.make_err(ctx, res)
        return

    @commands.command()
    async def psqlcmd(self, ctx, *cmd_SQL):
        """登録済みSQLコマンドのSQL文の表示"""
        res, text = cmd_sql.print_sql_command(cmd_SQL, SQLCMD_PATH)
        if (res == 1):
            await send_message(ctx.send, ctx.author.mention, text, title = '', delimiter = ['\n'])
        elif (res == 2):
            if (len(text) == 0):
                text = ''
            elif (len(text) == 1):
                text = '\n・'+text[0][0]+'\n'+text[0][1]
            else:
                text[0][0] = '・' + text[0][0]
            await send_message(ctx.send, ctx.author.mention, text, title = '', delimiter = ['\n・', '：\n    '])
        else:
            await self.make_err(ctx, res)
        return

    @commands.command()
    async def delsql(self, ctx, cmd):
        """登録済みSQL文の削除"""
        res = cmd_sql.delsql(cmd, SQLCMD_PATH)
        if (res == 1):
            await send_message(ctx.send, ctx.author.mention, ' 削除しました')
        else:
            await self.make_err(ctx, res)
        return

class __Home(commands.Cog, name = 'Home'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    def getbattlerule(self, args, argnum):
        battlerule = 1
        rate = []
        if (len(args) == argnum+1):
            for i in range(argnum):
                rate.append(args[i+1])
            if (args[0] == '2' or args[0] == '1'):
                battlerule = int(args[0])
            else:
                return [-1], None
        elif (len(args) == argnum):
            for i in range(argnum):
                rate.append(args[i])
        else:
            return [-2], None
        try:
            intrate = [int(i) for i in rate]
        except:
            return [-3], None
        return intrate, battlerule
        
    def getbattlerulestr(self, args, argnum):
        battlerule = 1
        s = []
        if (len(args) == argnum+1):
            for i in range(argnum):
                s.append(args[i+1])
            if (args[0] == '2' or args[0] == '1'):
                battlerule = int(args[0])
            else:
                return [-1], None
        elif (len(args) == argnum):
            for i in range(argnum):
                s.append(args[i])
        else:
            return [-2], None
        return s, battlerule
    
    async def printerror(self, ctx):
        await ctx.send(f'{ctx.author.mention} 引数が間違っています')
        return
    
    @commands.command()
    async def rank(self, ctx, *battlerule_rate):
        """レートに対応する順位を求める"""
        rate, battlerule = self.getbattlerule(battlerule_rate, 1)
        if (battlerule == None):
            await self.printerror(ctx)
            return
        rate = rate[0]
        print('rank:'+str(rate))
        success = await cmd_home.get_rank(ctx, rate, battlerule)
        if (success == 0):
            await send_message(ctx.send, ctx.author.mention, 'データの取得に失敗しました')
            return
        return

    @commands.command()
    async def rate(self, ctx, *battlerule_rank):
        """順位に対応するレートを求める"""
        rank, battlerule = self.getbattlerule(battlerule_rank, 1)
        if (battlerule == None):
            await self.printerror(ctx)
            return
        rank = rank[0]
        print('rate:'+str(rank))
        success = await cmd_home.get_rate(ctx, rank, battlerule)
        if (success == 0):
            await send_message(ctx.send, ctx.author.mention, 'データの取得に失敗しました')
            return
        return

    @commands.command()
    async def pokerank(self, ctx, *battlerule_upper_lower):
        """ポケモンの使用率を求める"""
        rank, battlerule = self.getbattlerule(battlerule_upper_lower, 2)
        if (battlerule == None):
            await self.printerror(ctx)
            return
        print('pokerank:'+str(rank))
        pokelist, update_time = await cmd_home.pokerank(ctx, rank, battlerule)
        if (len(pokelist) <= 0):
            await send_message(ctx.send, ctx.author.mention, 'No data('+update_time+')')
            return
        await send_message(ctx.send, ctx.author.mention, pokelist)
        await send_message(ctx.send, '', '('+update_time+')')
        return

    @commands.command()
    async def pokeinfo(self, ctx, *battle_rule_pokename):
        """ホームのポケモンの情報を求める"""
        name, battlerule = self.getbattlerulestr(battle_rule_pokename, 1)
        print('pokeinfo:'+str(name))
        if (battlerule == None):
            await self.printerror(ctx)
            return
        res, update_time = await cmd_home.pokeinfo(ctx, name[0], battlerule)
        if (len(res) <= 0):
            await send_message(ctx.send, ctx.author.mention, '\nNo data\n('+update_time+')')
            return
        print(update_time)
        await send_message(ctx.send, '', '('+update_time+')')
        return

##  改行を伴うコマンドの受け付け
@bot.event
async def on_message(message):
    content = message.content
    if (len(content) == 1):
        return
    head = content[:11].lower()
    if head == '!sql select':
        with message.channel.typing():
            res, result = cmd_sql.playsql(iter(content))
            if (res == 1):
                await send_message(message.channel.send, message.author.mention, result, delimiter = ['\n', ','])
            else:
                await send_message(message.channel.send, message.author.mention, result)
        return
    
    head = content[:9].lower()
    if head == '!editsql ':
        await send_message(message.channel.send, message.author.mention, cmd_sql.editsql(iter(content), SQLCMD_PATH))
        return
    
    if head[:8] == '!addsql ':
        res, cmd = cmd_sql.addsql(content[8:].split(), SQLCMD_PATH)
        if (res == 1):
            await send_message(message.channel.send, message.author.mention, 'コマンド「'+cmd+'」が登録されました')
            print('addcmd='+cmd)
        else:
            if (res == -1):
                await send_message(message.channel.send, message.author.mention, 'エラー：コマンドが不適切です')
            if (res == -2):
                await send_message(message.channel.send, message.author.mention, 'エラー：既に定義されています')
            if (res == -3):
                await send_message(message.channel.send, message.author.mention, 'エラー：コマンドが登録されていません')
            if (res == -4):
                await send_message(message.channel.send, message.author.mention, 'エラー：コマンドが見つかりません')
            if (res == -5):
                await send_message(message.channel.send, message.author.mention, '<:9mahogyaku:766976884562198549>')
        return

    if head[:8] == '!showsql':
        res, text = cmd_sql.showsql(content[8:].split(), SQLCMD_PATH)
        if (res == 1):
            await send_message(message.channel.send, message.author.mention, text, title = '', delimiter = ['\n'])
        elif (res == 2):
            if (len(text) == 0):
                text = ''
            elif (len(text) == 1):
                text = '\n・'+text[0][0]+'\n'+text[0][1]
            else:
                text[0][0] = '・' + text[0][0]
            await send_message(message.channel.send, message.author.mention, text, title = '', delimiter = ['\n・', '：\n    '])
        else:
            await self.make_err(message, res)
        return
    
    if(content.startswith('?')):
        with message.channel.typing():
            res, result = cmd_sql.registered_sql(content, SQLCMD_PATH)
            if (res == 1):
                await send_message(message.channel.send, message.author.mention, result, delimiter = ['\n', ','])
            else:
                await send_message(message.channel.send, message.author.mention, result)
        return

    if(content.startswith('=')):
        res, result = cmd_other.calc(content)
        if (res == 1):
            print('calc')
            await send_message(message.channel.send, message.author.mention, result)
        else:
            await send_message(message.channel.send, message.author.mention, result, title = '不明な文字')
        return
    
    await bot.process_commands(message)
    return

#発言の削除
@bot.event
async def on_raw_reaction_add(payload):
    if (payload.emoji.name == 'jomei'):
        channel = bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if (is_me(message)):
            await message.delete()
            print(payload.member.name + ' has deleted bot comment')
    return
        
################################
#VC
################################
@bot.event
async def on_voice_state_update(member, before, after):
    global voice, vc_state, now_vc
    if (member == bot.user):
        return
    result = await vc.move_member(member, before, after, int(config.get('DEFAULT', 'server')), [int(channel_id['afk']), int(channel_id['afk2'])])
    vc_state += result[0]
    if (result[1] == 1 and vc_state == 1):
        print('通話開始')
        #channel = bot.get_channel(int(channel_id['call']))
        #role = bot.get_guild(int(config.get('DEFAULT', 'server'))).get_role(int(role_id['call']))
        #await channel.send(f'{role.mention} 通話が始まりました')
    elif ((now_vc is not None) and (len(now_vc.members) == 1) and (voice is not None)):
        await voice.disconnect()
        activity = discord.Activity(name='Python', type=discord.ActivityType.playing)
        await bot.change_presence(activity=activity)
        voice = None
        now_vc = None
    return

bot.add_cog(__Status(bot=bot))
bot.add_cog(__SQL(bot=bot))
bot.add_cog(__Home(bot=bot))
bot.add_cog(__BGM(bot=bot))
bot.run(TOKEN)
