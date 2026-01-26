import re
from typing import Any, override

import discord.colour
from discord import ButtonStyle, Embed, Interaction, ui
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.constants import INTERACTION_CHECK_GIF, bot

logger = get_logger("boozebot.modules.views")


class ConfirmView(ui.View):
    def __init__(self, author: discord.Member):
        super().__init__()
        self.author = author
        self.value: bool | None = None

    async def interaction_check(
        self, interaction: discord.Interaction
    ):  # only allow original command user to interact with buttons
        return await interaction_check_owner(self, interaction)

    @ui.button(label="Confirm", style=ButtonStyle.green)
    async def confirm_callback(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        logger.info(f"Confirm view for {self.author} ({self.author.id}) confirmed")
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`.
    @ui.button(label="Cancel", style=ButtonStyle.grey)
    async def cancel_callback(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        logger.info(f"Confirm view for {self.author} ({self.author.id}) cancelled")
        self.value = False
        self.stop()


async def interaction_check_owner(view: ui.View, interaction: Interaction):
    """only allow original command user to interact with buttons"""

    logger.debug(f"Checking interaction user ID {interaction.user.id} against view author ID {view.author.id}")

    if interaction.user.id == view.author.id:
        logger.debug("Interaction user is the command author. Allowing interaction.")
        return True
    else:
        logger.debug("Interaction user is NOT the command author. Denying interaction.")
        embed = Embed(
            description="Only the command author may use these interactions.", color=discord.colour.Colour.red()
        )
        embed.set_image(url=INTERACTION_CHECK_GIF)
        embed.set_footer(text="Seriously, are you 4? 🙄")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False


class DynamicButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"steve:user:(?P<user_id>[0-9]+):message:(?P<message_id>[0-9]+):action:(?P<action>[a-z]+)",
):
    def __init__(self, label, action: str, user_id: int, message_id: int) -> None:
        logger.debug(
            f"Creating DynamicButton: label={label}, action={action}, user_id={user_id}, message_id={message_id}"
        )
        super().__init__(
            discord.ui.Button(
                label=label,
                style=ButtonStyle.green,
                custom_id=f"steve:user:{user_id}:message:{message_id}:action:{action}",
            )
        )
        self.action: str = action
        self.user_id: int = user_id
        self.message_id: int = message_id
        logger.debug("DynamicButton created successfully")

    @override
    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        logger.debug(f"Parsing DynamicButton from custom_id: {item.custom_id}")
        action = str(match["action"])
        user_id = int(match["user_id"])
        message_id = int(match["message_id"])
        label = item.label
        return cls(label, action, user_id, message_id)

    async def callback(self, interaction: discord.Interaction) -> None:
        logger.info(
            f"DynamicButton clicked: action={self.action}, user_id={self.user_id}, message_id={self.message_id} by {interaction.user} ({interaction.user.id})"
        )

        event_name = f"dynamic_button_{self.action}"

        bot.dispatch(event_name, interaction, self)
