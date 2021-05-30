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
        if store_dict is None:
            return cls(0, 0, 0, 0, 0, 0, 0)
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
        self.game_modes = (self.solos, self.doubles, self.trios, self.fours, self.two_four)
        self.experience = experience

    @property
    def fkdr(self) -> float:
        if self.total_deaths == 0:
            return 0
        return self.total_kills / self.total_deaths

    @property
    def total_kills(self) -> int:
        return sum(x.kills for x in self.game_modes)

    @property
    def kills(self) -> int:
        return self.total_kills

    @property
    def deaths(self) -> int:
        return self.total_deaths

    @property
    def total_deaths(self) -> int:
        return sum(x.deaths for x in self.game_modes)

    @property
    def games_played(self) -> int:
        return sum(x.games_played for x in self.game_modes)

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
        return sum(x.wins for x in self.game_modes)

    @property
    def losses(self) -> int:
        return sum(x.losses for x in self.game_modes)

    @property
    def beds_broken(self) -> int:
        return sum(x.beds_broken for x in self.game_modes)

    @property
    def beds_lost(self) -> int:
        return sum(x.beds_lost for x in self.game_modes)

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

    def copy(self):
        return HypixelStats.from_dict(self.to_dict())

    @classmethod
    def split_up(cls, last_record, new_record) -> list:
        last_record: HypixelStats = last_record
        new_record: HypixelStats = new_record
        if new_record.games_played - last_record.games_played == 1:
            return [new_record]
        elif new_record.games_played - last_record.games_played < 1:
            return []
        all_have_one = True
        modes_with_one = []
        game_mode_names = ("solos", "doubles", "trios", "fours", "two_four")
        for game_mode_name in game_mode_names:
            old_mode = getattr(last_record, game_mode_name)
            new_mode = getattr(new_record, game_mode_name)
            if new_mode.games_played - old_mode.games_played > 1:
                all_have_one = False
                break
            elif new_mode.games_played - old_mode.games_played == 1:
                modes_with_one.append(game_mode_name)
        returning_list = []
        intermediary = cls(last_record.solos, last_record.doubles, last_record.trios, last_record.fours,
                           last_record.two_four, last_record.experience)
        if all_have_one:
            for mode_name in modes_with_one:
                changing_record = intermediary.copy()
                setattr(changing_record, mode_name, getattr(new_record, mode_name))
                intermediary = changing_record
                returning_list.append(changing_record)
            return returning_list
        for mode_name in game_mode_names:
            new_mode = getattr(new_record, mode_name)
            old_mode = getattr(last_record, mode_name)
            games_difference = new_mode.games_played - old_mode.games_played
            if games_difference == 0:
                continue
            losses = new_mode.losses - old_mode.losses
            wins = new_mode.wins - old_mode.wins
            final_deaths = new_mode.deaths - old_mode.deaths
            final_kills = new_mode.kills - old_mode.kills
            beds_broken = new_mode.beds_broken - old_mode.beds_broken
            beds_lost = new_mode.beds_lost - old_mode.beds_lost
            for i in range(games_difference):
                current_stats = getattr(intermediary, mode_name)
                if i == games_difference - 1:
                    stats = new_mode
                elif losses > 0:
                    if final_deaths > 0:
                        deaths = current_stats.deaths + 1
                        final_deaths -= 1
                    else:
                        deaths = current_stats.deaths
                    if beds_lost > 0:
                        this_lost = current_stats.beds_lost + 1
                        beds_lost -= 1
                    else:
                        this_lost = current_stats.beds_lost
                    stats = GameModeStats(deaths, current_stats.kills, this_lost, current_stats.beds_broken,
                                          current_stats.wins, current_stats.losses + 1, current_stats.games_played + 1)
                    losses -= 1
                else:
                    if final_deaths > 0:
                        deaths = current_stats.deaths + 1
                        final_deaths -= 1
                    else:
                        deaths = current_stats.deaths
                    if beds_lost > 0:
                        this_lost = current_stats.beds_lost + 1
                        beds_lost -= 1
                    else:
                        this_lost = current_stats.beds_lost
                    if final_kills > 0:
                        this_kills = int(final_kills / wins)
                        final_kills -= this_kills
                        this_kills += current_stats.kills
                    else:
                        this_kills = current_stats.kills
                    if beds_broken > 0:
                        this_broken = int(beds_broken / wins)
                        beds_broken -= this_broken
                        this_broken += current_stats.beds_broken
                    else:
                        this_broken = current_stats.beds_broken
                    stats = GameModeStats(deaths, this_kills, this_lost, this_broken,
                                          current_stats.wins + 1, current_stats.losses, current_stats.games_played + 1)
                    wins -= 1
                changing_record = intermediary.copy()
                setattr(changing_record, mode_name, stats)
                intermediary = changing_record
                returning_list.append(changing_record)
        return returning_list

    @classmethod
    def from_dict(cls, store_dict):
        if store_dict is None:
            solos = GameModeStats.from_dict(None)
            doubles = GameModeStats.from_dict(None)
            trios = GameModeStats.from_dict(None)
            fours = GameModeStats.from_dict(None)
            two_four = GameModeStats.from_dict(None)
            experience = 0
            return cls(solos, doubles, trios, fours, two_four, experience)
        solos = GameModeStats.from_dict(store_dict["solos"])
        doubles = GameModeStats.from_dict(store_dict["doubles"])
        trios = GameModeStats.from_dict(store_dict["trios"])
        fours = GameModeStats.from_dict(store_dict["fours"])
        two_four = GameModeStats.from_dict(store_dict["two_four"])
        experience = store_dict["experience"]
        return cls(solos, doubles, trios, fours, two_four, experience)


def create_delta_embeds(title, yesterday: HypixelStats, today: HypixelStats, image=False) -> list[Embed]:
    all_embeds = []
    categories = [("Overall", (today, yesterday)), ("Solos", (today.solos, yesterday.solos)),
                  ("Doubles", (today.doubles, yesterday.doubles)), ("Trios", (today.trios, yesterday.trios)),
                  ("Fours", (today.fours, yesterday.fours)), ("4v4", (today.two_four, yesterday.two_four))]
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
        if image:
            embed.set_thumbnail(url="attachment://head.png")
        if subtitle == "Overall":
            games_played = today.games_played - yesterday.games_played
            level = round(today.level - yesterday.level, 2)
            threat_index = round(today.threat_index - yesterday.threat_index, 2)
            embed.add_field(name="Games Played", value=str(games_played))
            embed.add_field(name="Level Change", value=str(level))
            embed.add_field(name="Threat Index Change", value=str(threat_index))
        all_embeds.append(embed)

    return all_embeds