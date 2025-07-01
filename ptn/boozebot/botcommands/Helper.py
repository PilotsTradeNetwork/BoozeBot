"""
Steve's help command

"""

# libraries
import re
import enum
import logging

# discord.py
import discord
from discord.ext import commands
from discord import app_commands

# local constants
from ptn.boozebot.constants import get_steve_says_channel, get_wine_carrier_channel, wine_carrier_command_channel, \
    server_mod_role_id, server_sommelier_role_id, server_council_role_ids, server_connoisseur_role_id, server_wine_carrier_role_id, \
    bot_guild_id, get_primary_booze_discussions_channel

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
        
        self.roles = {
        }

    # custom global error handler
    # attaching the handler when the cog is loaded
    # and storing the old handler
    async def cog_load(self):
        tree = self.bot.tree
        self._old_tree_error = tree.on_error
        tree.on_error = on_app_command_error

    # detaching the handler when the cog is unloaded
    async def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = self._old_tree_error
        
    # Fetch all the role names
    @commands.Cog.listener()
    async def on_ready(self):
        try:
            guild = self.bot.get_guild(bot_guild_id())
        except Exception as e:
            logging.exception(f"Failed to get guild: {e}")

        for command in self.HelpCommandInformation:
            # Get lowest role associated with command and add it to that category
            try:
                role = guild.get_role(command.value["roles"][-1]).name
            except Exception as e:
                logging.exception(f"Failed to get role: {e}")

            if role not in self.roles:
                self.roles[role] = []
            self.roles[role].append(command.name)

    """
    Class to store all the different commands and their information
        
    """

    class HelpCommandInformation(enum.Enum):
        # Admin commands
        _update = {
            "method_desc": "Restart the bot.",
            "roles": [*server_council_role_ids()],
            "params": [],
            "channel_restrictions": [],
        }
        _exit = {
            "method_desc": "Stop the bot.",
            "roles": [*server_council_role_ids()],
            "params": [],
            "channel_restrictions": [],
        }
        _version = {
            "method_desc": "Get the bot version.",
            "roles": [*server_council_role_ids()],
            "params": [],
            "channel_restrictions": [],
        }
        _sync = {
            "method_desc": "Sync the bot command tree.",
            "roles": [*server_council_role_ids()],
            "params": [],
            "channel_restrictions": [],
        }
        
        # Somm commands
        _ping = {
            "method_desc": "Ping the bot.",
            "roles": [*server_council_role_ids(), server_sommelier_role_id()],
            "params": [],
            "channel_restrictions": [],
        }
        steve_says = {
            "method_desc": "Send a message as PirateSteve.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "message",
                    "description": "The message to send",
                    "type": "str"
                },
                {
                    "name": "send_channel",
                    "description": "The channel to send the message in. Defaults to the current channel.",
                    "type": "discord.TextChannel"
                }
            ],
            "channel_restrictions": [],
        }
        booze_started_admin_override = {
            "method_desc": "Override the Public Holiday Started State.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "state",
                    "description": "The state to set the Public Holiday Started State to.",
                    "type": "bool"
                },
                {
                    "name": "force_update",
                    "description": "Force the update of the holiday state, even if it is already set.",
                    "type": "bool"
                }
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        wine_mark_completed_forcefully = {
            "method_desc": "Forcefully mark a wine as completed.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "carrier_id",
                    "description": "The ID of the carrier to mark as completed.",
                    "type": "str"
                }
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        booze_channels_open = {
            "method_desc": "Open the booze channels to the public.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        booze_channels_close = {
            "method_desc": "Close the booze channels to the public.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        clear_booze_roles = {
            "method_desc": "Clear all the booze cruise roles from everyone.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        booze_update_blurb_message = {
            "method_desc": "Update a blurb message (WCO welcome or status announcement).",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "blurb",
                    "description": "The blurb to update",
                    "type": "str"
                }
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        booze_pin_message = {
            "method_desc": "Pin a steve tally embed for automatic updating.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "message_link",
                    "description": "The link of the message to pin.",
                    "type": "str"
                }
            ],
            "channel_restrictions": [],
        }
        booze_unpin_all = {
            "method_desc": "Unpin and forget all automatic updating tallies",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        booze_unpin_message = {
            "method_desc": "Unpin and forget an automatic updating tally message",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "message_link",
                    "description": "The link of the message to unpin.",
                    "type": "str"
                }
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        booze_delete_carrier = {
            "method_desc": "Delete a carrier from the database.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "carrier_id",
                    "description": "The ID of the carrier to delete.",
                    "type": "str"
                }
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        booze_archive_database = {
            "method_desc": "Archive the database after the cruise has ended.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        booze_configure_signup_forms = {
            "method_desc": "Configure the signup forms for the cruise.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        booze_reuse_signup_form = {
            "method_desc": "Reuse the signup form from the last cruise again.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        remove_wine_carrier = {
            "method_desc": "Removes the Wine Carrier role from a user.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "user",
                    "description": "An @ mention of the Discord user to receive the role.",
                    "type": "discord.Member"
                }
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        start_task = {
            "method_desc": "Start a background task.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "task_name",
                    "description": "The name of the task to start.",
                    "type": "str"
                },
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        stop_task = {
            "method_desc": "Stop a background task.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "task_name",
                    "description": "The name of the task to stop.",
                    "type": "str"
                },
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        task_status = {
            "method_desc": "Get the status of a background task.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "task_name",
                    "description": "The name of the task to get the status of.",
                    "type": "str"
                },
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        booze_purge_full_carriers = {
            "method_desc": "Purge all carriers from the database that have no wine.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        open_wine_carrier_feedback = {
            "method_desc": "Open the wine carrier feedback channel.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        close_wine_carrier_feedback = {
            "method_desc": "Close the wine carrier feedback channel.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        set_allowed_departures = {
            "method_desc": "Set the allowed departures to be posted.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "status",
                    "description": "The status to set the allowed departures to.",
                    "type": "str"
                }
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        toggle_timed_unloads = {
            "method_desc": "Toggle timed unloads on or off.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        booze_timestamp_admin_override = {
            "method_desc": "Override the Public Holiday start timestamp.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "timestamp",
                    "description": "The timestamp to set the Public Holiday start timestamp to.",
                    "type": "str"
                }
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        booze_update_bc_status_embed = {
            "method_desc": "Update the BC status embed.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "status",
                    "description": "The status to set the BC status embed to.",
                    "type": "str"
                }
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        official_carrier_departure = {
            "method_desc": "Post an official carrier departure notice.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()],
            "params": [
                {
                    "name": "carrier_id",
                    "description": "The ID of the carrier to post a departure notice for.",
                    "type": "str"
                },
                {
                    "name": "departure_location",
                    "description": "The location the carrier is departing from.",
                    "type": "str"
                },
                {
                    "name": "arrival_location",
                    "description": "The location the carrier is arriving to.",
                    "type": "str"
                },
                {
                    "name": "departure_time_type",
                    "description": "The type of departure time to use. Start/End of PH or a specific time.",
                    "type": "str"
                },
                {
                    "name": "departure_timestamp",
                    "description": "The unix timestamp, or discord timestamp of the carrier departure.",
                    "type": "str"
                }
            ],
            "channel_restrictions": [get_steve_says_channel()],
        }
        
        
        # Connoisseur commands
        update_booze_db = {
            "method_desc": "Update the booze database from the google sheet.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        make_wine_carrier = {
            "method_desc": "Give user the Wine Carrier role.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id()],
            "params": [
                {
                    "name": "user",
                    "description": "An @ mention of the Discord user to receive the role.",
                    "type": "discord.Member"
                }
            ],
            "channel_restrictions": [],
        }
        booze_tally = {
            "method_desc": "Get the current booze tally.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id()],
            "params": [
                {
                    "name": "cruise_select",
                    "description": "The cruise to get the tally for. Defaults to the current cruise.",
                    "type": "str"
                }    
            ],
            "channel_restrictions": [],
        }
        booze_carrier_summary = {
            "method_desc": "Get the summary of the carriers.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id()],
            "params": [],
            "channel_restrictions": [],
        }
        booze_tally_extra_stats = {
            "method_desc": "Get the extra stats for the booze tally.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id()],
            "params": [
                {
                    "name": "cruise_select",
                    "description": "The cruise to get the tally for. Defaults to the current cruise.",
                    "type": "str"
                }    
            ],
            "channel_restrictions": [],
        }
        biggest_cruise_tally = {
            "method_desc": "Get the biggest cruise tally.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id()],
            "params": [
                {
                    "name": "extended",
                    "description": "Whether to return the extended stats.",
                    "type": "bool"
                    }
                ],
            "channel_restrictions": [],
        }
        booze_started = {
            "method_desc": "Get the Public Holiday Started State.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel()],
        }
        
        
        # Wine carrier commands
        find_carriers_with_wine = {
            "method_desc": "Find carriers with wine.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()],
            "params": [],
            "channel_restrictions": [get_steve_says_channel(), get_wine_carrier_channel()],
        }
        find_wine_carriers_for_platform = {
            "method_desc": "Find carriers with wine for a specific platform.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()],
            "params": [
                {
                    "name": "platform",
                    "description": "The platform to search for.",
                    "type": "str"
                }
            ],
            "channel_restrictions": [get_steve_says_channel(), get_wine_carrier_channel()],
        }
        find_wine_carrier_by_id = {
            "method_desc": "Find a wine carrier by their ID.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()],
            "params": [
                {
                    "name": "carrier_id",
                    "description": "The ID of the carrier to search for.",
                    "type": "str"
                }
            ],
            "channel_restrictions": [get_steve_says_channel(), get_wine_carrier_channel()],
        }
        wine_unload_complete = {
            "method_desc": "Close the unload of a carrier and delete the wine unload post.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()],
            "params": [
                {
                    "name": "carrier_id",
                    "description": "The ID of the carrier to mark as unloaded.",
                    "type": "str"
                }
            ],
            "channel_restrictions": [wine_carrier_command_channel()],
        }
        wine_unload = {
            "method_desc": "Track the unload of a carrier and create a wine unload post.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()],
            "params": [
                {
                    "name": "carrier_id",
                    "description": "The ID of the carrier to mark as unloaded.",
                    "type": "str"
                },
                {
                    "name": "body",
                    "description": "A string representing the location of the carrier, ie Star, P1, P2",
                    "type": "str"
                }
            ],
            "channel_restrictions": [wine_carrier_command_channel()],
        }
        wine_timed_unload = {
            "method_desc": "Post a new timed unload notice for a carrier.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()],
            "params": [
                {
                    "name": "carrier_id",
                    "description": "The ID of the carrier to mark as unloaded.",
                    "type": "str"
                },
                {
                    "name": "body",
                    "description": "A string representing the location of the carrier, ie Star, P1, P2",
                    "type": "str"
                },
                {
                    "name": "unload_channel",
                    "description": "The discord channel #xxx which the carrier will run timed unloads in",
                    "type": "str"
                }
            ],
            "channel_restrictions": [wine_carrier_command_channel()],
        }
        wine_helper_market_open = {
            "method_desc": "Creates a new unloading helper operation in this channel.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()],
            "params": [],
            "channel_restrictions": [],
        }
        wine_helper_market_closed = {
            "method_desc": "Sends a message to indicate you have closed your market. Command sent in active channel.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()],
            "params": [],
            "channel_restrictions": [],
        }
        wine_carrier_departure = {
            "method_desc": "Post a departure notice for a carrier.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()],
            "params": [
                {
                    "name": "carrier_id",
                    "description": "The ID of the carrier to post a departure notice for.",
                    "type": "str"
                },
                {
                    "name": "departure_location",
                    "description": "The location the carrier is departing from.",
                    "type": "str"
                },
                {
                    "name": "arrival_location",
                    "description": "The location the carrier is arriving to.",
                    "type": "str"
                },
                {
                    "name": "departing_at",
                    "description": "The unix timestamp, or discord timestamp of the carrier departure.",
                    "type": "str"
                },
                {
                    "name": "departing_in",
                    "description": "The number of minutes until the carrier departs.",
                    "type": "float"
                }
            ],
            "channel_restrictions": [wine_carrier_command_channel()],
        }
        
        booze_carrier_stats = {
            "method_desc": "Get the stats for a specific carrier.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()],
            "params": [
                {
                    "name": "carrier_id",
                    "description": "The ID of the carrier to get stats for.",
                    "type": "str"
                }
            ],
            "channel_restrictions": [],
        }
        
        # Everyone commands
        pirate_steve_help = {
            "method_desc": "Returns some information for each command.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id(), bot_guild_id()],
            "params": [],
            "channel_restrictions": [],
        }
        booze_duration_remaining = {
            "method_desc": "Get the remaining duration of the cruise.",
            "roles": [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id(), bot_guild_id()],
            "params": [],
            "channel_restrictions": [steve_says(), get_primary_booze_discussions_channel()],
        }
        
    
    def get_command_info(self, command_name):
        """
        Function to get the command information for a specific command.

        :param str command_name: The command name to get information for
        :returns: dict
        """

        # Get the command information from the enum class
        command = self.HelpCommandInformation[command_name]
        return command
      
    def buildHelpEmbed(self, command):
        """
        Function to send the help information for a specific command.

        :param dict command: The command information to send help for
        :returns: None
        """

        #Get command name and info from enum class
        commandName = command.name
        
        if commandName.startswith("_"):
            commandName = commandName[1:]
            commandName = "b/"+commandName
        else:
            commandName = "/"+commandName
        
        commandInfo = command.value
        
        method_desc = commandInfo["method_desc"]
        roles = commandInfo["roles"]
        params = commandInfo["params"]
        channels = commandInfo["channel_restrictions"]
        
        channels = [f'<#{channel}>' for channel in channels]
        channelText = f'**Channel Restrictions**: {", ".join(channels)}.' if channels else ''
        
        roles = [f'<@&{role}>' for role in roles]
        roleText = f'**Required Roles**: {", ".join(roles)}.' if roles else ''
        
        response_embed = discord.Embed(
            title=f'Batten down the hatches!\nPirate Steve knows the following for: {commandName}.',
            description=f'**Description**: {method_desc}\n'
                        f'{roleText}\n'
                        f'{channelText}\n'
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
            
        return response_embed
   
   
    @app_commands.command(name="pirate_steve_help", description="Returns some information for each command.")
    async def get_help(self, interaction: discord.Interaction):
        
        print(f"pirate_steve_help called by {interaction.user.name} in {interaction.channel.name}")
                
        options = [
            discord.SelectOption(label=role, value=role)
            for role in self.roles.keys()
        ]
        role_select = discord.ui.Select(placeholder="Choose a role...", options=options)
        
        main_interaction = interaction

        async def select_callback(interaction: discord.Interaction):
            role = role_select.values[0]
            print(f"Role selected: {role}")
            commands = self.roles[role]
            command_options = [
                discord.SelectOption(label=cmd, value=cmd)
                for cmd in commands
            ]
            command_select = discord.ui.Select(placeholder="Choose a command...", options=command_options)

            async def command_select_callback(interaction: discord.Interaction):
                command_name = command_select.values[0]
                print(f"Command selected: {command_name}")
                command = self.get_command_info(command_name)
                response_embed = self.buildHelpEmbed(command)
                print("Sending command information message")
                await interaction.response.defer()
                await main_interaction.edit_original_response(embed=response_embed, view=None)

            command_select.callback = command_select_callback
            view = discord.ui.View()
            view.add_item(command_select)
            print("Sending command selection message")
            await interaction.response.defer()
            await main_interaction.edit_original_response(content="Select a command:", view=view)

        role_select.callback = select_callback
        view = discord.ui.View()
        view.add_item(role_select)
        print("Sending role selection message")
        await interaction.response.send_message("Commands for role:", view=view, ephemeral=True)