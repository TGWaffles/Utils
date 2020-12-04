from src.storage import config

new_suggestion_format = ("We have a new format now, {}. Please format your message like so: \n\n"
                         "`suggest suggestion_goes_here`")

suggestion_changed = "The suggestion \"{}\" has been {} by {}. \nAdditional information: `{}`"

suggestion_channel_feedback = "Suggestion '{}' {} Reason: {}"

# ERRORS
invalid_message_id = "That wasn't a valid message id, '{}'"
id_not_found = "I couldn't find a message with the specified id."
bot_not_author = "I didn't send that message."
no_embed = "No embed was found in that message. That's odd."

purge_limit = (f"I have a limit of {config.purge_max} imposed on this command to prevent accidents. "
               f"Tag Thomas or do an amount <= {config.purge_max}.")

no_purge_amount = "You included no amount. I am not allowing this so I can prevent accidents."
