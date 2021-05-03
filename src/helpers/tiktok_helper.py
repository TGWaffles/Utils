from TikTokApi import TikTokApi
import bs4
import requests


def get_proxy():
    site = requests.get("https://scrapingant.com/free-proxies/").text

    soup = bs4.BeautifulSoup(site, 'html.parser')

    table = [x.string for x in soup.find_all("td")]
    first_proxy_ip = table[0]
    first_proxy_port = table[1]
    complete_proxy = f"{first_proxy_ip}:{first_proxy_port}"
    return complete_proxy


def get_video(username):
    api = TikTokApi.get_instance(custom_verifyFp="verify_knxvpdqn_jjZdu7Te_mwZy_4EpT_8zzG_fVOU4SrmsLpA",
                                 use_test_endpoints=True, proxy=get_proxy())
    videos = api.by_username(username, count=1)
    last_video = videos[0]
    dynamic_cover = last_video.get("video", {}).get("cover", "")
    image = requests.get(dynamic_cover, stream=True).raw
    return last_video, image.read()


def get_user(username):
    api = TikTokApi.get_instance(custom_verifyFp="verify_knxvpdqn_jjZdu7Te_mwZy_4EpT_8zzG_fVOU4SrmsLpA",
                                 use_test_endpoints=True, proxy=get_proxy())
    user = api.get_user(username)
    return user
