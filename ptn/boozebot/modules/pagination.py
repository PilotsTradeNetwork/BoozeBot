import asyncio

import discord
from ptn_utils.logger.logger import get_logger
from ptn.boozebot.constants import bot

logger = get_logger("boozebot.modules.pagination")


async def createPagination(
    interaction: discord.Interaction, title: str, content: list[tuple[str, str]], pageLength: int = 10
):
    logger.info(f"Creating pagination for {title} requested by {interaction.user.name}")

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
        logger.trace(f"Validating reaction: {react.emoji} from user: {user.name}")
        valid = user == interaction.user and str(react.emoji) in ["◀️", "▶️"]
        logger.trace(f"Reaction valid: {valid}")
        return valid

    def createPageEmbed():
        logger.trace(f"Creating embed for page {current_page} of {max_pages} for {title}")
        embed = discord.Embed(title=f"{len(content)} {title}. Page: #{current_page} of {max_pages}")

        count = (current_page - 1) * pageLength

        for entry in pages[current_page - 1]:
            count += 1
            embed.add_field(
                name=f"{count}: {entry[0]}",
                value=f"{entry[1]}",
                inline=False,
            )
        logger.trace(f"Embed for page {current_page} created.")
        return embed

    pages = [page for page in chunk(content)]
    max_pages = len(pages)
    current_page = 1

    # Send page 1 and and wait on a reaction
    await interaction.edit_original_response(content=None, embed=createPageEmbed())
    logger.info(f"Pagination for {title} initialized with {max_pages} pages by {interaction.user.name}.")

    message = await interaction.original_response()

    # From page 0 we can only go forwards
    await message.add_reaction("▶️")
    logger.trace("Added ▶️ reaction for pagination.")
    # 60 seconds time out gets raised by Asyncio
    while True:
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=60, check=validate_response)

            if str(reaction.emoji) == "▶️":
                if current_page == max_pages:
                    logger.trace(f"{interaction.user.name} requested to go forward a page but was on the last page.")
                    await message.remove_reaction(reaction, user)
                    continue

                logger.trace(f"{interaction.user.name} requested to go forward a page.")
                current_page += 1
                await message.edit(content=None, embed=createPageEmbed())
                logger.trace(f"Edited message to show page {current_page}.")

                if current_page == max_pages:
                    await message.clear_reaction("▶️")
                    logger.trace("Cleared ▶️ reaction from message.")

                await message.remove_reaction(reaction, user)
                await message.add_reaction("◀️")
                logger.trace("Added ◀️ reaction to message.")

            elif str(reaction.emoji) == "◀️":
                if current_page == 1:
                    logger.trace(f"{interaction.user.name} requested to go back a page but was on the first page.")
                    await message.remove_reaction(reaction, user)
                    continue

                logger.trace(f"{interaction.user.name} requested to go back a page.")
                current_page -= 1
                await message.edit(content=None, embed=createPageEmbed())
                logger.trace(f"Edited message to show page {current_page}.")

                if current_page == 1:
                    await message.clear_reaction("◀️")
                    logger.trace("Cleared ◀️ reaction from message.")

                await message.remove_reaction(reaction, user)
                await message.add_reaction("▶️")
                logger.trace("Added ▶️ reaction to message.")

            else:
                # It should be impossible to hit this part, but lets gate it just in case.
                logger.error(
                    f"HAL9000 error: {interaction.user.name} ended in a random state while trying to handle: {reaction.emoji} "
                    f"and on page: {current_page}."
                )
                # HAl-9000 error response.
                error_embed = discord.Embed(title=f"I'm sorry {interaction.user.name}, I'm afraid I can't do that.")
                await message.edit(content=None, embed=error_embed)
                await message.remove_reaction(reaction, user)

        except asyncio.TimeoutError:
            logger.info(f"Pagination for {title} requested by {interaction.user.name} timed out due to inactivity.")
            await interaction.edit_original_response(
                content=f"Closed the active {title} list request from: {interaction.user.name} due to no input in 60 seconds.",
                embed=None,
            )
            await message.clear_reactions()
            return
