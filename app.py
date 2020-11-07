# 大致做一个，用户输入某个店铺关键词，查询和该关键词相关的地点/店铺，全国有哪些城市有，每个城市有多少
# 用户输入一个地点，输出默认半径1公里的交通态势-- 整个区域的整体交通状况、区域内路段的交通状况
# 查询天气
from flask import Flask, render_template, url_for
from flask_bootstrap import Bootstrap
import time, os, json
import requests
import pandas as pd
import jieba
import matplotlib.pyplot as plt
from datetime import timedelta
from bs4 import BeautifulSoup
import re

# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

#              请关闭 flask debug模式 下面的代码才能跑
#               启动程序后会需要你输入一个密钥解密码

# 下面的ak、sk为 百度情感分析的接口密钥，这个请自己去申请一个，反正是免费申请的
# myKey 是 高德地图的 接口key，也是免费申请的，请自己申请
# 为了防止我申请的账户被超额使用，这里我进行了简单的加密（真的很垃圾的加密哈哈哈，我专业是学密码）
import  base64
mykey_bs64 = 'OWE3cXU9cHJlc2VudCBieSBSLkcuNTk5ODQ4Y2Y0NmUxYmMwMjA5NjVlOTMzNGMxMDMzNDc='
ak_bs64 = 'OWE3cXU9cHJlc2VudCBieSBSLkcubURhS3oxNHY1TnBzb2V1ZXh5WDVEQTJ0'
sk_bs64 = 'OWE3cXU9cHJlc2VudCBieSBSLkcuZm5Gdlc5ejk0Mnc1VXRoZVo0ZnhuZ2lzMmZ5WEtwamM='

keyStart = int(input('key start postion='))
ak = base64.b64decode(ak_bs64.encode()).decode()[keyStart:]
sk = base64.b64decode(sk_bs64.encode()).decode()[keyStart:]
myKey = base64.b64decode(mykey_bs64.encode()).decode()[keyStart:]

# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

app = Flask(__name__)
bootstrap = Bootstrap(app)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(seconds=1)  # 将浏览器缓存时间设为1s，不然每次更新了静态图bar、pie，
# 都会默认读取缓存的，导致显示的不是最新的图片 。，。 不过好像没p用，直接在html页面加了 <meta>设置不缓存
SENSI_PATH = os.path.join(os.getcwd(), 'static', 'data', 'sensitive_words.xlsx')


# ++++++++++++++++++++++++++++++++++++++++++++++++++++++ bilibili 搜索页模块 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
@app.route('/bili_search')
def bili_search():
    return render_template('bili_search.html')

# ++++++++++++++++++++++++++++++++++++++++++++++++++++++ 获取视频信息模块 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/78.0.3904.108 Safari/537.36 '
}


def get_video_info(bvid=None, aid=None) -> dict:
    """
    获取视频信息：视频基本信息（发布时间、类型、时常etc）、发布者信息、视频播放相关数据
    参数：bvid、aid，均为str类型，两者选其一
    """
    api_base = 'http://api.bilibili.com/x/web-interface/view'
    # url = api_base + '?bvid={}'.format(bvid) if aid == None else api_base + '?aid={}'.format(aid)
    # 一行太丑了，还是展开吧
    if aid == None:
        url = api_base + '?bvid={}'.format(bvid)
    else:
        url = api_base + '?aid={}'.format(aid)
    try:
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            data = response.json()['data']
            # 提取视频基本信息
            discard_keys = ['state', 'attribute']
            discard_keys += list(data.keys())[-10:]  # 注意要把 dic.keys()转换成list才能和list（discard_keys）拼接
            if 'duration' in discard_keys:  # 有的视频，可能没设置版权啥的，所以上面-10切片会切掉时长，这里补进去
                discard_keys.remove('duration')
            video_basic_info = dict(
                (key, data[key]) for key in list(data.keys()) if key not in discard_keys
            )
            # 将时间戳换算成具体时间
            video_basic_info['pubdate'] = time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(video_basic_info['pubdate'])
            )
            video_basic_info['ctime'] = time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(video_basic_info['ctime'])
            )
            # 提取up主信息
            video_owner_info = data['owner']
            # 提取视频播放相关数据
            discard_keys = ['aid', 'now_rank', 'dislike', 'evaluation']
            video_stat_info = dict(
                (key, data['stat'][key]) for key in data['stat'].keys() if key not in discard_keys
            )
            return dict(video_basic_info, **video_owner_info, **video_stat_info)  # 拼接三个信息字典
        return {}
    except requests.exceptions.RequestException:
        print('Oops, something goes wrong!')
        time.sleep(3)
        return {}


@app.route('/video_info/<bvid>')
def video_info(bvid=None):
    video_info_dict = get_video_info(bvid)
    return render_template('video_info.html', bvid=bvid, video_data=video_info_dict)


# +++++++++++++++++++++++++++++++++++++++++++++++ 获取视频评论信息模块 ++++++++++++++++++++++++++++++++++++++++++++++++++++
def del_duplicate(dict_list) -> list:
    ''' 字典列表[{}] 去重 '''
    a = dict_list
    return [dict(tuple_item) for tuple_item in set([tuple(dict_in_a.items()) for dict_in_a in a])]


def get_video_comments(bvid=None, aid=None) -> list:
    '''获取视频的评论数据，【评论内容、发送者、发送时间、点赞数】'''
    base_api = 'http://api.bilibili.com/x/v2/reply/main'
    if aid == None:
        aid = get_video_info(bvid)['aid']  # 获取视频bvid
    bili_type = 1
    oid = aid  # 视频稿件必须用aid，bvid不行
    mode = 0  # 排序方式
    ps = 1
    # 每页项数，这里控制一项
    # up主置顶的那项在 top关键字里面，所以只需要读取一次top关键字的内容即可
    pg_next = 0  # 评论页选择，0
    cursor = False
    # ----------------------------------------------------------------------------------------------------------------
    # 先直接获取置顶评论，top
    url = base_api + '?type={}&oid={}&mode={}&ps={}&next={}'.format(
        bili_type, oid, mode, ps, 1  # 这里pg_next随便选一页就可以，置顶评论如果有则每页都会出现
    )
    response = requests.get(url, headers=headers)
    data = response.json()['data']
    top_comment_raw = data['top']
    comments = []
    if top_comment_raw['upper'] != None:
        # 获取楼层根评论
        try:
            comments.append(  # 获取楼层根评论
                {
                    'rpid': top_comment_raw['upper']['rpid'],  # 新增评论id
                    'msg': top_comment_raw['upper']['content']['message'],
                    'sender_id': top_comment_raw['upper']['member']['mid'],
                    'sender_name': top_comment_raw['upper']['member']['uname'],
                    'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(top_comment_raw['upper']['ctime'])),
                    'like': top_comment_raw['upper']['like']
                }
            )
        except:
            print("err!")
        replies = top_comment_raw['upper']['replies']  # 楼层根评论的回复评论-raw
        if replies != None:  # 有可能这一层只有根评论，没有回复评论
            # 获取楼层根评论的回复评论
            for reply in replies:
                comments.append(  # 获取楼层根评论的回复评论
                    {
                        'rpid': reply['rpid'],  # 新增评论id
                        'msg': reply['content']['message'],
                        'sender_id': reply['member']['mid'],
                        'sender_name': reply['member']['uname'],
                        'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(reply['ctime'])),
                        'like': reply['like']
                    }
                )
    # ----------------------------------------------------------------------------------------------------------------
    while not cursor:  # cursor == False, 即还没有到评论末页
        pg_next += 1  # 翻页
        # print(pg_next)
        url = base_api + '?type={}&oid={}&mode={}&ps={}&next={}'.format(  # 更新api的url
            bili_type, oid, mode, ps, pg_next
        )
        response = requests.get(url, headers)
        data = response.json()['data']  # 获取评论数据
        cursor = data['cursor']['is_end']  # 更新cursor
        if cursor:  # 如果到末页了，跳出循环
            break
        comments_raw = data['replies'][0]  # 获取评论raw数据
        # 获取楼层根评论
        try:
            comments.append(  # 获取楼层根评论
                {
                    'rpid': comments_raw['rpid'],  # 新增评论id
                    'msg': comments_raw['content']['message'],
                    'sender_id': comments_raw['member']['mid'],
                    'sender_name': comments_raw['member']['uname'],
                    'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(comments_raw['ctime'])),
                    'like': comments_raw['like']
                }
            )
        except:
            print("err!")
        replies = comments_raw['replies']  # 楼层根评论的回复评论-raw
        if replies != None:  # 有可能这一层只有根评论，没有回复评论
            # 获取楼层根评论的回复评论
            for reply in replies:
                comments.append(  # 获取楼层根评论的回复评论
                    {
                        'rpid': reply['rpid'],  # 新增评论id
                        'msg': reply['content']['message'],
                        'sender_id': reply['member']['mid'],
                        'sender_name': reply['member']['uname'],
                        'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(reply['ctime'])),
                        'like': reply['like']
                    }
                )

    return del_duplicate(comments)


def sensi_word_detector(seg_word_list, sensi_words_df) -> tuple:
    '''
        敏感词检测器，检测到第一个敏感词即停止，
        输出 有则(True，检测到的第一个敏感词，敏感词类型)，无则 (False,)
        seg_word_list：list，分词后的词序列
        sensi_word_list：list，敏感词列表，注意，如果是pandas读取的Series类型要转换成list
    '''
    flag = False
    for word in seg_word_list:
        if word in list(sensi_words_df['SENSITIVEWORDS']):
            flag = True
            tmp = sensi_words_df['SENSITIVETYPE'][
                sensi_words_df[sensi_words_df['SENSITIVEWORDS'] == word].index.tolist()[0]]
            return flag, word, tmp
    return (flag,)


def stupid_sender(comments_df, sensi_words_df) -> list:
    '''
    敏感词发送者捕获，输出 [{}]
    comments_df：pandas.dataframe，数据库读出来的评论df对象
    sensi_words_df：pandas.dataframe，读取的敏感词df对象
    '''
    stupid_comment_info = []
    for comment, index in zip(comments_df['msg'], comments_df.index.tolist()):
        seg_list = jieba.lcut(comment, cut_all=True)
        sensi_detector_result = sensi_word_detector(seg_list, sensi_words_df)
        if sensi_detector_result[0]:  # 有敏感词
            stupid_comment_info.append(
                {
                    'sender_id': comments_df['sender_id'].iloc[index],
                    'sender_name': comments_df['sender_name'].iloc[index],
                    'msg': comment,  # comments_df['msg'].iloc[index]
                    'sensi_word': sensi_detector_result[1],
                    'sensi_type': sensi_detector_result[2],
                    'time': comments_df['time'].iloc[index]
                }
            )
    return stupid_comment_info


def get_top_like(comments_df, top_num=10) -> list:
    '''
    获取点赞数top n的热评，默认10条
    点赞相同，按照时间先后排序，最新时间排序先
    '''
    if top_num > comments_df.shape[0]:  # 评论总数没到10条，则重置top_num
        print('top_num out of range!\n max={}'.format(comments_df.shape[0]))
        print('resign top_num={}'.format(comments_df.shape[0]))
        top_num = comments_df.shape[0]
    tmp_df = comments_df.sort_values(by=['like', 'time'], ascending=False).head(top_num)
    return [
        {
            'rpid': tmp_df.iloc[i]['rpid'],
            'msg': tmp_df.iloc[i]['msg'],
            'sender_id': tmp_df.iloc[i]['sender_id'],
            'sender_name': tmp_df.iloc[i]['sender_name'],
            'time': tmp_df.iloc[i]['time'],
            'like': tmp_df.iloc[i]['like']
        }
        for i in range(tmp_df.shape[0])
    ]


def get_access_token(ak: str, sk: str) -> str:
    '''
    获取baidu-api的access token
    ak为API Key，sk为Secret Key，需要通过百度账号申请
    '''
    api_base = 'https://aip.baidubce.com/oauth/2.0/token'
    grant_type = 'client_credentials'  # 固定为client_credentials
    url = api_base + '?grant_type={}&client_id={}&client_secret={}'.format(
        grant_type, ak, sk
    )
    response = requests.get(url, headers=headers)
    data = response.json()
    return data['access_token']


def get_comment_sentiment(comment: str, access_token: str) -> dict:
    '''利用baidu-api获取评论情感倾向'''
    api_base = 'https://aip.baidubce.com/rpc/2.0/nlp/v1/sentiment_classify'
    url = api_base + '?access_token={}'.format(access_token)
    text_json = json.dumps({'text': comment})
    response = requests.post(url, data=text_json, headers=headers)
    if response.status_code == 200:
        return response.json()['items'][0]
    else:
        'Resquest err !!!'
        return {}


def comments_sentiment_analyse(comments_list: list, ak: str, sk: str) -> dict:
    '''
    评论区情感分析统计
    画2个图：柱状图分析正负中立情绪的评论数量、饼图分析占比
    '''
    token = get_access_token(ak, sk)
    positive, negative, neutral = 0, 0, 0
    count = 0
    for comment in comments_list:
        time.sleep(0.5)  # 不加这个延迟，可能请求太频繁了，会出错
        count += 1
        print(count, comment['msg'])
        sentiment = get_comment_sentiment(comment['msg'], token)['sentiment']
        if sentiment == 2:
            positive += 1
        elif sentiment == 1:
            neutral += 1
        else:
            negative += 1
    result = {
        'positive': positive,
        'negative': negative,
        'neutral': neutral,
        'posiprop': positive / len(comments_list),
        'negprop': negative / len(comments_list),
        'neuprop': neutral / len(comments_list)
    }
    name_list = list(result.keys())[:3]
    value_list = list(result.values())[:3]
    # 清空画布
    plt.cla()
    # 画柱状图
    plt.bar(name_list, value_list, width=0.5, color=['firebrick', 'navy', 'limegreen'])
    plt.xlabel('Sentiment type')
    plt.ylabel('Amount')
    plt.title('Comments Sentiment Tendency')
    plt.ylim(ymin=0, ymax=max(value_list) + 20)
    for a, b in zip(name_list, value_list):
        plt.text(a, b + 0.05, '%.0f' % b, ha='center', va='bottom', fontsize=10)
    plt.savefig('./static/img/bar.png', dpi=500)
    # 清空画布
    plt.cla()
    # 画饼图
    explode = (0, 0, 0)  # 让positive 那部分脱离出来
    plt.pie(value_list, labels=name_list, autopct="%1.2f%%",
            colors=['lightcoral', 'slateblue', 'skyblue'], explode=explode)
    plt.axis('equal')
    # 添加标题
    plt.title("Comment Sentiment Proportion")
    plt.savefig('./static/img/pie.png', dpi=500)
    return result


@app.route('/video_comments/<bvid>')
def video_comments(bvid):
    comments_list = get_video_comments(bvid)
    count = len(comments_list)
    comments_df = pd.DataFrame(comments_list)  # 将字典列表[{}]转换成 df对象
    sensi_words_df = pd.read_excel(SENSI_PATH, sheet_name=0)
    top_likes = get_top_like(comments_df)
    sensi_comments_list = stupid_sender(comments_df, sensi_words_df)
    comments_sentiment_analyse(comments_list, ak, sk)
    return render_template('video_comments.html', bvid=bvid, count=count, top_likes=top_likes,
                           sensi_comments_list=sensi_comments_list)





# ++++++++++++++++++++++++++++++++++++++++++++++++++++++ 交通态势抓取模块 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
@app.route('/traffic')
def traffic_entry():
    return render_template('traffic.html', address=None, jsonData=None)


# 输入 杭州电子科技大学 这种有明显具体城市的关键字，这种关键字才会返回 pois 字段
# 输入 新华书店 这种比较泛的地址，不会返回 pois 因此不要输入这种地址
def getAddrPos(address):  # 这个函数
    baseAPI = 'https://restapi.amap.com/v3/place/text?'
    output = 'json'
    offset = '20'  # 每页记录数据,不能大于25
    page = '1'
    extensions = 'all'
    url = baseAPI + 'key={}&keywords={}&offset={}&page={}&extensions={}&output={}'.format(myKey, address, offset, page,
                                                                                          extensions, output)
    response = requests.get(url)
    jsonData = response.json()
    return jsonData['pois'][0]['location']


@app.route('/traffic/<addr>')
def getTrafficInfo(addr, radius=1000):  # 获取圆形区域交通态势
    location = getAddrPos(addr)
    baseAPI = 'https://restapi.amap.com/v3/traffic/status/circle?'
    output = 'json'
    level = '5'
    url = baseAPI + 'key={}&location={}&radius={}&level={}&extensions=all&output={}'.format(myKey, location, radius,
                                                                                            level, output)
    response = requests.get(url)
    jsonData = response.json()
    return render_template('traffic.html', address=addr, jsonData=jsonData)


# ++++++++++++++++++++++++++++++++++++++++++++++++++++++ 关键词地点抓取模块 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
@app.route('/search')
def search_entry():
    return render_template('search.html', keywords=None)


@app.route('/search/<keywords>')
# 不要输入 杭州电子科技大学 这种有明显具体城市的关键字，这种关键字不返回 sugesstion 字段
# 多个关键字用“|”分割,若不指定city，并且搜索的为泛词（例如“美食”）的情况下
# 返回的内容为城市列表以及此城市内有多少结果符合要求。
def getSearchInfo(keywords: str):
    baseAPI = 'https://restapi.amap.com/v3/place/text?'
    output = 'json'
    offset = '20'  # 每页记录数据,不能大于25
    page = '1'
    extensions = 'all'
    url = baseAPI + 'key={}&keywords={}&offset={}&page={}&extensions={}&output={}'.format(myKey, keywords, offset, page,
                                                                                          extensions, output)
    response = requests.get(url)
    jsonData = response.json()
    total = 0
    for i in jsonData['suggestion']['cities']:
        total += int(i['num'])
    return render_template('search.html', keywords=keywords, total=total, jsonData=jsonData)


def getCity_adcode(cityname):  # 最好地区加上 市/县，比如 桐乡 最好输入 桐乡市，这样最精准
    baseAPI = 'https://restapi.amap.com/v3/geocode/geo?'
    output = 'json'
    url = baseAPI + 'key={}&address={}&output={}'.format(myKey, cityname, output)
    responese = requests.get(url)
    jsonData = responese.json()
    # filename = 'cityInfo.json'
    # with open(filename,'w') as fp:
    #     json.dump(jsonData,fp) # 抓取到的数据存在jsondata.json里
    #     print('Done！')
    # 上面输出，然后分析格式，提取出adcode
    return jsonData['geocodes'][0]['adcode']


# ++++++++++++++++++++++++++++++++++++++++++++++++++++++ 天气抓取模块 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
@app.route('/weather')  # 天气查询入口
def weather_entry():
    return render_template('weather.html', liveData=None, forecastData=None)


@app.route('/weather/live/<cityname>')
def getWeatherLive(cityname):
    # if request.method == "POST":
    # cityname = request.form.get('cityname','杭州市') # 只获取cityname键的值，没有就默认杭州市
    baseAPI = 'https://restapi.amap.com/v3/weather/weatherInfo?'
    city_adcode = str(getCity_adcode(cityname))
    extensions = 'base'  # base:返回实况天气 all:返回预报天气
    output = 'json'
    url = baseAPI + 'key={}&city={}&extensions={}&output={}'.format(myKey, city_adcode, extensions, output)
    response = requests.get(url)
    jsonData = response.json()
    # filename = 'weatherLive.json'
    # with open(filename, 'w') as fp:
    #     json.dump(jsonData, fp)  # 抓取到的数据存在jsondata.json里
    #     print('Done！')
    # return render_template('weatherlive.html', cityname=cityname, jsonData=jsonData)
    return render_template('weather.html', cityname=cityname, liveData=jsonData, forecastData=None)


@app.route('/weather/forecast/<cityname>')
def getWeatherForcast(cityname):
    baseAPI = 'https://restapi.amap.com/v3/weather/weatherInfo?'
    city_adcode = str(getCity_adcode(cityname))
    extensions = 'all'  # base:返回实况天气 all:返回预报天气
    output = 'json'
    url = baseAPI + 'key={}&city={}&extensions={}&output={}'.format(myKey, city_adcode, extensions, output)
    response = requests.get(url)
    jsonData = response.json()
    filename = 'weatherForecast.json'
    # with open(filename, 'w') as fp:
    #     json.dump(jsonData, fp)  # 抓取到的数据存在jsondata.json里
    #     print('Done！')
    # return jsonData
    return render_template('weather.html', cityname=cityname, liveData=None, forecastData=jsonData)


# ++++++++++++++++++++++++++++++++++++++++++++++++++++++ 豆瓣电影抓取模块 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
def merge_dicts(*dict_args):
    """
    Given any number of dicts, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dicts.
    """
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


def getPageJson(page_limit: int, sort='recommend', tag='豆瓣高分', page_start=0) -> dict:
    """
    此函数抓取豆瓣排行榜页面的所有电影链接信息，主要用page_limit控制抓取的电影数量，
    sort用于控制抓取的排行榜排序规则，其余两个参数建议不要动
    """
    # base = 'https://movie.douban.com/explore#!type=movie' # 这个是网页显示的地址
    base = 'https://movie.douban.com/j/search_subjects?type=movie'  # 这个才是传送json数据的地址
    url = base + '&tag={}&sort={}&page_limit={}&page_start={}'.format(
        tag, sort, page_limit, page_start)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        print('Requests Error retrying...')
        time.sleep(3)
        return getPageJson(page_limit, page_start=0, sort='recommend', tag='豆瓣高分')


def getfilmRawData(page_json) -> dict:
    """
    此函数传入参数page_json依赖于getPageJson()，
    返回值为处理过的json（dict类型）--filmRaw
    """
    filmRaw = [
        {
            'filmname': data['title'],
            'rate': data['rate'],
            'url': data['url']
        }
        for data in page_json['subjects']
    ]
    return filmRaw


def getfilmDetailPage(film_url) -> str:
    """
    film_url是一部电影对应的url，此函数用于获取一部电影的详情页html
    """
    try:
        response = requests.get(film_url, headers=headers)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            return response.text
        return None
    except requests.exceptions.RequestException:
        print('Requests Error retrying...')
        time.sleep(3)
        return getfilmDetailPage(film_url)

def getfilmInfo(filmHtmlTxt) -> dict:
    """
    filmHtmlInfo是由getfilmDetailPage()获取的一部电影的详情页html文本，
    此函数用于分析电影详情页html，用正则提取该电影的详细信息
    """
    soup = BeautifulSoup(filmHtmlTxt, 'html.parser')
    infoBlock = soup.select('#info')  # 类名前要加. id前要加#
    infoBlock = str(infoBlock[0])  # 文本化，原本infoBlock是list
    detilInfo = {
        'director': re.findall('irectedBy">(.*?)</a>', infoBlock),
        'editor': re.findall('/">(.*?)</a>', infoBlock),
        'cast': re.findall('starring">(.*?)</a>', infoBlock),
        'type': re.findall('genre">(.*?)</span>', infoBlock),
        'region': re.findall('制片国家/地区:</span> (.*?)<br/>', infoBlock),
        'language': re.findall('语言:</span>(.*?)<br/>', infoBlock),
        'date': re.findall('initialReleaseDate">(.*?)</span>', infoBlock),
        'runtime': re.findall('runtime">(.*?)</span>', infoBlock)
    }
    castScale = 15  # 由于html展示的时候表格里放全部演员会很难看，这里控制只取前15个演员
    if len(detilInfo['cast']) > castScale:
        detilInfo['cast'] = detilInfo['cast'][:castScale]
    return detilInfo


def getfilmAll(filmRaw: dict) -> dict:
    """
    将filmRaw中所有电影，进行抓取详情信息，最后返回
    json格式（dict类型）的filmInfo，保存了所有电影的详情信息
    """
    filmAll = []
    for film in filmRaw:
        filminfo = getfilmInfo(getfilmDetailPage(film['url']))
        filmAll.append(merge_dicts(film, filminfo))
    return filmAll


@app.route('/film/<tag>/<sort>/<int:page_limit>')
def crawling(page_limit: int, tag='豆瓣高分', sort='recommend'):
    page_json = getPageJson(page_limit, sort=sort, tag=tag)
    filmRaw = getfilmRawData(page_json)
    filmAll = getfilmAll(filmRaw)
    return render_template('film.html', filmAmount=page_limit, jsonData=filmAll, tag=tag, sort=sort)


@app.route('/film')
def film_entry():
    return render_template('film.html', filmAmount=None, jsonData=None, tag=None, sort=None)


# ++++++++++++++++++++++++++++++++++++++++++++++++++++++ 首页地址模块 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
@app.route('/')
def home_page():
    return render_template('home_page.html')

def listJoin2str(mylist):
    return '/'.join(mylist)

app.add_template_global(listJoin2str, 'list2str')

if __name__ == '__main__':
    app.run(debug=True)
