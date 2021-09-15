# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
# useful for handling different item types with a single interface
import json
import logging
import os
import shutil
from typing import Any
from urllib.parse import urlparse

import pymongo
import scrapy
from itemadapter import ItemAdapter

logger = logging.getLogger(__name__)


def url2path(url: str) -> str:

    url_path = urlparse(url).path

    exclude = ['http:', 'https:']
    url_list = url_path.split('/')
    url_list = list(filter(lambda s: len(s) > 0 and s not in exclude,
                           url_list))

    url_list = url_list[1:]
    path = os.path.join(*url_list)

    return path


def path_from_url(url: str, root_path: str) -> str:

    subdir = url2path(url)
    outpath = os.path.join(root_path, subdir)

    if not os.path.exists(outpath):
        os.makedirs(outpath)

    return outpath


class JsonWriterPipeline:

    SETTING_ROOT_DIR = 'json_root_dir'
    SETTING_CLEAR = 'json_clear'

    _default_root_dir = os.path.expanduser('~/anynews_wbm')

    def __init__(self, root_dir: str, clear: bool, encoding: str = 'utf-8'):
        """
        Parameters
        ----------
        root_dir : str
            Root directory.
        """
        self.root_dir = root_dir
        self.clear = clear
        self.encoding = encoding

    def output_dir(self, spider: scrapy.Spider) -> str:
        """Returns spider output directory."""

        return os.path.join(self.root_dir, spider.name)

    @classmethod
    def from_crawler(cls,
                     crawler: scrapy.crawler.Crawler) -> 'JsonWriterPipeline':

        root_dir = crawler.settings.get(cls.SETTING_ROOT_DIR,
                                        cls._default_root_dir)
        clear = crawler.settings.get(cls.SETTING_CLEAR, False)

        return cls(
            root_dir=root_dir,
            clear=clear
        )

    def open_spider(self, spider: scrapy.Spider):

        output_dir = self.output_dir(spider)

        logger.info("Output directory: %s", output_dir)

        if self.clear and os.path.exists(output_dir):
            shutil.rmtree(output_dir)

        os.makedirs(output_dir, exist_ok=True)

        filename = os.path.join(output_dir, 'name')
        with open(filename, "w", encoding=self.encoding) as fobj:
            fobj.write(spider.name)

    def process_item(self, item: Any, spider: scrapy.Spider):

        output_dir = self.output_dir(spider)

        item_dict = ItemAdapter(item).asdict()

        to_json = {
            key: val
            for key, val in item_dict.items()
            if key != 'snapshot'
        }

        outdir = path_from_url(item_dict['url'], output_dir)
        outpath = os.path.join(outdir, 'meta.json')
        with open(outpath, 'w', encoding=self.encoding) as fobj:
            json.dump(to_json, fobj, ensure_ascii=False, indent=4)

        self.save_snapshot(item_dict, outdir)

        return item

    def save_snapshot(self, snapshot: str, outpath: str):

        outpath = os.path.join(outpath, 'snapshot.html')
        with open(outpath, 'w', encoding='utf-8') as fobj:
            fobj.write(snapshot)


class MongodbWriterPipeline:

    CONNECTION = 'mongodb://localhost'
    DATABASE = 'anynews_wbm'

    def __init__(self):

        self.client = None
        self.db = None

    def open_spider(self, spider: scrapy.Spider):

        self.client = pymongo.MongoClient(self.CONNECTION)
        self.db = self.client[self.DATABASE]

    def close_spider(self, spider):
        self.client.close()

    def process_item(self, item: Any, spider: scrapy.Spider):

        self.db[spider.name].insert_one(ItemAdapter(item).asdict())
