""" Azure Function to retrieve today's MLB stats and schedule """
import azure.functions as func

from src.mlb_today.blueprints.bp_pitching import bp as bp_pitching
from src.mlb_today.blueprints.bp_batting import bp as bp_batting
from src.mlb_today.blueprints.bp_probables import bp as bp_probables
from src.mlb_today.blueprints.bp_schedule import bp as bp_schedule
from src.mlb_today.blueprints.bp_email import bp as bp_email

app = func.FunctionApp()

app.register_blueprint(bp_pitching)
app.register_blueprint(bp_batting)
app.register_blueprint(bp_probables)
app.register_blueprint(bp_schedule)
app.register_blueprint(bp_email)
