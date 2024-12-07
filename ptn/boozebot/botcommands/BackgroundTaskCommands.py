# discord.py
import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice, describe

# local constants
from ptn.boozebot.constants import bot, server_mod_role_id, server_sommelier_role_id, server_connoisseur_role_id, server_council_role_ids, get_steve_says_channel

# local modules
from ptn.boozebot.modules.helpers import check_roles, check_command_channel

class BackgroundTaskCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="start_task", description="Starts a background task.")
    @check_roles([server_mod_role_id(), server_sommelier_role_id(), *server_council_role_ids()])
    @check_command_channel(get_steve_says_channel())
    @describe(
        task_name="The name of the task to start."
    )
    @app_commands.choices(
        task_name=[
            Choice(name="periodic_stat_update", value="periodic_stat_update"),
            Choice(name="check_departure_messages_loop", value="check_departure_messages_loop"),
            Choice(name="public_holiday_loop", value="public_holiday_loop"),
        ]
    )
    async def start_task(self, interaction: discord.Interaction, task_name: str):
        task = self.get_task(task_name)
        if task:
            if not task.is_running():
                task.start()
                await interaction.response.send_message(f"Started task: {task_name}")
            else:
                await interaction.response.send_message(f"Task {task_name} is already running.")
        else:
            await interaction.response.send_message(f"Task {task_name} not found.", ephemeral=True)


    @app_commands.command(name="stop_task", description="Stops a background task.")
    @check_roles([server_mod_role_id(), server_sommelier_role_id(), *server_council_role_ids()])
    @check_command_channel(get_steve_says_channel())
    @describe(
        task_name="The name of the task to stop."
    )
    @app_commands.choices(
        task_name=[
            Choice(name="periodic_stat_update", value="periodic_stat_update"),
            Choice(name="check_departure_messages_loop", value="check_departure_messages_loop"),
            Choice(name="public_holiday_loop", value="public_holiday_loop"),
        ]
    )
    async def stop_task(self, interaction: discord.Interaction, task_name: str):
        task = self.get_task(task_name)
        if task:
            if task.is_running():
                task.stop()
                await interaction.response.send_message(f"Stopped task: {task_name}. (Task will finish its current iteration before stopping.)")
            else:
                await interaction.response.send_message(f"Task {task_name} is not running.")
        else:
            await interaction.response.send_message(f"Task {task_name} not found.", ephemeral=True)            
          
    
    @app_commands.command(name="task_status", description="Gets the status of a background task.")
    @check_roles([server_mod_role_id(), server_sommelier_role_id(), *server_council_role_ids()])
    @check_command_channel(get_steve_says_channel())
    @describe(
        task_name="The name of the task to check."
    )
    @app_commands.choices(
        task_name=[
            Choice(name="periodic_stat_update", value="periodic_stat_update"),
            Choice(name="check_departure_messages_loop", value="check_departure_messages_loop"),
            Choice(name="public_holiday_loop", value="public_holiday_loop"),
        ]
    )
    async def task_status(self, interaction: discord.Interaction, task_name: str):
        task = self.get_task(task_name)
        if task:
            status = "running" if task.is_running() else "stopped"
            await interaction.response.send_message(f"Task {task_name} is currently {status}.")
        else:
            await interaction.response.send_message(f"Task {task_name} not found.", ephemeral=True)
    
    
    def get_task(self, task_name: str):
        tasks = {
            "periodic_stat_update": bot.get_cog("DatabaseInteraction").periodic_stat_update,
            "check_departure_messages_loop": bot.get_cog("Departures").check_departure_messages_loop,
            "public_holiday_loop": bot.get_cog("PublicHoliday").public_holiday_loop,
        }
        return tasks.get(task_name)
    