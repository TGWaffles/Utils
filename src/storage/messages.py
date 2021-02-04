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

no_voice_clients = "There were no active voice clients in your server."
already_has_perms = "That user already has permission to add people to speak!"
already_speaking = "That user is already on the speaking list."
not_already_speaking = "That user is not already on the speaking list."


invalid_chess_command = """That is not a valid command. Your message should be formatted like one of the following: 
1. "move a1 a2" where a1 is the square to move from and a2 is the square to move to. \
Or you could use a7 a8q to move a pawn to the last square on the board AND promote to a queen :) OR you could do \
"move a1" to see all viable moves of the piece in a1.
2. "resign" to resign from a game.
3. "draw" to attempt to draw a game (the viability of which will be determined later)."""

invalid_chess_square = """That was not a valid square. If you want to make a move remember to leave a space between the 
from-square and the to-square, eg "move a2 a4". Only one argument tells me that you'd like to see all possible moves 
for that piece."""

chess_win = "Congratulations! You have won the chess game with {}!"
chess_loss = "Chess Game with {} - You lost!"
chess_draw = "The chess game with {} was a draw."
