"""
Steve's help command

"""

# libraries
import re
import enum

# discord.py
import discord
from discord.app_commands import Group, describe, Choice
from discord.ext import commands
from discord import app_commands

# local constants
from ptn.boozebot.constants import server_admin_role_id, server_sommelier_role_id, server_mod_role_id, bot, get_steve_says_channel, bot_guild_id

# local modules
from ptn.boozebot.modules.ErrorHandler import on_app_command_error, GenericError, CustomError, on_generic_error
from ptn.boozebot.modules.helpers import bot_exit, check_roles, check_command_channel


"""
STEVE HELPER COMMAND

/pirate_steve_help - everyone
"""


# initialise the Cog and attach our global error handler
class Helper(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # custom global error handler
    # attaching the handler when the cog is loaded
    # and storing the old handler
    def cog_load(self):
        tree = self.bot.tree
        self._old_tree_error = tree.on_error
        tree.on_error = on_app_command_error

    # detaching the handler when the cog is unloaded
    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = self._old_tree_error


    """
    Class to store all the different commands and their information
        
    """

    class HelpCommandInformation(enum.Enum):
        booze_tally = {
            "params": [
                {
                    "name": "cruise_select",
                    "type": "int",
                    "description": "An integer value representing the cruise you wish data for. 0 (default) is the "
                    "current cruise, 1 the last etc. [Optional]",
                }
            ],
            "method_desc": "Logs the current tally of carriers, wine and some basic stats.",
            "roles": ["Admin", "Mod", "Sommelier", "Connoisseur"],
        }
        booze_delete_carrier = {
            "params": [
                {
                    "name": "carrier_id",
                    "type": "str",
                    "description": "The XXX-XXX ID of the carrier you want to look for.",
                }
            ],
            "method_desc": "Removes a carrier from the database.",
            "roles": ["Admin", "Mod", "Sommelier"],
        }
        booze_pin_message = {
            "params": [
                {
                    "name": "message_id",
                    "type": "str",
                    "description": "The message ID to pin",
                },
                {
                    "name": "channel_id",
                    "type": "str",
                    "description": "The channel ID to pin. Optional, uses the current channel if not provided.",
                },
            ],
            "method_desc": "Pins a message to the channel.",
            "roles": ["Admin", "Mod", "Sommelier"],
        }
        booze_unpin_all = {
            "params": None,
            "method_desc": "Unpins all message for booze bot.",
            "roles": ["Admin", "Mod", "Sommelier"],
        }
        booze_unpin_message = {
            "params": [
                {
                    "name": "message_id",
                    "type": "str",
                    "description": "The message ID to pin",
                }
            ],
            "method_desc": "Unpins the specific message for booze bot.",
            "roles": ["Admin", "Mod", "Sommelier"],
        }
        booze_tally_extra_stats = {
            "params": None,
            "method_desc": "Logs some stats regarding what the volume of wine looks like.",
            "roles": ["Admin", "Mod", "Sommelier", "Connoisseur"],
        }
        find_carriers_with_wine = {
            "params": None,
            "method_desc": "Returns all the remaining carriers with wine to unload.",
            "roles": ["Admin", "Mod", "Sommelier", "WineCarrier"],
        }
        find_carriers_by_id = {
            "params": [
                {
                    "name": "carrier_id",
                    "type": "str",
                    "description": "The XXX-XXX ID of the carrier you want to look for.",
                }
            ],
            "method_desc": "Returns a carrier object from the ID",
            "roles": ["Everyone"],
        }
        find_wine_carriers_for_platform = {
            "params": [
                {
                    "name": "platform",
                    "type": "str",
                    "description": "PC (All), PC (Horizons Only), PC (Horizons + Odyssey), Xbox or Playstation.",
                },
                {
                    "name": "with_wine",
                    "type": "bool",
                    "description": "Restrict the search to those with or without wine.",
                },
            ],
            "method_desc": "Find carriers for the platform.",
            "roles": ["Admin", "Mod", "Sommelier", "WineCarrier"],
        }
        update_booze_db = {
            "params": None,
            "method_desc": "Forces an update of the booze database.",
            "roles": ["Admin", "Sommelier", "Connoisseur"],
        }
        booze_started = {
            "params": None,
            "method_desc": "Queries the current state of the holiday.",
            "roles": ["Admin", "Sommelier", "Mod", "Connoisseur"],
        }
        booze_started_admin_override = {
            "params": [
                {
                    "name": "state",
                    "type": "bool",
                    "description": "Set the override flag to the provided state",
                }
            ],
            "method_desc": "Forces the parameter flag to the provided value. Overrides the holiday checker if True.",
            "roles": ["Admin", "Sommelier", "Mod"],
        }
        wine_helper_market_closed = {
            "params": None,
            "method_desc": "Drops a helper embed into the channel for timed market closure.",
            "roles": ["Admin", "Mod", "Sommelier", "Wine Carrier"],
        }
        wine_helper_market_open = {
            "params": None,
            "method_desc": "Drops a helper embed into the channel for timed market unloading",
            "roles": ["Admin", "Mod", "Sommelier", "Wine Carrier"],
        }
        wine_mark_completed_forcefully = {
            "params": [
                {
                    "name": "carrier_id",
                    "type": "str",
                    "description": "The XXX-XXX ID of the carrier you want to look for.",
                }
            ],
            "method_desc": "Marks a carrier as forcefully completed. Useful if someone unloaded and did not tell us.",
            "roles": ["Admin", "Mod", "Sommelier"],
        }
        wine_unload = {
            "params": [
                {
                    "name": "carrier_id",
                    "type": "str",
                    "description": "The XXX-XXX ID of the carrier you want to look for.",
                },
                {
                    "name": "planetary_body",
                    "type": "str",
                    "description": "The location of the carrier in system",
                },
                {
                    "name": "market_type",
                    "type": "str",
                    "description": "The unload operation for the carrier: Timed (managed markets), Squadron, "
                    "Squadron & Friends or Fully Open.",
                },
                {
                    "name": "unload_channel",
                    "type": "str",
                    "description": "The discord channel used for unloading. Required for Timed "
                    "unloads. [Optional].",
                },
            ],
            "method_desc": "Creates a wine unload notification post",
            "roles": ["Admin", "Mod", "Sommelier", "Wine Carrier"],
        }
        wine_unload_complete = {
            "params": [
                {
                    "name": "carrier_id",
                    "type": "str",
                    "description": "The XXX-XXX ID of the carrier you want to look for.",
                }
            ],
            "method_desc": "Closes a wine unload and removes the notifications.",
            "roles": ["Admin", "Mod", "Sommelier", "Wine Carrier"],
        }
        booze_archive_database = {
            "params": None,
            "method_desc": "Archives the current booze cruise database and drops the data. This is an irreversible "
            "action.",
            "roles": ["Admin"],
        }
        booze_configure_signup_forms = {
            "params": None,
            "method_desc": "Configure the current booze cruise signup forms. Expected to be a google doc (sheet).",
            "roles": ["Admin"],
        }
        make_wine_carrier = {
            "params": [
                {
                    "name": "user",
                    "type": "str",
                    "description": "An @ mention of the user to receive the role.",
                }
            ],
            "method_desc": "Gives the user the Wine Carrier role and sends them a welcome message.",
            "roles": ["Admin", "Sommelier", "Connoisseur", "Mod"],
        }
        remove_wine_carrier = {
            "params": [
                {
                    "name": "user",
                    "type": "str",
                    "description": "An @ mention of the user to remove the role.",
                }
            ],
            "method_desc": "Removes the Wine Carrier role from a user.",
            "roles": ["Admin", "Sommelier", "Connoisseur", "Mod"],
        }
        steve_says = {
            "params": [
                {
                    "name": "message",
                    "type": "str",
                    "description": "A message to send as Pirate Steve.",
                },
                {
                    "name": "send_channel",
                    "type": "str",
                    "description": "The channel to send the message in.",
                },
            ],
            "method_desc": "Sends a message as Pirate Steve",
            "roles": ["Admin", "Sommelier", "Mod"],
        }
        booze_channels_open = {
            "params": None,
            "method_desc": "Opens all public-facing Booze Cruise channels.",
            "roles": ["Admin", "Sommelier", "Mod"],
        }
        booze_channels_close = {
            "params": None,
            "method_desc": "Closes (hides) all public-facing Booze Cruise channels.",
            "roles": ["Admin", "Sommelier", "Mod"],
        }
        booze_duration_remaining = {
            "params": None,
            "method_desc": "Returns the remaining time for the current booze cruise.",
            "roles": ["Everyone"],
        }
        booze_timestamp_admin_override = {
            "params": [
                {
                    "name": "timestamp",
                    "type": "str",
                    "description": "A timestamp in the format YYYY-MM-DD HH:MM:SS",
                }
            ],
            "method_desc": "Overrides the current booze cruise start timestamp.",
            "roles": ["Admin", "Sommelier", "Mod"],
        }
        booze_reuse_signup_forms = {
            "params": None,
            "method_desc": "Reuses the current booze cruise signup forms. This is an irreversible action.",
            "roles": ["Admin"],
        }

    # pirate_steve_help slash command - get information about a specific command
    @app_commands.command(name="pirate_steve_help", description="Returns some information for each command.")
    @app_commands.describe(command="The command you want help with")
    async def get_help(self, interaction: discord.Interaction, command: HelpCommandInformation):

        #Get command name and info from enum class
        commandName = command.name
        commandInfo = command.value
        
        method_desc = commandInfo["method_desc"]
        roles = commandInfo["roles"]
        params = commandInfo["params"]

        print(f'User {interaction.user.name} has requested help for command: {commandName}')        

        response_embed = discord.Embed(
            title=f'Baton down the hatches!\nPirate Steve knows the following for: {commandName}.',
            description=f'**Description**: {method_desc}\n'
                        f'**Required Roles**: {", ".join(roles)}.\n'
                        f'**Params**: '
        )

        # Go build some fields for each param and log the information into it
        if params:
            for param in params:
                response_embed.add_field(
                    name=f'• {param["name"]}:',
                    value=f'- Description: {param["description"]}.\n'
                          f'- Type: {param["type"]}.',
                    inline=False
                )
        else:
            # In the case of no params, just append None to the description.
            response_embed.description += 'None.'

        print(f"Returning the response to: {interaction.user.name}")
        await interaction.response.send_message(embed=response_embed, ephemeral=True)
        return