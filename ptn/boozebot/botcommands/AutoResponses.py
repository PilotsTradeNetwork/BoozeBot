# libraries
import random
import re

# discord.py
import discord
from discord import app_commands
from discord.ext import commands
from ptn.boozebot.classes.AutoResponse import AutoResponse
# local constants
from ptn.boozebot.constants import (
    get_primary_booze_discussions_channel, get_steve_says_channel, get_wine_carrier_channel,
    get_wine_cellar_deliveries_channel, ping_response_messages, server_council_role_ids, server_mod_role_id,
    server_sommelier_role_id
)
# local modules
from ptn.boozebot.database.database import pirate_steve_conn, pirate_steve_db, pirate_steve_db_lock
from ptn.boozebot.modules.ErrorHandler import on_app_command_error
from ptn.boozebot.modules.helpers import check_command_channel, check_roles

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
        self.auto_responses = [AutoResponse(row) for row in pirate_steve_db.fetchall()]

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
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
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

        if is_regex:
            try:
                re.compile(trigger)
            except re.error as e:
                await interaction.edit_original_response(content=f"Invalid regex pattern: {trigger}. Error: {e}")
                return

        async with pirate_steve_db_lock:
            # Check if the name already exists
            pirate_steve_db.execute("SELECT * FROM auto_responses WHERE name = ?", (name,))
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

        await interaction.edit_original_response(content=f"Auto response '{name}' created successfully.")

    @app_commands.command(name="booze_delete_auto_response", description="Delete an auto response")
    @app_commands.describe(name="Name of the auto response to delete")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
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
            pirate_steve_db.execute("SELECT * FROM auto_responses WHERE name = ?", (name,))
            if not pirate_steve_db.fetchone():
                await interaction.edit_original_response(content=f"No auto response found with the name '{name}'.")
                return

            # Delete the auto response
            pirate_steve_db.execute("DELETE FROM auto_responses WHERE name = ?", (name,))
            pirate_steve_conn.commit()

        # Remove the auto response from the list
        self.auto_responses = [ar for ar in self.auto_responses if ar.name != name]

        await interaction.edit_original_response(content=f"Auto response '{name}' deleted successfully.")

    @app_commands.command(name="booze_list_auto_responses", description="List all auto responses")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
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

        view = ListAutoResponseView(self.auto_responses, self)
        embed = view.create_embed()

        message = await interaction.edit_original_response(embed=embed, view=view)

        # Used to allow the message to be edited on timeout
        view.message = message


class ListAutoResponseView(discord.ui.View):
    """
    View for displaying paginated list of auto responses with edit buttons.
    """

    def __init__(self, auto_responses: list[AutoResponse], cog: AutoResponses):
        super().__init__(timeout=180)
        self.auto_responses = auto_responses.copy()
        self.cog = cog
        self.current_page = 0
        self.page_size = 5
        self.total_pages = (len(auto_responses) - 1) // self.page_size + 1
        self.update_buttons()

    async def on_timeout(self):
        """
        Handle view timeout by disabling all buttons.
        """
        for item in self.children:
            item.disabled = True

        embed = discord.Embed(title="Auto Responses", description="This menu has expired.")

        try:
            await self.message.edit(embed=embed, view=None)
        except discord.DiscordException:
            print("Failed to edit auto response list on timeout.")

    def create_embed(self) -> discord.Embed:
        """
        Create an embed displaying the current page of auto responses.
        """
        embed = discord.Embed(
            title="Auto Responses",
            color=discord.Color.blue(),
            description=f"Page {self.current_page + 1}/{self.total_pages}",
        )

        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.auto_responses))

        for i in range(start_idx, end_idx):
            auto_response = self.auto_responses[i]
            trigger_display = (
                f"Regex: `{auto_response.trigger}`" if auto_response.is_regex else f"`{auto_response.trigger}`"
            )
            embed.add_field(
                name=f"**{auto_response.name}**",
                value=f"**Trigger:** {trigger_display}\n**Response:** {auto_response.response[:100]}{'...' if len(auto_response.response) > 100 else ''}",
                inline=False,
            )

        return embed

    def update_buttons(self):
        """
        Update view buttons based on current page and available auto responses.
        """
        self.clear_items()

        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.auto_responses))

        for i in range(start_idx, end_idx):
            auto_response = self.auto_responses[i]
            button = discord.ui.Button(
                label=f"Edit {auto_response.name}", style=discord.ButtonStyle.secondary, custom_id=f"edit_{i}"
            )
            button.callback = self.create_edit_callback(i)
            self.add_item(button)

        if self.total_pages > 1:
            previous_button = discord.ui.Button(
                label="Previous", style=discord.ButtonStyle.primary, disabled=self.current_page == 0
            )
            previous_button.callback = self.previous_page
            self.add_item(previous_button)

            next_button = discord.ui.Button(
                label="Next", style=discord.ButtonStyle.primary, disabled=self.current_page >= self.total_pages - 1
            )
            next_button.callback = self.next_page
            self.add_item(next_button)

    def create_edit_callback(self, index: int):
        """
        Create callback function for edit buttons.
        """

        async def edit_callback(interaction: discord.Interaction):
            auto_response = self.auto_responses[index]
            modal = EditAutoResponseModal(auto_response, self)
            await interaction.response.send_modal(modal)

        return edit_callback

    async def previous_page(self, interaction: discord.Interaction):
        """
        Navigate to previous page of auto responses.
        """
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    async def next_page(self, interaction: discord.Interaction):
        """
        Navigate to next page of auto responses.
        """
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    async def refresh_view(self):
        """
        Refetch the auto responses from the database and update the view, also update the main auto_responses list to match the db for any edits.
        """
        pirate_steve_db.execute("SELECT * FROM auto_responses")
        self.auto_responses = [AutoResponse(row) for row in pirate_steve_db.fetchall()]
        self.cog.auto_responses = self.auto_responses
        self.total_pages = (len(self.auto_responses) - 1) // self.page_size + 1 if self.auto_responses else 1

        if self.current_page >= self.total_pages:
            self.current_page = max(0, self.total_pages - 1)

        self.update_buttons()


class EditAutoResponseModal(discord.ui.Modal):
    """
    Modal for editing auto response trigger and response text.
    """

    def __init__(self, auto_response: AutoResponse, view: ListAutoResponseView):
        super().__init__(title=f"Edit Auto Response: {auto_response.name}")
        self.auto_response = auto_response
        self.view = view

        self.trigger_input = discord.ui.TextInput(label="Trigger", default=auto_response.trigger, max_length=500)
        self.add_item(self.trigger_input)

        self.response_input = discord.ui.TextInput(
            label="Response", default=auto_response.response, style=discord.TextStyle.paragraph, max_length=2000
        )
        self.add_item(self.response_input)

    async def on_submit(self, interaction: discord.Interaction):
        """
        Handle modal submission and update auto response in database.
        """
        await interaction.response.defer()

        new_trigger = self.trigger_input.value.strip()
        new_response = self.response_input.value.strip()

        if not new_trigger:
            await interaction.followup.send("Trigger cannot be empty.")
            return

        if not new_response:
            await interaction.followup.send("Response cannot be empty.")
            return

        if self.auto_response.is_regex:
            try:
                re.compile(new_trigger)
            except re.error as e:
                await interaction.followup.send(f"Invalid regex pattern: {new_trigger}. Error: {e}")
                return

        async with pirate_steve_db_lock:
            pirate_steve_db.execute(
                "UPDATE auto_responses SET trigger = ?, response = ? WHERE name = ?",
                (new_trigger, new_response, self.auto_response.name),
            )
            pirate_steve_conn.commit()

        await self.view.refresh_view()
        embed = self.view.create_embed()
        await interaction.edit_original_response(embed=embed, view=self.view)
        await interaction.followup.send(f"Auto response '{self.auto_response.name}' updated successfully.")
