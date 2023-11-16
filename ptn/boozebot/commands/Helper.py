from typing import List

import discord
from discord import app_commands
from discord.app_commands import describe
from discord.ext import commands
from ptn.boozebot.bot import bot
# from discord_slash import SlashContext, cog_ext
# from discord_slash.utils.manage_commands import create_option, create_choice

from ptn.boozebot.commands.ErrorHandler import CommandRoleError, on_app_command_error
from ptn.boozebot.constants import bot_guild_id, server_admin_role_id, server_mod_role_id


@bot.listen()
async def on_command_error(ctx, error):
    print(error)
    if isinstance(error, commands.BadArgument):
        message = f'Bad argument: {error}'

    elif isinstance(error, commands.CommandNotFound):
        message = f"Sorry, were you talking to me? I don't know that command."

    elif isinstance(error, commands.MissingRequiredArgument):
        message = f"Sorry, that didn't work.\n• Check you've included all required arguments." \
                  "\n• If using quotation marks, check they're opened *and* closed, and are in the proper place.\n• Check quotation" \
                  " marks are of the same type, i.e. all straight or matching open/close smartquotes."

    elif isinstance(error, commands.MissingPermissions):
        message = 'Sorry, you\'re missing the required permission for this command.'

    elif isinstance(error, commands.MissingAnyRole):
        message = f'You require one of the following roles to use this command:\n<@&{server_admin_role_id()}> • <@&{server_mod_role_id()}>'

    else:
        message = f'Sorry, that didn\'t work: {error}'

    embed = discord.Embed(description=f"❌ {message}")
    await ctx.send(embed=embed)


class Helper(commands.Cog):
    """
    This class is a collection of helper commands for the booze bot
    """

    def __init__(self, bot: commands.Cog):
        self.bot = bot
        self.summon_message_ids = {}

    def cog_load(self):
        tree = self.bot.tree
        self._old_tree_error = tree.on_error
        tree.on_error = on_app_command_error

    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = self._old_tree_error

    # @cog_ext.cog_slash(
    #     name='pirate_steve_help',
    #     guild_ids=[bot_guild_id()],
    #     description='Returns some information for each command.',
    #     options=[
    #         create_option(
    #             name='command',
    #             description='The command you want help with',
    #             option_type=3,
    #             required=True,
    #             choices=[
    #                 create_choice(
    #                     name='booze_archive_database',
    #                     value='booze_archive_database'
    #                 ),
    #                 create_choice(
    #                     name='booze_configure_signup_forms',
    #                     value='booze_configure_signup_forms'
    #                 ),
    #                 create_choice(
    #                     name="booze_delete_carrier",
    #                     value="booze_delete_carrier"
    #                 ),
    #                 create_choice(
    #                     name="booze_started",
    #                     value="booze_started"
    #                 ),
    #                 create_choice(
    #                     name="booze_started_admin_override",
    #                     value="booze_started_admin_override"
    #                 ),
    #                 create_choice(
    #                     name="booze_tally",
    #                     value="booze_tally"
    #                 ),
    #                 create_choice(
    #                     name="booze_tally_extra_stats",
    #                     value="booze_tally_extra_stats"
    #                 ),
    #                 create_choice(
    #                     name="find_carriers_with_wine",
    #                     value="find_carriers_with_wine"
    #                 ),
    #                 create_choice(
    #                     name="find_carriers_by_id",
    #                     value="find_carriers_by_id"
    #                 ),
    #                 create_choice(
    #                     name="find_wine_carriers_for_platform",
    #                     value="find_wine_carriers_for_platform"
    #                 ),
    #                 create_choice(
    #                     name="update_booze_db",
    #                     value="update_booze_db"
    #                 ),
    #                 create_choice(
    #                     name="wine_helper_market_closed",
    #                     value="wine_helper_market_closed"
    #                 ),
    #                 create_choice(
    #                     name="wine_helper_market_open",
    #                     value="wine_helper_market_open"
    #                 ),
    #                 create_choice(
    #                     name="wine_mark_completed_forcefully",
    #                     value="wine_mark_completed_forcefully"
    #                 ),
    #                 create_choice(
    #                     name="wine_unload",
    #                     value="wine_unload"
    #                 ),
    #                 create_choice(
    #                     name="wine_unload_complete",
    #                     value="wine_unload_complete"
    #                 ),
    #                 create_choice(
    #                     name="make_wine_carrier",
    #                     value="make_wine_carrier"
    #                 ),
    #                 create_choice(
    #                     name="remove_wine_carrier",
    #                     value="remove_wine_carrier"
    #                 ),
    #                 create_choice(
    #                     name="steve_says",
    #                     value="steve_says"
    #                 ),
    #                 create_choice(
    #                     name="booze_channels_open",
    #                     value="booze_channels_open"
    #                 ),
    #                 create_choice(
    #                     name="booze_channels_close",
    #                     value="booze_channels_close"
    #                 )
    #             ]
    #         ),
    #     ]
    # )
    @app_commands.command(name='pirate_steve_help', description='Returns some information for each command.')
    @describe(command='The command you want help with')
    async def get_help(self, interaction: discord.Interaction, command: str):
        """
        Returns a help context message privately to the user.

        :param ctx:
        :param command:
        :returns: None
        """
        print(f'User {interaction.user.display_name} has requested help for command: {command}')
        # For each value we just populate some data.
        if command == 'booze_tally':
            params = [
                {
                    'name': 'cruise_select',
                    'type': 'int',
                    'description': 'An integer value representing the cruise you wish data for. 0 (default) is the '
                                   'current cruise, 1 the last etc. [Optional]'
                }
            ]
            method_desc = 'Logs the current tally of carriers, wine and some basic stats.'
            roles = ['Admin', 'Mod', 'Sommelier', 'Connoisseur']
        elif command == 'booze_delete_carrier':
            params = [
                {
                    'name': 'carrier_id',
                    'type': 'str',
                    'description': 'The XXX-XXX ID of the carrier you want to look for.'
                }
            ]
            method_desc = 'Removes a carrier from the database.'
            roles = ['Admin', 'Mod', 'Sommelier']
        elif command == 'booze_pin_message':
            params = [
                {
                    'name': 'message_id',
                    'type': 'str',
                    'description': 'The message ID to pin'
                },
                {
                    'name': 'channel_id',
                    'type': 'str',
                    'description': 'The channel ID to pin. Optional, uses the current channel if not provided.'
                }
            ]
            method_desc = 'Pins a message to the channel.'
            roles = ['Admin', 'Mod', 'Sommelier']
        elif command == 'booze_unpin_all':
            params = None
            method_desc = 'Unpins all message for booze bot.'
            roles = ['Admin', 'Mod', 'Sommelier']
        elif command == 'booze_unpin_message':
            params = [
                {
                    'name': 'message_id',
                    'type': 'str',
                    'description': 'The message ID to pin'
                }
            ]
            method_desc = 'Unpins the specific message for booze bot.'
            roles = ['Admin', 'Mod', 'Sommelier']
        elif command == 'booze_tally_extra_stats':
            params = None
            method_desc = 'Logs some stats regarding what the volume of wine looks like.'
            roles = ['Admin', 'Mod', 'Sommelier', 'Connoisseur']
        elif command == 'find_carriers_with_wine':
            params = None
            method_desc = 'Returns all the remaining carriers with wine to unload.'
            roles = ['Admin', 'Mod', 'Sommelier', 'WineCarrier']
        elif command == 'find_carriers_by_id':
            params = [
                {
                    'name': 'carrier_id',
                    'type': 'str',
                    'description': 'The XXX-XXX ID of the carrier you want to look for.'
                }
            ]
            method_desc = 'Returns a carrier object from the ID'
            roles = ['Everyone']
        elif command == 'find_wine_carriers_for_platform':
            params = [
                {
                    'name': 'platform',
                    'type': 'str',
                    'description': 'PC (All), PC (Horizons Only), PC (Horizons + Odyssey), Xbox or Playstation.'
                },
                {
                    'name': 'with_wine',
                    'type': 'bool',
                    'description': 'Restrict the search to those with or without wine.'
                },
            ]
            method_desc = 'Find carriers for the platform.'
            roles = ['Admin', 'Mod', 'Sommelier', 'WineCarrier']
        elif command == 'update_booze_db':
            params = None
            method_desc = 'Forces an update of the booze database.'
            roles = ['Admin', 'Sommelier', 'Connoisseur']
        elif command == 'booze_started':
            params = None
            method_desc = 'Queries the current state of the holiday.'
            roles = ['Admin', 'Sommelier', 'Mod', 'Connoisseur']
        elif command == 'booze_started_admin_override':
            params = [
                {
                    'name': 'state',
                    'type': 'bool',
                    'description': 'Set the override flag to the provided state'
                }
            ]
            method_desc = 'Forces the parameter flag to the provided value. Overrides the holiday checker if True.'
            roles = ['Admin', 'Sommelier', 'Mod']
        elif command == 'wine_helper_market_closed':
            params = None
            method_desc = 'Drops a helper embed into the channel for timed market closure.'
            roles = ['Admin', 'Mod', 'Sommelier', 'Wine Carrier']
        elif command == 'wine_helper_market_open':
            params = None
            method_desc = 'Drops a helper embed into the channel for timed market unloading'
            roles = ['Admin', 'Mod', 'Sommelier', 'Wine Carrier']
        elif command == 'wine_mark_completed_forcefully':
            params = [
                {
                    'name': 'carrier_id',
                    'type': 'str',
                    'description': 'The XXX-XXX ID of the carrier you want to look for.'
                }
            ]
            method_desc = 'Marks a carrier as forcefully completed. Useful if someone unloaded and did not tell us.'
            roles = ['Admin', 'Mod', 'Sommelier']
        elif command == 'wine_unload':
            params = [
                {
                    'name': 'carrier_id',
                    'type': 'str',
                    'description': 'The XXX-XXX ID of the carrier you want to look for.'
                },
                {
                    'name': 'planetary_body',
                    'type': 'str',
                    'description': 'The location of the carrier in system'
                },
                {
                    'name': 'market_type',
                    'type': 'str',
                    'description': 'The unload operation for the carrier: Timed (managed markets), Squadron, '
                                   'Squadron & Friends or Fully Open.'
                },
                {
                    'name': 'unload_channel',
                    'type': 'str',
                    'description': 'The discord channel used for unloading. Required for Timed '
                                   'unloads. [Optional].'
                }
            ]
            method_desc = 'Creates a wine unload notification post'
            roles = ['Admin', 'Mod', 'Sommelier', 'Wine Carrier']
        elif command == 'wine_unload_complete':
            params = [
                {
                    'name': 'carrier_id',
                    'type': 'str',
                    'description': 'The XXX-XXX ID of the carrier you want to look for.'
                }
            ]
            method_desc = 'Closes a wine unload and removes the notifications.'
            roles = ['Admin', 'Mod', 'Sommelier', 'Wine Carrier']
        elif command == 'booze_archive_database':
            params = None
            method_desc = 'Archives the current booze cruise database and drops the data. This is an irreversible ' \
                          'action.'
            roles = ['Admin']
        elif command == 'booze_configure_signup_forms':
            params = None
            method_desc = 'Configure the current booze cruise signup forms. Expected to be a google doc (sheet).'
            roles = ['Admin']
        elif command == 'make_wine_carrier':
            params = [
                {
                    'name': 'user',
                    'type': 'str',
                    'description': 'An @ mention of the user to receive the role.'
                }
            ]
            method_desc = 'Gives the user the Wine Carrier role and sends them a welcome message.'
            roles = ['Admin', 'Sommelier', 'Connoisseur', 'Mod']
        elif command == 'remove_wine_carrier':
            params = [
                {
                    'name': 'user',
                    'type': 'str',
                    'description': 'An @ mention of the user to remove the role.'
                }
            ]
            method_desc = 'Removes the Wine Carrier role from a user.'
            roles = ['Admin', 'Sommelier', 'Connoisseur', 'Mod']
        elif command == 'steve_says':
            params = [
                {
                    'name': 'message',
                    'type': 'str',
                    'description': 'A message to send as Pirate Steve.'
                },
                {
                    'name': 'send_channel',
                    'type': 'str',
                    'description': 'The channel to send the message in.'
                }
            ]
            method_desc = 'Sends a message as Pirate Steve'
            roles = ['Admin', 'Sommelier', 'Mod']
        elif command == 'booze_channels_open':
            params = None
            method_desc = 'Opens all public-facing Booze Cruise channels.'
            roles = ['Admin', 'Sommelier', 'Mod']
        elif command == 'booze_channels_close':
            params = None
            method_desc = 'Closes (hides) all public-facing Booze Cruise channels.'
            roles = ['Admin', 'Sommelier', 'Mod']
        else:
            print('User did not provide a valid command.')
            return await interaction.response.send_message(f'Unknown handling for command: {command}.')

        response_embed = discord.Embed(
            title=f'Baton down the hatches!\nPirate Steve knows the following for: {command}.',
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

        print(f"Returning the response to: {interaction.user.display_name}")
        await interaction.user.send_message(embed=response_embed, ephemeral=True)

    @get_help.autocomplete('command')
    async def booze_operation_autocomplete(
            self,
            interaction: discord.Interaction,
            current: str
    ) -> List[app_commands.Choice[str]]:
        booze_operations = [
            'booze_archive_database',
            'booze_configure_signup_forms',
            'booze_delete_carrier',
            'booze_started',
            'booze_started_admin_override',
            'booze_tally',
            'booze_tally_extra_stats',
            'find_carriers_with_wine',
            'find_carriers_by_id',
            'find_wine_carriers_for_platform',
            'update_booze_db',
            'wine_helper_market_closed',
            'wine_helper_market_open',
            'wine_mark_completed_forcefully',
            'wine_unload',
            'wine_unload_complete',
            'make_wine_carrier',
            'remove_wine_carrier',
            'steve_says',
            'booze_channels_open',
            'booze_channels_close',
        ]
        return [
            app_commands.Choice(name=operation, value=operation)
            for operation in booze_operations if current.lower() in operation.lower()
        ]


# 3 functions for verifying roles
def get_role(ctx, id):  # takes a Discord role ID and returns the role object
    role = discord.utils.get(ctx.guild.roles, id=id)
    return role


async def checkroles_actual(interaction: discord.Interaction, permitted_role_ids):
    try:
        """
        Check if the user has at least one of the permitted roles to run a command
        """
        print(f"checkroles called.")
        author_roles = interaction.user.roles
        permitted_roles = [get_role(interaction, role) for role in permitted_role_ids]
        # print(author_roles)
        # print(permitted_roles)
        permission = True if any(x in permitted_roles for x in author_roles) else False
        # print(f'Permission: {permission}')
        return permission, permitted_roles
    except Exception as e:
        print(e)
    return permission


def check_roles(permitted_role_ids):
    async def checkroles(interaction: discord.Interaction):
        permission, permitted_roles = await checkroles_actual(interaction, permitted_role_ids)
        print("Inherited permission from checkroles")
        if not permission:  # raise our custom error to notify the user gracefully
            role_list = []
            for role in permitted_role_ids:
                role_list.append(f'<@&{role}> ')
                formatted_role_list = " • ".join(role_list)
            try:
                raise CommandRoleError(permitted_roles, formatted_role_list)
            except CommandRoleError as e:
                print(e)
                raise
        return permission

    return app_commands.check(checkroles)

    return app_commands.check(checkroles)
