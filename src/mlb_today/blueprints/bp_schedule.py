""" Azure Function to compile today's schedule """
import azure.functions as func

import src.mlb_today.config as config

bp = func.Blueprint()

SCHEDULE_CRON = config.SCHEDULE_CRON

@bp.function_name("todays_games")
@bp.timer_trigger(
    arg_name="schedulearg",
    schedule=SCHEDULE_CRON,
    run_on_startup=False
)
def main(schedulearg: func.TimerRequest) -> None:
    """
    Azure function to compile today's schedule

    Args:
        schedulearg (func.TimerRequest): timer trigger
    """
    print(SCHEDULE_CRON)
