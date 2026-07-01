import asyncio
from google.adk.cli.runners import Runner
from google.adk.sessions import InMemorySessionService
from app.agent import root_agent

async def main():
    runner = Runner(
        agent=root_agent,
        session_service=InMemorySessionService()
    )
    
    print("RUNNING GRAPH...")
    async for event in runner.run_stream(
        input_data="Analyze this repository: https://github.com/facebook/react"
    ):
        print("EVENT:", event)
    
    print("DONE RUNNING!")

if __name__ == "__main__":
    asyncio.run(main())
