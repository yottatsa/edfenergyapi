#!/usr/bin/python3
import json
import logging
import os
import time
from contextlib import contextmanager
from http.cookiejar import LWPCookieJar

import html5lib
from warrant.aws_srp import AWSSRP

import boto3
import botocore
import requests
from botocore.config import Config

AUTH_FILE = ".edf.json"
COOKIES_FILE = ".edf.cookies"


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EDF(object):
    def __init__(self, username, password, cookies_file=COOKIES_FILE):
        self.username = username
        self.password = password
        self.cookies_file = cookies_file
        self.session = requests.Session()
        self.session.cookies = LWPCookieJar(self.cookies_file)
        if not os.path.exists(self.cookies_file):
            self.session.cookies.save()
        else:
            self.session.cookies.load(ignore_discard=True)

    def save(self):
        self.session.cookies.save(ignore_discard=True)

    def _get_data(self, method, url, *args, **kwargs):
        headers = kwargs.get("headers", {})
        headers.setdefault("Referer", url)
        resp = getattr(self.session, method)(url, *args, **kwargs)
        htmlpage = html5lib.parse(resp.content, treebuilder="dom")
        scripts = [
            i.firstChild and i.firstChild.data
            for i in htmlpage.getElementsByTagName("script")
        ]
        settings = filter(lambda s: s and "Drupal.settings" in s, scripts).__next__()
        data = json.loads("{" + settings.split("{", 1)[1].rsplit("}", 1)[0] + "}")
        edf_customer = data.get("edf_customer")
        if edf_customer:
            logger.warn("edf_customer %s %s", resp.url, edf_customer)
        return data

    def get(self, *args, **kwargs):
        return self._get_data("get", *args, **kwargs)

    def post(self, *args, **kwargs):
        return self._get_data("post", *args, **kwargs)

    def _awssrp(self, aws_cognito_conf):
        config = Config(signature_version=botocore.UNSIGNED)
        client = boto3.client(
            "cognito-idp", region_name=aws_cognito_conf["AWS_REGION"], config=config
        )
        aws = AWSSRP(
            username=self.username,
            password=self.password,
            pool_id=aws_cognito_conf["AWS_USERPOOLID"],
            client_id=aws_cognito_conf["AWS_CLIENTID"],
            client=client,
        )
        return aws.authenticate_user()

    def login_request(self, url):
        # get_data(s.get, 'https://my.edfenergy.com/user/login?destination={}'.format(url))

        login_data = self.post(
            "https://my.edfenergy.com/user/login?destination={}".format(url),
            data={
                "name": self.username,
                "form_id": "user_login",
                "easy_online_flag": "0",
                "hid_flag": "0",
                "myaccount_check": "TRUE",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )["edf_customer"]

        tokens = self._awssrp(login_data["aws_cognito_conf"])

        id_token = tokens["AuthenticationResult"]["IdToken"]
        refresh_token = tokens["AuthenticationResult"]["RefreshToken"]
        access_token = tokens["AuthenticationResult"]["AccessToken"]

        expires_at = tokens["AuthenticationResult"]["ExpiresIn"] + int(time.time())

        logged_in = self.post(
            "https://my.edfenergy.com/login/pwdorotp?destination={}".format(url),
            data={
                "customer_pwd": self.password,
                "customer_scenario": 1,
                "customer_email": self.username,
                "customer_id_token": id_token,
                "customer_access_token": access_token,
                "customer_refresh_token": refresh_token,
                "customer_expiresin": expires_at,
                "form_id": "edf_customer_pwd_form",
                "easy_online_flag": "0",
                "hid_flag": "0",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        edf.save()
        return logged_in

    def request(self, url):
        data = self.get("https://my.edfenergy.com/{}".format(url))
        if "edf_customer" in data:
            # seems that we nedd to log in
            return self.login_request(url)
        return data


if os.path.exists(AUTH_FILE):
    with open(AUTH_FILE, "r") as f:
        auth = json.load(f)
    edf = EDF(**auth)
    logger.info("Usage %s", edf.request("myaccount/energygraph/month")["data"])
    edf.save()
