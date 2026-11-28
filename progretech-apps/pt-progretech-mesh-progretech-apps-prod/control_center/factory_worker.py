"""Run in a separately installed factory environment, never Mesh's web interpreter."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    os.environ.setdefault('CREWAI_TELEMETRY_DISABLED', 'true')
    os.environ.setdefault('OTEL_SDK_DISABLED', 'true')
    body = json.load(sys.stdin)
    model = os.environ['MESH_FACTORY_MODEL']
    key = os.environ.get('MESH_FACTORY_API_KEY') or 'local'
    base = os.environ.get('MESH_FACTORY_BASE_URL') or None
    if sys.argv[1] == 'crewai':
        from crewai import Agent, Crew, LLM, Process, Task
        if os.environ.get('MESH_FACTORY_GGUF'):
            from offline.local_llm import LocalGGUF
            llm = LocalGGUF(os.environ['MESH_FACTORY_GGUF'])
        else:
            llm = LLM(model=model, api_key=key, base_url=base)
        if body.get('office'):
            from control_center.office_crew import kickoff
            print(kickoff(body, llm))
            return
        planner = Agent(role='Factory planner', goal='Produce a concrete bounded plan for the supplied task',
                        backstory='You clarify acceptance criteria and implementation steps.', llm=llm, allow_delegation=False, max_iter=8)
        reviewer = Agent(role='Factory reviewer', goal='Review the plan and provide an actionable final result',
                         backstory='You check risks, feasibility, and validation requirements.', llm=llm, allow_delegation=False, max_iter=8)
        plan = Task(description=body['task'], expected_output='A concrete plan with acceptance criteria', agent=planner)
        review = Task(description='Review and refine the prior plan for the owner task', expected_output='Reviewed implementation plan and validation steps', agent=reviewer, context=[plan])
        print(Crew(agents=[planner, reviewer], tasks=[plan, review], process=Process.sequential, verbose=False).kickoff())
    elif sys.argv[1] == 'openhands':
        from openhands.sdk import LLM, Agent, Conversation, Tool
        from openhands.tools.file_editor import FileEditorTool
        from openhands.tools.task_tracker import TaskTrackerTool
        from openhands.tools.terminal import TerminalTool
        llm = LLM(model=model, api_key=key, base_url=base)
        agent = Agent(llm=llm, tools=[Tool(name=TerminalTool.name), Tool(name=FileEditorTool.name), Tool(name=TaskTrackerTool.name)])
        conversation = Conversation(agent=agent, workspace=body['workspace'])
        conversation.send_message(body['task']); conversation.run()
        print('OpenHands task finished; review the configured workspace changes.')
    else:
        raise ValueError('unknown_factory_provider')


if __name__ == '__main__': main()
