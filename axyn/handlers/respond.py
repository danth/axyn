from __future__ import annotations
from axyn.channel import channel_members
from axyn.database import MessageRecord, MessageRevisionRecord
from axyn.filters import reason_not_to_respond, is_direct
from axyn.handlers import Handler
from axyn.privacy import can_send_in_channel
from opentelemetry.trace import get_current_span, get_tracer
from random import random, shuffle
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from typing import Optional, Literal


_tracer = get_tracer(__name__)


class RespondHandler(Handler):
    async def handle(self):
        """Respond to this message, if allowed."""

        with _tracer.start_as_current_span(
            "respond to message",
            attributes=self._attributes(),
        ) as span:
            reason = reason_not_to_respond(self.message)
            if reason:
                span.add_event(f"Not responding because {reason}")
                return

            if is_direct(self.client, self.message):
                # If the prompt was direct, then a response is guaranteed, and
                # the user is probably waiting for one. So it makes sense to
                # indicate that we are working on it.
                async with self._channel.typing():
                    response, distance = await self._get_response()
            else:
                # Otherwise, we may decide not to respond, so work silently.
                response, distance = await self._get_response()

            if response is None:
                return

            probability = self._get_probability(distance)

            if random() <= probability:
                span.add_event(
                    "Probability check succeeded",
                    attributes={"probability": probability},
                )

                await self._send_response(response)
            else:
                span.add_event(
                    "Probability check failed",
                    attributes={"probability": probability},
                )

    def _get_probability(self, distance: float) -> float:
        """Return the probability of sending a response."""

        with _tracer.start_as_current_span("get response probability") as span:
            if is_direct(self.client, self.message):
                probability = 1
            else:
                members = len(channel_members(self._channel)) - 1

                # https://www.desmos.com/calculator/jqyrqevoad
                probability = (2 - distance) / (2 * members * (distance + 1))

            span.set_attribute("probability", probability)

            return probability

    @_tracer.start_as_current_span("choose response")
    async def _get_response(self) -> tuple[Optional[str], float]:
        """Return a chosen response and its cosine distance."""

        async with self.client.database_manager.session() as session:
            responses = self.client.index_manager.get_responses_to_text(
                session,
                self.message.content,
            )

            group: list[tuple[MessageRevisionRecord, MessageRevisionRecord]] = []
            group_distance = float("inf")

            async for prompt, response, distance in responses:
                if group_distance > distance:
                    if text := await self._get_response_from_group(session, group):
                        return text, group_distance

                    group = []
                    group_distance = distance

                group.append((prompt, response))

            if text := await self._get_response_from_group(session, group):
                return text, group_distance

        get_current_span().add_event("Found no suitable responses")
        return None, float("inf")

    async def _get_response_from_group(
        self,
        session: AsyncSession,
        group: list[tuple[MessageRevisionRecord, MessageRevisionRecord]],
    ) -> Optional[str]:
        shuffle(group)

        for prompt_revision, response_revision in group:
            prompt_message = await session.get_one(
                MessageRecord,
                prompt_revision.message_id,
            )

            response_message = await session.get_one(
                MessageRecord,
                response_revision.message_id,
            )

            can_send = await can_send_in_channel(
                self.client,
                session,
                response_message,
                self._channel,
            )

            if not can_send:
                get_current_span().add_event(
                    "Rejected response due to privacy filter",
                    attributes={"revision.id": response_revision.revision_id},
                )
                continue

            get_current_span().add_event(
                "Selected response",
                attributes={"revision.id": response_revision.revision_id},
            )

            replacements: dict[int, int | Literal["everyone", "here"]] = {}
            replacements.setdefault(prompt_message.author_id, self.message.author.id)
            replacements.setdefault(response_message.author_id, self.client.axyn().id)
            replacements.setdefault(self.client.axyn().id, "everyone")

            text = response_revision.replace_pings(replacements)

            return text

    @_tracer.start_as_current_span("send response")
    async def _send_response(self, response: str):
        await self._channel.send(
            response,
            reference=self.message,
            mention_author=True,
        )

