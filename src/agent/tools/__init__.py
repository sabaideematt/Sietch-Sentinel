"""Agent tool definitions — the 11 tools available to the orchestrator."""

from src.agent.tools.tle_fetcher import tle_fetcher_tool
from src.agent.tools.orbital_propagator import orbital_propagator_tool
from src.agent.tools.delta_v_calculator import delta_v_calculator_tool
from src.agent.tools.space_weather import space_weather_tool
from src.agent.tools.conjunction_data import conjunction_data_tool
from src.agent.tools.ground_station import ground_station_tool
from src.agent.tools.ttp_matcher import ttp_matcher_tool
from src.agent.tools.operator_schedule import operator_schedule_tool
from src.agent.tools.fleet_correlator import fleet_correlator_tool
from src.agent.tools.memory_rw import memory_read_tool, memory_write_tool
from src.agent.tools.analyst_feedback import analyst_feedback_tool

ALL_TOOLS = [
    tle_fetcher_tool,
    orbital_propagator_tool,
    delta_v_calculator_tool,
    space_weather_tool,
    conjunction_data_tool,
    ground_station_tool,
    ttp_matcher_tool,
    operator_schedule_tool,
    fleet_correlator_tool,
    memory_read_tool,
    memory_write_tool,
    analyst_feedback_tool,
]
