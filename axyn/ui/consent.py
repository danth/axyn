from __future__ import annotations
from axyn.database import ConsentResponse, InteractionRecord
from discord import SelectOption
from discord.ui import Select, View
from typing import TYPE_CHECKING, cast


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from discord import Interaction


class ConsentSelect(Select[View]):
    def __init__(self):
        super().__init__(
            custom_id="consent",
            options=[
                SelectOption(
                    label="Yes, share with anyone.",
                    value=ConsentResponse.WITHOUT_PRIVACY.name,
                    description=(
                        "Quotes can be used anywhere, including other servers. "
                        "Be careful not to share private information."
                    ),
                ),
                SelectOption(
                    label="Yes, share in the same community.",
                    value=ConsentResponse.WITH_PRIVACY.name,
                    description=(
                        "Quotes can be used if everyone in the channel has "
                        "access to the original message."
                    ),
                ),
                SelectOption(
                    label="No, don't store my messages.",
                    value=ConsentResponse.NO.name,
                    description=(
                        "Axyn will still respond to you, but won't remember "
                        "things you've said."
                    ),
                ),
            ],
            placeholder="Choose a setting",
        )

    @property
    def selection(self) -> ConsentResponse:
        return ConsentResponse[self.values[0]]

    async def callback(self, interaction: Interaction):
        client = cast("AxynClient", interaction.client)

        async with client.database_manager.session() as session:
            await InteractionRecord.insert(session, interaction)

            interaction_record = await session.get_one(
                InteractionRecord,
                interaction.id,
            )

            await client.consent_manager.set_response(
                session,
                interaction_record,
                self.selection,
            )

            await session.commit()

        await interaction.response.send_message(
            "Setting changed.",
            ephemeral=True,
        )


class ConsentMenu(View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(ConsentSelect())

