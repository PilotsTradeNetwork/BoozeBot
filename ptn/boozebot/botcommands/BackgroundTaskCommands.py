from loguru import logger

# discord.py
import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice, describe

# local constants
from ptn.boozebot.constants import bot, server_mod_role_id, server_sommelier_role_id, server_council_role_ids, get_steve_says_channel

# local modules
from ptn.boozebot.modules.helpers import check_roles, check_command_channel

class BackgroundTaskCommands(commands.Cog):
    
    task_choices = [
        Choice(name="periodic_stat_update", value="periodic_stat_update"),
        Choice(name="check_departure_messages_loop", value="check_departure_messages_loop"),
        Choice(name="public_holiday_loop", value="public_holiday_loop"),
        Choice(name="last_unload_time_loop", value="last_unload_time_loop"),
    ]
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="start_task", description="Starts a background task.")
    @check_roles([server_mod_role_id(), server_sommelier_role_id(), *server_council_role_ids()])
    @check_command_channel(get_steve_says_channel())
    @describe(
        task_name="The name of the task to start."
    )
    @app_commands.choices(
        task_name=task_choices
    )
    async def start_task(self, interaction: discord.Interaction, task_name: str):

        logger.info(f"start_task command called by {interaction.user} for task {task_name}")

        task = self.get_task(task_name)
        if task:
            logger.debug(f"Found task {task_name}")
            if not task.is_running():
                logger.debug(f"Starting task {task_name}")
                task.start()
                logger.info(f"Task {task_name} started successfully")
                await interaction.response.send_message(f"Started task: {task_name}")#
            else:
                logger.info(f"Task {task_name} is already running")
                await interaction.response.send_message(f"Task {task_name} is already running.")
        else:
            logger.error(f"Task {task_name} not found.")
            await interaction.response.send_message(f"Task {task_name} not found.", ephemeral=True)


    @app_commands.command(name="stop_task", description="Stops a background task.")
    @check_roles([server_mod_role_id(), server_sommelier_role_id(), *server_council_role_ids()])
    @check_command_channel(get_steve_says_channel())
    @describe(
        task_name="The name of the task to stop."
    )
    @app_commands.choices(
        task_name=task_choices
    )
    async def stop_task(self, interaction: discord.Interaction, task_name: str):
        
        logger.info(f"stop_task command called by {interaction.user} for task {task_name}")
        
        task = self.get_task(task_name)
        if task:
            logger.debug(f"Found task {task_name}")
            if task.is_running():
                logger.debug(f"Stopping task {task_name}")
                task.cancel()
                logger.info(f"Task {task_name} stopped successfully")
                await interaction.response.send_message(f"Stopped task: {task_name}.")
            else:
                logger.info(f"Task {task_name} is not running")
                await interaction.response.send_message(f"Task {task_name} is not running.")
        else:
            logger.error(f"Task {task_name} not found.")
            await interaction.response.send_message(f"Task {task_name} not found.", ephemeral=True)
          
    
    @app_commands.command(name="task_status", description="Gets the status of a background task.")
    @check_roles([server_mod_role_id(), server_sommelier_role_id(), *server_council_role_ids()])
    @check_command_channel(get_steve_says_channel())
    @describe(
        task_name="The name of the task to check."
    )
    @app_commands.choices(
        task_name=task_choices
    )
    async def task_status(self, interaction: discord.Interaction, task_name: str):
        
        logger.info(f"task_status command called by {interaction.user} for task {task_name}")
        
        task = self.get_task(task_name)
        
        if not task:
            logger.error(f"Task {task_name} not found.")
            await interaction.response.send_message(f"Task {task_name} not found.", ephemeral=True)

        last_run_time = getattr(task, 'last_run_time', None)
        logger.debug(f"Task {task_name} last run time: {last_run_time}")
        if last_run_time:
            unix_timestamp = int(last_run_time.timestamp())
            last_run_str = f"at <t:{unix_timestamp}:f> (<t:{unix_timestamp}:R>)"
        else:
            last_run_str = "never"
            
        next_run_time = getattr(task, 'next_iteration', None)
        logger.debug(f"Task {task_name} next run time: {next_run_time}")
        if task.is_running():
            next_run_unix = int(next_run_time.timestamp())
            next_run_str = f", next at <t:{next_run_unix}:f> (<t:{next_run_unix}:R>)"
        else:
            next_run_str = ""

        status = "running" if task.is_running() else "stopped"
        logger.debug(f"Task {task_name} is {status}, last run {last_run_str}{next_run_str}")
        await interaction.response.send_message(f"Task {task_name} is currently {status}, last run was {last_run_str}{next_run_str}.")
    
    
    def get_task(self, task_name: str):
        tasks = {
            "periodic_stat_update": bot.get_cog("DatabaseInteraction").periodic_stat_update,
            "check_departure_messages_loop": bot.get_cog("Departures").check_departure_messages_loop,
            "public_holiday_loop": bot.get_cog("PublicHoliday").public_holiday_loop,
            "last_unload_time_loop": bot.get_cog("Unloading").last_unload_time_loop,
        }
        logger.debug(f"Retrieving task {task_name} from available tasks: {list(tasks.keys())}")
        return tasks.get(task_name)
    