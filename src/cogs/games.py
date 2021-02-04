import discord
import numpy as np
import chess.svg
import random
from io import BytesIO
from cairosvg import svg2png

from src.helpers.storage_helper import DataHelper
from src.storage import messages
from src.storage import config
from discord.ext import commands
from main import UtilsBot
from scipy.signal import convolve2d


class Games(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.data = DataHelper()

    async def connect4_send_to_player(self, player, board: np.array, their_turn):
        board_embed = discord.Embed(title="Connect Four!", colour=discord.Colour.light_grey())
        for array in board:
            for character in array:
                board_embed.description += [config.c4_none, config.c4_red, config.c4_yellow][character]
            board_embed.description += "\n"
        board_embed.add_field(name="Turn", value="It is " + ("NOT ", "")[their_turn] +"your turn!")

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
        horizontal_kernel = np.array([[ 1, 1, 1, 1]])
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
    async def chess(self, ctx, player2: discord.Member):
        print("1")
        all_games = self.data.get("ongoing_games", {})
        chess_games = all_games.get("chess_games", {})
        print(2)
        player1 = ctx.author
        possible_id_1 = "{}-{}".format(player1.id, player2.id)
        possible_id_2 = "{}-{}".format(player2.id, player1.id)
        print(3)
        if possible_id_1 in chess_games or possible_id_2 in chess_games:
            await ctx.reply(embed=self.bot.create_error_embed("You already have a chess game with that person!"))
            return
        new_game = chess.Board()
        print(4)
        both_ids = [player1.id, player2.id]
        random.shuffle(both_ids)
        white, black = both_ids
        game_id = "{}-{}".format(white, black)
        print(5)
        chess_games[game_id] = new_game.fen()
        all_games["chess_games"] = chess_games
        self.data["ongoing_games"] = all_games
        print(6)
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

    async def send_current_board_state(self, game_id):
        print(7)
        chess_games = self.data.get("ongoing_games", {}).get("chess_games", {})
        print(chess_games)
        if game_id not in chess_games:
            return False
        board_fen = chess_games.get(game_id)
        board = chess.Board(fen=board_fen)
        print(8)
        player1_id, player2_id = [int(x) for x in game_id.split("-")]
        player1 = self.bot.get_user(player1_id)
        player2 = self.bot.get_user(player2_id)
        player1_embed = discord.Embed(title="Chess Game between {} and {}!".format(player1.name, player2.name))
        player2_embed = discord.Embed(title="Chess Game between {} and {}!".format(player1.name, player2.name))
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
        print(9)
        await player1.send(file=player1_file, embed=player1_embed)
        await player2.send(file=player2_file, embed=player2_embed)
        print(10)

    async def check_game_over(self, game_id, claiming_draw=False):
        all_games = self.data.get("ongoing_games", {})
        chess_games = all_games.get("chess_games", {})
        board = chess.Board(fen=chess_games[game_id])
        if not board.is_game_over():
            return False
        player1_id, player2_id = [int(x) for x in game_id.split("-")]
        player1 = self.bot.get_user(player1_id)
        player2 = self.bot.get_user(player2_id)
        result = board.result()
        white_points, black_points = result.split("-")
        player1_embed = discord.Embed()
        player2_embed = discord.Embed()
        if white_points == "1":
            player1_embed.title = messages.chess_win.format(player2.name)
            player2_embed.title = messages.chess_loss(player1.name)
        elif black_points == "1":
            player2_embed.title = messages.chess_win.format(player1.name)
            player1_embed.title = messages.chess_loss(player2.name)
        else:
            player1_embed.title = messages.chess_draw.format(player2.name)
            player2_embed.title = messages.chess_draw.format(player1.name)
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
        white_id, black_id = [int(x) for x in game_id.split("-")]
        player_colour = (chess.WHITE, chess.BLACK)[black_id == turn_message.author.id]
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
            squares = board.attacks(square)
            board_svg = chess.svg.board(board=board, orientation=player_colour, squares=squares)
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
                await turn_message.reply(embed=self.bot.create_error_embed("That move is NOT legal. Make sure that's "
                                                                           "your piece, a valid move for that piece, "
                                                                           "and that you're not in check."))
                return
            board.push(move)
            all_games = self.data.get("ongoing_games", {})
            chess_games = all_games.get("chess_games", {})
            chess_games[game_id] = board.fen()
            all_games["chess_games"] = chess_games
            self.data["ongoing_games"] = all_games
            if not await self.check_game_over(game_id):
                print("not game over, sending.")
                await self.send_current_board_state(game_id)
            print("Finished move checking, ig")

    async def parse_message(self, game_id, turn_message):
        chess_games = self.data.get("ongoing_games", {}).get("chess_games", {})
        if game_id not in chess_games:
            return False
        board_fen = chess_games.get(game_id)
        board = chess.Board(fen=board_fen)
        turn_command = turn_message.content.partition(" ")[0].lower()
        white_id, black_id = [int(x) for x in game_id.split("-")]
        if ((turn_message.author.id == white_id and board.turn == chess.BLACK) or
                (turn_message.author.id == black_id and board.turn == chess.WHITE)):
            await turn_message.reply(embed=self.bot.create_error_embed("It is not your turn!"))
            return True
        if turn_command == "move":
            await self.handle_move(game_id, turn_message, board, turn_message.content.partition("move ")[2])
        elif turn_command == "resign":
            pass
        elif turn_command == "draw":
            pass
        else:
            await turn_message.reply(embed=self.bot.create_error_embed(messages.invalid_chess_command))
            return False
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is not None or message.author == self.bot.user:
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

