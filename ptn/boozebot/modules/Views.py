import discord

class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value: bool | None = None


    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        print("Confirmed")
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`.
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        print("Cancelled")
        self.value = False
        self.stop()
