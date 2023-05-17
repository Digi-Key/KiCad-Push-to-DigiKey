import json
import re
import requests
import time
import wx
from threading import Thread
from .ki_result_event import ResultEvent


class PushThread(Thread):
    def __init__(self, wx_object, json_data, list_name):
        Thread.__init__(self)
        self.wx_object = wx_object
        self.json_data = json_data
        self.list_name = list_name
        self.start()

    def run(self):
        base_api_url = 'https://www.digikey.com/mylists/api/thirdparty'
        json_data = self.json_data
        params = {'listName': self.list_name}

        self._post_event({'state': 'Initializing...', 'gauge_int': 10})
        time.sleep(0.5)

        self._post_event({'state': 'Uploading your BOM...', 'gauge_int': 40})

        r = None
        try:
            r = requests.post(base_api_url, json=json_data, params=params, verify=True, timeout=10)
        except requests.exceptions.RequestException:
            self._post_event({'state': 'ERR_REQUESTS_EXCEPTION', 'api_url': base_api_url})
            return
        except Exception:
            self._post_event({'state': 'ERR_SENDING_REQUEST', 'api_url': base_api_url})
            return

        self._post_event({'state': 'Preparing the webpage...', 'gauge_int': 70})
        time.sleep(0.5)

        returned_short_url = ''
        try:
            returned_short_url = json.loads(r.text)
            short_url_regex = r'^http.+digikey\.com/short/[0-9a-z]{7}'
            if not re.match(short_url_regex, returned_short_url):
                self._post_event({'state': 'SHORT_URL_NOT_RETURNED', 'r_text': returned_short_url})
                return
        except json.decoder.JSONDecodeError:
            self._post_event({'state': 'SHORT_URL_NOT_RETURNED', 'r_text': returned_short_url})
            return

        self._post_event({'state': 'Done', 'gauge_int': 100})
        time.sleep(0.5)

        try:
            wx.LaunchDefaultBrowser(returned_short_url)
        except:
            self._post_event({'state': 'CANNOT_LAUNCH_DEFAULT_BROWSER', 'url': returned_short_url})
            return
        self._post_event({'state': 'Finished'})  # keyword: "Finished", to close the wxForm.

    def _post_event(self, event_data):
        wx.PostEvent(self.wx_object, ResultEvent(event_data))
