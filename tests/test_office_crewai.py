"""Run real CrewAI delegation with an offline deterministic LLM, no API spend."""
import tempfile
import unittest
try:
    from crewai import BaseLLM
    from pydantic import PrivateAttr
except ImportError:
    BaseLLM = None
from control_center.office import engine
from control_center.office_crew import kickoff


if BaseLLM:
    class OfflineLLM(BaseLLM):
        _delegated: bool = PrivateAttr(False)
        _calls: list = PrivateAttr(default_factory=list)
        def call(self, messages, **kwargs):
            agent = kwargs.get('from_agent')
            role = getattr(agent, 'role', '')
            self._calls.append(role)
            if role == 'Scrum Master' and not self._delegated:
                self._delegated = True
                return 'Thought: Delegate the bounded mission.\nAction: Delegate work to coworker\nAction Input: {"task":"Check the acceptance criteria","context":"This is an offline integration test","coworker":"Researcher"}'
            return 'Thought: The evidence is sufficient.\nFinal Answer: The acceptance criteria were checked by the office worker.'


@unittest.skipUnless(BaseLLM, 'Run with the isolated CrewAI test environment')
class CrewIntegrationTests(unittest.TestCase):
    def test_hierarchical_delegation_with_real_framework(self):
        with tempfile.TemporaryDirectory() as home:
            role = 'office-test'
            worker = engine(home, role, 'hire', {'name': 'Ada', 'role': 'Researcher', 'goal': 'Check evidence'})['result']['id']
            task = engine(home, role, 'task.create', {'title': 'Acceptance', 'description': 'Check acceptance', 'assignee': 'orchestrator', 'dependsOn': [], 'needsApproval': False})['result']['id']
            office = engine(home, role, 'begin', {'id': task})['result']
            llm = OfflineLLM(model='offline-integration')
            output = kickoff({'office': office, 'home': home, 'role': role}, llm)
            self.assertIn('acceptance criteria', str(output))
            self.assertTrue(llm._delegated)
            self.assertIn('Researcher', llm._calls)
            import time
            time.sleep(.1)
            events = engine(home, role, 'snapshot')['snapshot']['events']
            self.assertTrue(any(e.get('agentId') == worker and e.get('kind') == 'agent.start' for e in events))
