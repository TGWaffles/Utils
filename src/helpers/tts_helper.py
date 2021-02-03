import pydub

from pydub import effects
from gtts import gTTS
from io import BytesIO


def get_speak_file(message_content, lang, speed):
    pre_processed = BytesIO()
    post_processed = BytesIO()
    try:
        spoken_google = gTTS(message_content, lang=lang)
        spoken_google.write_to_fp(fp=pre_processed)
        pre_processed.seek(0)
        segment = pydub.AudioSegment.from_file(pre_processed, bitrate=356000, format="mp3")
        segment = effects.speedup(segment, 1.25, 150, 25)  # normally 1.25
        frames = int(95000 * 1 / speed)
        segment.set_frame_rate(frames).export(post_processed, format="s16le")
        return post_processed
    except AssertionError:
        return post_processed
