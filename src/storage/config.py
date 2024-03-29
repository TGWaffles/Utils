import os
import src.storage.token as token

version_number = "3.0.6"

port = 8080
restart_port = 8880
api_port = 9987

mongo_connection_uri = (f'mongodb://{token.mongo_user}:{token.mongo_password}@mongo1.thom.club:27017,' 
                        f'mongo1.thom.club:27018,mongo1.thom.club:27016,mongo2.thom.club:27017/'
                        f'{token.auth_db}?replicaSet=thomasRep0')

bot_prefix = "!"
description = "Discord Utility Bot"
owner_id = 230778630597246983
power_id = 739600091480064010
zex_id = 734597893624692778
lexi_id = 280843294508974103
darby_id = 513116059470004275
lexibot_id = 730015197980262424


extensions = [os.path.splitext(x)[0] for x in os.listdir("src/cogs") if not x.startswith("__")]
if "text_to_speech" in extensions:
    extensions.remove("text_to_speech")
    extensions.insert(0, "text_to_speech")
if "restart" in extensions:
    extensions.remove("restart")
    extensions.insert(0, "restart")

dev = False
if dev:
    token.token = token.dev_token
    extensions.remove("suggestions")
    extensions.remove("games")

monkey_guild_id = 725886999646437407
apollo_guild_id = 770972021487304714
cat_guild_id = 689012589455474710

error_channel_id = 795057163768037376
staff_role_ids = [726453086331338802, 889184675346665502]
mod_role_id = 725894916839964682
mod_dev_role_id = 759431719748501575
mod_god_role_id = 750406434180563055
dep_mod_role_id = 740871749956009984
head_mod_role_id = 727294744777982003
lexi_role_id = 725895255198531675
motw_role_id = 802584127634669609
trusted_role_id = 794993948572516392
high_staff = [mod_role_id, mod_dev_role_id, mod_god_role_id, dep_mod_role_id, head_mod_role_id, lexi_role_id]

# Settings for the Suggestions cog
staff_polls_channel_id = 831959824337076264
suggestions_channel_id = 798972358878167080
archive_channel_id = 725920625956225055
motw_channel_id = 816299775108055081
main_channel_id = 725896089542197278
monkey_message_count_channel = 816702703509700618
jace_message_count_channel = 822123300116234301

# suggestions_decisions_id = 727563806762598450
suggestions_decisions_id = 798972358878167080
counting_channel_id = 773952078404911123

# Settings for audit/general reactions cog
fast_forward_emoji = u"\u23E9"
rewind_emoji = u"\u23EA"
robot_emoji = u"\U0001F916"
computer_emoji = u"\U0001F4BB"
forward_arrow = u"\u25B6"
backwards_arrow = u"\u25C0"
both_arrow = u"\u2194"
heart_emoji = u"\u2764"
discord_emoji = "<:discord:784309400524292117>"
c4_yellow = "<:c4yellow:806008963803381810>"
c4_red = "<:c4red:806009125497864204>"
c4_none = ":black_large_square:"
emoji_regex = u"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+"


chess_difficulties = {"easiest": 0.1,
                      "easier": 0.25,
                      "easy": 0.5,
                      "medium": 3,
                      "hard": 10,
                      "grandmaster": 30}

limit_amount = 7
limit_period_days = 7


# Settings for purge
purge_max = 40
purge_all = -1  # DO NOT CHANGE THIS FOR FEAR OF DEATH
confirm_amount = 10

data_path = os.path.join(os.getcwd(), "data.json")  # src/storage/data.json
