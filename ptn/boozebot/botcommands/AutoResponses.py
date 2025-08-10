# libraries
import random

# discord.py
import discord
from discord import app_commands
from discord.ext import commands

from ptn.boozebot._metadata import __version__
from ptn.boozebot.classes.AutoResponse import AutoResponse

# local constants
from ptn.boozebot.constants import (
    get_primary_booze_discussions_channel, get_steve_says_channel, get_wine_carrier_channel,
    get_wine_cellar_deliveries_channel, ping_response_messages, server_council_role_ids, server_mod_role_id,
    server_sommelier_role_id
)

# local modules
from ptn.boozebot.database.database import pirate_steve_conn, pirate_steve_db, pirate_steve_db_lock
from ptn.boozebot.modules.ErrorHandler import TimeoutError, on_app_command_error
from ptn.boozebot.modules.helpers import check_command_channel, check_roles
from ptn.boozebot.modules.pagination import createPagination

"""
LISTENERS
on_message
- If pinged in #booze-cruise-chat respond

commands

"""


class AutoResponses(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.text_commands = ["ping", "exit", "update", "version", "sync"]

        pirate_steve_db.execute(
            """
            SELECT * FROM auto_responses
        """
        )
        self.auto_responses = [
            AutoResponse(response) for response in pirate_steve_db.fetchall()
        ]

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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.channel.id not in [
            get_primary_booze_discussions_channel(),
            get_wine_carrier_channel(),
            get_wine_cellar_deliveries_channel(),
        ]:
            return

        if message.is_system():
            return

        if message.author == self.bot.user:
            return

        for auto_response in self.auto_responses:
            if auto_response.matches(message):
                print(f"Auto response triggered: {auto_response.name} by {message.author} in {message.channel.name}")
                await message.channel.send(
                    auto_response.response,
                    reference=message,
                )
                return

        if not self.bot.user.mentioned_in(message):
            return

        if message.reference:
            return

        msg_split = message.content.split()

        if len(msg_split) >= 2 and msg_split[1].lower() in self.text_commands:
            return

        print(f"{message.author} mentioned PirateSteve.")

        await message.channel.send(
            random.choice(ping_response_messages).format(
                message_author_id=message.author.id
            ),
            reference=message,
        )

    @app_commands.command(
        name="booze_create_auto_response", description="Create a new auto response"
    )
    @app_commands.describe(
        name="Name of the auto response",
        trigger="Trigger phrase for the auto response",
        is_regex="Is the trigger a regex pattern?",
        response="Response message to send when the trigger is matched",
    )
    @check_roles(
        [*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()]
    )
    @check_command_channel(get_steve_says_channel())
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

        async with pirate_steve_db_lock:
            # Check if the name already exists
            pirate_steve_db.execute(
                "SELECT * FROM auto_responses WHERE name = ?", (name,)
            )
            if pirate_steve_db.fetchone():
                await interaction.edit_original_response(
                    content=f"An auto response with the name '{name}' already exists.",
                )
                return

            # Insert the new auto response
            pirate_steve_db.execute(
                "INSERT INTO auto_responses (name, trigger, is_regex, response) VALUES (?, ?, ?, ?)",
                (name, trigger, is_regex, response),
            )
            pirate_steve_conn.commit()

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

        await interaction.edit_original_response(
            content=f"Auto response '{name}' created successfully."
        )

    @app_commands.command(
        name="booze_delete_auto_response", description="Delete an auto response"
    )
    @app_commands.describe(name="Name of the auto response to delete")
    @check_roles(
        [*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()]
    )
    @check_command_channel(get_steve_says_channel())
    async def delete_auto_response(self, interaction: discord.Interaction, name: str):
        """
        Delete an auto response by name.

        :param interaction: The interaction object.
        :param name: The name of the auto response to delete.
        """

        await interaction.response.defer()

        async with pirate_steve_db_lock:
            # Check if the auto response exists
            pirate_steve_db.execute(
                "SELECT * FROM auto_responses WHERE name = ?", (name,)
            )
            if not pirate_steve_db.fetchone():
                await interaction.edit_original_response(
                    content=f"No auto response found with the name '{name}'."
                )
                return

            # Delete the auto response
            pirate_steve_db.execute(
                "DELETE FROM auto_responses WHERE name = ?", (name,)
            )
            pirate_steve_conn.commit()

        # Remove the auto response from the list
        self.auto_responses = [ar for ar in self.auto_responses if ar.name != name]

        await interaction.edit_original_response(
            content=f"Auto response '{name}' deleted successfully."
        )

    @app_commands.command(
        name="booze_list_auto_responses", description="List all auto responses"
    )
    @check_roles(
        [*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()]
    )
    @check_command_channel(get_steve_says_channel())
    async def list_auto_responses(self, interaction: discord.Interaction):
        """
        List all auto responses.

        :param interaction: The interaction object.
        """

        await interaction.response.defer()

        if not self.auto_responses:
            await interaction.edit_original_response(content="No auto responses found.")
            return

        auto_response_list = [ar.to_tuple() for ar in self.auto_responses]

        await createPagination(
            interaction,
            "Auto Responses",
            auto_response_list,
        )
