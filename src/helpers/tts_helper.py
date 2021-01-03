import pydub

from pydub import effects
from gtts import gTTS
from time import sleep
from io import BytesIO


def get_speak_file(message_content, lang):
    pre_processed = BytesIO()
    post_processed = BytesIO()
    print(1)
    print(message_content)
    print(lang)
    spoken_google = gTTS(message_content, lang=lang)
    with open("test.mp3", 'wb') as file:
        spoken_google.write_to_fp(fp=file)
    print(2)
    sleep(5)
    print(pre_processed.read())
    segment = pydub.AudioSegment.from_file(pre_processed, format="mp3")
    print(3)
    segment = effects.speedup(segment, 1.25, 150, 25)
    print(4)
    segment.set_frame_rate(16000).export(post_processed, format="wav")
    print(5)
    return post_processed
