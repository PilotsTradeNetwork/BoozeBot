import random
import re
from typing import override

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Bot
from discord.ui import TextInput
from discord.ui.view import BaseView
from ptn_utils.global_constants import (
    CHANNEL_BC_BOOZE_CRUISE_CHAT,
    CHANNEL_BC_STEVE_SAYS,
    CHANNEL_BC_WINE_CARRIER,
    CHANNEL_BC_WINE_CELLAR_DELIVERIES,
    ROLE_SOMM,
    any_council_role,
    any_moderation_role,
)
from ptn_utils.logger.logger import get_logger
from ptn_utils.pagination.pagination import PaginationView

from ptn.boozebot.classes.AutoResponse import AutoResponse
from ptn.boozebot.constants import ping_response_messages
from ptn.boozebot.database.database import database
from ptn.boozebot.modules.helpers import check_command_channel, check_roles

"""
LISTENERS
on_message
- If pinged in #booze-cruise-chat respond

commands

"""

logger = get_logger("boozebot.commands.autoresponses")


class AutoResponses(commands.Cog):
    auto_responses: list[AutoResponse]
    text_commands: list[str]
    bot: Bot

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.text_commands = ["ping", "exit", "update", "version", "sync"]

        self.auto_responses = []

    @override
    async def cog_load(self):
        self.auto_responses = await database.get_auto_responses()
        logger.debug(f"Loaded {len(self.auto_responses)} auto responses from database.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id not in [
            CHANNEL_BC_BOOZE_CRUISE_CHAT,
            CHANNEL_BC_WINE_CARRIER,
            CHANNEL_BC_WINE_CELLAR_DELIVERIES,
        ]:
            logger.trace(f"Ignoring message in channel {message.channel.id} (not a monitored channel).")
            return

        if message.is_system():
            logger.trace("Ignoring system message.")
            return

        if message.author == self.bot.user:
            logger.trace("Ignoring message from bot itself.")
            return

        logger.trace(
            f"Checking {len(self.auto_responses)} auto responses for message from {message.author} in {message.channel.name}"
        )
        for auto_response in self.auto_responses:
            if auto_response.matches(message):
                logger.info(
                    f"Auto response triggered: {auto_response.name} by {message.author} in {message.channel.name}"
                )
                await message.channel.send(
                    auto_response.response,
                    reference=message,
                )
                return

        if not self.bot.user.mentioned_in(message):
            logger.trace("Bot not mentioned in message, ignoring.")
            return

        if message.reference:
            logger.trace("Ignoring mention in reply message.")
            return

        msg_split = message.content.split()

        if len(msg_split) >= 2 and msg_split[1].lower() in self.text_commands:
            logger.trace(f"Ignoring mention with text command: {msg_split[1].lower()}")
            return

        logger.info(f"{message.author} ({message.author.id}) mentioned PirateSteve.")

        await message.channel.send(
            random.choice(ping_response_messages).format(message_author_id=message.author.id),
            reference=message,
        )

    @app_commands.command(name="booze_create_auto_response", description="Create a new auto response")
    @app_commands.describe(
        name="Name of the auto response",
        trigger="Trigger phrase for the auto response",
        is_regex="Is the trigger a regex pattern?",
        response="Response message to send when the trigger is matched",
    )
    @check_roles([*any_council_role, ROLE_SOMM, *any_moderation_role])
    @check_command_channel(CHANNEL_BC_STEVE_SAYS)
    async def create_auto_response(
        self,
        interaction: discord.Interaction,
        name: str,
        trigger: str,
        response: str,
        is_regex: bool = False,
    ):
        """
        Create a new auto response.

        :param interaction: The interaction object.
        :param name: The name of the auto response.
        :param trigger: The trigger phrase for the auto response.
        :param is_regex: Whether the trigger is a regex pattern.
        :param response: The response message to send when the trigger is matched.
        """

        await interaction.response.defer()

        logger.info(
            f"{interaction.user} ({interaction.user.id}) called {interaction.command.name} with name: {name} trigger: {trigger} is_regex: {is_regex}"
        )

        if is_regex:
            try:
                re.compile(trigger)
                logger.debug(f"Regex pattern '{trigger}' validated successfully.")
            except re.error as e:
                await interaction.edit_original_response(content=f"Invalid regex pattern: {trigger}. Error: {e}")
                return

        if await database.get_auto_response_by_name(name):
            logger.warning(f"Auto response creation failed: name '{name}' already exists.")
            await interaction.edit_original_response(content=f"An auto response with the name '{name}' already exists.")
            return

        await database.add_auto_response(name, trigger, response, is_regex)

        # Add the new auto response to the list
        self.auto_responses.append(
            AutoResponse(
                {
                    "name": name,
                    "trigger": trigger,
                    "is_regex": is_regex,
                    "response": response,
                }
            )
        )

        logger.info(f"Auto response '{name}' created successfully.")
        await interaction.edit_original_response(content=f"Auto response '{name}' created successfully.")

    @app_commands.command(name="booze_delete_auto_response", description="Delete an auto response")
    @app_commands.describe(name="Name of the auto response to delete")
    @check_roles([*any_council_role, ROLE_SOMM, *any_moderation_role])
    @check_command_channel(CHANNEL_BC_STEVE_SAYS)
    async def delete_auto_response(self, interaction: discord.Interaction, name: str):
        """
        Delete an auto response by name.

        :param interaction: The interaction object.
        :param name: The name of the auto response to delete.
        """

        await interaction.response.defer()

        logger.info(f"{interaction.user} ({interaction.user.id}) called {interaction.command.name} with name: {name}")

        if not await database.get_auto_response_by_name(name):
            logger.warning(f"Auto response deletion failed: name '{name}' does not exist.")
            await interaction.edit_original_response(content=f"No auto response found with the name '{name}'.")
            return

        await database.delete_auto_response(name)

        # Remove the auto response from the list
        self.auto_responses = [ar for ar in self.auto_responses if ar.name != name]

        logger.info(f"Auto response '{name}' deleted successfully.")

        await interaction.edit_original_response(content=f"Auto response '{name}' deleted successfully.")

    @app_commands.command(name="booze_list_auto_responses", description="List all auto responses")
    @check_roles([*any_council_role, ROLE_SOMM, *any_moderation_role])
    @check_command_channel(CHANNEL_BC_STEVE_SAYS)
    async def list_auto_responses(self, interaction: discord.Interaction):
        """
        List all auto responses.

        :param interaction: The interaction object.
        """

        await interaction.response.defer()

        logger.info(f"{interaction.user} ({interaction.user.id}) called {interaction.command.name}.")

        if not self.auto_responses:
            await interaction.edit_original_response(content="No auto responses found.")
            return

        logger.debug(f"Creating embed for {len(self.auto_responses)} auto responses to send to {interaction.user}.")
        content = [
            (ar.name, f"Trigger: {ar.trigger.pattern if ar.is_regex else ar.trigger}") for ar in self.auto_responses
        ]

        view = PaginationView("Auto Responses", content, buttons_text="Edit", buttons_callback=None)

        async def edit_callback(interaction: discord.Interaction, title: str, index: int):
            auto_response = self.auto_responses[index]

            logger.info(
                f"{interaction.user} ({interaction.user.id}) clicked edit button for auto response: {auto_response.name}"
            )

            modal = EditAutoResponseModal(auto_response, index, view)
            await interaction.response.send_modal(modal)

        view.buttons_callback = edit_callback
        await view.refresh_page()

        message = await interaction.followup.send(view=view)
        view.message = message


class EditAutoResponseModal(discord.ui.Modal):
    """
    Modal for editing auto response trigger and response text.
    """

    response_input: TextInput[BaseView]
    trigger_input: TextInput[BaseView]
    auto_response: AutoResponse

    def __init__(self, auto_response: AutoResponse, auto_response_index: int, view: PaginationView):
        super().__init__(title=f"Edit Auto Response: {auto_response.name}")
        self.auto_response = auto_response
        self.view: PaginationView = view
        self.auto_response_index: int = auto_response_index

        trigger = auto_response.trigger.pattern if auto_response.is_regex else auto_response.trigger

        self.trigger_input = discord.ui.TextInput(label="Trigger", default=trigger, max_length=500)
        self.add_item(self.trigger_input)

        self.response_input = discord.ui.TextInput(
            label="Response", default=auto_response.response, style=discord.TextStyle.paragraph, max_length=2000
        )
        self.add_item(self.response_input)

    @override
    async def on_submit(self, interaction: discord.Interaction):
        """
        Handle modal submission and update auto response in database.
        """
        await interaction.response.defer()

        logger.info(
            f"{interaction.user} ({interaction.user.id}) submitted edit modal for auto response: {self.auto_response.name}. New trigger: {self.trigger_input.value} New response: {self.response_input.value}"
        )

        new_trigger = self.trigger_input.value.strip()
        new_response = self.response_input.value.strip()

        if not new_trigger:
            logger.warning(f"Auto response update failed: empty trigger for auto response '{self.auto_response.name}'.")
            await interaction.followup.send("Trigger cannot be empty.")
            return

        if not new_response:
            logger.warning(
                f"Auto response update failed: empty response for auto response '{self.auto_response.name}'."
            )
            await interaction.followup.send("Response cannot be empty.")
            return

        if self.auto_response.is_regex:
            try:
                re.compile(new_trigger)
                logger.debug(
                    f"Regex pattern '{new_trigger}' validated successfully for auto response '{self.auto_response.name}'."
                )
            except re.error as e:
                logger.warning(
                    f"Auto response update failed: invalid regex pattern for auto response '{self.auto_response.name}'. Error: {e}"
                )
                await interaction.followup.send(f"Invalid regex pattern: {new_trigger}. Error: {e}")
                return

        self.auto_response.trigger = new_trigger if not self.auto_response.is_regex else re.compile(new_trigger)
        self.auto_response.response = new_response
        await database.update_auto_response(self.auto_response.name, new_trigger, new_response)

        self.view.content[self.auto_response_index] = (self.auto_response.name, f"Trigger: {new_trigger}")
        await self.view.refresh_page()

        logger.info(f"Auto response '{self.auto_response.name}' updated successfully.")
        await interaction.followup.send(f"Auto response '{self.auto_response.name}' updated successfully.", ephemeral=True)
