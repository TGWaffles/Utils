from TikTokApi import TikTokApi
import requests


def get_video(username):
    api = TikTokApi.get_instance(custom_verifyFp="verify_knxvpdqn_jjZdu7Te_mwZy_4EpT_8zzG_fVOU4SrmsLpA",
                                 use_test_endpoints=True)
    videos = api.by_username(username, count=1)
    last_video = videos[0]
    dynamic_cover = last_video.get("video", {}).get("cover", "")
    image = requests.get(dynamic_cover, stream=True).raw
    return last_video, image.read()


def get_user(username):
    api = TikTokApi.get_instance(custom_verifyFp="verify_knxvpdqn_jjZdu7Te_mwZy_4EpT_8zzG_fVOU4SrmsLpA",
                                 use_test_endpoints=True)
    user = api.get_user(username)
    return user
