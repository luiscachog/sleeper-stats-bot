# -*- coding: utf-8 -*-
import logging
import os
import subprocess
import time

import pendulum
import requests
import schedule
from constants import CLOSE_NUM, HTTP_USER_AGENT, LEAGUE_NAME, TIMEZONE
from discord import Discord
from group_me import GroupMe
from prettytable import PrettyTable
from slack import Slack
from sleeper_wrapper import League, Players, Stats
from telegram import Telegram


def get_current_season(api_key, logger):
    """
    Returns the current season year
    :param api_key: String https://sportsdata.io API Key
    :param logger: A logger object for logging debug
    :return: String with the current season year
    """
    headers = {
        "User-Agent": HTTP_USER_AGENT,
        "Ocp-Apim-Subscription-Key": api_key,
    }

    try:
        response = requests.get(
            "https://api.sportsdata.io/v3/nfl/scores/json/CurrentSeason",
            headers=headers,
            timeout=10,
        )
    except Exception:
        response = None

    if not response or response.status_code != 200:
        logger.debug(
            "Check SportsData API, status code: %s", response.status_code
        )
        raise Exception(
            "Check SportsData API. \n endpoint: "
            + str(response.url)
            + " \n status code: "
            + str(response.status_code)
        )
    else:
        current_season = response.text
        return current_season


def get_season_week_date(
    current_season, season_type, game_number, api_key, logger
):
    """
    Returns the date when the current season starts
    :param current_season: String with the current season year
    :param season_type: String with the season type.
        Examples: PRE, POST, STAR, It will concatenate to
        current_season to form the final string.
        Examples: 2021, 2021PRE, 2021POST, 2021STAR, 2022
    :param game_number: Number of the game that we want to pull
    :param api_key: String https://sportsdata.io API Key
    :param logger: A logger object for logging debug
    :return: String with the current season year
    """

    headers = {
        "User-Agent": HTTP_USER_AGENT,
        "Ocp-Apim-Subscription-Key": api_key,
    }
    url = (
        "https://api.sportsdata.io/v3/nfl/scores/json/Schedules/"
        + current_season
        + season_type
    )
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Error ({response.status_code}), check API address")
    else:
        data = response.json()
        season_week = data[game_number]

    season_week_date = pendulum.parse(season_week["Date"], tz=TIMEZONE)

    return season_week_date


def get_league_scoreboards(league, week):
    """
    Returns the scoreboards from the specified sleeper league.
    :param league: Object league
    :param week: Int week to get the scoreboards of
    :return: dictionary of the scoreboards;
        https://github.com/SwapnikKatkoori/sleeper-api-wrapper#get_scoreboards
    """
    matchups = league.get_matchups(week)
    users = league.get_users()
    rosters = league.get_rosters()
    scoreboards = league.get_scoreboards(
        rosters, matchups, users, "pts_half_ppr", week
    )

    return scoreboards


def get_highest_score(league, api_key):
    """
    Gets the highest score of the week
    :param league: Object league
    :return: List [score, team_name]
    """
    week = get_current_week(api_key)
    scoreboards = get_league_scoreboards(league, week)
    max_score = [0, None]

    for matchup_id in scoreboards:
        matchup = scoreboards[matchup_id]
        # check both teams in the matchup to see if they
        # have the highest score in the league
        if float(matchup[0][1]) > max_score[0]:
            score = matchup[0][1]
            team_name = matchup[0][0]
            max_score[0] = score
            max_score[1] = team_name
        if float(matchup[1][1]) > max_score[0]:
            score = matchup[1][1]
            team_name = matchup[1][0]
            max_score[0] = score
            max_score[1] = team_name
    return max_score


def get_lowest_score(league, api_key):
    """
    Gets the lowest score of the week
    :param league: Object league
    :return: List[score, team_name]
    """
    week = get_current_week(api_key)
    scoreboards = get_league_scoreboards(league, week)
    min_score = [999, None]

    for matchup_id in scoreboards:
        matchup = scoreboards[matchup_id]
        # check both teams in the matchup to see if they
        # have the lowest score in the league
        if float(matchup[0][1]) < min_score[0]:
            score = matchup[0][1]
            team_name = matchup[0][0]
            min_score[0] = score
            min_score[1] = team_name
        if float(matchup[1][1]) < min_score[0]:
            score = matchup[1][1]
            team_name = matchup[1][0]
            min_score[0] = score
            min_score[1] = team_name
    return min_score


def make_roster_dict(starters_list, bench_list):
    """
    Takes in a teams starter list and bench list and makes
    a dictionary with positions.
    :param starters_list: List of a teams starters
    :param bench_list: List of a teams bench players
    :return: {starters:{position: []} , bench:{ position: []} }
    """
    week = get_current_week()
    players = Players().get_all_players()
    stats = Stats()
    week_stats = stats.get_week_stats("regular", STARTING_YEAR, week)

    roster_dict = {"starters": {}, "bench": {}}
    for player_id in starters_list:
        player = players[player_id]
        player_position = player["position"]
        player_name = player["first_name"] + " " + player["last_name"]
        try:
            player_std_score = week_stats[player_id]["pts_std"]
        except KeyError:
            player_std_score = None

        player_and_score_tup = (player_name, player_std_score)
        if player_position not in roster_dict["starters"]:
            roster_dict["starters"][player_position] = [player_and_score_tup]
        else:
            roster_dict["starters"][player_position].append(
                player_and_score_tup
            )

    for player_id in bench_list:
        player = players[player_id]
        player_position = player["position"]
        player_name = player["first_name"] + " " + player["last_name"]

        try:
            player_std_score = week_stats[player_id]["pts_std"]
        except KeyError:
            player_std_score = None

        player_and_score_tup = (player_name, player_std_score)
        if player_position not in roster_dict["bench"]:
            roster_dict["bench"][player_position] = [player_and_score_tup]
        else:
            roster_dict["bench"][player_position].append(player_and_score_tup)

    return roster_dict


def get_highest_bench_points(bench_points):
    """
    Returns a tuple of the team with the highest scoring bench
    :param bench_points: List [(team_name, std_points)]
    :return: Tuple (team_name, std_points) of the team with
            most std_points
    """
    max_tup = ("team_name", 0)
    for tup in bench_points:
        if tup[1] > max_tup[1]:
            max_tup = tup
    return max_tup


def map_users_to_team_name(users):
    """
    Maps user_id to team_name
    :param users:  https://docs.sleeper.app/#getting-users-in-a-league
    :return: Dict {user_id:team_name}
    """
    users_dict = {}

    # Maps the user_id to team name for easy lookup
    for user in users:
        try:
            users_dict[user["user_id"]] = user["metadata"]["team_name"]
        except Exception:
            users_dict[user["user_id"]] = user["display_name"]
    return users_dict


def map_roster_id_to_owner_id(league):
    """

    :return: Dict {roster_id: owner_id, ...}
    """
    rosters = league.get_rosters()
    result_dict = {}
    for roster in rosters:
        roster_id = roster["roster_id"]
        owner_id = roster["owner_id"]
        result_dict[roster_id] = owner_id

    return result_dict


def get_bench_points(league, api_key):
    """

    :param league: Object league
    :return: List [(team_name, score), ...]
    """
    week = get_current_week(api_key)

    users = league.get_users()
    matchups = league.get_matchups(week)

    stats = Stats()
    # WEEK STATS NEED TO BE FIXED
    week_stats = stats.get_week_stats("regular", STARTING_YEAR, week)

    owner_id_to_team_dict = map_users_to_team_name(users)
    roster_id_to_owner_id_dict = map_roster_id_to_owner_id(league)
    result_list = []

    for matchup in matchups:
        starters = matchup["starters"]
        all_players = matchup["players"]
        bench = set(all_players) - set(starters)

        std_points = 0
        for player in bench:
            try:
                std_points += week_stats[str(player)]["pts_std"]
            except Exception:
                continue
        owner_id = roster_id_to_owner_id_dict[matchup["roster_id"]]
        if owner_id is None:
            team_name = "Team name not available"
        else:
            team_name = owner_id_to_team_dict[owner_id]
        result_list.append((team_name, std_points))

    return result_list


def get_negative_starters(league, api_key):
    """
    Finds all of the players that scores negative points in standard and
    :param league: Object league
    :return: Dict { "owner_name":[("player_name", std_score), ...],
                    "owner_name":...}
    """
    week = get_current_week(api_key)

    users = league.get_users()
    matchups = league.get_matchups(week)

    stats = Stats()
    # WEEK STATS NEED TO BE FIXED
    week_stats = stats.get_week_stats("regular", STARTING_YEAR, week)

    players = Players()
    players_dict = players.get_all_players()
    owner_id_to_team_dict = map_users_to_team_name(users)
    roster_id_to_owner_id_dict = map_roster_id_to_owner_id(league)

    result_dict = {}

    for i, matchup in enumerate(matchups):
        starters = matchup["starters"]
        negative_players = []
        for starter_id in starters:
            try:
                std_pts = week_stats[str(starter_id)]["pts_std"]
            except KeyError:
                std_pts = 0
            if std_pts < 0:
                player_info = players_dict[starter_id]
                player_name = "{} {}".format(
                    player_info["first_name"], player_info["last_name"]
                )
                negative_players.append((player_name, std_pts))

        if len(negative_players) > 0:
            owner_id = roster_id_to_owner_id_dict[matchup["roster_id"]]

            if owner_id is None:
                team_name = "Team name not available" + str(i)
            else:
                team_name = owner_id_to_team_dict[owner_id]
            result_dict[team_name] = negative_players
    return result_dict


def check_starters_and_bench(lineup_dict):
    """

    :param lineup_dict: A dict returned by make_roster_dict
    :return:
    """
    for key in lineup_dict:
        pass


def get_current_week(api_key):
    """
    Gets the current week.
    :return: Int current week
    """
    headers = {
        "User-Agent": HTTP_USER_AGENT,
        "Ocp-Apim-Subscription-Key": api_key,
    }
    url = "https://api.sportsdata.io/v3/nfl/scores/json/CurrentWeek"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Error ({response.status_code}), check API address")
    else:
        current_week = response.json()

    return current_week


def get_bot_message_schedule():
    x = PrettyTable()

    x.add_column(
        "Day",
        [
            "Thursday",
            "Friday",
            "Sunday",
            "Monday",
            "Tuesday",
            "Tuesday",
            "Daily",
        ],
    )
    x.add_column(
        "Hour", ["19:00", "10:00", "22:00", "10:00", "10:00", "11:00", "18:00"]
    )
    x.add_column(
        "Message",
        [
            "Week Matchups",
            "Thursday Night Scores",
            "Close Games",
            "Sunday Night Scores",
            "PDF Report",
            "League Standings",
            "Draft Reminder",
        ],
    )

    return x.get_string()


def get_welcome_string():
    """
    Creates and returns the welcome message
    :return: String welcome message
    """
    welcome_message = "👋 Hello, I am the " + LEAGUE_NAME + " Stats Bot! \n\n"
    welcome_message += "I am going to sent you some stats about the league"
    welcome_message += " according to this schedule: \n "
    welcome_message += "<pre>" + get_bot_message_schedule() + "</pre> \n "
    welcome_message += "Welcome to the {} season \n\n".format(STARTING_YEAR)
    welcome_message += "I'm still in dev mode, new features on the way."

    return welcome_message


def send_any_string(string_to_send):
    """
    Send any string to the bot.
    :param string_to_send: The string to send a bot
    :return: string to send
    """
    return string_to_send


def get_matchups_string(league, api_key):
    """
    Creates and returns a message of the current week's matchups.
    :param league: Object league
    :return: string message of the current week matchups.
    """
    week = get_current_week(api_key)
    scoreboards = get_league_scoreboards(league, week)
    final_message_string = "________________________________\n"
    final_message_string += "Matchups for Week {}:\n".format(week)
    final_message_string += "________________________________\n\n"

    for i, matchup_id in enumerate(scoreboards):
        matchup = scoreboards[matchup_id]
        matchup_string = "Matchup {}:\n".format(i + 1)
        matchup_string += "{} VS. {} \n\n".format(matchup[0][0], matchup[1][0])
        final_message_string += matchup_string

    return final_message_string


def get_playoff_bracket_string(league):
    """
    Creates and returns a message of the league's playoff bracket.
    :param league: Object league
    :return: string message league's playoff bracket
    """
    bracket = league.get_playoff_winners_bracket()
    return bracket


def get_scores_string(league, api_key):
    """
    Creates and returns a message of the league's current
    scores for the current week.
    :param league: Object league
    :return: string message of the current week's scores
    """
    week = get_current_week(api_key)
    scoreboards = get_league_scoreboards(league, week)
    final_message_string = "Scores \n____________________\n\n"
    for i, matchup_id in enumerate(scoreboards):
        matchup = scoreboards[matchup_id]
        first_score = 0
        second_score = 0
        if matchup[0][1] is not None:
            first_score = matchup[0][1]
        if matchup[1][1] is not None:
            second_score = matchup[1][1]
        string_to_add = ""
        string_to_add = (
            "Matchup {}\n{:<8} {:<8.2f}\n{:<8} {:<8.2f}\n\n".format(
                i + 1, matchup[0][0], first_score, matchup[1][0], second_score
            )
        )
        final_message_string += string_to_add

    return final_message_string


def get_close_games_string(league, close_num, api_key):
    """
    Creates and returns a message of the league's close games.
    :param league: Object league
    :param close_num: Int point difference to considered a close game.
    :return: string message of the current week's close games.
    """
    week = get_current_week(api_key)
    scoreboards = get_league_scoreboards(league, week)
    close_games = league.get_close_games(scoreboards, close_num)

    final_message_string = "___________________\n"
    final_message_string += "Close games😰😰\n"
    final_message_string += "___________________\n\n"

    for i, matchup_id in enumerate(close_games):
        matchup = close_games[matchup_id]
        string_to_add = ""
        string_to_add += (
            "Matchup {}\n{:<8} {:<8.2f}\n{:<8} {:<8.2f}\n\n".format(
                i + 1,
                matchup[0][0],
                matchup[0][1],
                matchup[1][0],
                matchup[1][1],
            )
        )
        final_message_string += string_to_add
    return final_message_string


def get_standings_string(league):
    """
    Creates and returns a message of the league's standings.
    :param league: Object league
    :return: string message of the leagues standings.
    """
    rosters = league.get_rosters()
    users = league.get_users()
    standings = league.get_standings(rosters, users)
    final_message_string = "________________________________\n"
    final_message_string += (
        "Standings \n|{0:^7}|{1:^7}|{2:^7}|{3:^7}\n".format(
            "rank", "team", "wins", "points"
        )
    )
    final_message_string += "________________________________\n\n"
    try:
        playoff_line = os.environ["NUMBER_OF_PLAYOFF_TEAMS"] - 1
    except Exception:
        playoff_line = 5
    for i, standing in enumerate(standings):
        team = standing[0]
        if team is None:
            team = "Team NA"
        if len(team) >= 50:
            team_name = team[:50]
        else:
            team_name = team
        string_to_add = "{0:^7} | {1:^10} | {2:>7} | {3:>7}\n".format(
            i + 1, team_name, standing[1], standing[3]
        )
        if i == playoff_line:
            string_to_add += "________________________________\n\n"
        final_message_string += string_to_add
    return final_message_string


def get_best_and_worst_string(league, api_key):
    """
    :param league: Object league
    :return: String of the highest Scorer, lowest scorer,
            most points left on the bench, and Why bother section.
    """
    highest_scorer = get_highest_score(league, api_key)[1]
    highest_score = get_highest_score(league, api_key)[0]
    highest_score_emojis = "🏆🏆"
    lowest_scorer = get_lowest_score(league, api_key)[1]
    lowest_score = get_lowest_score(league, api_key)[0]
    lowest_score_emojis = "😢😢"
    final_string = ""
    final_string += "{} Highest Scorer:\n{}\n{:.2f}\n\n".format(
        highest_score_emojis, highest_scorer, highest_score
    )
    final_string += "{} Lowest Scorer:\n {}\n{:.2f}\n\n".format(
        lowest_score_emojis, lowest_scorer, lowest_score
    )
    highest_bench_score_emojis = " 😂😂"
    bench_points = get_bench_points(league, api_key)
    largest_scoring_bench = get_highest_bench_points(bench_points)
    final_string += "{} Most points left on the bench:\n{}\n{:.2f}\n\n".format(
        highest_bench_score_emojis,
        largest_scoring_bench[0],
        largest_scoring_bench[1],
    )
    negative_starters = get_negative_starters(league, api_key)
    if negative_starters:
        final_string += "🤔🤔Why bother?\n"

    for key in negative_starters:
        negative_starters_list = negative_starters[key]
        final_string += "{} Started:\n".format(key)
        for negative_starter_tup in negative_starters_list:
            final_string += "{} who sucks, and had {} points \n".format(
                negative_starter_tup[0], negative_starter_tup[1]
            )
        final_string += "\n"
    return final_string


def get_bench_beats_starters_string(league, api_key):
    """
    Gets all bench players that outscored starters at their position.
    :param league: Object league
    :return: String teams which had bench players outscore their
            starters in a position.
    """
    week = get_current_week(api_key)
    matchups = league.get_matchups(week)

    final_message_string = "________________________________\n"
    final_message_string += "Worst of the week💩💩\n"
    final_message_string += "________________________________\n\n"

    for matchup in matchups:
        starters = matchup["starters"]
        all_players = matchup["players"]
        bench = set(all_players) - set(starters)

    return bench


def get_draft_reminder_string(league):
    """
    Gets a string of the current season draft reminder.
    :param league: Object league
    :return: String with
    """
    draft_date = pendulum.from_timestamp(
        league.get_all_drafts()[0]["start_time"] / 1000, tz=TIMEZONE
    )

    time_to_draft = draft_date - pendulum.now(tz=TIMEZONE)

    draft_reminder_string = "________________________________\n"
    draft_reminder_string += "Draft Reminder\n"
    draft_reminder_string += "________________________________\n\n"

    if 0 < time_to_draft.days <= 4:
        draft_reminder_string += (
            time_to_draft.in_words()
            + " until draft day.  [ "
            + draft_date.format("dddd Do [of] MMMM YYYY HH:mm A")
            + "] \n"
        )
    else:
        draft_reminder_string += (
            "Draft day is today! [ " + draft_date.format("HH:mm A") + " ]\n"
        )

    return draft_reminder_string


def get_pdf_report_link(league_id, season):
    script_path = "weekly-report/main.py"
    options = (
        " -a -l " + league_id + " -y " + season + " -r -c ../etc/config.ini"
    )
    dirname = os.path.dirname(os.path.realpath("__file__"))
    gdrive_message_path = os.path.join(
        dirname, "weekly-report/output/data/gdrive_message.txt"
    )

    if os.path.exists(gdrive_message_path):
        os.remove(gdrive_message_path)
    else:
        print("Before The file " + gdrive_message_path + " does not exist")

    subprocess.Popen(
        "yes | python " + script_path + options, shell=True
    ).wait()

    if os.path.exists(gdrive_message_path):
        print("File was found")
        file = open(gdrive_message_path, "r")
        return file.read()
    else:
        print("The file " + gdrive_message_path + " does not exist")


if __name__ == "__main__":
    """
    Main script for the bot
    """
    bot = None
    bot_type = os.environ["BOT_TYPE"]
    league_id = os.environ["LEAGUE_ID"]

    api_key = os.environ["API_KEY"]

    # Check if the user specified the close game num. Default is 10.
    try:
        close_num = os.environ["CLOSE_NUM"]
    except Exception:
        close_num = CLOSE_NUM

    # Check if the user specified the debug flag. Default is True
    try:
        show_debug = os.environ["DEBUG"]
    except Exception:
        show_debug = True

    # Check if the user specified the init_message flag. Default is True
    try:
        init_message = os.environ["INIT_MESSAGE"]
    except Exception:
        init_message = True

    logging.basicConfig()

    schedule_logger = logging.getLogger("schedule")
    schedule_logger.setLevel(level=logging.DEBUG)
    schedule_logger.disabled = not show_debug

    bot_logger = logging.getLogger("bot")
    bot_logger.setLevel(level=logging.DEBUG)
    bot_logger.disabled = not show_debug

    season = get_current_season(api_key, bot_logger)
    league = League(league_id)
    draft_date = pendulum.from_timestamp(
        league.get_all_drafts()[0]["start_time"] / 1000
    )

    pre_season_start_date = get_season_week_date(
        season, "PRE", 0, api_key, bot_logger
    )
    season_start_date = get_season_week_date(
        season, "", 0, api_key, bot_logger
    )
    post_season_start_date = get_season_week_date(
        season, "", 240, api_key, bot_logger
    )
    off_season_start_date = get_season_week_date(
        season, "", 303, api_key, bot_logger
    )

    STARTING_YEAR = season

    if bot_type == "groupme":
        bot_id = os.environ["BOT_ID"]
        bot = GroupMe(bot_id)
    elif bot_type == "slack":
        webhook = os.environ["SLACK_WEBHOOK"]
        bot = Slack(webhook)
    elif bot_type == "discord":
        webhook = os.environ["DISCORD_WEBHOOK"]
        bot = Discord(webhook)
    elif bot_type == "telegram":
        webhook = os.environ["TELEGRAM_WEBHOOK"]
        bot = Telegram(webhook)

    bot_logger.debug("bot_type= " + bot_type)

    if init_message == "true":
        bot.send(get_welcome_string)  # inital message to send

    week = get_current_week(api_key)

    pre_season_scheduler = schedule.Scheduler()
    post_draft_scheduler = schedule.Scheduler()
    season_scheduler = schedule.Scheduler()
    post_season_scheduler = schedule.Scheduler()
    off_season_scheduler = schedule.Scheduler()

    pre_season_scheduler.every().day.at("18:00").do(
        bot.send, get_draft_reminder_string, league_id
    )  # Draft reminder every day at 18:00 pm CDT

    season_scheduler.every().thursday.at("19:00").do(
        bot.send, get_matchups_string, league, api_key
    )  # Matchups Thursday at 7:00 pm CDT
    season_scheduler.every().friday.at("10:00").do(
        bot.send, get_scores_string, league, api_key
    )  # Scores Friday at 10 am CDT
    season_scheduler.every().sunday.at("22:00").do(
        bot.send, get_close_games_string, league, int(close_num), api_key
    )  # Close games Sunday on 10:00 pm CDT
    season_scheduler.every().monday.at("10:00").do(
        bot.send, get_scores_string, league, api_key
    )  # Scores Monday at 10 am CDT
    season_scheduler.every().tuesday.at("10:00").do(
        bot.send, get_pdf_report_link, league_id, season
    )  # PDF Report Tuesday at 10:00 am CDT
    season_scheduler.every().tuesday.at("11:00").do(
        bot.send, get_standings_string, league
    )  # Standings Tuesday at 11:00 am CDT
    season_scheduler.every().tuesday.at("11:01").do(
        bot.send, get_best_and_worst_string, league, api_key
    )  # Standings Tuesday at 11:01 am CDT

    while True:
        my_days = 0
        today = pendulum.today(TIMEZONE).add(days=my_days)
        now = pendulum.now(TIMEZONE)
        bot_logger.debug(str(now))

        bot_logger.debug(
            "\n"
            + str(pre_season_start_date)
            + " = pre_season_start_date\n"
            + str(draft_date)
            + " = draft\n"
            + str(season_start_date)
            + " = season_start_date\n"
            + str(post_season_start_date)
            + " = post_season_start_date\n"
            + str(off_season_start_date)
            + " = off_season_start_date\n"
            + str(today)
            + " = today\n"
        )

        # Start sending Messages between pre-season and season
        if pre_season_start_date <= today <= draft_date:
            bot_logger.debug("Period between PRE-SEASON and DRAFT DAY")
            bot_logger.debug(
                "\n"
                + str(pre_season_start_date)
                + " = pre_season_start_date\n"
                + str(today)
                + " = today\n"
                + str(draft_date)
                + " = draft"
            )
            pre_season_scheduler.run_pending()
        elif draft_date <= today <= season_start_date:
            bot_logger.debug("Period between DRAFT DAY and REGULAR SEASON")
            bot_logger.debug(
                "\n"
                + str(draft_date)
                + " = draft\n"
                + str(today)
                + " = today\n"
                + str(season_start_date)
                + " = season_start_date"
            )
            season_scheduler.run_pending()
        elif season_start_date <= today <= post_season_start_date:
            bot_logger.debug("Period between SEASON and POST-SEASON")
            bot_logger.debug(
                "\n"
                + str(season_start_date)
                + " = season_start_date\n"
                + str(today)
                + " = today\n"
                + str(post_season_start_date)
                + " = post_season_start_date"
            )
            season_scheduler.run_pending()
        elif post_season_start_date <= today <= off_season_start_date:
            bot_logger.debug("Period between POST-SEASON and OFF-SEASON")
            bot_logger.debug(
                "\n"
                + str(post_season_start_date)
                + " = post_season_start_date\n"
                + str(today)
                + " = today\n"
                + str(off_season_start_date)
                + " = off_season_start_date"
            )
            post_season_scheduler.run_pending()
        elif (
            off_season_start_date
            <= today
            <= pre_season_start_date.add(days=365)
        ):
            bot_logger.debug(
                "Period between OFF-SEASON and NEXT YEAR PRE-SEASON"
            )
            bot_logger.debug(
                "\n"
                + str(off_season_start_date)
                + " = off_season_start_date\n"
                + str(today)
                + " = today\n"
                + str(pre_season_start_date.add(days=365))
                + " = pre_season_start_date_next_year"
            )
            off_season_scheduler.run_pending()

        time.sleep(50)
