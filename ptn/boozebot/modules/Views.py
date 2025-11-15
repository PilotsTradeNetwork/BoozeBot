from loguru import logger

import discord.colour
from discord import ButtonStyle, Embed, Interaction, ui

from ptn.boozebot.constants import INTERACTION_CHECK_GIF

class ConfirmView(ui.View):
    def __init__(self, author: discord.Member):
        super().__init__()
        self.author = author
        self.value: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction):  # only allow original command user to interact with buttons
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
            description="Only the command author may use these interactions.",
            color=discord.colour.Colour.red()
        )
        embed.set_image(url=INTERACTION_CHECK_GIF)
        embed.set_footer(text="Seriously, are you 4? 🙄")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False
