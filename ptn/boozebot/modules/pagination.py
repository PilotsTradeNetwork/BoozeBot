import asyncio

import discord
from ptn.boozebot.constants import bot


async def createPagination(
    interaction: discord.Interaction, title: str, content: list[tuple[str, str]], pageLength: int = 10
):
    print("Creating a pagination.")

    def chunk(chunk_list, max_size=10):
        """
        Take an input list, and an expected max_size.

        :returns: A chunked list that is yielded back to the caller
        :rtype: iterator
        """
        for i in range(0, len(chunk_list), max_size):
            yield chunk_list[i : i + max_size]

    def validate_response(react, user):
        """
        Validates the user response
        """
        return user == interaction.user and str(react.emoji) in ["◀️", "▶️"]

    def createPageEmbed():
        embed = discord.Embed(title=f"{len(content)} {title}. Page: #{current_page} of {max_pages}")

        count = (current_page - 1) * pageLength

        for entry in pages[current_page - 1]:
            count += 1
            embed.add_field(
                name=f"{count}: {entry[0]}",
                value=f"{entry[1]}",
                inline=False,
            )
        return embed

    pages = [page for page in chunk(content)]
    max_pages = len(pages)
    current_page = 1

    # Send page 1 and and wait on a reaction
    await interaction.edit_original_response(content=None, embed=createPageEmbed())

    message = await interaction.original_response()

    # From page 0 we can only go forwards
    await message.add_reaction("▶️")
    # 60 seconds time out gets raised by Asyncio
    while True:
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=60, check=validate_response)

            if str(reaction.emoji) == "▶️":
                if current_page == max_pages:
                    print(f"{interaction.user.name} requested to go forward a page but was on the last page.")
                    await message.remove_reaction(reaction, user)
                    continue

                print(f"{interaction.user.name} requested to go forward a page.")
                current_page += 1

                await message.edit(content=None, embed=createPageEmbed())

                if current_page == max_pages:
                    await message.clear_reaction("▶️")

                await message.remove_reaction(reaction, user)
                await message.add_reaction("◀️")

            elif str(reaction.emoji) == "◀️":
                if current_page == 1:
                    print(f"{interaction.user.name} requested to go back a page but was on the first page.")
                    await message.remove_reaction(reaction, user)
                    continue

                print(f"{interaction.user.name} requested to go back a page.")
                current_page -= 1

                await message.edit(content=None, embed=createPageEmbed())

                if current_page == 1:
                    await message.clear_reaction("◀️")

                await message.remove_reaction(reaction, user)
                await message.add_reaction("▶️")

            else:
                # It should be impossible to hit this part, but lets gate it just in case.
                print(
                    f"HAL9000 error: {interaction.user.name} ended in a random state while trying to handle: {reaction.emoji} "
                    f"and on page: {current_page}."
                )
                # HAl-9000 error response.
                error_embed = discord.Embed(title=f"I'm sorry {interaction.user.name}, I'm afraid I can't do that.")
                await message.edit(content=None, embed=error_embed)
                await message.remove_reaction(reaction, user)

        except asyncio.TimeoutError:
            print(f"Timeout hit during {title} list request by: {interaction.user.name}")
            await interaction.edit_original_response(
                content=f"Closed the active {title} list request from: {interaction.user.name} due to no input in 60 seconds.",
                embed=None,
            )
            return await message.clear_reactions()
