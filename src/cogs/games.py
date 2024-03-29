import discord
import numpy as np
import chess.svg
import chess.engine
import random
from typing import Optional
from io import BytesIO
from cairosvg import svg2png

from src.helpers.storage_helper import DataHelper
from src.storage import messages
from src.storage import config
from src.storage.token import token
from discord.ext import commands
from main import UtilsBot
from scipy.signal import convolve2d


class Games(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.data = DataHelper()
        self.transport, self.engine = None, None

    async def connect4_send_to_player(self, player, board: np.array, their_turn):
        board_embed = discord.Embed(title="Connect Four!", colour=discord.Colour.light_grey())
        for array in board:
            for character in array:
                board_embed.description += [config.c4_none, config.c4_red, config.c4_yellow][character]
            board_embed.description += "\n"
        board_embed.add_field(name="Turn", value="It is " + ("NOT ", "")[their_turn] + "your turn!")

    @commands.command(description="Play connect four!", aliases=["connectfour", "connect_four", "c4"],
                      enabled=False)
    async def connect4(self, ctx, player2: discord.Member):
        connect_four_games = self.data.get("ongoing_games", {}).get("connect_four", {})
        player1 = ctx.author
        sorted_ids = sorted([player1.id, player2.id])
        combined_id = "{}-{}".format(*sorted_ids)
        if combined_id in connect_four_games:
            await ctx.reply(embed=self.bot.create_error_embed("You already have a connect four game with that person!"))
            return
        game_board = np.array([[None] * 6] * 7)

    @staticmethod
    def get_kernels():
        horizontal_kernel = np.array([[1, 1, 1, 1]])
        vertical_kernel = np.transpose(horizontal_kernel)
        diag1_kernel = np.eye(4, dtype=np.uint8)
        diag2_kernel = np.fliplr(diag1_kernel)
        return [horizontal_kernel, vertical_kernel, diag1_kernel, diag2_kernel]

    async def connect4_check_win(self, board, player_id):
        detection_kernels = self.get_kernels()
        for kernel in detection_kernels:
            if (convolve2d(board == player_id, kernel, mode="valid") == 4).any():
                return True
        return False

    @commands.command()
    async def chess_ai(self, ctx, difficulty: str = "easy"):
        if self.engine is None:
            print("starting engine...")
            self.transport, self.engine = await chess.engine.popen_uci("/usr/games/stockfish")
        all_games = self.data.get("ongoing_games", {})
        chess_games = all_games.get("chess_games", {})
        difficulty = difficulty.lower()
        player = ctx.author
        if difficulty not in config.chess_difficulties:
            await ctx.reply(embed=self.bot.create_error_embed("That difficulty is not available. "
                                                              "Please choose from the following: " +
                                                              ", ".join(config.chess_difficulties.keys())))
            return
        for difficulty_level in config.chess_difficulties:
            if ("{}-{}".format(ctx.author.id, difficulty_level) in chess_games
                    or "{}-{}".format(difficulty_level, ctx.author.id) in chess_games):
                await ctx.reply(embed=self.bot.create_error_embed("You already have an AI chess game!"))
                return
        new_game = chess.Board()
        both_ids = [player.id, difficulty]
        random.shuffle(both_ids)
        white, black = both_ids
        game_id = "{}-{}".format(white, black)
        chess_games[game_id] = new_game.fen()
        all_games["chess_games"] = chess_games
        self.data["ongoing_games"] = all_games
        await self.send_current_board_state(game_id)

    @commands.command()
    async def chess(self, ctx, player2: discord.Member):
        all_games = self.data.get("ongoing_games", {})
        chess_games = all_games.get("chess_games", {})
        player1 = ctx.author
        if player2 == player1:
            await ctx.reply(embed=self.bot.create_error_embed("You can't play a game against yourself you loner! "
                                                              "Was \"!chess_ai\" what you meant?"))
            return
        possible_id_1 = "{}-{}".format(player1.id, player2.id)
        possible_id_2 = "{}-{}".format(player2.id, player1.id)
        if possible_id_1 in chess_games or possible_id_2 in chess_games:
            await ctx.reply(embed=self.bot.create_error_embed("You already have a chess game with that person!"))
            return
        new_game = chess.Board()
        both_ids = [player1.id, player2.id]
        random.shuffle(both_ids)
        white, black = both_ids
        game_id = "{}-{}".format(white, black)
        chess_games[game_id] = new_game.fen()
        all_games["chess_games"] = chess_games
        self.data["ongoing_games"] = all_games
        await self.send_current_board_state(game_id)

    @staticmethod
    def get_board_images(board):
        try:
            last_move = board.peek()
        except IndexError:
            last_move = None
        player1_oriented_svg = chess.svg.board(board=board, orientation=chess.WHITE, lastmove=last_move)
        player2_oriented_svg = chess.svg.board(board=board, orientation=chess.BLACK, lastmove=last_move)
        player1_png = BytesIO()
        player2_png = BytesIO()
        svg2png(bytestring=player1_oriented_svg, write_to=player1_png)
        svg2png(bytestring=player2_oriented_svg, write_to=player2_png)
        player1_png.seek(0)
        player2_png.seek(0)
        player1_file = discord.File(fp=player1_png, filename="image.png")
        player2_file = discord.File(fp=player2_png, filename="image.png")
        return player1_file, player2_file

    async def handle_ai_board_state(self, game_id, board):
        print("handling board state...")
        try:
            player_id = int(game_id.split("-")[0])
            difficulty_level = game_id.split("-")[1]
            ai_colour = chess.BLACK
            player_file, _ = self.get_board_images(board)
        except ValueError:
            player_id = int(game_id.split("-")[1])
            difficulty_level = game_id.split("-")[0]
            _, player_file = self.get_board_images(board)
            ai_colour = chess.WHITE
        player = self.bot.get_user(player_id)
        thinking_message = None
        if ai_colour == chess.WHITE:
            embed = discord.Embed(title="Chess Game between {} AI (WHITE) and {} (BLACK)!".format(difficulty_level,
                                                                                                  player.name))
        else:
            embed = discord.Embed(title="Chess Game between {} (WHITE) and {} AI (BLACK)!".format(player.name,
                                                                                                  difficulty_level))
        embed.colour = discord.Colour.orange()
        if board.turn == ai_colour:
            embed.set_footer(text="It's the AI's turn!")
            embed.set_image(url="attachment://image.png")
            await player.send(file=player_file, embed=embed)
        if board.turn == ai_colour:
            thinking_message = await player.send(embed=self.bot.create_processing_embed("Thinking...",
                                                                                        "The bot is thinking. "
                                                                                        "Please wait."))
            if self.engine is None:
                print("starting engine...")
            self.transport, self.engine = await chess.engine.popen_uci("/usr/games/stockfish")
            limit = chess.engine.Limit(time=config.chess_difficulties[difficulty_level])
            result = await self.engine.play(board, limit)
            board.push(result.move)
            all_games = self.data.get("ongoing_games", {})
            chess_games = all_games.get("chess_games", {})
            chess_games[game_id] = board.fen()
            all_games["chess_games"] = chess_games
            self.data["ongoing_games"] = all_games
            if await self.check_game_over(game_id):
                return
        if ai_colour == chess.BLACK:
            player_file, _ = self.get_board_images(board)
        else:
            _, player_file = self.get_board_images(board)
        player_embed = discord.Embed(title="Chess Game between {} and {} bot!".format(player.name, difficulty_level),
                                     colour=discord.Colour.orange())
        player_embed.set_image(url="attachment://image.png")
        player_embed.set_author(name=game_id)
        player_embed.set_footer(text="It's your turn to move!")
        await player.send(file=player_file, embed=player_embed)
        if thinking_message is not None:
            await thinking_message.delete()

    async def send_current_board_state(self, game_id, board=None):
        chess_games = self.data.get("ongoing_games", {}).get("chess_games", {})
        if game_id not in chess_games:
            return False
        board_fen = chess_games.get(game_id)
        if board is None:
            board = chess.Board(fen=board_fen)
        try:
            player1_id, player2_id = [int(x) for x in game_id.split("-")]
        except ValueError:
            await self.handle_ai_board_state(game_id, board)
            return
        player1 = self.bot.get_user(player1_id)
        player2 = self.bot.get_user(player2_id)
        player1_embed = discord.Embed(title="Chess Game between {} and {}!".format(player1.name, player2.name),
                                      colour=discord.Colour.orange())
        player2_embed = discord.Embed(title="Chess Game between {} and {}!".format(player1.name, player2.name),
                                      colour=discord.Colour.orange())
        player1_embed.set_author(name=game_id)
        player2_embed.set_author(name=game_id)
        player1_embed.set_image(url="attachment://image.png")
        player2_embed.set_image(url="attachment://image.png")
        if board.turn == chess.WHITE:
            player1_embed.set_footer(text="It's your turn to move!")
            player2_embed.set_footer(text="It's {}'s turn to move!".format(player1.name))
        else:
            player1_embed.set_footer(text="It's {}'s turn to move!".format(player2.name))
            player2_embed.set_footer(text="It's your turn to move!")
        player1_file, player2_file = self.get_board_images(board)
        await player1.send(file=player1_file, embed=player1_embed)
        await player2.send(file=player2_file, embed=player2_embed)

    def mark_win_loss_draw(self, player_id, has_won):
        all_players = self.data.get("chess_scores", {})
        current_player = all_players.get(str(player_id), {})
        if has_won is None:
            draw_score = current_player.get("draws", 0)
            current_player["draws"] = draw_score + 1
        elif has_won == 0:
            loss_score = current_player.get("losses", 0)
            current_player["losses"] = loss_score + 1
        elif has_won == 1:
            win_score = current_player.get("wins", 0)
            current_player["wins"] = win_score + 1
        all_players[str(player_id)] = current_player
        self.data["chess_scores"] = all_players

    async def ai_game_over(self, game_id, board):
        try:
            player_file, _ = self.get_board_images(board)
            player_id = int(game_id.split("-")[0])
            difficulty_level = game_id.split("-")[1]
            ai_colour = chess.BLACK
        except ValueError:
            _, player_file = self.get_board_images(board)
            player_id = int(game_id.split("-")[1])
            difficulty_level = game_id.split("-")[0]
            ai_colour = chess.WHITE
        result = board.result()
        white_points, black_points = result.split("-")
        player_embed = discord.Embed()
        player = self.bot.get_user(player_id)
        if white_points == "1" and ai_colour == chess.BLACK or black_points == "1" and ai_colour == chess.WHITE:
            player_embed.title = messages.chess_win.format("{} AI".format(difficulty_level))
            player_embed.colour = discord.Colour.green()
        elif black_points == "1" and ai_colour == chess.BLACK or white_points == "1" and ai_colour == chess.WHITE:
            player_embed.title = messages.chess_loss.format("{} AI".format(difficulty_level))
            player_embed.colour = discord.Colour.red()
        else:
            player_embed.title = messages.chess_draw.format("{} AI".format(difficulty_level))
            player_embed.colour = discord.Colour.blue()
        player_embed.set_image(url="attachment://image.png")
        await player.send(file=player_file, embed=player_embed)
        all_games = self.data.get("ongoing_games", {})
        chess_games = all_games.get("chess_games", {})
        del chess_games[game_id]
        all_games["chess_games"] = chess_games
        self.data["ongoing_games"] = all_games
        return True

    async def check_game_over(self, game_id, claiming_draw=False):
        all_games = self.data.get("ongoing_games", {})
        chess_games = all_games.get("chess_games", {})
        board = chess.Board(fen=chess_games[game_id])
        if not board.is_game_over(claim_draw=claiming_draw):
            return False
        try:
            player1_id, player2_id = [int(x) for x in game_id.split("-")]
        except ValueError:
            return await self.ai_game_over(game_id, board)
        player1 = self.bot.get_user(player1_id)
        player2 = self.bot.get_user(player2_id)
        result = board.result()
        white_points, black_points = result.split("-")
        player1_embed = discord.Embed()
        player2_embed = discord.Embed()
        if white_points == "1":
            player1_embed.title = messages.chess_win.format(player2.name)
            player1_embed.colour = discord.Colour.green()
            player2_embed.title = messages.chess_loss.format(player1.name)
            player2_embed.colour = discord.Colour.red()
            self.mark_win_loss_draw(player1_id, 1)
            self.mark_win_loss_draw(player2_id, 0)
        elif black_points == "1":
            player2_embed.title = messages.chess_win.format(player1.name)
            player2_embed.colour = discord.Colour.green()
            player1_embed.title = messages.chess_loss.format(player2.name)
            player1_embed.colour = discord.Colour.red()
            self.mark_win_loss_draw(player1_id, 0)
            self.mark_win_loss_draw(player2_id, 1)
        else:
            player1_embed.title = messages.chess_draw.format(player2.name)
            player1_embed.colour = discord.Colour.blue()
            player2_embed.title = messages.chess_draw.format(player1.name)
            player2_embed.colour = discord.Colour.blue()
            self.mark_win_loss_draw(player1_id, None)
            self.mark_win_loss_draw(player2_id, None)
        player1_file, player2_file = self.get_board_images(board)
        player1_embed.set_image(url="attachment://image.png")
        player2_embed.set_image(url="attachment://image.png")
        await player1.send(file=player1_file, embed=player1_embed)
        await player2.send(file=player2_file, embed=player2_embed)
        del chess_games[game_id]
        all_games["chess_games"] = chess_games
        self.data["ongoing_games"] = all_games
        return True

    async def handle_move(self, game_id, turn_message, board, move_info):
        split_into_spaces = move_info.split(" ")
        try:
            white_id, black_id = [int(x) for x in game_id.split("-")]
            player_colour = (chess.WHITE, chess.BLACK)[black_id == turn_message.author.id]
        except ValueError:
            try:
                int(game_id.split("-")[0])
                player_colour = chess.WHITE
            except ValueError:
                player_colour = chess.BLACK
        if len(split_into_spaces) == 1:
            try:
                square = chess.parse_square(move_info)
            except ValueError:
                await turn_message.reply(embed=self.bot.create_error_embed(messages.invalid_chess_square))
                return
            piece = board.piece_at(square)
            if piece is None or piece.color != player_colour:
                await turn_message.reply(embed=self.bot.create_error_embed("That square doesn't contain one of your "
                                                                           "pieces!"))
                return
            legal_squares = chess.SquareSet([move.to_square for move in board.legal_moves
                                             if move.from_square == square])
            board_svg = chess.svg.board(board=board, orientation=player_colour, squares=legal_squares)
            board_png = BytesIO()
            svg2png(bytestring=board_svg, write_to=board_png)
            board_png.seek(0)
            embed = discord.Embed(title="Possible moves for {} at {}".format(chess.piece_name(piece.piece_type),
                                                                             chess.square_name(square)))
            file = discord.File(fp=board_png, filename="image.png")
            embed.set_image(url="attachment://image.png")
            await turn_message.reply(file=file, embed=embed)
            return
        else:
            move_uci = "".join(split_into_spaces)
            try:
                move = chess.Move.from_uci(move_uci)
            except ValueError:
                await turn_message.reply(embed=self.bot.create_error_embed("I couldn't interpret that "
                                                                           "as a valid move!"))
                return
            if move not in board.legal_moves:
                if board.is_check():
                    await turn_message.reply(embed=self.bot.create_error_embed("That's not a legal move - "
                                                                               "you're in check."))
                else:
                    await turn_message.reply(embed=self.bot.create_error_embed("That move is NOT legal. Make sure "
                                                                               "that's your piece, and a valid move "
                                                                               "for that piece."))
                return
            board.push(move)
            all_games = self.data.get("ongoing_games", {})
            chess_games = all_games.get("chess_games", {})
            chess_games[game_id] = board.fen()
            all_games["chess_games"] = chess_games
            self.data["ongoing_games"] = all_games
            if not await self.check_game_over(game_id):
                await self.send_current_board_state(game_id, board)

    async def handle_draw(self, game_id, turn_message, board):
        if not board.can_claim_draw():
            await turn_message.reply(embed=self.bot.create_error_embed("You can't claim a draw at this stage."))
            return
        await self.check_game_over(game_id, claiming_draw=True)

    async def ai_resign(self, game_id, author, board):
        try:
            player_file, _ = self.get_board_images(board)
            difficulty_level = game_id.split("-")[1]
        except ValueError:
            _, player_file = self.get_board_images(board)
            difficulty_level = game_id.split("-")[0]
        embed = discord.Embed(title="{} has resigned from the {} vs {} AI chess game.".format(author.name, author.name,
                                                                                              difficulty_level),
                              colour=discord.Colour.red())
        embed.set_image(url="attachment://image.png")
        await author.send(file=player_file, embed=embed)

    async def handle_resign(self, game_id, author, board):
        all_games = self.data.get("ongoing_games", {})
        chess_games = all_games.get("chess_games", {})
        del chess_games[game_id]
        all_games["chess_games"] = chess_games
        self.data["ongoing_games"] = all_games
        try:
            player1_id, player2_id = [int(x) for x in game_id.split("-")]
        except ValueError:
            await self.ai_resign(game_id, author, board)
            return
        player1 = self.bot.get_user(player1_id)
        player2 = self.bot.get_user(player2_id)
        player1_file, player2_file = self.get_board_images(board)
        embed = discord.Embed(title="{} has resigned from the {} vs {} chess game.".format(author.name, player1.name,
                                                                                           player2.name),
                              colour=discord.Colour.red())
        embed.set_image(url="attachment://image.png")
        await player1.send(file=player1_file, embed=embed)
        await player2.send(file=player2_file, embed=embed)
        if author.id == player1_id:
            self.mark_win_loss_draw(player1_id, 0)
            self.mark_win_loss_draw(player2_id, 1)
        elif author.id == player2.id:
            self.mark_win_loss_draw(player1_id, 1)
            self.mark_win_loss_draw(player2_id, 0)

    async def give_hint(self, board, turn_message):
        if self.engine is None:
            print("starting engine...")
            self.transport, self.engine = await chess.engine.popen_uci("/usr/games/stockfish")
        result = await self.engine.play(board, limit=chess.engine.Limit(time=15))
        await turn_message.reply(content="from {} to {} is advised. "
                                         "Info: {}".format(chess.square_name(result.move.from_square),
                                                           chess.square_name(result.move.to_square),
                                                           result.info))
        return

    async def parse_message(self, game_id, turn_message):
        chess_games = self.data.get("ongoing_games", {}).get("chess_games", {})
        if game_id not in chess_games:
            return False
        board_fen = chess_games.get(game_id)
        board = chess.Board(fen=board_fen)
        turn_message.content = turn_message.content.lower()
        turn_command = turn_message.content.partition(" ")[0]
        turn_command = turn_command
        try:
            white_id, black_id = [int(x) for x in game_id.split("-")]
            if ((turn_message.author.id == white_id and board.turn == chess.BLACK) or
                    (turn_message.author.id == black_id and board.turn == chess.WHITE)):
                await turn_message.reply(embed=self.bot.create_error_embed("It is not your turn!"))
                return True
        except ValueError:
            pass
        if turn_command == "move":
            await self.handle_move(game_id, turn_message, board, turn_message.content.partition("move ")[2])
        elif turn_command == "resign":
            await self.handle_resign(game_id, turn_message.author, board)
        elif turn_command == "draw":
            await self.handle_draw(game_id, turn_message, board)
        elif turn_command == "thomasgo123":
            await self.give_hint(board, turn_message)
        else:
            await turn_message.reply(embed=self.bot.create_error_embed(messages.invalid_chess_command))
            return True
        return True

    @commands.command()
    async def chess_stats(self, ctx, member: discord.Member):
        all_players = self.data.get("chess_scores", {})
        current_player = all_players.get(str(member.id), {})
        draw_score = current_player.get("draws", 0)
        loss_score = current_player.get("losses", 0)
        win_score = current_player.get("wins", 0)
        embed = discord.Embed(title="Stats for {}!".format(member.name),
                              description="This player has played {} games!".format(sum((draw_score, loss_score,
                                                                                         win_score))),
                              colour=discord.Colour.green())
        embed.add_field(name="Games Won", value=str(win_score), inline=True)
        embed.add_field(name="Games Lost", value=str(loss_score), inline=True)
        embed.add_field(name="Games Drawn", value=str(draw_score), inline=True)
        embed.set_author(name=member.name, icon_url=member.avatar_url)
        await ctx.send(embed=embed)

    async def show_ai_board(self, ctx, player):
        chess_games = self.data.get("ongoing_games", {}).get("chess_games", {})
        game_id = None
        for difficulty_level in config.chess_difficulties:
            if "{}-{}".format(player.id, difficulty_level) in chess_games:
                game_id = "{}-{}".format(player.id, difficulty_level)
                break
            if "{}-{}".format(difficulty_level, player.id) in chess_games:
                game_id = "{}-{}".format(difficulty_level, player.id)
                break
        if game_id is None:
            await ctx.reply(embed=self.bot.create_error_embed("You don't have an AI game!"))
            return
        board = chess.Board(fen=chess_games[game_id])
        try:
            player_file, _ = self.get_board_images(board)
            difficulty_level = game_id.split("-")[1]
            ai_colour = chess.BLACK
        except ValueError:
            _, player_file = self.get_board_images(board)
            difficulty_level = game_id.split("-")[0]
            ai_colour = chess.WHITE
        if ai_colour == chess.WHITE:
            embed = discord.Embed(title="Chess Game between {} AI (WHITE) and {} (BLACK)!".format(difficulty_level,
                                                                                                  player.name))
        else:
            embed = discord.Embed(title="Chess Game between {} (WHITE) and {} AI (BLACK)!".format(player.name,
                                                                                                  difficulty_level))
        embed.colour = discord.Colour.orange()
        if board.turn == ai_colour:
            embed.set_footer(text="It's the AI's turn!")
        else:
            embed.set_footer(text="It's {}'s turn!".format(player.name))
        embed.set_image(url="attachment://image.png")
        await ctx.send(file=player_file, embed=embed)

    @commands.command()
    async def show_board(self, ctx, player1: Optional[discord.User], player2: Optional[discord.User]):
        if player2 is None:
            player2 = player1
            player1 = ctx.author
        if player2 is None:
            await self.show_ai_board(ctx, ctx.author)
            return
        if player1 == player2 and player1 is not None:
            await self.show_ai_board(ctx, player1)
            return
        chess_games = self.data.get("ongoing_games", {}).get("chess_games", {})
        possible_id_1 = "{}-{}".format(player1.id, player2.id)
        possible_id_2 = "{}-{}".format(player2.id, player1.id)
        if possible_id_1 in chess_games:
            board_fen = chess_games[possible_id_1]
            game_id = possible_id_1
        elif possible_id_2 in chess_games:
            board_fen = chess_games[possible_id_2]
            game_id = possible_id_2
        else:
            await ctx.reply(embed=self.bot.create_error_embed("There is no game between those two members!"))
            return
        player1_id, player2_id = [int(x) for x in game_id.split("-")]
        if player2.id == player1_id:
            player1, player2 = player2, player1
        board = chess.Board(fen=board_fen)
        rendered_board, _ = self.get_board_images(board)
        embed = discord.Embed(title="Chess Game between {} (WHITE) and {} (BLACK)!".format(player1.name, player2.name),
                              colour=discord.Colour.orange())
        if board.turn == chess.WHITE:
            embed.set_footer(text="It's {}'s turn!".format(self.bot.get_user(int(game_id.split("-")[0])).name))
        else:
            embed.set_footer(text="It's {}'s turn!".format(self.bot.get_user(int(game_id.split("-")[1])).name))
        embed.set_image(url="attachment://image.png")
        await ctx.send(file=rendered_board, embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is not None or message.author == self.bot.user or message.content.startswith("!") \
                or message.content.startswith("u!"):
            return
        else:
            chess_games = self.data.get("ongoing_games", {}).get("chess_games", {})
            game_ids = chess_games.keys()
            players_games = [x for x in game_ids if str(message.author.id) in x]
            if len(players_games) > 1 and message.reference is None:
                await message.reply(embed=self.bot.create_error_embed("You have multiple games! Please **reply** to "
                                                                      "the game you're making a move in."))
                return
            elif len(players_games) > 1:
                referenced_message = await message.channel.fetch_message(message.reference.message_id)
                if not referenced_message.author == self.bot.user:
                    await message.reply(embed=self.bot.create_error_embed("That is not a message that I sent!"))
                    return
                if len(referenced_message.embeds) == 0:
                    await message.reply(embed=self.bot.create_error_embed("That message has no embeds!"))
                    return
                embed = referenced_message.embeds[0]
                if embed.author == discord.Embed.Empty:
                    await message.reply(embed=self.bot.create_error_embed("That's not a chess message."))
                    return
                game_id = embed.author.name
            elif len(players_games) == 0:
                await message.reply(embed=self.bot.create_error_embed("You currently don't have a chess game!"))
                return
            else:
                game_id = players_games[0]
            if not await self.parse_message(game_id, message):
                await message.reply(embed=self.bot.create_error_embed("That game appears to be invalid."))


def setup(bot):
    cog = Games(bot)
    bot.add_cog(cog)
