""" Azure Function to retrieve today's MLB stats and schedule """
import azure.functions as func

from src.mlb_today.blueprints.bp_pitching import bp as bp_pitching
from src.mlb_today.blueprints.bp_batting import bp as bp_batting
from src.mlb_today.blueprints.bp_probables import bp as bp_probables

app = func.FunctionApp()

app.register_blueprint(bp_pitching)
app.register_blueprint(bp_batting)
app.register_blueprint(bp_probables)
