from __future__ import annotations
from asyncio import create_task, sleep, timeout
from axyn.channel import channel_members
from axyn.database import MessageRecord, MessageRevisionRecord
from axyn.filters import reason_not_to_respond, is_direct
from axyn.handlers import Handler
from axyn.privacy import can_send_in_channel
from datetime import datetime, timedelta, timezone
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

            response, distance = await self._get_response()

            if response is None:
                return

            probability = self._get_probability(distance)

            if random() <= probability:
                span.add_event(
                    "Probability check succeeded",
                    attributes={"probability": probability},
                )

                self._schedule_response(response)
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

    def _schedule_response(self, response: str):
        """
        Schedule the given response to be sent soon.

        The response will normally be sent after a few seconds. If during that
        time, the prompt author starts typing another message, the delay will
        be extended until they stop.

        If during the delay, another response is scheduled with the same
        channel and prompt author, then this response will be discarded. This
        particular key was chosen because:

        - Keeping channels separate means that high traffic elsewhere does not
          reduce the number of responses seen.
        - Keeping users separate mimics a human responding to a few messages
          they found interesting, rather than only the most recent message,
          which makes the fact that responses can be cancelled less obvious.
        - Cancelling responses to the same user avoids amplifying spam, because
          if they message too fast, then we will discard most of our responses
          before they are sent.
        """

        key = (self.message.author.id, self.message.channel.id)

        if task := self.client.response_tasks.get(key):
            if not task.done():
                get_current_span().add_event("Cancelling existing scheduled response")
                task.cancel()

        task = create_task(self._do_response(response))
        self.client.response_tasks[key] = task

    async def _do_response(self, response: str):
        """
        Wait for a short length of time, then send the given response.

        If during the delay, the prompt author starts typing another message,
        the delay will be extended until they stop. If we are waiting for an
        excessive length of time then the response will be discarded.
        """

        async with self._channel.typing():
            try:
                async with timeout(30):
                    await self._delay_response()
            except TimeoutError:
                get_current_span().add_event("Cancelling scheduled response because the user is typing")
                return

        await self._send_response(response)

    @_tracer.start_as_current_span("delay response")
    async def _delay_response(self):
        """
        Wait for a short length of time.

        If during the delay, the prompt author starts typing another message,
        the delay will be extended until they stop.
        """

        delay = 2

        while delay > 0:
            await sleep(delay)

            try:
                last_typing = self.client.last_typing[self.message.author.id]
            except KeyError:
                break

            typing_until = last_typing + timedelta(seconds=10)
            delay = typing_until - datetime.now(timezone.utc)
            delay = delay.total_seconds()

    @_tracer.start_as_current_span("send response")
    async def _send_response(self, response: str):
        await self._channel.send(
            response,
            reference=self.message,
            mention_author=True,
        )

