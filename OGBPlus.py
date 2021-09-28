import hikari
import lightbulb
import typing
from lightbulb import help as help_


class OGBotPlus(lightbulb.Bot):
    def __init__(self,
                 *,
                 prefix=None,
                 slash_commands_only: bool = False,
                 **kwargs):
        super().init(self, **kwargs)
