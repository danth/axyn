from __future__ import annotations
from asyncio import create_task, sleep, timeout
from axyn.channel import channel_members
from axyn.database import MessageRecord, MessageRevisionRecord
from axyn.filters import reason_not_to_reply, is_direct
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


class ReplyHandler(Handler):
    async def handle(self):
        """Respond to this message, if allowed."""

        with _tracer.start_as_current_span(
            "reply to message",
            attributes=self._attributes(),
        ) as span:
            reason = reason_not_to_reply(self.message)
            if reason:
                span.add_event(f"Not replying because {reason}")
                return

            reply, distance = await self._get_reply()

            if reply is None:
                return

            probability = self._get_probability(distance)

            if random() <= probability:
                span.add_event(
                    "Probability check succeeded",
                    attributes={"probability": probability},
                )

                self._schedule_reply(reply)
            else:
                span.add_event(
                    "Probability check failed",
                    attributes={"probability": probability},
                )

    def _get_probability(self, distance: float) -> float:
        """Return the probability of sending a reply."""

        with _tracer.start_as_current_span("get reply probability") as span:
            if is_direct(self.client, self.message):
                probability = 1
            else:
                members = len(channel_members(self._channel)) - 1

                # https://www.desmos.com/calculator/jqyrqevoad
                probability = (2 - distance) / (2 * members * (distance + 1))

            span.set_attribute("probability", probability)

            return probability

    @_tracer.start_as_current_span("choose reply")
    async def _get_reply(self) -> tuple[Optional[str], float]:
        """Return a chosen reply and its cosine distance."""

        async with self.client.database_manager.session() as session:
            responses = self.client.index_manager.get_responses_to_text(
                session,
                self.message.content,
            )

            group: list[tuple[MessageRevisionRecord, MessageRevisionRecord]] = []
            group_distance = float("inf")

            async for prompt, response, distance in responses:
                if group_distance > distance:
                    if text := await self._get_reply_from_group(session, group):
                        return text, group_distance

                    group = []
                    group_distance = distance

                group.append((prompt, response))

            if text := await self._get_reply_from_group(session, group):
                return text, group_distance

        get_current_span().add_event("Found no suitable responses")
        return None, float("inf")

    async def _get_reply_from_group(
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

    def _schedule_reply(self, reply: str):
        """
        Schedule the given reply to be sent soon.

        The reply will normally be sent after a few seconds. If during that
        time, the prompt author starts typing another message, the delay will
        be extended until they stop.

        If during the delay, another reply is scheduled with the same channel
        and prompt author, then this reply will be discarded. This particular
        key was chosen because:

        - Keeping channels separate means that high traffic elsewhere does not
          reduce the number of replies seen.
        - Keeping users separate mimics a human replying to a few messages they
          found interesting, rather than only the most recent message, which
          makes the fact that replies can be cancelled less obvious.
        - Cancelling replies to the same user avoids amplifying spam, because
          if they message too fast, then we will discard most of our replies
          before they are sent.
        """

        key = (self.message.author.id, self.message.channel.id)

        if task := self.client.reply_tasks.get(key):
            if not task.done():
                get_current_span().add_event("Cancelling existing scheduled reply")
                task.cancel()

        task = create_task(self._do_reply(reply))
        self.client.reply_tasks[key] = task

    async def _do_reply(self, reply: str):
        """
        Wait for a short length of time, then send the given reply.

        If during the delay, the prompt author starts typing another message,
        the delay will be extended until they stop. If we are waiting for an
        excessive length of time then the reply will be discarded.
        """

        async with self._channel.typing():
            try:
                async with timeout(30):
                    await self._delay_reply()
            except TimeoutError:
                get_current_span().add_event("Cancelling scheduled reply because the user is typing")
                return

        await self._send_reply(reply)

    @_tracer.start_as_current_span("delay reply")
    async def _delay_reply(self):
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

    @_tracer.start_as_current_span("send reply")
    async def _send_reply(self, reply: str):
        await self._channel.send(
            reply,
            reference=self.message,
            mention_author=True,
        )

