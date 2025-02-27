#!/usr/bin python3
# -*- coding: utf-8 -*-
import random
from apscheduler.schedulers.background import BackgroundScheduler, BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.triggers.interval import IntervalTrigger
from urllib.parse import quote
from threading import Thread
from app.tools import *


class container:
    def __init__(self):
        self.repo = None
        self.para = {}
        self.filename = dict()  # -1->redis | 0->downloading | 1->completed
        self.owner = repoowner
        Thread(target=self.init).start()

    def inin_repo(self):
        print("开始初始化")
        self.repo = str(datetime.date.today())
        state = agit(repoaccess_token).cat_repo(self.owner, self.repo)
        if state == 404:
            agit(repoaccess_token).create_repo(self.repo)
            print("创建repo", self.repo, "完成")

    def init(self):
        self.inin_repo()
        # 读取redis缓存数据到内存
        keys = cur.keys()
        _ = []
        for k in keys:
            _.append(k)
        for key, value in zip(_, cur.mget(_)):
            _ = eval(value)
            if len(_) < 3:
                continue
            self.updatelocal(key, _)

        # 读取已上传到agit的文件名到内存
        reposha = agit(repoaccess_token).get_repo_sha(self.owner, self.repo)
        for i in agit(repoaccess_token).cat_repo_tree(self.owner, self.repo, reposha)['tree']:
            if i["size"] >= 5000 and ".ts" in i["path"]:
                self.filename.update({i["path"]: -1})
        print("init final")

    def updateonline(self, fid, hd):
        url = get4gtvurl(fid, idata[fid]['nid'], hd)
        last = int(re.findall(r"expires.=(\d+)", url).pop())
        start, seq, gap = genftlive(url)
        cur.setex(fid, last - now_time(), str([url, last, start, seq, gap]))
        self.para[fid] = {
            "url": url,
            "last": last,
            "start": start,
            "seq": seq,
            "gap": gap
        }

    def updatelocal(self, fid, _):
        self.para[fid] = {
            "url": _[0],
            "last": _[1],
            "start": _[2],
            "seq": _[3],
            "gap": _[4]
        }

    def check(self, fid, hd):
        """
        处理参数
        :param fid:
        :param hd:
        :return:
        """
        if not self.para.get(fid) or self.para.get(fid)['last'] - now_time() < 0:  # 本地找
            _temp = cur.get(fid)
            if not _temp or eval(_temp)[1] - now_time() < 0:  # redis找
                if hd == "1080" and fid in """
                    4gtv-4gtv070
                    4gtv-4gtv083
                    4gtv-4gtv059
                    4gtv-4gtv077
                    4gtv-4gtv014
                    4gtv-4gtv084
                    4gtv-4gtv085
                    4gtv-4gtv080
                    """:
                    hd = "720"
                self.updateonline(fid, hd)
            else:
                _ = eval(_temp)
                self.updatelocal(fid, _)

    def generalfun(self, fid, hd):
        """
        通用生成参数
        :param fid:
        :param hd:
        :return:
        """
        now = now_time()
        data = self.para[fid]
        if "4gtv-4gtv" in fid or "litv-ftv10" in fid or "litv-longturn17" == fid or "litv-longturn18" == fid:
            url = idata[fid][hd]
            seq = round((now - data['start']) / idata[fid]["x"])
            begin = (seq + data['seq']) * idata[fid]["x"]
            return data["gap"], seq, url, begin
        elif "4gtv-live" in fid:
            token = re.findall(r"(token1=.*&expires1=\d+)&", data['url']).pop()
            url = idata[fid]['url'] + "?" + token
            seq = solvelive(now, data['start'], data['seq'], idata[fid]["x"])
            return data["gap"], seq, url, 0
        else:
            url = idata[fid][hd]
            seq = solvelive(now, data['start'], data['seq'], idata[fid]["x"])
            return data["gap"], seq, url, 0

    def generatem3u8(self, host, fid, hd):
        self.check(fid, hd)
        gap, seq, url, begin = self.generalfun(fid, hd)
        yield f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:{gap}
#EXT-X-ALLOW-CACHE:YES
#EXT-X-MEDIA-SEQUENCE:{seq}
#EXT-X-INDEPENDENT-SEGMENTS"""
        for num1 in range(5):
            yield f"\n#EXTINF:{idata[fid]['gap']}" \
                  + "\n" + generate_url(fid, host, hd, begin + (num1 * idata[fid]["x"]), seq + num1, url)

    def new_generatem3u8(self, host, fid, hd, background_tasks):
        self.check(fid, hd)
        gap, seq, url, begin = self.generalfun(fid, hd)
        background_tasks.add_task(backtaskonline, url, fid, seq, hd, begin, host)
        yield f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:{gap}
#EXT-X-MEDIA-SEQUENCE:{seq}
#EXT-X-INDEPENDENT-SEGMENTS"""
        tsname = fid + str(seq) + ".ts"
        if tsname in self.filename and self.filename.get(tsname) == 1:
            for num1 in range(5): # 控制第一次读取是从第一个ts开始
                url = "\n" + os.environ['local'] + f"/call.ts?fid={fid}&seq={str(seq + num1)}&hd={hd}"
                yield f"\n#EXTINF:{idata[fid]['gap']}" + url
        else:
            for num1 in range(1):
                url = "\n" + os.environ['local'] + f"/call.ts?fid={fid}&seq={str(seq + num1)}&hd={hd}"
                yield f"\n#EXTINF:{idata[fid]['gap']}" + url

    def geturl(self, fid, hd):
        self.check(fid, hd)
        return re.sub(r"(\w+\.m3u8)", HD[hd], self.para[fid]['url'])


get = container()


def call_get(url, tsname):
    res = request.get(url)
    get.filename.update({tsname: 1})
    # print(tsname, url[:20], res.text)


def backtaskonline(url, fid, seq, hd, begin, host):
    threads = []
    urlset = ["https://xxxx/url3?url=", "https://xxxx/url3?url=",
              "https://xxxx/url3?url=", "https://xxxx/url3?url=",
              "https://xxxx/url3?url="]
    # random.shuffle(urlset)
    for i in range(0, 5):
        tsname = fid + str(seq + i) + ".ts"
        # .ts已下载或正在下载
        if tsname in get.filename:
            continue
        get.filename.update({tsname: 0})
        herf = generate_url(fid, host, hd, begin + (i * idata[fid]["x"]), seq + i, url)
        x = urlset.pop() + quote(herf) + f"&filepath={tsname}"
        t = Thread(target=call_get, args=(x, tsname))
        threads.append(t)
    for i in range(len(threads)):
        threads[i].start()
        time.sleep(1 + i * 0.1)
        # time.sleep(1)
    for t in threads:
        t.join()


def gotask():
    get.filename.clear()
    get.inin_repo()
    if "Windows" in platform.platform():
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(postask())
    else:
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        loop = asyncio.get_event_loop()
        task = asyncio.ensure_future(postask())
        loop.run_until_complete(asyncio.wait([task]))

    content = generateprog(gdata())
    filepath = "4gtvchannel.xml"
    agit(xmlaccess_token).update_repo_file(xmlowner, xmlrepo, filepath, content)
    with open("EPG.xml", "wb") as f:
        f.write(content)
    print("今日任务完成")


def sqltask():
    keys = list(get.filename)
    keys.reverse()
    _ = {}
    if len(keys) > 100:
        for i in range(len(keys)):
            if i < 100:
                _.update({keys[i]: get.filename.get(keys[i])})
        get.filename = _
    print("删除完成")


def everyday(t=2):
    executors = {
        'default': ThreadPoolExecutor(5),  # 名称为“default ”的ThreadPoolExecutor，最大线程20个
        'processpool': ProcessPoolExecutor(2)  # 名称“processpool”的ProcessPoolExecutor，最大进程5个
    }
    job_defaults = {
        'coalesce': False,  # 默认为新任务关闭合并模式（）
        'max_instances': 3  # 设置新任务的默认最大实例数为3
    }
    scheduler = BlockingScheduler(executors=executors, job_defaults=job_defaults, timezone='Asia/Shanghai')
    scheduler.add_job(gotask, 'cron', day_of_week='0-6', hour=t, minute=00, second=00, misfire_grace_time=120)
    scheduler.add_job(func=sqltask, trigger=IntervalTrigger(minutes=59), misfire_grace_time=120)
    print(scheduler.get_jobs())
    scheduler.start()

