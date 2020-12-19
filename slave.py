import discord
from discord.ext import commands
import os
import sys
import re
import asyncio
import configparser
sys.path.append(os.path.join(os.path.dirname(__file__), 'Commands'))
import cmd_raid
import cmd_card
import cmd_status
import cmd_sql
import cmd_home
import cmd_system
import cmd_other
import cmd_event
import vc
import rw_csv
import userinfo

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

vc_state     = 0                        #ボイスチャンネルにいる人の数を0で初期化
TOKEN_PATH   = get_path('token')
STOCK_PATH   = get_path('stock')
IMG_PATH     = get_path('img')
SQLCMD_PATH  = get_path('sql_cmd')
EVENT_PATH   = get_path('event')

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

#botの作成
bot = commands.Bot(command_prefix='!', help_command=JapaneseHelpCommand())

# bot起動時に"login"と表示
@bot.event
async def on_ready():
    activity = discord.Activity(name='Python', type=discord.ActivityType.playing)
    await bot.change_presence(activity=activity)
    print('login\n')

#コマンドに関するエラー
@bot.event
async def on_command_error(ctx, error):
    print(type(error))
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

def listcontent(list_):
    if (type(list_) is not list):
        return list_
    return listcontent(list_[0])

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

async def send_message(send_method, mention, mes, title = 'Result', delimiter = ['\n'], isembed = True):
    message = None
    mtype = type(mes)
    if (mtype is list):
        if (len(mes) == 0):
            message = await send_method(f'{mention} 該当するデータがありません')
        elif (len(mes) == 1 and mtype is not list):
            message = await send_method(f'{mention} ' + listcontent(mes))
            
        else:
            reply = list2str(mes, delimiter)
            if (isembed):
                try:
                    embed = discord.Embed(title=title, description=reply)
                    message = await send_method(f'{mention} ', embed=embed)
                except:
                    message = await send_method(f'{mention} エラー：該当するデータが多すぎます')
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

async def confirm(member):
    def check_y(m):
        return (m.content == 'y') and (m.author == member)
    try:
        await bot.wait_for('message', check=check_y, timeout=30.0)
    except asyncio.TimeoutError:
        return False
    else:
        return True

async def del_message(_channel, mes_id):
    channel = bot.get_channel(_channel)
    try:
        message = await channel.fetch_message(mes_id)
        if is_me(message):
            await message.delete()
    except:
        pass
    return

class __Roles(commands.Cog, name = '役職の管理'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    def select_roll(self, role):
        if role == 'slave' or role == 'call':
            return int(role_id[role])
        return None
        
    def exist_role(self, ctx, role):
        r = self.select_roll(role)
        if (r == None):
            return None
        return ctx.message.guild.get_role(r)

    @commands.command()
    # 役職の付与
    async def add(self, ctx, role):
        """役職を付与：slave->レイドの奴隷、call->通話通知"""
        r = self.exist_role(ctx, role)
        print(r)
        if (r == None):
            await send_message(ctx.send, ctx.author.mention, role+'オプションは実装されていません\n実装済みのオプション：\'slave\', \'call\'')
        else:
            print(str(ctx.message.author.name)+'->'+str(role))
            await ctx.author.add_roles(r)
            await send_message(ctx.send, ctx.author.mention, '役職を追加しました')
        return
        
    # 役職の解除
    @commands.command()
    async def rm(self, ctx, role):
        """役職を解除"""
        r = self.exist_role(ctx, role)
        if (r == None):
            await send_message(ctx.send, ctx.author.mention, role+'オプションは実装されていません\n実装済みのオプション：\'slave\', \'call\'')
        else:
            print(str(ctx.message.author.name)+' del '+str(role))
            await ctx.author.remove_roles(r)
            await send_message(ctx.send, ctx.author.mention, '役職を削除しました')
        return

class __Raid(commands.Cog, name = 'レイド関連'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    def make_err(self, res):
        if (res[0] == -1):
            return 'ポケモン名が短すぎます。ポケモン名は3文字以上にしてください。'
        if (res[0] == -2):
            return res[1]+'\nのレイドは開催済みです'
        return
        
    # 在庫の確認
    @commands.command()
    async def check(self, ctx, poke):
        """レイドが開催済みかどうかを検索"""
        print('check:' + poke)
        res = cmd_raid.process_raid_check(poke, STOCK_PATH)
        if (res[0] == 1):
            await send_message(ctx.send, ctx.author.mention, str(poke) + 'レイドのデータはありません')
        else:
            await send_message(ctx.send, ctx.author.mention, self.make_err(res))
        return
        
    @commands.command()
    async def store(self, ctx, poke):
        """開催済みレイドの追加"""
        print('add:' + poke)
        res = cmd_raid.process_raid_add(poke, STOCK_PATH)
        if (res[0] == 1):
            await send_message(ctx.send, ctx.author.mention, str(poke) + 'レイドを登録しました')
        else:
            await send_message(ctx.send, ctx.author.mention, self.make_err(res))
        return

    @commands.command()
    async def raid(self, ctx, cmd, poke):
        """レイド関連のコマンド：add->store, check, del:削除（HOSTのみ使用可)"""
        if (cmd == 'add'):
            self.store(ctx, poke)
            return
        if (cmd == 'check'):
            self.check(ctx, poke)
            return
        if (cmd == 'del'):
            if (ctx.message.author.top_role.id != int(role_id['host'])):
                await send_message(ctx.send, ctx.author.mention, '権限が足りません')
                return
            print('del:' + poke)
            res = cmd_raid.process_raid_del(poke, int(role_id['host']), STOCK_PATH)
            if (res[0] == 1):
                await send_message(ctx.send, ctx.author.mention, '\n' + str(poke) + 'レイドを削除しました')
            elif (res[0] == 0):
                await send_message(ctx.send, ctx.author.mention, '\n' + str(poke) + 'レイドが見つかりませんでした')
            else:
                await send_message(ctx.send, ctx.author.mention, self.make_err(res))
            return
        return

class __Event(commands.Cog, name= 'イベント管理'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.event_status = rw_csv.read_csv(EVENT_PATH)
    
    def have_authority(self, author, organizer):
        return (author.top_role.id == int(role_id['host'])) or (str(author.id) == organizer)

    def delete_event(self, num):
        del self.event_status[num]
        rw_csv.write_csv(EVENT_PATH, self.event_status)
        return

    async def send_err(self, ctx, errtype):
        if(errtype >= 0):
            await send_message(ctx.send, ctx.author.mention, 'エラー:同名のイベントが既に登録されています')
        if(errtype == -1):
            await send_message(ctx.send, ctx.author.mention, 'エラー:イベントが見つかりません')
        if(errtype == -2):
            await send_message(ctx.send, ctx.author.mention, 'エラー:この動作はイベントの企画者かHOSTにのみ許可されています')

    @commands.command()
    async def plan(self, ctx, name, *detail):
        """イベントの企画"""
        overlapping = cmd_event.lookup_ev(name, self.event_status)
        if (overlapping != -1):
            await self.send_err(ctx, overlapping)
        else:
            txt = '\n'.join(detail)
            embed = discord.Embed(title='[イベント告知] '+name, description=txt+'\n参加したい方はこの投稿にリアクションをつけてください。')
            channel = bot.get_channel(int(channel_id['event']))
            msg = await channel.send(embed=embed)
            self.event_status.append([str(msg.id), name, txt, str(ctx.author.id)])
            rw_csv.write_csv(EVENT_PATH, self.event_status)
            print('plan event\nev_name:' +name+ '\nev_id:' +str(msg.id)+ '\n')
        return

    @commands.command()
    async def cancel(self, ctx, ev_name):
        """イベントのキャンセル"""
        exists = cmd_event.lookup_ev(ev_name, self.event_status)
        if (exists == -1):
            await self.send_err(ctx, exists)
        else:
            target_ev = self.event_status[exists]
            if self.have_authority(ctx.author, target_ev[3]):
                await send_message(ctx.send, ctx.author.mention, '%sを本当に削除しますか？\n削除 -> \' y \'\n※この動作は30秒後にキャンセルされます。'%target_ev[1])
                confirmation = await confirm(ctx.author)
                if (confirmation):
                    self.delete_event(exists)
                    await del_message(int(channel_id['event']), int(target_ev[0]))
                    print('delete event\nev_name:%s\n'%target_ev[1])
                    await send_message(ctx.send, ctx.author.mention, target_ev[1] + 'を削除しました')
                else:
                    await send_message(ctx.send, ctx.author.mention, '削除をキャンセルしました')
            else:
                await self.send_err(ctx, -2)
        return 

    @commands.command()
    async def start(self, ctx, ev_name):
        """イベントの開始"""
        exists = cmd_event.lookup_ev(ev_name, self.event_status)
        if (exists == -1):
            await self.send_err(ctx, exists)
        else:
            current_ev = self.event_status[exists]
            print(exists)
            print(current_ev)
            if self.have_authority(ctx.author, current_ev[3]):
                await send_message(ctx.send, ctx.author.mention, '参加者募集を締め切って%sを開始してもよろしいですか？\n開始 -> \' y \'\n※この動作は30秒後にキャンセルされます。'%current_ev[1])
                confirmation = await confirm(ctx.author)
                if (confirmation):
                    channel = bot.get_channel(int(channel_id['event']))
                    players = await cmd_event.get_players(int(current_ev[0]), channel)
                    if (len(players) > 0):
                        await send_message(channel.send, '', '%sを開始します。\n参加メンバー：\n'%current_ev[1] + '\n'.join(map(userinfo.get_mention, players)))
                        self.delete_event(exists)
                        print('start event\nev_name:%s\nplayers\n'%current_ev[1] + '\n'.join(map(userinfo.get_username, players)))
                    else:
                        await send_message(ctx.send, ctx.author.mention, '参加者がいません')
                else:
                    await send_message(ctx.send, ctx.author.mention, 'イベントの開始をキャンセルしました')
            else:
                await self.send_err(ctx, -2)

@bot.command()
async def shuffle(ctx, *arguments):
    """与えられた要素をシャッフル"""
    await send_message(ctx.send, ctx.author.mention, cmd_other.shuffle(list(arguments)), title = '結果')
    return

@bot.command()
async def card(ctx, *pokes):
    """簡易な構築の画像を生成"""
    #ユーザーアイコンDL
    await ctx.message.author.avatar_url.save(IMG_PATH+'user.png', seek_begin = True)
    res, candidate = await cmd_card.makecard(pokes, IMG_PATH)
    file_img = discord.File(IMG_PATH+'out.jpg')
    await ctx.send(file=file_img)
    await ctx.message.delete()
    if (res == 0):
        if (len(candidate) == 1):
            candidate.append([''])
        await send_message(ctx.send, ctx.author.mention, candidate, delimiter = ['\n', '\n'], title = 'もしかして')
    return
        
@bot.command()
async def bkp(ctx):
    """botのデータのバックアップを取る"""
    if (ctx.message.author.top_role.id != int(role_id['host'])):
        await send_message(ctx.send, ctx.author.mention, '権限が足りません')
        return
    channel  = bot.get_channel(int(channel_id['bkp']))
    filelist = ['Stock.txt', 'cmdsql.pickle', 'event_status.csv']
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
            print(result)
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
    async def addsql(self, ctx, *cmd_SQL):
        """新規SQL文の登録"""
        res, cmd = cmd_sql.addsql(cmd_SQL, SQLCMD_PATH)
        if (res == 1):
            await send_message(ctx.send, ctx.author.mention, 'コマンド「'+cmd+'」が登録されました')
            print('addcmd='+cmd)
        else:
            await self.make_err(ctx, res)
        return
      
    @commands.command()
    async def showsql(self, ctx, *cmd_SQL):
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
            await send_message(ctx.send, ctx.author.mention, 'No data('+update_time+')')
            return
        print(update_time)
        await send_message(ctx.send, '', '('+update_time+')')
        return

##  改行を伴うコマンドの受け付け
@bot.event
async def on_message(message):
    content = message.content
    head = content[:11].lower()
    if head == '!sql select':
        if (message.channel.id != int(channel_id['sql']) and message.channel.guild.id != int(channel_id['myserver1']) and message.channel.guild.id != int(channel_id['myserver2'])):
            return
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
    if (payload.emoji.name == '8jyomei'):
        channel = bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        exists = cmd_event.lookup_ev2(str(payload.message_id), __Event(bot=bot).event_status)
        if (is_me(message) and exists == -1):
            await message.delete()
            print(payload.member.name + ' has deleted bot comment')
    return
        
################################
#VC
################################
@bot.event
async def on_voice_state_update(member, before, after):
    global vc_state
    result = await vc.move_member(member, before, after, int(config.get('DEFAULT', 'server')), [int(channel_id['afk'])])
    vc_state += result[0]
    if (result[1] == 1 and vc_state == 1):
        print('通話開始')
        channel = bot.get_channel(int(channel_id['call']))
        role = bot.get_guild(int(config.get('DEFAULT', 'server'))).get_role(int(role_id['call']))
        await channel.send(f'{role.mention} 通話が始まりました')
        
bot.add_cog(__Roles(bot=bot))
bot.add_cog(__Raid(bot=bot))
bot.add_cog(__Status(bot=bot))
bot.add_cog(__SQL(bot=bot))
bot.add_cog(__Home(bot=bot))
bot.add_cog(__Event(bot=bot))
bot.run(TOKEN)
