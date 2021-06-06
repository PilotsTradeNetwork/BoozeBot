import discord
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option, create_choice

from ptn.boozebot.constants import bot_guild_id


class Helper(commands.Cog):

    """
    This class is a collection of helper commands for the booze bot
    """

    @cog_ext.cog_slash(
        name='pirate_steve_help',
        guild_ids=[bot_guild_id()],
        description='Returns some information for each command.',
        options=[
            create_option(
                name='command',
                description='The command you want help with',
                option_type=3,
                required=True,
                choices=[
                    create_choice(
                        name="booze_started",
                        value="booze_started"
                    ),
                    create_choice(
                        name="booze_started_admin_override",
                        value="booze_started_admin_override"
                    ),
                    create_choice(
                        name="booze_tally",
                        value="booze_tally"
                    ),
                    create_choice(
                        name="booze_tally_extra_stats",
                        value="booze_tally_extra_stats"
                    ),
                    create_choice(
                        name="find_carriers_with_wine",
                        value="find_carriers_with_wine"
                    ),
                    create_choice(
                        name="find_carriers_by_id",
                        value="find_carriers_by_id"
                    ),
                    create_choice(
                        name="find_wine_carriers_for_platform",
                        value="fine_wine_carriers_for_platform"
                    ),
                    create_choice(
                        name="update_booze_db",
                        value="update_booze_db"
                    ),
                    create_choice(
                        name="wine_helper_market_closed",
                        value="wine_helper_market_closed"
                    ),
                    create_choice(
                        name="wine_helper_market_open",
                        value="wine_helper_market_open"
                    ),
                    create_choice(
                        name="wine_mark_completed_forcefully",
                        value="wine_mark_completed_forcefully"
                    ),
                    create_choice(
                        name="wine_unload",
                        value="wine_unload"
                    ),
                    create_choice(
                        name="wine_unload_complete",
                        value="wine_unload_complete"
                    )
                ]
            ),
        ]
    )
    async def get_help(self, ctx: SlashContext, command: str):
        """
        Returns a help context message privately to the user.

        :param ctx:
        :param command:
        :returns: None
        """
        print(f'User {ctx.author} has requested help for command: {command}')
        # For each value we just populate some data.
        if command == 'booze_tally':
            params = None
            method_desc = 'Logs the current tally of carriers, wine and some basic stats.'
            roles = ['Admin', 'Mod', 'Sommelier']
        elif command == 'booze_tally_extra_stats':
            params = None
            method_desc = 'Logs some stats regarding what the volume of wine looks like.'
            roles = ['Admin', 'Mod', 'Sommelier']
        elif command == 'find_carriers_with_wine':
            params = None
            method_desc = 'Returns all the remaining carriers with wine to unload.'
            roles = ['Admin', 'Mod', 'Sommelier']
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
                    'description': 'PC, Xbox or Playstation.'
                },
                {
                    'name': 'with_wine',
                    'type': 'bool',
                    'description': 'Restrict the search to those with or without wine.'
                },
            ]
            method_desc = 'Find carriers for the platform.'
            roles = ['Admin', 'Mod', 'Sommelier']
        elif command == 'update_booze_db':
            params = None
            method_desc = 'Forces an update of the booze database.'
            roles = ['Admin', 'Sommelier']
        elif command == 'booze_started':
            params = None
            method_desc = 'Queries the current state of the holiday.'
            roles = ['Admin', 'Sommelier', 'Mod']
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
            roles = ['Admin', 'Mod', 'Sommelier', 'Carrier Owner', 'Auxiliary Carrier Owner']
        elif command == 'wine_helper_market_open':
            params = None
            method_desc = 'Drops a helper embed into the channel for timed market unloading'
            roles = ['Admin', 'Mod', 'Sommelier', 'Carrier Owner', 'Auxiliary Carrier Owner']
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
                    'description': 'The unload operation for the carrier: Timed (managed markets),'
                                   ' Squadron & Friends or Fully Open.'
                },
                {
                    'name': 'unload_channel',
                    'type': 'str',
                    'description': 'The discord channel used for unloading. Required for Timed '
                                   'unloads. [Optional].'
                }
            ]
            method_desc = 'Creates a wine unload notification post'
            roles = ['Admin', 'Mod', 'Sommelier']
        elif command == 'wine_unload_complete':
            params = [
                {
                    'name': 'carrier_id',
                    'type': 'str',
                    'description': 'The XXX-XXX ID of the carrier you want to look for.'
                }
            ]
            method_desc = 'Closes a wine unload and removes the notifications.'
            roles = ['Admin', 'Mod', 'Sommelier']
        else:
            print('User did not provide a valid command.')
            return await ctx.send(f'Unknown handling for command: {command}.')

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

        print(f"Returning the response to: {ctx.author}")
        await ctx.send(embed=response_embed, hidden=True)
