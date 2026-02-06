from types import CoroutineType
from typing import Callable, Any, override

from discord import Interaction, ButtonStyle, Message
from discord.ui import LayoutView, Container, Section, Button, ActionRow, TextDisplay
from ptn_utils.logger.logger import get_logger

logger = get_logger("boozebot.modules.pagination")


class PaginationView(LayoutView):
    message: Message | None = None

    def __init__(
        self,
        title: str,
        content: list[tuple[str, str]],
        ephemeral: bool = False,
        buttons_text: str | None = None,
        buttons_callback: Callable[[Interaction, str, int], CoroutineType[Any, Any, None]] | None = None,
        page_length: int = 10,
    ):
        self.title: str = title
        self.content: list[tuple[str, str]] = content
        self.ephemeral: bool = ephemeral
        self.buttons_text: str | None = buttons_text
        self.buttons_callback: Callable[[Interaction, str, int], CoroutineType[Any, Any, None]] | None = (
            buttons_callback
        )

        self.chunked_content: list[list[tuple[str, str]]] = [
            content[i : i + page_length] for i in range(0, len(content), page_length)
        ]
        self.page_length: int = page_length
        self.current_page: int = 1
        self.max_pages: int = len(self.chunked_content)

        super().__init__(timeout=60)

        self._create_page_embed()

    async def refresh_page(self):
        self._create_page_embed()
        if self.message:
            await self.message.edit(view=self)

    def _create_page_embed(self, disabled: bool = False):
        logger.trace(f"Creating embed for page {self.current_page} of {self.max_pages} for {self.title}")

        self.clear_items()

        container = Container()

        header_section = TextDisplay(
            f"**{len(self.content)} {self.title}. Page: #{self.current_page} of {self.max_pages}**"
        )

        container.add_item(header_section)

        for index, text in enumerate(self.chunked_content[self.current_page - 1]):
            title, info = text
            button = None
            if self.buttons_text and self.buttons_callback:
                button_text = self.buttons_text.format(title=title, info=info)
                button = Button(
                    label=button_text,
                    style=ButtonStyle.primary,
                    custom_id=f"{self.title} {index + (self.current_page - 1) * self.page_length}",
                    disabled=disabled,
                )
                button.callback = self._create_button_callback(
                    title, index + (self.current_page - 1) * self.page_length
                )

                section = Section(accessory=button if button else None)

                section.add_item(f"**{title}**\n{info}")

                container.add_item(section)

            else:
                text_display = TextDisplay(f"**{title}**\n{info}")
                container.add_item(text_display)

        previous_button = Button(
            label="Previous",
            style=ButtonStyle.secondary,
            custom_id="previous",
            disabled=self.current_page == 1 or disabled,
        )
        previous_button.callback = self._handle_pagination_control
        next_button = Button(
            label="Next",
            style=ButtonStyle.secondary,
            custom_id="next",
            disabled=self.current_page == len(self.chunked_content) or disabled,
        )
        next_button.callback = self._handle_pagination_control
        close_button = Button(label="Close", style=ButtonStyle.danger, custom_id="close", disabled=disabled)
        close_button.callback = self._end_pagination

        buttons = (previous_button, next_button, close_button)

        if self.ephemeral:
            broadcast_button = Button(
                label="Broadcast", style=ButtonStyle.success, custom_id="broadcast", disabled=disabled
            )
            broadcast_button.callback = self._broadcast_message
            buttons += (broadcast_button,)

        pagination_buttons_row = ActionRow(*buttons)

        container.add_item(pagination_buttons_row)

        self.add_item(container)

    def _create_button_callback(self, title: str, index: int):
        async def callback(interaction: Interaction):
            logger.info(f"Button for {title}: {index} clicked by {interaction.user.name}")
            if self.buttons_callback:
                await self.buttons_callback(interaction, title, index)
            else:
                logger.warning(f"No callback defined")

        return callback

    async def _handle_pagination_control(self, interaction: Interaction):
        logger.info(f"Pagination button clicked by {interaction.user.name} on page {self.current_page}")

        custom_id = interaction.data.get("custom_id")

        if not custom_id:
            logger.error("No custom_id found in interaction data")
            return

        if custom_id == "previous" and self.current_page > 1:
            self.current_page -= 1

        elif custom_id == "next" and self.current_page < len(self.chunked_content):
            self.current_page += 1

        self._create_page_embed()
        await interaction.response.edit_message(view=self)

    async def _end_pagination(self, interaction: Interaction):
        logger.info(f"Close button clicked by {interaction.user.name}. Ending pagination.")

        view = LayoutView()
        view.add_item(TextDisplay(f"Closed the active {self.title} list request from: {interaction.user.mention}."))

        await interaction.response.edit_message(view=view)
        self.stop()

    @override
    async def on_timeout(self) -> None:
        logger.info(f"Pagination for {self.title} timed out due to inactivity.")

        view = LayoutView()
        view.add_item(
            TextDisplay(
                f"Closed the active {self.title} list request from: {self.message.interaction_metadata.user.mention} due to no input in 60 seconds."
            )
        )

        await self.message.edit(view=view)
        self.stop()

    @override
    async def interaction_check(self, interaction: Interaction, /) -> bool:
        if interaction.user != self.message.interaction_metadata.user:
            self.message.interaction_metadata.user

            logger.warning(f"Only {self.message.interaction.user.name} can interact with this pagination.")
            await interaction.response.send_message("You are not the owner of this pagination", ephemeral=True)
            return False
        return True

    async def _broadcast_message(self, interaction: Interaction):
        logger.info(f"Broadcast button clicked by {interaction.user.name}. Broadcasting message.")

        broadcast_view = self
        broadcast_view.ephemeral = False
        broadcast_view._create_page_embed(disabled=True)
        broadcast_view.stop()

        await interaction.response.send_message(view=broadcast_view, ephemeral=False)

        message = await interaction.original_response()

        view = LayoutView()
        view.add_item(TextDisplay(f"Broadcasted the {self.title} list request from: {interaction.user.mention}."))
        await self.message.edit(view=view)

        broadcast_view.message = message
