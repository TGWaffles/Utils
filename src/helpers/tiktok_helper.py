from TikTokApi import TikTokApi, exceptions
import bs4
import time
import requests


def get_proxy(restarting_event, offset=0):
    while True:
        if restarting_event.is_set():
            exit()
        try:
            site = requests.get("https://scrapingant.com/free-proxies/").text

            soup = bs4.BeautifulSoup(site, 'html.parser')
            offset = 5 * offset
            table = [x.string for x in soup.find_all("td")]
            first_proxy_ip = table[offset]
            first_proxy_port = table[offset + 1]
            if "China" in table[offset + 3]:
                return get_proxy(restarting_event, offset+1)
            complete_proxy = f"{first_proxy_ip}:{first_proxy_port}"
            return complete_proxy
        except IndexError:
            time.sleep(1)
            offset = 0


def get_video(username, restarting_event):
    offset = 0
    while True:
        if restarting_event.is_set():
            return
        try:
            api = TikTokApi.get_instance(custom_verifyFp="verify_knxvpdqn_jjZdu7Te_mwZy_4EpT_8zzG_fVOU4SrmsLpA",
                                         use_test_endpoints=True, proxy=get_proxy(restarting_event, offset))
            videos = api.by_username(username, count=1)
            last_video = videos[0]
            dynamic_cover = last_video.get("video", {}).get("cover", "")
            image = requests.get(dynamic_cover, stream=True).raw
            return last_video, image.read()
        except exceptions.TikTokCaptchaError:
            offset += 1


def get_user(username, restarting_event):
    offset = 0
    while True:
        if restarting_event.is_set():
            return
        try:
            api = TikTokApi.get_instance(custom_verifyFp="verify_knxvpdqn_jjZdu7Te_mwZy_4EpT_8zzG_fVOU4SrmsLpA",
                                         use_test_endpoints=True, proxy=get_proxy(restarting_event, offset))
            user = api.get_user(username)
            return user
        except exceptions.TikTokCaptchaError:
            offset += 1
