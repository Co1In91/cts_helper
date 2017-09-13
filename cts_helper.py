from BeautifulSoup import BeautifulSoup
import sched
import logging
import os
import sys
import time
import requests
import yaml
import re
import argparse


def logger(name):
    l = logging.getLogger(name)
    l.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(funcName)s] %(message)s")
    ch.setFormatter(formatter)
    l.addHandler(ch)
    return l

logging.getLogger("requests").setLevel(logging.WARNING)
logger = logger(__file__)
schedule = sched.scheduler(time.time, time.sleep)


class Helper(object):
    is_active = False
    media = []
    cts = []
    cts_verifier = []

    def __init__(self, platform='arm', path=os.path.abspath(os.path.dirname(__file__))):
        self.path = path
        self.platform = platform
        self.is_active = os.path.exists(os.path.join(path, 'CTS'))
        if not self.is_active:
            self.setup()

    def setup(self):
        logger.debug('Setup wizard for first use')
        try:
            url = raw_input("mirror url: ")
            if not requests.get(url).status_code == 200:
                print 'Server is invalid'
                sys.exit(0)
        except requests.exceptions.MissingSchema as e:
            print e
            sys.exit(0)
        os.mkdir(os.path.join(self.path, 'CTS'))
        config_dict = {
            'server': url
        }
        with open(os.path.join(self.path, 'config.yaml'), 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)
            f.close()
        self.is_active = True

    def check_pkg(self, inc):
        schedule.enter(inc, 0, self.check, ('update cts packages',))
        schedule.run()

    def check(self, *arg):
        config = yaml.load(open(os.path.join(self.path, 'config.yaml'), 'r'))
        soup = BeautifulSoup(requests.get(config['server']).content)
        a_tags = soup.findAll('a')
        links = map(lambda x: x['href'], a_tags)
        self.media = filter(lambda x: re.match(r'android-cts-media', x.split('/')[-1]), links)
        self.cts = filter(lambda x: re.match(r'android-cts-\d(.+)' + self.platform + '\.zip$', x.split('/')[-1]), links)
        self.cts_verifier = filter(lambda x: re.match(r'android-cts-verifier(.+)' + self.platform + '\.zip$', x.split('/')[-1]), links)
        # update media files
        sorted(self.media, key=lambda x: re.search(r'(\d.\d).zip', x))[0]
        sorted(self.cts_verifier, key=lambda x: re.search(r'(\d.\d).zip', x))[0]
        sorted(self.cts, key=lambda x: re.search(r'(\d.\d).zip', x))[0]

    def download(self, url):
        if os.path.exists(os.path.join(self.path, 'CTS', url.split('/')[-1])):
            logger.debug('Skip %s' % url)
        else:
            r = requests.get(url, stream=True)
            f = open(os.path.join(self.path, 'CTS', url.split('/')[-1]), "wb")
            for chunk in r.iter_content(chunk_size=512):
                if chunk:
                    f.write(chunk)

    @staticmethod
    def download_media(self):
        self.download(self.media[0])


if __name__ == '__main__':
    helper = Helper()
    parser = argparse.ArgumentParser(description='Android CTS Helper')
    parser.add_argument('-d', '--debug', help='Update once immediately', action='store_true')
    parser.add_argument('-a', '--add', help='Add specified Android release number to track list')
    parser.add_argument('-s', '--start', help='Start update mode', action='store_true')
    args = parser.parse_args()
    if args.add:
        helper.check()
        if len(args.add) > 1:
            regex = args.add
        else:
            regex = args.add + '.\d'
        cts_urls = filter(lambda x: re.search(regex, x.split('/')[-1]), helper.cts)
        verifier_urls = filter(lambda x: re.search(regex, x.split('/')[-1]), helper.cts_verifier)
        for url in cts_urls + verifier_urls:
            helper.download(url)
        sys.exit(0)
    elif args.debug:
        helper.check()
        sys.exit(0)
    elif args.start:
        logger.debug('Auto update mode')
        while helper.is_active:
            helper.check_pkg(3600)
    else:
        parser.print_help()
