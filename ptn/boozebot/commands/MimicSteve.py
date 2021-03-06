import re

import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.model import SlashCommandPermissionType
from discord_slash.utils.manage_commands import create_option, create_permission

from ptn.boozebot.constants import bot_guild_id, server_admin_role_id, server_sommelier_role_id, server_mod_role_id, \
    bot, get_sommelier_notification_channel, get_steve_says_channel


class MimicSteve(commands.Cog):

    """
    This class implements functionality for a user to send commands as PirateSteve
    """

    @cog_ext.cog_slash(
        name='Steve_Says',
        guild_ids=[bot_guild_id()],
        description='Send a message as PirateSteve.',
        options=[
            create_option(
                name='message',
                description='The message to send',
                option_type=3,
                required=True
            ),
            create_option(
                name='send_channel',
                description='The channel to send the message in',
                option_type=3,
                required=True
            )
        ],
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
    )
    async def impersonate_steve(self, ctx: SlashContext, message: str, send_channel: str):
        """
        Sends the provided message as Pirate Steve in the provided channel.

        :param SlashContext ctx: The discord context
        :param str message: The message to send
        :param str send_channel: The discord channel to send the message in.
        :returns: A message of pass/fail
        :rtype: SlashMessage
        """
        print(f'User {ctx.author} has requested to send the message {message} as PirateSteve in: {send_channel}.')

        # Check we are in the designated steve_says channel, if not go no farther.
        restricted_channel = bot.get_channel(get_steve_says_channel())

        if ctx.channel != restricted_channel:
            # problem, wrong channel, no progress
            print(f'Error, the command can only be ran out of: {restricted_channel}. You are in: {ctx.channel}.')
            return await ctx.send(f'Sorry, you can only run this command out of: {restricted_channel}.', hidden=True)

        channel = bot.get_channel(int(send_channel.replace('#', '').replace('<', '').replace('>', '')))
        print(f'Channel resolved into: {channel}. Checking for any potential use names to be resolved.')

        possible_id = None
        # Try to resolve any @<int> to a user
        for word in message.split():
            if word.startswith('@'):
                try:
                    print(f'Potential user id found: {word}.')
                    # this might be a user ID, int convert it
                    possible_id = int(re.search(r'\d+', word).group())

                    # Ok this was in fact an int, try to see if it resolves to a discord user
                    member = await bot.fetch_user(possible_id)
                    print(f'Member determined as: {member}')

                    message = message.replace(word, f'<@{member.id}>')
                    print(f'New message is: {message}')
                except discord.errors.NotFound as ex:
                    print(f'Potential user string "{possible_id if possible_id else word}" is invalid: {ex}. Continuing '
                          f'on as-is')
                except ValueError as ex:
                    # Ok continue on anyway and send it as-is
                    print(f'Error converting the word: {word}. {ex}')

        response = f'{message}'
        msg = await channel.send(content=response)
        if msg:
            print('Message was impersonated successfully.')
            return await ctx.send(f'Pirate Steve said: {message} in: {send_channel} successfully')
        # Error case
        print(f'Error sending message in {message} channel: {send_channel}')
        return await ctx.send(f'Pirate Steve failed to say: {message} in: {send_channel}.')
