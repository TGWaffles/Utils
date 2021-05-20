from discord import Embed, Colour

from src.helpers.hypixel_helper import get_level_from_xp


class GameModeStats:
    def __init__(self, deaths, kills, beds_lost, beds_broken, wins, losses, games_played):
        self.deaths = deaths
        self.kills = kills
        self.beds_lost = beds_lost
        self.beds_broken = beds_broken
        self.wins = wins
        self.losses = losses
        self.games_played = games_played

    @classmethod
    def from_stats(cls, bedwars_stats, identifier: str):
        deaths = bedwars_stats.get(f"{identifier}_final_deaths_bedwars", 0)
        kills = bedwars_stats.get(f"{identifier}_final_kills_bedwars", 0)
        beds_lost = bedwars_stats.get(f"{identifier}_beds_lost_bedwars", 0)
        beds_broken = bedwars_stats.get(f"{identifier}_beds_broken_bedwars", 0)
        wins = bedwars_stats.get(f"{identifier}_wins_bedwars", 0)
        losses = bedwars_stats.get(f"{identifier}_losses_bedwars", 0)
        games_played = bedwars_stats.get(f"{identifier}_games_played_bedwars", 0)
        return cls(deaths, kills, beds_lost, beds_broken, wins, losses, games_played)

    @property
    def fkdr(self):
        return self.kills / self.deaths

    @property
    def bblr(self):
        return self.beds_broken / self.beds_lost

    def to_dict(self):
        return {"kills": self.kills, "deaths": self.deaths, "beds_lost": self.beds_lost,
                "beds_broken": self.beds_broken, "wins": self.wins, "losses": self.losses,
                "games_played": self.games_played}

    @classmethod
    def from_dict(cls, store_dict):
        deaths = store_dict["deaths"]
        kills = store_dict["kills"]
        beds_lost = store_dict["beds_lost"]
        beds_broken = store_dict["beds_broken"]
        wins = store_dict["wins"]
        losses = store_dict["losses"]
        games_played = store_dict["games_played"]
        return cls(deaths, kills, beds_lost, beds_broken, wins, losses, games_played)


class HypixelStats:
    def __init__(self, solos, doubles, trios, fours, two_four, experience):
        self.solos: GameModeStats = solos
        self.doubles: GameModeStats = doubles
        self.trios: GameModeStats = trios
        self.fours: GameModeStats = fours
        self.two_four: GameModeStats = two_four
        self.experience = experience

    @property
    def fkdr(self) -> float:
        return self.total_kills / self.total_deaths

    @property
    def total_kills(self) -> int:
        return self.solos.kills + self.doubles.kills + self.trios.kills + self.fours.kills + self.two_four.kills

    @property
    def kills(self) -> int:
        return self.total_kills

    @property
    def deaths(self) -> int:
        return self.total_deaths

    @property
    def total_deaths(self) -> int:
        return self.solos.deaths + self.doubles.deaths + self.trios.deaths + self.fours.deaths + self.two_four.deaths

    @property
    def games_played(self) -> int:
        return (self.solos.games_played + self.doubles.games_played + self.trios.games_played +
                self.fours.games_played + self.two_four.games_played)

    @property
    def threat_index(self) -> float:
        return ((self.fkdr ** 2) * self.level) / 10

    @property
    def level(self) -> float:
        return get_level_from_xp(self.experience)

    @property
    def bblr(self) -> float:
        return self.beds_broken / self.beds_lost

    @property
    def win_rate(self) -> float:
        return self.wins / self.losses

    @property
    def wins(self) -> int:
        return self.solos.wins + self.doubles.wins + self.trios.wins + self.fours.wins + self.two_four.wins

    @property
    def losses(self) -> int:
        return self.solos.losses + self.doubles.losses + self.trios.losses + self.fours.losses + self.two_four.losses

    @property
    def beds_broken(self) -> int:
        return (self.solos.beds_broken + self.doubles.beds_broken + self.trios.beds_broken +
                self.fours.beds_broken + self.two_four.beds_broken)

    @property
    def beds_lost(self) -> int:
        return (self.solos.beds_lost + self.doubles.beds_lost + self.trios.beds_lost +
                self.fours.beds_lost + self.two_four.beds_lost)

    @classmethod
    def from_stats(cls, bedwars_stats: dict):
        solos = GameModeStats.from_stats(bedwars_stats, "eight_one")
        doubles = GameModeStats.from_stats(bedwars_stats, "eight_two")
        trios = GameModeStats.from_stats(bedwars_stats, "four_three")
        fours = GameModeStats.from_stats(bedwars_stats, "four_four")
        two_four = GameModeStats.from_stats(bedwars_stats, "two_four")
        experience = bedwars_stats.get("Experience", 0)
        return cls(solos, doubles, trios, fours, two_four, experience)

    def to_dict(self):
        return {"solos": self.solos.to_dict(), "doubles": self.doubles.to_dict(),
                "trios": self.trios.to_dict(), "fours": self.fours.to_dict(),
                "two_four": self.two_four.to_dict(), "experience": self.experience}

    @classmethod
    def from_dict(cls, store_dict):
        solos = GameModeStats.from_dict(store_dict["solos"])
        doubles = GameModeStats.from_dict(store_dict["doubles"])
        trios = GameModeStats.from_dict(store_dict["trios"])
        fours = GameModeStats.from_dict(store_dict["fours"])
        two_four = GameModeStats.from_dict(store_dict["two_four"])
        experience = store_dict["experience"]
        return cls(solos, doubles, trios, fours, two_four, experience)


def create_delta_embeds(title, yesterday: HypixelStats, today: HypixelStats) -> list[Embed]:
    all_embeds = []
    categories = [("Overall Daily Statistics", (today, yesterday)), ("Solos", (today.solos, yesterday.solos)),
                  ("Doubles", (today.doubles, yesterday.doubles)), ("Trios", (today.trios, yesterday.trios)),
                  ("Fours", (today.fours, yesterday.fours)), ("Two_Fours", (today.two_four, yesterday.two_four))]
    for category in categories:
        subtitle = category[0]
        today, yesterday = category[1]
        embed = Embed(title=title, colour=Colour.blue(), description=subtitle)

        final_kills = today.kills - yesterday.kills
        embed.add_field(name="Final Kills", value=str(final_kills), inline=True)
        final_deaths = today.deaths - yesterday.deaths
        embed.add_field(name="Final Deaths", value=str(final_deaths), inline=True)
        final_fkdr = str(round(final_kills / final_deaths, 2)) if final_deaths != 0 else "Infinite"
        embed.add_field(name="FKDR", value=final_fkdr, inline=True)

        beds_broken = today.beds_broken - yesterday.beds_broken
        embed.add_field(name="Beds Broken", value=str(beds_broken))
        beds_lost = today.beds_lost - yesterday.beds_lost
        embed.add_field(name="Beds Lost", value=str(beds_lost))
        bblr = str(round(beds_broken / beds_lost, 2)) if beds_lost != 0 else "Infinite"
        embed.add_field(name="BBLR", value=bblr)

        games_won = today.wins - yesterday.wins
        embed.add_field(name="Games Won", value=str(games_won))
        games_lost = today.losses - yesterday.losses
        embed.add_field(name="Games Lost", value=str(games_lost))
        win_rate = str(round(games_won / games_lost, 2)) if games_lost != 0 else "Infinite"
        embed.add_field(name="Winrate", value=win_rate)
        all_embeds.append(embed)

    return all_embeds