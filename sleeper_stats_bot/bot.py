# -*- coding: utf-8 -*-
import logging
import os
import subprocess
import time
from collections import defaultdict
from pilmoji import Pilmoji
from PIL import ImageFont, Image
from io import BytesIO
import pandas as pd
import pendulum
import requests
import requests_cache
import schedule
from constants import (
    BONUS_FUMBLE_FORCED_DEF,
    BONUS_INT_QB,
    BONUS_REC_FIRST_DOWN,
    BONUS_REC_TE,
    CLOSE_NUM,
    DAILY_NIGHT_DRAFT_REMINDER_HOUR,
    DAY_IN_SECONDS,
    DAYS_BEFORE_DRAFT,
    HTTP_USER_AGENT,
    LEAGUE_NAME,
    MONDAY_NIGHT_SCORES_HOUR,
    SCORING_TYPE,
    SUNDAY_NIGHT_CLOSE_GAMES_HOUR,
    SUNDAY_NIGHT_SCORES_HOUR,
    THURSDAY_NIGHT_SCORES_HOUR,
    THURSDAY_NIGHT_WEEK_MATCHUPS_HOUR,
    TIMEZONE,
    TUESDAY_MORNING_BEST_WORST_HOUR,
    TUESDAY_MORNING_REPORT_HOUR,
    TUESDAY_MORNING_STANDINGS_HOUR,
    TUESDAY_MORNING_WEEK_SCORES_HOUR,
    FONT_NAME,
    FONT_SIZE,
    IMAGE_WIDTH_PIXELS,
)
from discord import Discord
from group_me import GroupMe
from prettytable import PrettyTable
from requests_ratelimiter import LimiterAdapter
from rich.logging import RichHandler
from slack import Slack
from sleeper_wrapper import League, Players, Stats
from telegram import Telegram
import numpy as nmp


def get_current_season(sportsdata_api_key, session, logger):
    """
    get_current_season Returns the current season year

    :param sportsdata_api_key: API Key from https://sportsdata.io
    :type sportsdata_api_key: str
    :param session: Requests session object
    :type session: requests.Session
    :param logger: A logger object for logging debug
    :type logger: logging.Logger (bot_logger)
    :return: Current season year
    :rtype: str
    """
    logger.debug("ENTERING GET_CURRENT_SEASON FUNCTION")

    endpoint = "https://api.sportsdata.io/v3/nfl/scores/json/CurrentSeason"

    sports_data_headers = {
        "User-Agent": HTTP_USER_AGENT,
        "Ocp-Apim-Subscription-Key": sportsdata_api_key,
    }

    # status_hook = lambda response,
    # *args, **kwargs: response.raise_for_status()
    # session.hooks["response"] = [status_hook]

    response = session.get(
        endpoint,
        headers=sports_data_headers,
        timeout=10,
    )
    response.raise_for_status()
    logger.debug("CURRENT_SEASON_RESPONSE: " + str(response.text))
    current_season = response.text

    logger.debug("LEAVING GET_CURRENT_SEASON FUNCTION")

    return current_season


def get_welcome_string(season, logger):
    """
    get_welcome_string Creates and returns the welcome message

    :return: Welcome message
    :rtype: str
    """
    logger.debug("ENTERING GET WELCOME STRING FUNCTION")
    welcome_message = "👋 Hello, I am the " + LEAGUE_NAME + " Stats Bot! \n\n"
    welcome_message += "I am going to sent you some stats about the league \n"
    welcome_message += "according to this schedule (CST): \n "
    welcome_message += get_bot_message_schedule() + "\n \n"
    welcome_message += "Welcome to the 🏈 {} season 🏈\n\n".format(season)
    welcome_message += "🎉 Enjoy!\n"
    welcome_message += "I'm still in dev mode, 🧑🏽‍💻 new features on the way 🚀"

    size = get_table_size(
        welcome_message, FONT_SIZE, FONT_NAME, IMAGE_WIDTH_PIXELS
    )
    print("SIZE: " + str(size))

    logger.debug("LEAVING GET WELCOME STRING FUNCTION")
    logger.debug("INIT_MESSAGE: " + welcome_message)

    return welcome_message, size[0], size[1]


def get_season_week_date(
    current_season,
    season_type,
    game_number,
    sportsdata_api_key,
    session,
    logger,
):
    """
    Returns the date when the current season starts
    :param current_season: String with the current season year
    :param season_type: String with the season type.
        Examples: PRE, POST, STAR, It will concatenate to
        current_season to form the final string.
        Examples: 2021, 2021PRE, 2021POST, 2021STAR, 2022
    :param game_number: Number of the game that we want to pull
    :param sportsdata_api_key: String https://sportsdata.io API Key
    :param logger: A logger object for logging debug
    :return: String with the current season year
    """
    logger.debug("ENTERING GET_SEASON_WEEK_DATE FUNCTION")
    endpoint = (
        "https://api.sportsdata.io/v3/nfl/scores/json/Schedules/"
        + current_season
        + season_type
    )
    headers = {
        "User-Agent": HTTP_USER_AGENT,
        "Ocp-Apim-Subscription-Key": sportsdata_api_key,
    }

    # assert_status_hook = lambda response, * \
    #     args, **kwargs: response.raise_for_status()
    # session.hooks["response"] = [assert_status_hook]

    response = session.get(endpoint, headers=headers, timeout=10)
    response.raise_for_status()

    data = response.json()
    season_week = data[game_number]

    season_week_date = pendulum.parse(season_week["Date"], tz=TIMEZONE)

    logger.debug("LEAVING GET_SEASON_WEEK_DATE FUNCTION")

    return season_week_date


def get_current_week(sportsdata_api_key, session, logger):
    """
    get_current_week Gets the current week.

    :param sportsdata_api_key: API Key from https://sportsdata.io
    :type sportsdata_api_key: str
    :param session: Requests session object
    :type session: requests.Session
    :param logger: A logger object for logging debug
    :type logger: logging.Logger (bot_logger)
    :return: current week number
    :rtype: int
    """
    logger.debug("ENTERING GET_CURRENT_WEEK FUNCTION")
    endpoint = "https://api.sportsdata.io/v3/nfl/scores/json/CurrentWeek"
    headers = {
        "User-Agent": HTTP_USER_AGENT,
        "Ocp-Apim-Subscription-Key": sportsdata_api_key,
    }

    # assert_status_hook = lambda response, * \
    #     args, **kwargs: response.raise_for_status()
    # session.hooks["response"] = [assert_status_hook]

    response = session.get(endpoint, headers=headers, timeout=10)
    response.raise_for_status()
    logger.debug("CURRENT_WEEK_RESPONSE: " + str(response.text))

    current_week = response.json()

    logger.debug("LEAVING GET_CURRENT_WEEK FUNCTION")

    return current_week


def get_draft_reminder_string(league, season, logger, days_until_draft):
    """
    get_draft_reminder_string Gets a string of the current
                                season draft reminder.

    :param league: League object
    :type league: obj
    :param season: Current season year
    :type season: str
    :param logger: _description_
    :type logger: _type_
    :param days_until_draft: _description_
    :type days_until_draft: _type_
    :return: _description_
    :rtype: _type_
    """
    logger.debug("ENTERING GET_DRAFT_REMINDER_STRING FUNCTION")
    draft_date = pendulum.from_timestamp(
        league.get_all_drafts()[0]["start_time"] / 1000, tz=TIMEZONE
    )
    logger.debug("DRAFT_DATE: " + str(draft_date))

    time_to_draft = draft_date - pendulum.now(tz=TIMEZONE)
    logger.debug("TIME_TO_DRAFT_DATE: " + str(time_to_draft))
    logger.debug("DAYS_TO_DRAFT_DATE: " + str(time_to_draft.days))

    final_table = PrettyTable()
    final_table.title = "Draft Reminder - {0} Season ".format(season)
    final_table.field_names = ["Days until Draft Day"]
    # final_message_string = "<pre>"

    if (
        int(time_to_draft.days) > 0
        and int(time_to_draft.days) <= days_until_draft
    ):
        draft_reminder_string = (
            time_to_draft.in_words()
            + "\n [ "
            + draft_date.format("dddd Do [of] MMMM YYYY HH:mm A")
            + "]"
        )
    else:
        draft_reminder_string = (
            "Draft day is today! [ " + draft_date.format("HH:mm A") + " ]\n"
        )
    logger.debug("DRAFT_REMINDER_STRING: " + str(draft_reminder_string))

    final_table.add_row([draft_reminder_string])
    final_message_string = final_table.get_string()
    # final_message_string += "</pre>"

    size = get_table_size(
        final_message_string, FONT_SIZE, FONT_NAME, IMAGE_WIDTH_PIXELS
    )
    print("SIZE: " + str(size))

    logger.debug("FINAL_MESSAGE_STRING: \n" + str(final_message_string))
    logger.debug("LEAVING GET_DRAFT_REMINDER_STRING FUNCTION")

    return final_message_string, size[0], size[1]


def get_matchups_string(league, week, logger):
    """
    Creates and returns a message of the current week's matchups.
    :param league: Object league
    :return: string message of the current week matchups.
    """
    logger.debug("ENTERING GET_MATCHUPS_STRING FUNCTION")
    scoreboards = get_league_scoreboards(league, week)
    logger.debug("SCOREBOARDS: " + str(scoreboards))

    # final_message_string = "<pre>"
    final_table = PrettyTable()
    final_table.title = "Matchups - Week {}".format(week)
    final_table.field_names = ["Match", "Team A", " ", "Team B"]

    if scoreboards is None:
        final_table.add_row(["No", "Scoreboards", "", "Found"])
        # final_table.add_row(["N/A", "N/A", " ", "N/A"])
    else:
        data_dict = defaultdict(list)

        for key, values in scoreboards.items():
            for i in values:
                data_dict[key].append(i[0])

        for key, values in sorted(data_dict.items()):
            final_table.add_row([key, values[0], "vs", values[1]])

    final_message_string = final_table.get_string()
    # final_message_string += "</pre>"

    size = get_table_size(
        final_message_string, FONT_SIZE, FONT_NAME, IMAGE_WIDTH_PIXELS
    )
    print("SIZE: " + str(size))

    logger.debug("MATCHUP_TABLES: " + str(final_message_string))
    logger.debug("LEAVING GET_MATCHUPS_STRING FUNCTION")

    return final_message_string, size[0], size[1]


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


def get_scores_string(league, week, event_title, logger):
    """
    Creates and returns a message of the league's current
    scores for the current week.
    :param league: Object league
    :return: string message of the current week's scores
    """
    logger.debug("ENTERING GET_SCORES_STRING FUNCTION")
    scoreboards = get_league_scoreboards(league, week)
    data_dict = defaultdict(list)
    final_table = PrettyTable()
    final_table.title = "{0} - Week {1}".format(event_title, week)
    final_table.field_names = ["Matchup", "Teams", "Points"]

    # final_message_string = "<pre>"
    # final_message_string = "{0} - Week {1}\n".format(event_title, week)

    if scoreboards is None:
        final_table.add_row(["No", "Scoreboards", "Found"])
        # final_table.add_row(["N/A", "N/A", "N/A"])
    else:
        for key, values in scoreboards.items():
            for i in values:
                data_dict[key].append(i[0])
                data_dict[key].append(i[1])

        for key, values in sorted(data_dict.items()):
            final_table.add_row([key, values[0], values[1]])
            final_table.add_row([key, values[2], values[3]])

    final_message_string = final_table.get_string()
    # final_message_string += "</pre>"

    size = get_table_size(
        final_message_string, FONT_SIZE, FONT_NAME, IMAGE_WIDTH_PIXELS
    )
    print("SIZE: " + str(size))

    logger.debug("SCORES_STRINGS: " + str(final_message_string))
    logger.debug("LEAVING GET_SCORES_STRING FUNCTION")

    return final_message_string, size[0], size[1]


def get_close_games_string(league, week, close_num, logger):
    """
    Creates and returns a message of the league's close games.
    :param league: Object league
    :param close_num: Int point difference to considered a close game.
    :return: string message of the current week's close games.
    """
    logger.debug("ENTERING GET_CLOSE_GAMES_STRING FUNCTION")
    scoreboards = get_league_scoreboards(league, week)
    data_dict = defaultdict(list)
    final_table = PrettyTable()
    final_table.title = "Close Games - Week {0}".format(week)
    final_table.field_names = ["Matchup", "Teams", "Points"]
    # final_message_string = "<pre>"
    # final_message_string = "Close Games - Week {0}\n".format(week)

    if scoreboards is None:
        final_table.add_row(["No", "Scoreboards", "Found"])
        # final_table.add_row(["N/A", "N/A", "N/A"])
    else:
        close_games = league.get_close_games(scoreboards, close_num)
        for key, values in close_games.items():
            for i in values:
                data_dict[key].append(i[0])
                data_dict[key].append(i[1])

        for key, values in sorted(data_dict.items()):
            final_table.add_row([key, values[0], values[1]])
            final_table.add_row([key, values[2], values[3]])

    final_message_string = final_table.get_string()
    # final_message_string += "</pre>"

    size = get_table_size(
        final_message_string, FONT_SIZE, FONT_NAME, IMAGE_WIDTH_PIXELS
    )
    print("SIZE: " + str(size))

    logger.debug("CLOSE_GAMES_STRINGS: " + str(final_message_string))
    logger.debug("LEAVING GET_CLOSE_GAMES_STRING FUNCTION")

    return final_message_string, size[0], size[1]


def get_standings_string(league, week, playoff_line, logger):
    """
    Creates and returns a message of the league's standings.
    :param league: Object league
    :return: string message of the leagues standings.
    """
    logger.debug("ENTERING GET_STANDINGS_STRING FUNCTION")
    rank_col = []
    team_col = []
    win_col = []
    loss_col = []
    points_col = []
    rosters = league.get_rosters()
    users = league.get_users()
    standings = league.get_standings(rosters, users)
    final_table = PrettyTable()
    final_table.title = "League Standings - Week {}".format(week)
    # final_message_string = "<pre>"
    # final_message_string = "League Standings - Week {} \n".format(week)

    for i, standings in enumerate(standings):
        rank_col.append(int(i + 1))
        team_col.append(standings[0])
        win_col.append(standings[1])
        loss_col.append(standings[2])
        points_col.append(standings[3])
        if i == int(playoff_line) - 1:
            rank_col.append("---")
            team_col.append("------------")
            win_col.append("---")
            loss_col.append("---")
            points_col.append("---")

    final_table.add_column("Rank", rank_col)
    final_table.add_column("Team Name", team_col)
    final_table.add_column("Wins", win_col)
    final_table.add_column("Loss", loss_col)
    final_table.add_column("Points", points_col)

    final_message_string = final_table.get_string()

    # final_message_string += "</pre>"

    size = get_table_size(
        final_message_string, FONT_SIZE, FONT_NAME, IMAGE_WIDTH_PIXELS
    )
    print("SIZE: " + str(size))

    logger.debug("STANDINGS_STRINGS: " + str(final_message_string))
    logger.debug("LEAVING GET_STANDINGS_STRING FUNCTION")

    return final_message_string, size[0], size[1]


def get_pdf_report_link(league_id, season, logger):
    logger.debug("ENTERING GET_PDF_REPORT_LINK FUNCTION")
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

    logger.debug("LEAVING GET_BENCH_POINTS FUNCTION")


def get_best_and_worst_string(league, season, week, logger):
    """
    :param league: Object league
    :return: String of the highest Scorer, lowest scorer,
            most points left on the bench, and Why bother section.
    """
    logger.debug("ENTERING GET_BEST_AND_WORST_STRING FUNCTION")
    highest_scorer_table = PrettyTable()
    lowest_scorer_table = PrettyTable()
    # final_message_string = "<pre>"

    highest_scorer_table.field_names = ["🏆🏆 Highest Scorer 🏆🏆"]
    highest_scorer_table.add_row([get_highest_score(league, week, logger)[1]])
    highest_scorer_table.add_row([get_highest_score(league, week, logger)[0]])

    lowest_scorer_table.field_names = ["😢😢 Lowest Scorer 😢😢"]
    lowest_scorer_table.add_row([get_lowest_score(league, week, logger)[1]])
    lowest_scorer_table.add_row([get_lowest_score(league, week, logger)[0]])

    final_message_string = highest_scorer_table.get_string()
    final_message_string += "\n"
    final_message_string += lowest_scorer_table.get_string()
    final_message_string += "\n"

    highest_bench_score_emojis = " 😂😂"
    bench_points = get_bench_points(league, season, week, logger)

    largest_scoring_bench = get_highest_bench_points(bench_points)
    final_message_string += "{} Most points left on the bench:".format(
        highest_bench_score_emojis
    )
    final_message_string += "\n{}\n{:.2f}\n\n".format(
        largest_scoring_bench[0],
        largest_scoring_bench[1],
    )
    negative_starters = get_negative_starters(league, season, week, logger)
    if negative_starters:
        final_message_string += "🤔🤔Why bother?\n"

    for key in negative_starters:
        negative_starters_list = negative_starters[key]
        final_message_string += "{} Started:\n".format(key)
        for negative_starter_tup in negative_starters_list:
            final_message_string += "{} who sucks, and had {} points\n".format(
                negative_starter_tup[0], negative_starter_tup[1]
            )
        final_message_string += "\n"

    size = get_table_size(
        final_message_string, FONT_SIZE, FONT_NAME, IMAGE_WIDTH_PIXELS
    )
    print("SIZE: " + str(size))

    logger.debug("FUN_FACTS_STRINGS: " + str(final_message_string))
    logger.debug("LEAVING GET_BEST_AND_WORST_STRING FUNCTION")

    return final_message_string, size[0], size[1]


def get_highest_score(league, week, logger):
    """
    Gets the highest score of the week
    :param league: Object league
    :return: List [score, team_name]
    """
    logger.debug("ENTERING GET_HIGHEST_SCORE FUNCTION")
    scoreboards = get_league_scoreboards(league, week)
    max_score = [0, None]

    if scoreboards is None:
        max_score = [0, None]
    else:
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

    logger.debug("LEAVING GET_HIGHEST_SCORE FUNCTION")

    return max_score


def get_lowest_score(league, week, logger):
    """
    Gets the lowest score of the week
    :param league: Object league
    :return: List[score, team_name]
    """
    logger.debug("ENTERING GET_LOWEST_SCORE FUNCTION")
    scoreboards = get_league_scoreboards(league, week)
    min_score = [999, None]

    if scoreboards is None:
        min_score = [999, None]
    else:
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
    logger.debug("LEAVING GET_LOWEST_SCORE FUNCTION")

    return min_score


def get_bench_points(league, season, week, logger):
    """

    :param league: Object league
    :return: List [(team_name, score), ...]
    """
    logger.debug("ENTERING GET_BENCH_POINTS FUNCTION")

    users = league.get_users()
    matchups = league.get_matchups(week)

    stats = Stats()
    # WEEK STATS NEED TO BE FIXED
    week_stats = stats.get_week_stats("regular", season, week)
    print("TP: ", type(week_stats))

    df_stats = pd.DataFrame.from_dict(week_stats)
    if df_stats.empty:
        logger.debug("EMPTY DF")
        result_list = []
    else:
        logger.debug("NOT EMPTY DF")
        df_stats = df_stats.fillna(0)
        print("initial DF: " + str(df_stats.shape))
        df_stats.to_csv(
            r"/tmp/pandas.txt", header=True, index=True, sep=" ", mode="a"
        )

        total_points = df_stats.loc[["bonus_rec_te", "rec_fd", "ff"]].sum()
        total_points.name = "total_points"

        # print(total_points)
        df_stats = df_stats.append(total_points.transpose())
        print("Added column: " + str(df_stats.shape))
        df_stats.to_csv(
            r"/tmp/pandas2.txt", header=True, index=True, sep=" ", mode="a"
        )

        print("before : " + df_stats["total_points"])

        # import pdb; pdb.set_trace()
        df_stats = df_stats.T

        print(df_stats["total_points"])

        df_stats[SCORING_TYPE] = df_stats[SCORING_TYPE]
        # - df_stats["pass_int"] )
        df_stats["bonus_rec_te"] = df_stats["bonus_rec_te"].multiply(
            BONUS_REC_TE
        )
        df_stats["rec_fd"] = df_stats["rec_fd"].multiply(BONUS_REC_FIRST_DOWN)
        df_stats["ff"] = df_stats["ff"].multiply(BONUS_FUMBLE_FORCED_DEF)
        df_stats["pass_int"] = df_stats["pass_int"].multiply(BONUS_INT_QB)

        print("Transposed and with math operations: " + str(df_stats.shape))

        owner_id_to_team_dict = map_users_to_team_name(users, logger)

        print("OWNER_ID_TO_TEAM_DICT: " + str(owner_id_to_team_dict))
        roster_id_to_owner_id_dict = map_roster_id_to_owner_id(league)
        print("ROSTER_ID_TO_OWNER_ID_DICT: " + str(roster_id_to_owner_id_dict))
        result_list = []

        print(type(matchups))
        df_matchups = pd.DataFrame(matchups)
        print(df_matchups)

        # df_matchups["bench"] = (set(df_matchups["players"])
        #                        - set(df_matchups["starters"]))
        # print(df_matchups[[x[0] in x[1] for x in zip(
        #       set(df_matchups['players']),
        #       set(df_matchups['starters']))]][['players', 'starters']])

        df_stats = df_stats.T
        df_stats = df_stats.round(2)

        for index, row in df_matchups.iterrows():
            # print(index)
            all_roster = row["players"]
            starters = row["starters"]
            bench = set(all_roster) - set(starters)

            # print(all_roster)
            # print(starters)
            print("BENCH: " + str(bench))
            print(type(bench))

            # df_stats.to_csv(r'/tmp/pandas.txt',
            # header=True,
            # index=True,
            # sep=' ',
            # mode='a')

            # from tabulate import tabulate
            # print(tabulate(df_stats, headers='keys', tablefmt='psql'))

            print(df_stats.loc[:, tuple(bench)])

            df_bench = df_stats.loc[:, tuple(bench)]

            df_bench = df_bench.T

            df_stats = df_stats.T

            print(df_stats)

            # player_points = 0
            # bonus_rec_te_points = 0
            # rec_fd_points = 0
            for player in bench:

                print("player in bench: " + player)
                #
                # print(df_stats.loc[:, [4218]])
                print(df_stats.loc[:, [player]])
                print(type(df_stats.loc[:, [player]]))
                player_l = pd.Series(df_stats.loc[:, [player]])
                print("player_series: " + player_l)

                # player_points = player[SCORING_TYPE]
                # print("pp: " + player_points)

                # if BONUS_REC_TE:
                #     bonus_rec_te_points = player["bonus_rec_te"]

                # if BONUS_REC_FIRST_DOWN:
                #     bonus_rec_fd_points = player["rec_fd"]

                # if BONUS_FUMBLE_FORCED_DEF:
                #     bonus_ff_def_points = player["ff"]

                # if BONUS_INT_QB:
                #     bonus_int_qb_points = player["pass_int"]

                # print("pp: " + player_points)
                # print("BON_REC_TE_P: " + bonus_rec_te_points)
                # print(rec_fd_points)
                # print(type(bonus_rec_te_points))

                # total_points = ( player_points
                # + bonus_rec_te_points
                # + bonus_rec_fd_points
                # + bonus_ff_def_points
                # - bonus_int_qb_points )
                # print("tp: " + total_points)

        # for matchup in matchups:
        #     starters = matchup["starters"]
        #     all_players = matchup["players"]
        #     bench = set(all_players) - set(starters)

        #     std_points = 0
        #     rec_fd = 0
        #     bonus_rec_te = 0
        #     total_points = 0
        #     for player in bench:
        #         try:
        #             std_points += week_stats[str(player)]["pts_half_ppr"]
        #             rec_fd += week_stats[str(player)]["rec_fd"] * 0.5
        #             bonus_rec_te += week_stats[str(player)]["rec_fd"] * 0.5
        #         except Exception:
        #             continue
        #     owner_id = roster_id_to_owner_id_dict[matchup["roster_id"]]
        #     if owner_id is None:
        #         team_name = "Team name not available"
        #     else:
        #         team_name = owner_id_to_team_dict[owner_id]
        #     result_list.append((team_name, total_points))

        result_list = []
    logger.debug("LEAVING GET_BENCH_POINTS FUNCTION")

    return result_list


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


def get_negative_starters(league, season, week, logger):
    """
    Finds all of the players that scores negative points in standard and
    :param league: Object league
    :return: Dict { "owner_name":[("player_name", std_score), ...],
                    "owner_name":...}
    """
    users = league.get_users()
    matchups = league.get_matchups(week)

    stats = Stats()
    # WEEK STATS NEED TO BE FIXED
    week_stats = stats.get_week_stats("regular", season, week)

    players = Players()
    players_dict = players.get_all_players()
    owner_id_to_team_dict = map_users_to_team_name(users, logger)
    roster_id_to_owner_id_dict = map_roster_id_to_owner_id(league)

    result_dict = {}

    for i, matchup in enumerate(matchups):
        starters = matchup["starters"]
        negative_players = []
        for starter_id in starters:
            try:
                std_pts = week_stats[str(starter_id)]["pts_half_ppr"]
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


def map_users_to_team_name(users, logger):
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


# from pyrate_limiter import (
#   BucketFullException,
#   Duration,
#   RequestRate,
#   Limiter,
#   MemoryListBucket,
#   MemoryQueueBucket,
# )

requests_cache.install_cache(
    cache_name="api_cache", backend="sqlite", expire_after=DAY_IN_SECONDS
)


def make_roster_dict(starters_list, bench_list, season, week):
    """
    Takes in a teams starter list and bench list and makes
    a dictionary with positions.
    :param starters_list: List of a teams starters
    :param bench_list: List of a teams bench players
    :return: {starters:{position: []} , bench:{ position: []} }
    """
    players = Players().get_all_players()
    stats = Stats()
    week_stats = stats.get_week_stats("regular", season, week)

    roster_dict = {"starters": {}, "bench": {}}
    for player_id in starters_list:
        player = players[player_id]
        player_position = player["position"]
        player_name = player["first_name"] + " " + player["last_name"]
        try:
            player_std_score = week_stats[player_id]["pts_half_ppr"]
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
            player_std_score = week_stats[player_id]["pts_half_ppr"]
        except KeyError:
            player_std_score = None

        player_and_score_tup = (player_name, player_std_score)
        if player_position not in roster_dict["bench"]:
            roster_dict["bench"][player_position] = [player_and_score_tup]
        else:
            roster_dict["bench"][player_position].append(player_and_score_tup)

    return roster_dict


def calculate_bonus_rec_te_points(row):
    for i, item in enumerate(row):
        row[i] = item * BONUS_REC_TE

    return row


def check_starters_and_bench(lineup_dict):
    """

    :param lineup_dict: A dict returned by make_roster_dict
    :return:
    """
    for key in lineup_dict:
        pass


def get_bot_message_schedule():
    x = PrettyTable()

    x.add_column(
        "Message",
        [
            "Week Games",
            "Thursday Night Scores",
            "Sunday Night Scores",
            "Sunday Night Close Games",
            "Monday Night Scores",
            "Week Scores",
            "Standings",
            "PDF Report",
            "Draft Reminder",
        ],
    )
    x.add_column(
        "Day",
        [
            "Thursday",
            "Thursday",
            "Sunday",
            "Sunday",
            "Monday",
            "Tuesday",
            "Tuesday",
            "Tuesday",
            "Daily",
        ],
    )
    x.add_column(
        "Hour",
        [
            THURSDAY_NIGHT_WEEK_MATCHUPS_HOUR,
            THURSDAY_NIGHT_SCORES_HOUR,
            SUNDAY_NIGHT_SCORES_HOUR,
            SUNDAY_NIGHT_CLOSE_GAMES_HOUR,
            MONDAY_NIGHT_SCORES_HOUR,
            TUESDAY_MORNING_WEEK_SCORES_HOUR,
            TUESDAY_MORNING_STANDINGS_HOUR,
            TUESDAY_MORNING_REPORT_HOUR,
            DAILY_NIGHT_DRAFT_REMINDER_HOUR,
        ],
    )

    return x.get_string()


def send_any_string(string_to_send):
    """
    Send any string to the bot.
    :param string_to_send: The string to send a bot
    :return: string to send
    """
    return string_to_send


def get_playoff_bracket_string(league):
    """
    Creates and returns a message of the league's playoff bracket.
    :param league: Object league
    :return: string message league's playoff bracket
    """
    bracket = league.get_playoff_winners_bracket()
    return bracket


def get_bench_beats_starters_string(league, week):
    """
    Gets all bench players that outscored starters at their position.
    :param league: Object league
    :return: String teams which had bench players outscore their
            starters in a position.
    """
    matchups = league.get_matchups(week)

    final_message_string = "________________________________\n"
    final_message_string += "Worst of the week💩💩\n"
    final_message_string += "________________________________\n\n"

    for matchup in matchups:
        starters = matchup["starters"]
        all_players = matchup["players"]
        bench = set(all_players) - set(starters)

    return bench


# def get_api_subscription_limits(monthly_limit):
#    monthly_rate = RequestRate(monthly_limit, Duration.MONTH) # and so on

#    limiter = Limiter(monthly_rate, bucket_class=MemoryListBucket)
# # default is MemoryQueueBucket

#    return limiter


def get_table_size(text, font_size, font_name, table_size):
    font = ImageFont.truetype(font_name, font_size)
    initial_size = font.getsize(text)
    print("INITIAL_SIZE: " + str(initial_size))

    size_width = int(nmp.ceil(initial_size[0] / table_size))
    print("SIZE_WIDTH: " + str(size_width))

    size_height = int(nmp.ceil((1.5 * initial_size[1] * size_width) + 50))
    print("SIZE_HEIGHT: " + str(size_height))

    return table_size, size_height


def create_image_from_string(text, width, height):

    byte_io = BytesIO()

    with Image.new("RGB", (width, height), "white") as image:
        font = ImageFont.truetype(FONT_NAME, FONT_SIZE)

    with Pilmoji(image) as pilmoji:
        pilmoji.text((10, 10), text.strip(), "black", font)

    image.save(byte_io, "PNG")
    byte_io.seek(0)

    image.show()

    return byte_io


def send_welcome_photo_to_telegram(logger):
    logger.debug("ENTERING SEND_WELCOME_PHOTO_TO_TELEGRAM FUNCTION")
    photo = create_image_from_string(*get_welcome_string(season, bot_logger))
    print("ARRAY: " + str(photo))
    bot.send("", photo)
    logger.debug("LEAVING SEND_WELCOME_PHOTO_TO_TELEGRAM FUNCTION")


def send_draft_reminder_photo_to_telegram():
    photo = create_image_from_string(
        *get_draft_reminder_string(
            league, season, bot_logger, DAYS_BEFORE_DRAFT
        )
    )
    print("ARRAY: " + str(photo))
    bot.send("", photo)


def send_week_matchups_photo_to_telegram():
    photo = create_image_from_string(
        *get_matchups_string(league, week, bot_logger)
    )
    print("ARRAY: " + str(photo))
    bot.send("", photo)


def send_scores_photo_to_telegram(title, logger):
    logger.debug("ENTERING SEND_SCORES_PHOTO_TO_TELEGRAM FUNCTION")
    photo = create_image_from_string(
        *get_scores_string(league, week, title, bot_logger)
    )
    print("ARRAY: " + str(photo))
    logger.debug("BEFORE SEND THE PHOTO")
    bot.send("", photo)
    logger.debug("LEAVING SEND_SCORES_PHOTO_TO_TELEGRAM FUNCTION")


def send_close_games_photo_to_telegram(logger):
    logger.debug("ENTERING SEND_CLOSE_GAMES_PHOTO_TO_TELEGRAM FUNCTION")
    photo = create_image_from_string(
        *get_close_games_string(league, week, int(close_num), bot_logger)
    )
    print("ARRAY: " + str(photo))
    logger.debug("BEFORE SEND THE PHOTO")
    bot.send("", photo)
    logger.debug("LEAVING SEND_CLOSE_GAMES_PHOTO_TO_TELEGRAM FUNCTION")


def send_standings_photo_to_telegram(logger):
    logger.debug("ENTERING SEND_STANDINGS_PHOTO_TO_TELEGRAM FUNCTION")
    photo = create_image_from_string(
        *get_standings_string(league, week, playoff_line, bot_logger)
    )
    print("ARRAY: " + str(photo))
    logger.debug("BEFORE SEND THE PHOTO")
    bot.send("", photo)
    logger.debug("LEAVING SEND_STANDINGS_PHOTO_TO_TELEGRAM FUNCTION")


def send_best_and_worst_photo_to_telegram(logger):
    logger.debug("ENTERING SEND_BEST_AND_WORST_PHOTO_TO_TELEGRAM FUNCTION")
    photo = create_image_from_string(
        *get_best_and_worst_string(league, season, week, bot_logger)
    )
    print("ARRAY: " + str(photo))
    logger.debug("BEFORE SEND THE PHOTO")
    bot.send("", photo)
    logger.debug("LEAVING SEND_BEST_AND_WORST_PHOTO_TO_TELEGRAM FUNCTION")


###############################################################################
# Main Script for the bot
###############################################################################

if __name__ == "__main__":
    """
    _Initialize variables_
    """
    bot = None
    bot_type = os.environ["BOT_TYPE"]
    league_id = os.environ["LEAGUE_ID"]
    sportsdata_api_key = os.environ["API_KEY"]

    # Check if the user specified the close_num variable . Default is 10.
    try:
        close_num = os.environ["CLOSE_NUM"]
    except Exception:
        close_num = CLOSE_NUM

    # Check if the user specified the init_message flag. Default is True
    try:
        init_message = os.environ["INIT_MESSAGE"]
    except Exception:
        init_message = True

    # Check if the user specified the playoff_line variable. Default is 8
    try:
        playoff_line = os.environ["NUMBER_OF_PLAYOFF_TEAMS"]
    except Exception:
        playoff_line = 8

    # Check if the user specified the debug flag. Default is True
    try:
        show_debug = os.environ["DEBUG"]
    except Exception:
        show_debug = True

    """
    _Initialize Different Schedulers for every time frame_
    Pre-season
    Post-draft
    Season
    Post-season
    Off-season
    """
    pre_season_scheduler = schedule.Scheduler()
    post_draft_scheduler = schedule.Scheduler()
    season_scheduler = schedule.Scheduler()
    post_season_scheduler = schedule.Scheduler()
    off_season_scheduler = schedule.Scheduler()

    """
    _Initialize Logger_
    """
    if show_debug:
        logging.basicConfig(
            level="DEBUG",
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler()],
        )
    else:
        logging.basicConfig(
            level="INFO",
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler()],
        )

    # Define loggers
    schedule_logger = logging.getLogger("schedule")
    bot_logger = logging.getLogger("bot")

    """
    _Define bot type_
    """
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
    bot_logger.debug("BOT_TYPE: " + bot_type)

    """
    _Initialize Request Session_
    """
    session = requests.Session()
    adapter = LimiterAdapter(per_month=1000)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    bot_logger.debug("REQUESTS_SESSION_OBJECT: " + str(session))

    """
    _Initialize Season_
    """
    season = get_current_season(sportsdata_api_key, session, bot_logger)
    bot_logger.debug("CURRENT_SEASON: " + str(season))

    # NOT USED
    # session = requests_cache.CachedSession()
    # print(str(session.cache.urls))

    #####
    # Initial message to send
    #####
    if init_message:
        send_welcome_photo_to_telegram(bot_logger)

    """
    _Initialize League Dates_
    get the following dates:
    draft_date
    pre_season_start_date
    season_start_date
    post_season_start_date
    off_season_start_date
    """
    league = League(league_id)
    draft_date = pendulum.from_timestamp(
        league.get_all_drafts()[0]["start_time"] / 1000, tz=TIMEZONE
    )
    bot_logger.debug("DRAFT_DATE: " + str(draft_date))

    pre_season_start_date = get_season_week_date(
        season, "PRE", 0, sportsdata_api_key, session, bot_logger
    )
    bot_logger.debug("PRE_SEASON_START_DATE: " + str(pre_season_start_date))

    season_start_date = get_season_week_date(
        season, "", 0, sportsdata_api_key, session, bot_logger
    )
    bot_logger.debug("SEASON_START_DATE: " + str(season_start_date))

    post_season_start_date = get_season_week_date(
        season, "", 240, sportsdata_api_key, session, bot_logger
    )
    bot_logger.debug("POST_SEASON_START_DATE: " + str(post_season_start_date))

    off_season_start_date = get_season_week_date(
        season, "", 303, sportsdata_api_key, session, bot_logger
    )
    bot_logger.debug("OFF_SEASON_START_DATE: " + str(off_season_start_date))

    week = get_current_week(sportsdata_api_key, session, bot_logger)

    # For testing
    # send_draft_reminder_photo_to_telegram()
    # send_week_matchups_photo_to_telegram()
    # send_scores_photo_to_telegram(
    #     title="Thursday Night Scores", logger=bot_logger
    # )
    # send_close_games_photo_to_telegram(logger=bot_logger)
    # send_standings_photo_to_telegram(logger=bot_logger)
    # send_best_and_worst_photo_to_telegram(logger=bot_logger)
    bot.send(get_pdf_report_link, league_id, season, bot_logger)
    time.sleep(10)

    # Draft Reminder
    # Send a message during pre_season, DAYS_BEFORE_DRAFT days before the draft
    # at DAILY_NIGHT_DRAFT_REMINDER_HOUR
    pre_season_scheduler.every().day.at(DAILY_NIGHT_DRAFT_REMINDER_HOUR).do(
        send_draft_reminder_photo_to_telegram
    )

    # Week Matchups:
    # Send a message during the season to know the matchups for the week
    # every Thursday at THURSDAY_NIGHT_WEEK_MATCHUPS_HOUR
    season_scheduler.every().day.at(THURSDAY_NIGHT_WEEK_MATCHUPS_HOUR).do(
        send_week_matchups_photo_to_telegram
    )

    # Thursday Night Scores:
    # Send a message during the season to know the Thursday Night Scores
    # every Thursday at THURSDAY_NIGHT_SCORES_HOUR
    season_scheduler.every().thursday.at(THURSDAY_NIGHT_SCORES_HOUR).do(
        send_scores_photo_to_telegram,
        title="Thursday Night Scores",
        logger=bot_logger,
    )

    # Sunday Night Scores:
    # Send a message during the season to know the Sunday Night Scores
    # every Sunday at SUNDAY_NIGHT_SCORES_HOUR
    season_scheduler.every().sunday.at(SUNDAY_NIGHT_SCORES_HOUR).do(
        send_scores_photo_to_telegram,
        title="Sunday Night Scores",
        logger=bot_logger,
    )

    # Sunday Night Close Games:
    # Send a message during the season to know the Sunday Night Close Games
    # every Sunday at SUNDAY_NIGHT_CLOSE_GAMES_HOUR
    season_scheduler.every().sunday.at(SUNDAY_NIGHT_CLOSE_GAMES_HOUR).do(
        send_close_games_photo_to_telegram, logger=bot_logger
    )

    # Monday Night Scores:
    # Send a message during the season to know the Monday Night Scores
    # every Sunday at MONDAY_NIGHT_SCORES_HOUR
    season_scheduler.every().monday.at(MONDAY_NIGHT_SCORES_HOUR).do(
        send_scores_photo_to_telegram,
        title="Monday Night Scores",
        logger=bot_logger,
    )

    # Tuesday Morning Week Scores:
    # Send a message during the season to know the Tuesday Morning Week Scores
    # every Tuesday at TUESDAY_MORNING_WEEK_SCORES_HOUR
    season_scheduler.every().tuesday.at(TUESDAY_MORNING_WEEK_SCORES_HOUR).do(
        send_scores_photo_to_telegram, title="Week Scores", logger=bot_logger
    )

    # Tuesday Morning Standings:
    # Send a message during the season to know the League Standings
    # every Tuesday at TUESDAY_MORNING_STANDINGS_HOUR
    season_scheduler.every().tuesday.at(TUESDAY_MORNING_STANDINGS_HOUR).do(
        send_standings_photo_to_telegram, logger=bot_logger
    )

    # Tuesday Morning Best and Worst:
    # Send a message during the season to know the Best and Worst Players
    # every Tuesday at TUESDAY_MORNING_BEST_WORST_HOUR
    season_scheduler.every().tuesday.at(TUESDAY_MORNING_BEST_WORST_HOUR).do(
        send_best_and_worst_photo_to_telegram, logger=bot_logger
    )

    # Tuesday Morning PDF Report
    # Send a message during the season with a League Report in a PDF format
    # every Tuesday at TUESDAY_MORNING_REPORT_HOUR
    season_scheduler.every().tuesday.at(TUESDAY_MORNING_REPORT_HOUR).do(
        bot.send, get_pdf_report_link, league_id, season, bot_logger
    )

    while True:
        bot_logger.debug("ENTERING WHILE LOOP")

        my_days = 0
        today = pendulum.today(TIMEZONE).add(days=my_days)
        now = pendulum.now(TIMEZONE)
        bot_logger.debug("NOW IS: " + str(now))

        bot_logger.debug(
            "\n"
            + "PRE_SEASON_START_DATE: "
            + str(pre_season_start_date)
            + "\n"
            + "DRAFT_START_DATE: "
            + str(draft_date)
            + "\n"
            + "SEASON_START_DATE: "
            + str(season_start_date)
            + "\n"
            + "POST_SEASON_START_DATE: "
            + str(post_season_start_date)
            + "\n"
            + "OFF_SEASON_START_DATE: "
            + str(off_season_start_date)
            + "\n"
            + "TODAY: "
            + str(today)
            + "\n"
        )

        # Start sending Messages between pre-season and season
        if pre_season_start_date <= today <= draft_date:
            bot_logger.debug("PRE-SEASON - DRAFT DAY PERIOD")
            bot_logger.debug(
                "\n"
                + "PRE_SEASON_START_DATE: "
                + str(pre_season_start_date)
                + "\n"
                + "TODAY: "
                + str(today)
                + "\n"
                + "DRAFT_START_DATE: "
                + str(draft_date)
                + "\n"
            )
            pre_season_scheduler.run_pending()

        elif draft_date <= today <= season_start_date:
            bot_logger.debug("DRAFT DAY - REGULAR-SEASON PERIOD")
            bot_logger.debug(
                "\n"
                + "DRAFT_START_DATE: "
                + str(draft_date)
                + "\n"
                + "TODAY: "
                + str(today)
                + "\n"
                + "SEASON_START_DATE: "
                + str(season_start_date)
                + "\n"
            )
            season_scheduler.run_pending()

        elif season_start_date <= today <= post_season_start_date:
            bot_logger.debug("REGULAR-SEASON - POST-SEASON PERIOD")
            bot_logger.debug(
                "\n"
                + "SEASON_START_DATE: "
                + str(season_start_date)
                + "\n"
                + "TODAY: "
                + str(today)
                + "\n"
                + "POST_SEASON_START_DATE: "
                + str(post_season_start_date)
                + "\n"
            )
            season_scheduler.run_pending()

        elif post_season_start_date <= today <= off_season_start_date:
            bot_logger.debug("POST-SEASON - OFF-SEASON PERIOD")
            bot_logger.debug(
                "\n"
                + "POST_SEASON_START_DATE: "
                + str(post_season_start_date)
                + "\n"
                + "TODAY: "
                + str(today)
                + "\n"
                + "OFF_SEASON_START_DATE: "
                + str(off_season_start_date)
                + "\n"
            )
            post_season_scheduler.run_pending()

        elif (
            off_season_start_date
            <= today
            <= pre_season_start_date.add(days=365)
        ):
            bot_logger.debug("OFF-SEASON and NEXT-YEAR-PRE-SEASON PERIOD")
            bot_logger.debug(
                "\n"
                + str(off_season_start_date)
                + " = off_season_start_date\n"
                + str(today)
                + " = today\n"
                + str(pre_season_start_date.add(days=365))
                + " = pre_season_start_date_next_year"
                + "OFF_SEASON_START_DATE: "
                + str(off_season_start_date)
                + "\n"
                + "TODAY: "
                + str(today)
                + "\n"
                + "NEXT_YEAR_PRE_SEASON_START_DATE: "
                + str(pre_season_start_date.add(days=365))
                + "\n"
            )
            off_season_scheduler.run_pending()

        time.sleep(50)
