import os

STARTING_YEAR = int(os.environ["SEASON_START_DATE"][0:4])
STARTING_MONTH = int(os.environ["SEASON_START_DATE"][6:7])
STARTING_DAY = int(os.environ["SEASON_START_DATE"][9:10])
START_DATE_STRING = os.environ["SEASON_START_DATE"]
PRE_STARTING_YEAR = int(os.environ["PRE_SEASON_START_DATE"][0:4])
PRE_STARTING_MONTH = int(os.environ["PRE_SEASON_START_DATE"][6:7])
PRE_STARTING_DAY = int(os.environ["PRE_SEASON_START_DATE"][9:10])
PRE_START_DATE_STRING = os.environ["PRE_SEASON_START_DATE"]
OFF_STARTING_YEAR = int(os.environ["OFF_SEASON_START_DATE"][0:4])
OFF_STARTING_MONTH = int(os.environ["OFF_SEASON_START_DATE"][6:7])
OFF_STARTING_DAY = int(os.environ["OFF_SEASON_START_DATE"][9:10])
OFF_START_DATE_STRING = os.environ["OFF_SEASON_START_DATE"]
GITHUB_REPOSITORY = "https://github.com/luiscachog/sleeper-stats-bot"
LEAGUE_NAME = "Nerd Football League"
CLOSE_NUM = 10
TIMEZONE = "America/Chicago"
