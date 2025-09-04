import discord
from discord import app_commands
from ptn.boozebot.constants import (
    server_connoisseur_role_id, server_council_role_ids, server_mod_role_id, server_sommelier_role_id,
    server_wine_carrier_role_id
)
from ptn.boozebot.modules.ErrorHandler import CommandRoleError


class DeferredCommandGroup:
    def __init__(self, name, description, allowed_role_ids=None):
        self.name = name
        self.description = description
        self.allowed_role_ids = allowed_role_ids

        self._stashed_commands = []

    # Decorator to stash commands
    def command(self, *args, **kwargs):
        def decorator(func):
            self._stashed_commands.append((func, args, kwargs))
            return func

        return decorator

    # Method to register stashed commands to a command group
    def register_commands(self, cogs):
        class Group(app_commands.Group):
            def __init__(self, name, description, allowed_role_ids):
                super().__init__(name=name, description=description)
                self.allowed_role_ids = allowed_role_ids

            async def interaction_check(self, interaction: discord.Interaction) -> bool:

                if not self.allowed_role_ids:
                    return True

                if any(role.id in self.allowed_role_ids for role in interaction.user.roles):
                    return True

                raise CommandRoleError(
                    permitted_roles=self.allowed_role_ids,
                    formatted_role_list="<@&"
                    + ">, <@&".join([str(role_id) for role_id in self.allowed_role_ids])
                    + ">",
                )

        command_group = Group(self.name, self.description, self.allowed_role_ids)
        
        print(len(self._stashed_commands))
        
        self._stashed_commands = self._stashed_commands[:25]

        for func, args, kwargs in self._stashed_commands:
            cog_name = func.__qualname__.split(".")[-2]
            for cog in cogs.values():
                if cog.__class__.__name__ == cog_name:
                    func = getattr(cog, func.__name__, None)
                    break

            if func is None:
                raise ValueError(f"Function {func.__name__} not found in any cog.")

            command_group.add_command(app_commands.Command(callback=func, *args, **kwargs))

        return command_group


somm_command_group = DeferredCommandGroup(
    name="booze_admin",
    description="Booze Cruise Admin Commands",
    allowed_role_ids=[*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()],
)

conn_command_group = DeferredCommandGroup(
    name="wine_staff",
    description="Connoisseur Commands",
    allowed_role_ids=[
        *server_council_role_ids(),
        server_sommelier_role_id(),
        server_mod_role_id(),
        server_connoisseur_role_id(),
    ],
)

wine_carrier_command_group = DeferredCommandGroup(
    name="wine_carrier",
    description="Wine Carrier Commands",
    allowed_role_ids=[
        *server_council_role_ids(),
        server_sommelier_role_id(),
        server_mod_role_id(),
        server_connoisseur_role_id(),
        server_wine_carrier_role_id(),
    ],
)

everyone_command_group = DeferredCommandGroup(name="booze", description="Booze Cruise Commands")
