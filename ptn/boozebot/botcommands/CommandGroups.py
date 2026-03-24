from typing import TYPE_CHECKING

from discord import app_commands
from discord.app_commands import Group
from discord.ext import commands
from discord.ext.subcommands import MultiFilesSubcommandsManager

if TYPE_CHECKING:
    from discord.ext.commands.bot import Bot


class CommandGroups(commands.Cog):
    """
    Cog to define command groups for booze bot.
    """

    def __init__(self, bot: commands.Bot):
        self.bot: Bot = bot
        self.sub_command_manager: MultiFilesSubcommandsManager = MultiFilesSubcommandsManager(bot)

    """
    Admin groups
    """

    admin_command_group: Group = app_commands.Group(
        name="booze_admin",
        description="Admin commands.",
    )

    admin_auto_response_command_group: Group = app_commands.Group(
        name="auto_response",
        description="Admin commands for managing auto responses.",
        parent=admin_command_group,
    )

    admin_background_task_command_group: Group = app_commands.Group(
        name="task",
        description="Admin commands for managing background tasks.",
        parent=admin_command_group,
    )

    admin_cleaner_command_group: Group = app_commands.Group(
        name="cleaner",
        description="Admin commands for opening channels and clearing roles.",
        parent=admin_command_group,
    )

    admin_departures_command_group: Group = app_commands.Group(
        name="departures",
        description="Admin commands for managing departures.",
        parent=admin_command_group,
    )

    admin_roles_command_group: Group = app_commands.Group(
        name="roles",
        description="Admin commands for managing roles.",
        parent=admin_command_group,
    )

    admin_ph_command_group: Group = app_commands.Group(
        name="ph",
        description="Admin commands for overriding the public holiday state and timestamp.",
        parent=admin_command_group,
    )

    admin_pin_command_group: Group = app_commands.Group(
        name="pin",
        description="Admin commands for managing pinned messages.",
        parent=admin_command_group,
    )

    admin_unload_command_group: Group = app_commands.Group(
        name="unload",
        description="Admin commands for managing unloads.",
        parent=admin_command_group,
    )

    """
    Staff Groups
    """

    wine_staff_command_group: Group = app_commands.Group(
        name="wine_staff",
        description="Commands for wine staff.",
    )

    wine_staff_roles_command_group: Group = app_commands.Group(
        name="roles",
        description="Commands for granting the wine carrier role",
        parent=wine_staff_command_group,
    )

    wine_staff_ph_command_group: Group = app_commands.Group(
        name="ph",
        description="Commands for querying public holiday state.",
        parent=wine_staff_command_group,
    )

    wine_staff_stats_command_group: Group = app_commands.Group(
        name="stats",
        description="Commands for getting cruise statistics.",
        parent=wine_staff_command_group,
    )

    """
    Wine Carrier Group
    """

    wine_carrier_command_group: Group = app_commands.Group(
        name="wine_carrier",
        description="Commands for wine carriers.",
    )

    wine_carrier_departure_command_group: Group = app_commands.Group(
        name="departure",
        description="Commands for wine carriers to post departures.",
        parent=wine_carrier_command_group,
    )

    wine_carrier_unload_command_group: Group = app_commands.Group(
        name="unload",
        description="Commands for wine carriers to post unloads.",
        parent=wine_carrier_command_group,
    )
