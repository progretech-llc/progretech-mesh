"""Real hierarchical CrewAI mission execution with Munder Difflin coordination."""
import sys
from pathlib import Path

# This worker may execute under a separately installed Python environment.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def kickoff(body, llm):
    from crewai import Agent, Crew, Process, Task
    from crewai.events import BaseEventListener, AgentExecutionStartedEvent, AgentExecutionCompletedEvent, AgentExecutionErrorEvent
    from crewai.tools import BaseTool
    from control_center.office import engine
    office = body['office']
    home, role = body['home'], body['role']
    mission = office['task']
    roster = office['agents']
    if len(roster) < 2:
        raise ValueError('Hire at least one worker before starting a mission.')
    director = next((a['id'] for a in roster if a.get('isDirector')), 'orchestrator')
    by_role = {a['role']: a['id'] for a in roster}
    by_id = {a['id']: a for a in roster}

    def ensure_running():
        state = engine(home, role, 'snapshot')['snapshot']
        if state['paused']:
            raise RuntimeError('Office paused by its owner or circuit breaker')

    class OfficeEvents(BaseEventListener):
        def setup_listeners(self, bus):
            def record(kind, event):
                agent = getattr(event, 'agent', None)
                aid = by_role.get(getattr(agent, 'role', ''))
                if aid:
                    engine(home, role, 'event', {'kind': kind, 'agentId': aid, 'taskId': mission['id']})
            @bus.on(AgentExecutionStartedEvent)
            def started(source, event):
                record('agent.start', event)
                aid = by_role.get(getattr(getattr(event, 'agent', None), 'role', ''))
                if aid and aid != director:
                    engine(home, role, 'event', {'kind': 'delegation', 'agentId': director, 'to': aid, 'taskId': mission['id'], 'summary': mission['title']})
            @bus.on(AgentExecutionCompletedEvent)
            def completed(source, event): record('agent.complete', event)
            @bus.on(AgentExecutionErrorEvent)
            def failed(source, event): record('agent.error', event)

    listener = OfficeEvents()

    def mail_tool(sender):
        class OfficeMail(BaseTool):
            name: str = 'Office mailbox'
            description: str = 'Send a work update to another office agent by its agent_id. Use CrewAI delegation for asking a coworker to execute work.'
            def _run(self, agent_id: str, message: str) -> str:
                ensure_running()
                if agent_id not in by_id: return 'Unknown office agent'
                if not 1 <= len(message) <= 1000: return 'Keep messages under 1000 characters'
                engine(home, role, 'event', {'kind': 'delegation', 'agentId': sender, 'to': agent_id, 'taskId': mission['id'], 'summary': message})
                return 'Delivered to the office mailbox'
        return OfficeMail()

    def step(step):
        ensure_running()

    def runtime_tool(aid):
        binding = body.get('local_bindings', {}).get(aid)
        if not binding: return []
        class LocalRuntime(BaseTool):
            name: str = 'Personally owned local agent'
            description: str = 'Ask the personally owned local runtime assigned to you to perform the supplied bounded question or task. Return its actual answer.'
            def _run(self, question: str) -> str:
                ensure_running()
                from offline.registry import Registry
                return Registry(home).ask(binding, question)['answer']
        return [LocalRuntime()]

    agents = []
    manager = None
    for item in roster:
        context = '\n'.join(filter(None, [item.get('memory'), item.get('messages')]))
        agent = Agent(role=item['role'], goal=item.get('goal') or item['role'],
            backstory=f"You are {item['name']}, office agent {item['id']}. Other workers: " +
                ', '.join(f"{a['role']} ({a['id']})" for a in roster if a['id'] != item['id']) +
                '\nUse only approved tools. Escalate spend, destructive operations and changes of scope to the owner.\nReviewed memory and inbox context:\n' + context,
            llm=llm, allow_delegation=True, max_iter=office['maxIterations'], tools=[] if item['id'] == director else [mail_tool(item['id']), *runtime_tool(item['id'])],
            step_callback=step, verbose=False)
        if item['id'] == director: manager = agent
        else: agents.append(agent)
    ensure_running()
    task = Task(description=mission.get('description') or mission['title'],
        expected_output='An evidence-based result addressing the mission and its acceptance criteria; clearly state incomplete work.',
        **({'agent': next(a for a in agents if a.role == by_id[mission['assignee']]['role'])} if mission.get('assignee') != director else {}))
    crew = Crew(agents=agents, tasks=[task], manager_agent=manager, process=Process.hierarchical,
        verbose=False, max_rpm=20, memory=False, tracing=False)
    # Keep the event listener live through kickoff; no mocked idle animations.
    try:
        return crew.kickoff()
    finally:
        from crewai.events.event_bus import crewai_event_bus
        crewai_event_bus.flush(timeout=10)
