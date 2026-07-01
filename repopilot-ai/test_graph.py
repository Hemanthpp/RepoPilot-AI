import asyncio
from app.agent import root_agent

async def main():
    async for event in root_agent.run_stream(
        input_data="Analyze this repository: https://github.com/facebook/react"
    ):
        print(f"Event: {event}")

if __name__ == "__main__":
    asyncio.run(main())
