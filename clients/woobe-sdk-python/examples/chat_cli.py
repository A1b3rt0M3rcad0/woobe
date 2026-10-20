import asyncio
import os

from woobe import Woobe


async def main() -> None:
    key = os.environ["WOOBE_RUNTIME_KEY"]

    async with Woobe() as woobe:
        agent = woobe.connect.agent(
            alias="support",
            key=key,
        )

        session_id: str | None = None

        print("Woobe Chat")
        print("Digite 'exit' para sair.\n")

        while True:
            message = input("You: ").strip()
            if not message:
                continue
            if message.lower() in {"exit", "quit"}:
                return

            chat = agent.chat(
                input=message,
                session_id=session_id,
            )

            print("Agent: ", end="", flush=True)

            async for event in chat.events():
                session_id = event.session_id

                # Current Woobe Agent streams expose public output as token events.
                if event.type == "token":
                    content = event.payload.get("content")
                    if isinstance(content, str):
                        print(content, end="", flush=True)

                elif event.type in {"done", "cancelled", "error"}:
                    print()

            print()


if __name__ == "__main__":
    asyncio.run(main())
