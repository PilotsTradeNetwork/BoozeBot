import re

import discord
from discord import app_commands
from discord.app_commands import describe
from discord.ext import commands

from ptn.boozebot.commands.ErrorHandler import on_app_command_error
# from discord_slash import cog_ext, SlashContext
# from discord_slash.model import SlashCommandPermissionType
# from discord_slash.utils.manage_commands import create_option, create_permission

from ptn.boozebot.constants import bot_guild_id, server_admin_role_id, server_sommelier_role_id, server_mod_role_id, \
    get_sommelier_notification_channel, get_steve_says_channel
from ptn.boozebot.bot import bot

class MimicSteve(commands.Cog):

    """
    This class implements functionality for a user to send commands as PirateSteve
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

    @app_commands.command(name='steve_says', description='Send a message as PirateSteve.')
    @describe(message='The message to send', send_channel='The channel to send the message in')
    async def impersonate_steve(self, interaction: discord.Interaction, message: str, send_channel: str):
        """
        Sends the provided message as Pirate Steve in the provided channel.

        :param SlashContext ctx: The discord context
        :param str message: The message to send
        :param str send_channel: The discord channel to send the message in.
        :returns: A message of pass/fail
        :rtype: SlashMessage
        """
        print(f'User {interaction.user.display_name} has requested to send the message {message} as PirateSteve in: {send_channel}.')

        # Check we are in the designated steve_says channel, if not go no farther.
        restricted_channel = bot.get_channel(get_steve_says_channel())

        if interaction.channel != restricted_channel:
            # problem, wrong channel, no progress
            print(f'Error, the command can only be ran out of: {restricted_channel}. You are in: {interaction.channel.jump_url}.')
            return await interaction.response.send_message(f'Sorry, you can only run this command out of: {restricted_channel}.', ephemeral=True)

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
            return await interaction.response.send_message(f'Pirate Steve said: {message} in: {send_channel} successfully')
        # Error case
        print(f'Error sending message in {message} channel: {send_channel}')
        return await interaction.response.send_message(f'Pirate Steve failed to say: {message} in: {send_channel}.')
